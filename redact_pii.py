import fitz  # PyMuPDF
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from faker import Faker
import docx
import os
import re

# Initialize Faker
fake = Faker()
# Set seed for reproducibility
Faker.seed(42)

# Entities to detect and anonymize
ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "US_SSN",
    "CREDIT_CARD",
    "DATE_TIME",
    "IP_ADDRESS",
    # Spacy specific:
    "LOCATION",
    "ORGANIZATION"
]

def generate_fake_data(entity_type):
    """Generate fake data based on entity type."""
    if entity_type == "PERSON":
        return fake.name()
    elif entity_type == "EMAIL_ADDRESS":
        return fake.email()
    elif entity_type == "PHONE_NUMBER":
        return fake.phone_number()
    elif entity_type == "ORGANIZATION":
        return fake.company()
    elif entity_type == "LOCATION":
        return fake.address().replace('\n', ', ')
    elif entity_type == "US_SSN":
        return fake.ssn()
    elif entity_type == "CREDIT_CARD":
        return fake.credit_card_number()
    elif entity_type == "DATE_TIME":
        return fake.date()
    elif entity_type == "IP_ADDRESS":
        return fake.ipv4()
    else:
        return "<REDACTED>"

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF page by page."""
    doc = fitz.open(pdf_path)
    text_pages = []
    for page in doc:
        text_pages.append(page.get_text())
    return text_pages

def save_to_docx(text_pages, output_path):
    """Save the redacted text to a docx file."""
    doc = docx.Document()
    for i, text in enumerate(text_pages):
        doc.add_paragraph(text)
        if i < len(text_pages) - 1:
            doc.add_page_break()
    doc.save(output_path)

def main():
    pdf_path = "prospectus.pdf"
    output_path = "redacted_output.docx"
    
    print("Extracting text from PDF...")
    text_pages = extract_text_from_pdf(pdf_path)
    
    print("Initializing Presidio Analyzer and Anonymizer...")
    # Initialize the analyzer with the larger spacy model
    # To support ORGANIZATION and LOCATION which map to Spacy's ORG, GPE, LOC
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
    
    anonymizer = AnonymizerEngine()
    
    print(f"Processing {len(text_pages)} pages...")
    redacted_pages = []
    
    # Define custom operators for Faker mapping
    operators = {
        entity: OperatorConfig("custom", {"lambda": lambda x, entity_type=entity: generate_fake_data(entity_type)})
        for entity in ENTITIES
    }
    
    for i, text in enumerate(text_pages):
        print(f"Redacting page {i+1}/{len(text_pages)}...")
        
        # Analyze text
        results = analyzer.analyze(text=text, entities=ENTITIES, language='en')
        
        # Anonymize text
        anonymized_result = anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=operators
        )
        
        redacted_pages.append(anonymized_result.text)
        
    print(f"Saving redacted text to {output_path}...")
    save_to_docx(redacted_pages, output_path)
    print("Done!")

if __name__ == "__main__":
    main()
