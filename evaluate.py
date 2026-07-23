from presidio_analyzer import AnalyzerEngine
import spacy

test_text = """
RED HERRING PROSPECTUS
Dated December 10, 2025
Please read section 32 of the Companies Act, 2013
100% Book Built Offer

KSH INTERNATIONAL LIMITED
CORPORATE IDENTITY NUMBER: U28129PN1979PLC141032

11/3, 11/4 and 11/5 Village Birdewadi
Chakan Taluka - Khed Pune - 410 501
Maharashtra, India

Sarthak Malvadkar
Company Secretary and Compliance Officer
Email: cs.connect@kshinternational.com Telephone: + 91 20 45053237
www.kshinternational.com

OUR PROMOTERS: KUSHAL SUBBAYYA HEGDE, PUSHPA KUSHAL HEGDE, RAJESH KUSHAL HEGDE,
ROHIT KUSHAL HEGDE, RAKHI GIRIJA SHETTY, DHAULAGIRI FAMILY TRUST, EVEREST FAMILY
TRUST, MAKALU FAMILY TRUST, BROAD FAMILY TRUST, ANNAPURNA FAMILY TRUST,
KANCHENJUNGA FAMILY TRUST AND WATERLOO INDUSTRIAL PARK VI PRIVATE LIMITED
"""

# Ground truth substrings for this test text
ground_truth = {
    "PERSON": [
        "Sarthak Malvadkar",
        "KUSHAL SUBBAYYA HEGDE",
        "PUSHPA KUSHAL HEGDE",
        "RAJESH KUSHAL HEGDE",
        "ROHIT KUSHAL HEGDE",
        "RAKHI GIRIJA SHETTY"
    ],
    "EMAIL_ADDRESS": [
        "cs.connect@kshinternational.com"
    ],
    "PHONE_NUMBER": [
        "+ 91 20 45053237"
    ],
    "ORGANIZATION": [
        "KSH INTERNATIONAL LIMITED",
        "DHAULAGIRI FAMILY TRUST",
        "EVEREST FAMILY TRUST",
        "MAKALU FAMILY TRUST",
        "BROAD FAMILY TRUST",
        "ANNAPURNA FAMILY TRUST",
        "KANCHENJUNGA FAMILY TRUST",
        "WATERLOO INDUSTRIAL PARK VI PRIVATE LIMITED"
    ],
    "LOCATION": [
        "11/3, 11/4 and 11/5 Village Birdewadi",
        "Chakan Taluka",
        "Khed",
        "Pune",
        "Maharashtra",
        "India"
    ],
    "DATE_TIME": [
        "December 10, 2025"
    ]
}

def overlap(start1, end1, start2, end2):
    return max(0, min(end1, end2) - max(start1, start2)) > 0

def evaluate():
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
    }
    provider = NlpEngineProvider(nlp_configuration=configuration)
    nlp_engine = provider.create_engine()
    
    analyzer = AnalyzerEngine(
        nlp_engine=nlp_engine, 
        supported_languages=["en"]
    )
    
    entities = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN", "CREDIT_CARD", "DATE_TIME", "IP_ADDRESS", "LOCATION", "ORGANIZATION"]
    
    results = analyzer.analyze(text=test_text, entities=entities, language='en')
    
    # Calculate TP, FP, FN
    metrics = {entity: {"TP": 0, "FP": 0, "FN": 0} for entity in ground_truth.keys()}
    metrics["OTHER"] = {"TP": 0, "FP": 0, "FN": 0}
    
    predicted_spans = []
    for res in results:
        entity_type = res.entity_type
        if entity_type not in metrics:
            entity_type = "OTHER"
        predicted_spans.append({"start": res.start, "end": res.end, "type": entity_type, "text": test_text[res.start:res.end], "matched": False})
        
    for gt_type, gt_list in ground_truth.items():
        for gt_str in gt_list:
            start_idx = test_text.find(gt_str)
            if start_idx == -1:
                continue
            end_idx = start_idx + len(gt_str)
            
            # Find matching prediction
            matched = False
            for pred in predicted_spans:
                if overlap(start_idx, end_idx, pred["start"], pred["end"]):
                    if pred["type"] == gt_type:
                        metrics[gt_type]["TP"] += 1
                        pred["matched"] = True
                        matched = True
                        break
            if not matched:
                metrics[gt_type]["FN"] += 1
                
    for pred in predicted_spans:
        if not pred["matched"]:
            if pred["type"] in metrics:
                metrics[pred["type"]]["FP"] += 1
            else:
                metrics["OTHER"]["FP"] += 1
                
    # Print report
    print("=== Evaluation Report ===")
    total_tp = 0
    total_fp = 0
    total_fn = 0
    
    for entity, counts in metrics.items():
        if entity == "OTHER" and counts["FP"] == 0:
            continue
        tp = counts["TP"]
        fp = counts["FP"]
        fn = counts["FN"]
        total_tp += tp
        total_fp += fp
        total_fn += fn
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        
        print(f"Entity: {entity}")
        print(f"  TP: {tp}, FP: {fp}, FN: {fn}")
        print(f"  Precision: {precision:.2f}")
        print(f"  Recall: {recall:.2f}")
        print()
        
    overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    overall_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
    overall_accuracy = total_tp / (total_tp + total_fp + total_fn) if (total_tp + total_fp + total_fn) > 0 else 0
    print("=== Overall Metrics ===")
    print(f"Precision: {overall_precision:.2f}")
    print(f"Recall: {overall_recall:.2f}")
    print(f"Accuracy (Jaccard index-like): {overall_accuracy:.2f}")
    
    print("\nPredicted entities that were False Positives or mismatches:")
    for pred in predicted_spans:
        if not pred["matched"]:
            print(f"  - [{pred['type']}] {pred['text']}")

if __name__ == "__main__":
    evaluate()
