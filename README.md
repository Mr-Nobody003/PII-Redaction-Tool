# PII Redaction Tool

This script extracts text from PDF documents and redacts Personally Identifiable Information (PII) using Microsoft Presidio and spaCy, replacing sensitive information with fake, synthetic data (using the `Faker` library).

## Approach
1. **Extraction**: The script uses PyMuPDF (`fitz`) to read text from the input PDF page by page.
2. **Detection**: `presidio-analyzer` is configured with the `en_core_web_lg` spaCy model to detect entities like PERSON, EMAIL_ADDRESS, PHONE_NUMBER, DATE_TIME, ORGANIZATION, LOCATION, US_SSN, IP_ADDRESS, and CREDIT_CARD.
3. **Anonymization**: `presidio-anonymizer` processes the analyzer results and replaces the flagged text with synthetic data corresponding to each entity type using the `Faker` library.
4. **Generation**: `python-docx` creates a Microsoft Word document (`.docx`) containing the redacted text.

## Tradeoffs and Observations
- **Processing Speed vs. Accuracy**: We chose the larger spaCy model (`en_core_web_lg`) over the small model to improve accuracy, especially for names, organizations, and locations. This introduces a slight tradeoff in processing speed, but considering the high sensitivity of financial documents, accuracy takes priority.
- **False Positives**: The model occasionally misclassifies non-sensitive terms as PII. For instance, in our evaluation, it flagged the document title "RED HERRING" as an `ORGANIZATION`, and "2025" / "2013" independently as a `DATE_TIME`. These false positives lead to over-redaction, which is generally safer than under-redaction but can occasionally make the text slightly less coherent.
- **False Negatives**: The tool missed certain complex addresses or location substrings when they were formatted in unstructured lines (e.g., missing specific parts of "11/3, 11/4 and 11/5 Village Birdewadi" as an address). Similarly, some Indian names or organization names that might not be heavily represented in the spaCy training data were missed. In a production scenario, training a custom NER model for regional names/addresses or adding regex rules for specific Indian entity structures (like PAN numbers) would improve recall.

## How to run
1. Install dependencies from `requirements.txt`.
2. Run `python redact_pii.py`.
3. The output will be saved as `redacted_output.docx`.
