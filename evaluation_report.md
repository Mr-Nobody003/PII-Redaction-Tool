# PII Redaction Tool - Evaluation Report

## Evaluation Approach
To accurately evaluate the performance of our PII redaction tool, we established a "ground truth" dataset. Since manually annotating the entire 128-page Red Herring Prospectus is unfeasible, we extracted the first few pages of the document, manually annotated the Personally Identifiable Information (PII) within it, and ran our redaction script (`evaluate.py`) against this annotated subset.

The evaluation process measures performance using three standard metrics:
- **True Positives (TP):** The tool successfully identified a piece of PII that matches the ground truth.
- **False Positives (FP):** The tool flagged text as PII that was NOT in the ground truth (over-redaction).
- **False Negatives (FN):** The tool missed a piece of PII that WAS in the ground truth (under-redaction).

Using these values, we calculated:
- **Precision:** `TP / (TP + FP)` - Out of all the items flagged as PII, how many were actually PII?
- **Recall:** `TP / (TP + FN)` - Out of all the actual PII in the document, how many did the tool successfully catch?
- **Accuracy (Jaccard Index-like):** `TP / (TP + FP + FN)` - The overall performance of the model on the text.

## Results

Below are the evaluation metrics broken down by PII type on our ground truth sample:

| Entity Type | True Positives | False Positives | False Negatives | Precision | Recall |
| --- | --- | --- | --- | --- | --- |
| **PERSON** | 2 | 1 | 4 | 0.67 | 0.33 |
| **EMAIL_ADDRESS** | 1 | 0 | 0 | 1.00 | 1.00 |
| **PHONE_NUMBER** | 1 | 0 | 0 | 1.00 | 1.00 |
| **ORGANIZATION** | 6 | 3 | 1 | 0.67 | 0.86 |
| **LOCATION** | 2 | 0 | 4 | 1.00 | 0.33 |
| **DATE_TIME** | 1 | 2 | 0 | 0.33 | 1.00 |

### Overall Metrics
- **Overall Precision:** 0.68
- **Overall Recall:** 0.59
- **Overall Accuracy:** 0.46

## Analysis

### 1. High Performance on Structured Data
The model performed exceptionally well (1.00 Precision, 1.00 Recall) on highly structured text such as `EMAIL_ADDRESS` and `PHONE_NUMBER`. These entities typically follow strict patterns, allowing the Presidio Analyzer's built-in regex components to identify them perfectly.

### 2. Challenges with Names and Addresses
The recall for `PERSON` (0.33) and `LOCATION` (0.33) was relatively low. The underlying spaCy model (`en_core_web_lg`) missed some Indian names (e.g., "KUSHAL SUBBAYYA HEGDE") likely because they were fully capitalized or did not match the statistical distribution of the model's training data. Similarly, complex unstructured addresses ("11/3, 11/4 and 11/5 Village Birdewadi") were only partially flagged.

### 3. False Positives (Over-Redaction)
The model's precision was affected by some false positives, such as identifying the document title "RED HERRING" as an `ORGANIZATION`, and standalone years like "2025" and "2013" as `DATE_TIME`. In the context of PII anonymization, false positives are generally less harmful than false negatives, as they ensure sensitive data is not leaked, although it may reduce the document's readability.

## Conclusion
The current implementation using Presidio and spaCy provides a solid baseline for redaction. To improve Recall (catching more instances of PII) for regional names and addresses, we recommend augmenting the analyzer with custom regex patterns (e.g., PAN Numbers) and fine-tuning a custom NER model on Indian corporate document datasets.
