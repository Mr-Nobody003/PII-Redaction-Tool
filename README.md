# PII Redaction Tool — README

## What this is

A script that reads `Red_Herring_Prospectus.docx` (a real, 128-page SEBI
regulatory filing) and produces `redacted_output.docx`, with personally
identifiable information replaced by consistent, clearly-fake values —
plus the scripts used to evaluate it.

```
pii_tool/
  redact_pii.py     # CLI + orchestration (run this)
  detectors.py       # one class per PII type — the extension point
  fake_data.py        # Faker replacement (no network access, see below)
  evaluate.py          # precision/recall/F1 harness
  evaluation_results.json
```

Run it:
```bash
python3 redact_pii.py Red_Herring_Prospectus.docx redacted_output.docx --log detections.json
python3 evaluate.py
```

## Approach

**Regex + heuristics, not an NER model.** The sandbox this was built in
has no outbound network access, which rules out `pip install
presidio-analyzer spacy faker` and downloading the `en_core_web_lg`
model (Presidio's `PERSON`/`ORG` recognizers depend on it). Everything
here is regex and light context rules instead. See "If you have network
access" below for the natural upgrade path.

The pipeline has two passes over the document:

1. **Structural pass.** A handful of tables in a document like this have
   unambiguous column headers — the Board of Directors table
   (`Name | Designation | DIN | Address`), the cover-page registered/
   corporate-office block (`Contact Person | E-mail and Telephone`).
   Where a table's headers map cleanly to a PII type, the whole cell is
   redacted according to that column, which is both higher precision and
   higher recall than regex on those specific rows. This pass also feeds
   every name/org it finds into a shared registry.

2. **Free-text pass.** Every other paragraph and cell runs through:
   - Regex detectors for emails, IPv4 addresses, SSNs, credit cards
     (Luhn-validated), phone numbers, and context-anchored dates of
     birth (a bare date is *not* treated as a DOB — only one within ~40
     characters of "Date of Birth"/"DOB"/"born on").
   - A heuristic address detector: a 6-digit Indian PIN code followed by
     a state name is used as the anchor for a whole address block.
   - An exact-match sweep for every name/org the structural pass (and a
     few extra context anchors — "OUR PROMOTERS: ...", "Contact Person:
     X", "X is our Company Secretary") discovered elsewhere in the
     document, so the same person is redacted consistently wherever
     they're mentioned in running prose, not just in the table they were
     first found in.

Overlapping matches are resolved by keeping the longer span; the
document is then rewritten right-to-left so earlier offsets stay valid.

**Fake replacements.** `fake_data.py` hands out a name from a small
fixed pool, cycling by first-seen order, and derives emails as
`first.last@example.com`, credit cards, addresses, IPs, etc.
Replacement is cached by the original value, so "Kushal Subbayya Hegde"
gets the same fake name every time it appears (as director, promoter, or
in prose), and the same DIN keeps pointing at the same fake address. It
deliberately mirrors the assignment's own example scheme (first name
found → "John Doe", first email found → "john.doe@example.com").

## Choices made explicit (per the assignment's own "be explicit" ask)

- **DIN, CIN, and job titles are not redacted.** A Director
  Identification Number / Corporate Identity Number is a public
  regulatory ID (comparable to the assignment's own "Order/Ticket
  number" carve-out) — including them in the output docx doesn't
  identify anyone beyond what the DIN already publicly does, and keeping
  them makes the redacted document still useful as a document. Same
  reasoning for "Designation" columns (a title alone isn't PII).

- **The issuer's own company name (and its two former names, "Bhandary
  Metal Extrusion Private Limited" / "KSH International Private
  Limited") is not redacted.** It's the subject of a public filing,
  named on every page and in the filename; redacting it doesn't protect
  anyone and makes the document nonsensical. It's on an explicit
  allowlist in `redact_pii.py`.

- **Regulatory/market-infrastructure bodies are not redacted** —
  SEBI, RBI, NSE, BSE, the Registrar of Companies, and named Acts
  (Companies Act, SEBI Act, Depositories Act). These are generic public
  institutions, not a confidential business relationship, the same
  category the assignment itself carves out.

- **Everything else that looks like a company — banks, lead managers,
  the statutory auditor, individual lenders — IS redacted**, on the
  view that a named business counterparty is the closest match in this
  document to what the assignment's "ticket log" framing was pointing
  at. This is a judgment call; the opposite choice (leave large public
  banks alone, since a bank name alone doesn't identify a *person*) is
  also defensible — I picked the more conservative option.

- **The assignment's own example row is inconsistent** — it shows
  `+91 9876543210: +91 9876543210` (phone number unchanged on both
  sides), unlike the name/email rows. I treated that as a likely
  copy-paste slip in the assignment text rather than an instruction, and
  this tool *does* replace phone numbers with fake ones.

## Known tradeoffs, false positives/negatives

- **No NER means recall depends on structural or lexical anchors.**
  Company names are only caught if they end in a legal suffix (Limited,
  Ltd, LLP, Pvt. Ltd., Inc., Corp.) or were discovered via a table
  column / "OUR PROMOTERS" list. In the evaluation sample this missed
  three counterparties without a suffix in that particular sentence —
  "Citibank N.A.", "Export-Import Bank of India", "State Bank of India" —
  even though "IndusInd Bank **Limited**" right next to them was caught.
  If network access were available, swapping the free-text pass for a
  spaCy/Presidio `ORG`/`PERSON` recognizer would close this gap; see
  below.
- **The address detector needs a well-formed 6-digit PIN code.** Two
  addresses in the evaluation sample were missed: one where the source
  document itself has a typo (`41l 005` — a lowercase L instead of a
  digit 1), and one that simply has no PIN code in the original text
  ("...BKC, Mumbai Maharashtra India"). Both are data-quality issues in
  the source, not something a PIN-code-anchored regex can recover from.
- **Website/URL fields are left alone** (not one of the nine required
  categories), even where a bank's redacted name is still recoverable
  from its untouched domain, e.g. `www.icicibank.com` sitting next to a
  redacted "ICICI Bank Limited". Worth adding as a tenth category if the
  scope ever expands.
- **Formatting fidelity is reduced.** The output is rebuilt paragraph-
  by-paragraph and table-by-table rather than edited in place, so
  run-level formatting inside a paragraph (e.g. a bolded name mid-
  sentence) collapses to a single run. Tables, headings, and the overall
  reading order are preserved.
- **Precision safeguards that cost some recall:** a bare 10-digit number
  is only treated as a phone number if a phone-ish word (Telephone,
  Mobile, Contact, Fax) appears within ~40 characters — otherwise it's
  as likely to be a DIN, a PIN code run together with something else, or
  a share count. Same logic for dates: a bare date is never redacted as
  a DOB without a "Date of Birth"/"DOB"/"born on" anchor nearby, since
  the document is otherwise full of legitimate non-birth dates
  (incorporation dates, resolution dates, offer dates).

## If you have network access

Swap `detectors.py`'s free-text `PERSON`/`COMPANY` detectors for a
Presidio `AnalyzerEngine` with the spaCy `en_core_web_lg` model — the
rest of the pipeline (structural pass, registry, fake-data provider,
docx rebuild) doesn't need to change. That should recover most of the
suffix-less company names and catch names that never appear near any of
the structural anchors this version relies on.
