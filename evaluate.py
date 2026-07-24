#!/usr/bin/env python3
"""
evaluate.py
-----------
Precision/recall/F1 for the redaction pipeline against a hand-annotated
ground truth sample pulled directly from Red_Herring_Prospectus.docx
(exact paragraph/cell text, read via python-docx -- see README.md for why
a sample rather than the full 128-page document was annotated).

The source document has zero real SSNs, credit-card numbers, IP addresses,
or dates of birth anywhere in it (confirmed by grep across the full text
extraction), so those four detectors are additionally evaluated against a
small hand-built synthetic set that exercises the formats each detector
is supposed to catch. This is called out explicitly rather than silently
reporting "recall: N/A" for four of the nine required PII types.

Matching is "lenient"/overlap-based (a detected span counts as a match if
it overlaps a ground-truth span of a compatible type), which is standard
for regex/heuristic NER evaluation -- see the Methodology section of
evaluation_report.md for the justification and its limits.
"""

import json
import re
import docx

from redact_pii import PIIRedactor, learn_pass, Span

SRC = "/mnt/user-data/uploads/Red_Herring_Prospectus.docx"

# ---------------------------------------------------------------------------
# Ground truth: (scope_name, text, [(type, exact_substring), ...])
# All text below was copied verbatim from python-docx paragraph/cell reads
# of the source document -- see README.md "Evaluation approach".
# ---------------------------------------------------------------------------
GROUND_TRUTH = []

GROUND_TRUTH.append((
    "cover_page.contact_block",
    "Contact Person: Sarthak Malvadkar, Company Secretary and Compliance "
    "Officer; Telephone: + 91 20 4505 3237; E-mail: cs.connect@kshinternational.com",
    [
        ("PERSON", "Sarthak Malvadkar"),
        ("PHONE_NUMBER", "+ 91 20 4505 3237"),
        ("EMAIL", "cs.connect@kshinternational.com"),
    ],
))

GROUND_TRUTH.append((
    "cover_page.promoters",
    "OUR PROMOTERS: KUSHAL SUBBAYYA HEGDE, PUSHPA KUSHAL HEGDE, RAJESH KUSHAL "
    "HEGDE, ROHIT KUSHAL HEGDE, RAKHI GIRIJA SHETTY, DHAULAGIRI FAMILY TRUST, "
    "EVEREST FAMILY TRUST, MAKALU FAMILY TRUST, BROAD FAMILY TRUST, ANNAPURNA "
    "FAMILY TRUST, KANCHENJUNGA FAMILY TRUST AND WATERLOO INDUSTRIAL PARK VI "
    "PRIVATE LIMITED",
    [
        ("PERSON", "KUSHAL SUBBAYYA HEGDE"), ("PERSON", "PUSHPA KUSHAL HEGDE"),
        ("PERSON", "RAJESH KUSHAL HEGDE"), ("PERSON", "ROHIT KUSHAL HEGDE"),
        ("PERSON", "RAKHI GIRIJA SHETTY"),
        ("COMPANY", "DHAULAGIRI FAMILY TRUST"), ("COMPANY", "EVEREST FAMILY TRUST"),
        ("COMPANY", "MAKALU FAMILY TRUST"), ("COMPANY", "BROAD FAMILY TRUST"),
        ("COMPANY", "ANNAPURNA FAMILY TRUST"), ("COMPANY", "KANCHENJUNGA FAMILY TRUST"),
        ("COMPANY", "WATERLOO INDUSTRIAL PARK VI PRIVATE LIMITED"),
    ],
))

# Board of Directors table (structural pass) -- one row per director.
_BOARD = [
    ("Kushal Subbayya Hegde", "S. no. 245/ 104, Pushpakamal, Deccan Gymkhana Society, lane no. 3 Prabhat Road, opposite PYC basketball court, Deccan Gymkhana, Pune – 411 004 Maharashtra, India"),
    ("Rajesh Kushal Hegde", "12 Buena Monte, NCL co-operative housing society, Panchvati, Pashan, Pune – 411 008, Maharashtra, India"),
    ("Rohit Kushal Hegde", "Pushpakamal Apartment, Flat – 1, S. no. 245/ 104, Prabhat Road Lane no. 3, Shivaji Nagar, Deccan Gymkhana, Pune – 411 004, Maharashtra, India"),
    ("Rakhi Girija Shetty", "S. no. 245/ 104, Pushpakamal, Deccan Gymkhana Society, lane no. 3 Prabhat Road, opposite PYC basketball court, Erandawane, Deccan Gymkhana, Pune – 411 004 Maharashtra, India"),
    ("Dinesh Hirachand Munot", "Pratik Bunglow, Senapati Bapat Road, behind Sahara Hotel, Shivajinagar, Model Colony, Pune – 411 016, Maharashtra, India"),
    ("Ajay Shriram Patil", "602, Gopalkrupa Apartment, Bhonde colony, Prabhat Road, Erandawane, Pune – 411 004, Maharashtra, India"),
    ("Ram Kumar Tiwari", "A-259, JK Road, Minal Residency, Huzur, Govindpura, Bhopal – 462 023, Madhya Pradesh, India"),
    ("Indu Jacob", "A29, Abhimanshree Society, Pashan Road, Pune – 411 008, Maharashtra, India"),
]
for _name, _addr in _BOARD:
    GROUND_TRUTH.append((
        f"board_of_directors.{_name}",
        f"{_name}\t{_addr}",
        [("PERSON", _name), ("ADDRESS", _addr)],
    ))

# Bankers to our Company -- 8 banks, each with company/address/phone/person/email.
_BANKS = [
    ("Citibank N.A.", "8th Floor, Onyx Tower North Main Road Koregaon Park, Pune – 411 001 Maharashtra, India",
     "+91 20 6606 4494", "Hitesh Ramani", "hitesh.ramani@citi.com"),
    ("Export-Import Bank of India", "No. 401, 401(A), 401(B) & 402, 402(A), 402(B), 4th Floor Signature Building, Bhandarkar road Shivaji Nagar, Pune – 411 004 Maharashtra, India",
     "+91 20 2640 3100", "Chitra Raste", "pro@eximbankindia.in"),
    ("IndusInd Bank Limited", "2401 Gen Thimmayya Road, Cantonment Pune – 411 001 Maharashtra, India",
     "+91-20-26234000", "Sharmila Joshi", "sharmila.joshi@indusind.com"),
    ("ICICI Bank Limited", "ICICI Bank, CBG, 3rd Floor, 362, Satguru House Next to Tanishq Showroom, CTS No. 30 Bund Garden Road, Pune – 411 001 Maharashtra, India",
     "+ 91 8879770456", "Cherag Gyara", "cherag.gyara@icicibank.com"),
    ("HDFC Bank Limited", "5th Floor, Marathon IT Park Bund Garden Road Pune – 411 001 Maharashtra, India",
     "+91 20 6769 4648", "Manisha Shukla", "manisha.shukla@hdfcbank.com"),
    ("State Bank of India, Industrial Finance Branch", "Tara Chambers, Mumbai-Pune Road, Wakdewadi Pune – 411 003 Maharashtra, India",
     "+91 20 2561 8211", "Tushar Wakhele", "rm6.ifbpune@sbi.co.in"),
    ("The Federal Bank Limited", "Ground Floor, Kubera Chambers Opp. Sancheti Hospital Shivajinagar, Pune – 41l 005 Maharashtra, India",
     "+ 91 91586 40360", "Ashish Mathew Pulloor", "ashishmp@federalbank.co.in"),
    ("Bajaj Finance Limited", "The Capital Unit no. 1601, B- wing BKC, Mumbai Maharashtra India",
     "+91 20 7157 6403", "Anand Soni", "anand.soni@bajajfinserv.in"),
]
for _co, _addr, _phone, _person, _email in _BANKS:
    text = f"{_co}\n{_addr}\nTelephone: {_phone} Contact Person: {_person} Email: {_email}"
    GROUND_TRUTH.append((
        f"bankers.{_co}",
        text,
        [("COMPANY", _co), ("ADDRESS", _addr), ("PHONE_NUMBER", _phone),
         ("PERSON", _person), ("EMAIL", _email)],
    ))

# ---------------------------------------------------------------------------
# Synthetic set: the source document has no real SSNs / credit cards / IPs /
# DOBs (verified by grep, see README.md), so these four categories are
# evaluated on hand-built sentences covering their typical formats instead.
# ---------------------------------------------------------------------------
SYNTHETIC_GROUND_TRUTH = [
    ("synthetic.ssn_1", "Employee SSN on file: 123-45-6789 for payroll purposes.",
     [("SSN", "123-45-6789")]),
    ("synthetic.ssn_2", "His social security number is 987-65-4320, recorded in 2019.",
     [("SSN", "987-65-4320")]),
    ("synthetic.cc_1", "Payment was charged to card 4532 0151 1283 0366 on file.",
     [("CREDIT_CARD", "4532 0151 1283 0366")]),
    ("synthetic.cc_2", "Refund issued to Mastercard ending 5425-2334-3010-9903 within 5 days.",
     [("CREDIT_CARD", "5425-2334-3010-9903")]),
    ("synthetic.cc_false_positive", "The invoice number 4532015112830367 does not correspond to any card.",
     []),  # fails Luhn -> should NOT be flagged; precision check
    ("synthetic.ip_1", "The intrusion originated from IP address 192.168.1.104 on the internal VPN.",
     [("IP_ADDRESS", "192.168.1.104")]),
    ("synthetic.ip_2", "Server logs show repeated login attempts from 8.8.8.8 and 10.0.0.55.",
     [("IP_ADDRESS", "8.8.8.8"), ("IP_ADDRESS", "10.0.0.55")]),
    ("synthetic.dob_1", "Date of Birth: 14/03/1985, as recorded in the HR system.",
     [("DATE_OF_BIRTH", "14/03/1985")]),
    ("synthetic.dob_2", "She was born on August 9, 1990 in Chennai.",
     [("DATE_OF_BIRTH", "August 9, 1990")]),
    ("synthetic.dob_false_positive", "The certificate of incorporation was issued on July 30, 1979.",
     []),  # a non-DOB date with no birth-context keyword -- should NOT fire
]

# ---------------------------------------------------------------------------
# Matching + scoring
# ---------------------------------------------------------------------------

TYPE_EQUIV = {"COMPANY": {"COMPANY"}, "PERSON": {"PERSON"}}


def normalize(s):
    return re.sub(r"\s+", " ", s.strip().lower())


def evaluate(cases, redactor):
    rows = []
    totals = {}
    for scope, text, gt_entities in cases:
        spans = []
        for det in redactor.free_text_detectors:
            spans.extend(det.find(text))
        for term, label in redactor.registry.all_terms():
            for m in re.finditer(re.escape(term), text, re.IGNORECASE):
                spans.append(Span(m.start(), m.end(), m.group(), label))

        matched_gt = [False] * len(gt_entities)
        matched_span = [False] * len(spans)
        for gi, (gtype, gtext) in enumerate(gt_entities):
            gnorm = normalize(gtext)
            for si, sp in enumerate(spans):
                if matched_span[si]:
                    continue
                if sp.label != gtype:
                    continue
                snorm = normalize(sp.text)
                if snorm in gnorm or gnorm in snorm:
                    matched_gt[gi] = True
                    matched_span[si] = True
                    break

        tp = sum(matched_gt)
        fn = len(gt_entities) - tp
        fp = sum(1 for m in matched_span if not m)
        rows.append((scope, tp, fp, fn))

        # per-type roll-up
        by_type_gt = {}
        for (gtype, _), m in zip(gt_entities, matched_gt):
            d = by_type_gt.setdefault(gtype, [0, 0])
            d[0] += 1 if m else 0
            d[1] += 0 if m else 1
        for sp, m in zip(spans, matched_span):
            if not m:
                d = totals.setdefault(sp.label, {"tp": 0, "fp": 0, "fn": 0})
                d["fp"] += 1
        for gtype, (tp_, fn_) in by_type_gt.items():
            d = totals.setdefault(gtype, {"tp": 0, "fp": 0, "fn": 0})
            d["tp"] += tp_
            d["fn"] += fn_

    return rows, totals


def print_report(title, totals):
    print(f"\n=== {title} ===")
    print(f"{'TYPE':15s} {'TP':>4s} {'FP':>4s} {'FN':>4s} {'Precision':>10s} {'Recall':>8s} {'F1':>6s}")
    all_tp = all_fp = all_fn = 0
    for t, d in sorted(totals.items()):
        tp, fp, fn = d["tp"], d["fp"], d["fn"]
        all_tp += tp; all_fp += fp; all_fn += fn
        prec = tp / (tp + fp) if (tp + fp) else float("nan")
        rec = tp / (tp + fn) if (tp + fn) else float("nan")
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) and prec == prec and rec == rec and (prec + rec) > 0 else float("nan")
        print(f"{t:15s} {tp:4d} {fp:4d} {fn:4d} {prec:10.2f} {rec:8.2f} {f1:6.2f}")
    prec = all_tp / (all_tp + all_fp) if (all_tp + all_fp) else float("nan")
    rec = all_tp / (all_tp + all_fn) if (all_tp + all_fn) else float("nan")
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else float("nan")
    acc = all_tp / (all_tp + all_fp + all_fn) if (all_tp + all_fp + all_fn) else float("nan")
    print(f"{'OVERALL':15s} {all_tp:4d} {all_fp:4d} {all_fn:4d} {prec:10.2f} {rec:8.2f} {f1:6.2f}")
    print(f"Entity-level accuracy (TP/(TP+FP+FN)): {acc:.2f}")
    return {"tp": all_tp, "fp": all_fp, "fn": all_fn, "precision": prec, "recall": rec, "f1": f1, "accuracy": acc}


def main():
    src = docx.Document(SRC)
    redactor = PIIRedactor()
    learn_pass(src, redactor)

    rows1, totals1 = evaluate(GROUND_TRUTH, redactor)
    summary1 = print_report("Document sample (real PII)", totals1)

    rows2, totals2 = evaluate(SYNTHETIC_GROUND_TRUTH, redactor)
    summary2 = print_report("Synthetic set (SSN / credit card / IP / DOB)", totals2)

    out = {
        "document_sample": {"by_type": totals1, "summary": summary1,
                             "per_case": [{"scope": s, "tp": tp, "fp": fp, "fn": fn} for s, tp, fp, fn in rows1]},
        "synthetic_set": {"by_type": totals2, "summary": summary2,
                           "per_case": [{"scope": s, "tp": tp, "fp": fp, "fn": fn} for s, tp, fp, fn in rows2]},
    }
    with open("evaluation_results.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("\nWrote evaluation_results.json")


if __name__ == "__main__":
    main()
