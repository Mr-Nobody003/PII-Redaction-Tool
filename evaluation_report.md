# Evaluation Report

## Methodology

Annotating all 128 pages / ~1,000 paragraphs / 76 tables of the source
document by hand isn't practical in the time available, so — as flagged
up front — this evaluates a **representative sample** instead, pulled
verbatim from the document via `python-docx` (not from a rendered/
copy-pasted view, to avoid transcription errors) and hand-labeled by
reading the surrounding context. The full list of sampled text and its
ground-truth labels lives in `evaluate.py` (`GROUND_TRUTH`), so it's
re-runnable and auditable, not just a table of numbers.

**Sample composition** (chosen to be dense in PII, and to span both the
structural and free-text code paths):
- The cover-page "Contact Person" / e-mail / telephone block
- The full "OUR PROMOTERS" list (5 individuals, 6 family trusts, 1
  promoter company — 12 entities)
- All 8 rows of the Board of Directors table (name + address)
- All 8 entries in the "Bankers to our Company" section (company,
  address, phone, contact person, email each) — free-flowing prose, not
  a table, so this exercises the regex/context detectors rather than
  the structural column pass

**SSN / credit card / IP address / date of birth are not present
anywhere in the source document** — confirmed by grepping the full text
extraction for the relevant patterns (see the assignment's own
implementation-plan notes; this was independently re-verified here).
Reporting "recall: N/A, 0 instances" for four of the nine required PII
types would be technically true but not very informative, so those four
detectors are additionally evaluated on a **10-sentence synthetic set**
built to exercise typical formats for each (`SYNTHETIC_GROUND_TRUTH` in
`evaluate.py`), including two deliberate negative cases — a 16-digit
number that fails the Luhn check, and a real non-birth date ("issued on
July 30, 1979") with no birth-context keyword nearby — to check the
detectors don't over-fire.

**Matching:** lenient/overlap matching — a detected span counts as a
true positive if it overlaps a ground-truth span of the same type,
rather than requiring an exact character-offset match. This is standard
for regex/heuristic entity extraction (an address detector that finds
"S. no. 245/104, Pushpakamal... Pune – 411 004" when the annotated span
is "S. no. 245/ 104, Pushpakamal,... Pune -- 411 004 Maharashtra, India"
is a hit, not a miss, over minor whitespace/punctuation differences).
This is more permissive than strict span-boundary matching, so these
numbers are an upper bound on what stricter scoring would show.

**"Accuracy"** for a span-extraction task doesn't have a natural
true-negative count (there's no fixed inventory of "non-PII spots" to
be right about), so, following common practice, this reports an
entity-level accuracy proxy: TP / (TP + FP + FN), i.e. the fraction of
all predicted-or-true entities that were correctly matched.

## Results — document sample (real PII)

| Type | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| ADDRESS | 14 | 0 | 2 | 1.00 | 0.88 | 0.93 |
| COMPANY | 12 | 0 | 3 | 1.00 | 0.80 | 0.89 |
| EMAIL | 9 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| PERSON | 22 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| PHONE_NUMBER | 9 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| **Overall** | **66** | **0** | **5** | **1.00** | **0.93** | **0.96** |

Entity-level accuracy: **0.93**

### The 5 false negatives, explained

- **3 companies:** "Citibank N.A.", "Export-Import Bank of India", "State
  Bank of India, Industrial Finance Branch" — none end in a legal suffix
  (Limited/Ltd/LLP/Inc/Corp) in the sentence they appear in, which is
  the only signal the free-text company detector has (the structural
  pass doesn't cover this section since it's prose, not a table). For
  comparison, "IndusInd Bank **Limited**" and "ICICI Bank **Limited**"
  in the same section were both caught.
- **2 addresses:** one where the source document has a typo in its own
  PIN code (`41l 005` — a lowercase "L" instead of the digit "1"), and
  one with no PIN code in the original text at all (a Mumbai address
  ending "...Mumbai Maharashtra India"). The address detector is
  anchored on a 6-digit PIN code by design (the alternative — matching
  any block of text ending in a state name — produced far too many
  false positives on ordinary sentences that just happen to mention
  "Maharashtra, India").

Zero false positives in this sample: nothing that wasn't PII got
redacted.

## Results — synthetic set (SSN / credit card / IP / DOB)

| Type | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| SSN | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| CREDIT_CARD | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| IP_ADDRESS | 3 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| DATE_OF_BIRTH | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 |
| **Overall** | **9** | **0** | **0** | **1.00** | **1.00** | **1.00** |

Both negative cases behaved correctly: the Luhn-invalid 16-digit "invoice
number" was *not* flagged as a credit card, and "issued on July 30, 1979"
(a real incorporation date elsewhere in the document, with no
birth-context keyword near it) was *not* flagged as a date of birth. This
is a small, hand-built set — it demonstrates the detectors work on
standard formats, not that they'd hold up against adversarial or
unusual real-world formatting (e.g. SSNs written without dashes, or
non-US credit card formats).

## Precision vs. recall — where this tool errs on which side, deliberately

Every design decision that had a precision/recall knob was turned toward
**precision** — better to miss a P II instance than to mangle a
non-PII figure in a financial disclosure document:
- Bare 10-digit numbers only count as phone numbers near a phone-ish
  keyword (DIN, PIN codes, and share counts are all bare numbers of
  similar length in this document).
- Bare dates only count as DOB near a birth-context keyword (the
  document has hundreds of legitimate non-birth dates).
- Credit-card-shaped numbers must pass a Luhn check.
- Addresses require an actual PIN code, not just a state name.

The cost shows up as recall (the 5 false negatives above), not as
precision (0 false positives across both samples). For a redaction tool
specifically, that's the safer failure mode to bias toward in most of
these cases — a false positive can silently corrupt a real figure (e.g.
turning a real DIN into a fake phone-shaped string), while most of these
particular false negatives are on organization names/addresses that
often repeat elsewhere in the document under a name the tool does catch
(the "IndusInd Bank Limited" address is redacted even though "Bandra
Kurla Complex" as a stand-alone phrase elsewhere might not be).
