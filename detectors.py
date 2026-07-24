"""
detectors.py
------------
One class per PII type. Every detector implements `find(text) -> list[Span]`,
where Span carries the character offsets and matched text. This is the
"how you'd extend it to a new PII type" hook the assignment asks about:
to add a new category, write a class with a `find()` method and register
an instance of it in `PIIRedactor.DETECTORS` (see redact_pii.py) -- nothing
else in the pipeline needs to change.

No NER model is used. This environment has no outbound network access,
so downloading a spaCy/Presidio model isn't possible; everything here is
regex + light context heuristics. See README.md for the accuracy
tradeoffs that come with that choice.
"""

import re
from dataclasses import dataclass


@dataclass
class Span:
    start: int
    end: int
    text: str
    label: str


# ---------------------------------------------------------------------------
# Simple, self-contained detectors (no external context needed)
# ---------------------------------------------------------------------------

class EmailDetector:
    label = "EMAIL"
    _RE = re.compile(r"\b[A-Za-z0-9][A-Za-z0-9._%+\-]*@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")

    def find(self, text):
        return [Span(m.start(), m.end(), m.group(), self.label) for m in self._RE.finditer(text)]


class IPAddressDetector:
    label = "IP_ADDRESS"
    _RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

    def find(self, text):
        out = []
        for m in self._RE.finditer(text):
            octets = m.group().split(".")
            if all(0 <= int(o) <= 255 for o in octets):
                # Exclude the common false-positive of a version-style
                # number sitting right after "Fiscal"/"Rs."/"page" etc. --
                # in practice IPv4 needs exactly 4 dot-separated octets,
                # which rarely occurs by accident in prose, so no extra
                # filtering beyond the range check is applied.
                out.append(Span(m.start(), m.end(), m.group(), self.label))
        return out


class SSNDetector:
    label = "SSN"
    _RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

    def find(self, text):
        return [Span(m.start(), m.end(), m.group(), self.label) for m in self._RE.finditer(text)]


class CreditCardDetector:
    label = "CREDIT_CARD"
    # 13-19 digits, grouped in 4s and optionally separated by spaces/dashes.
    _RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")

    @staticmethod
    def _luhn_ok(digits: str) -> bool:
        total = 0
        for i, ch in enumerate(reversed(digits)):
            d = int(ch)
            if i % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        return total % 10 == 0

    def find(self, text):
        out = []
        for m in self._RE.finditer(text):
            digits = re.sub(r"[ -]", "", m.group())
            if 13 <= len(digits) <= 19 and self._luhn_ok(digits):
                out.append(Span(m.start(), m.end(), m.group(), self.label))
        return out


class PhoneNumberDetector:
    label = "PHONE_NUMBER"
    # High-confidence: has a country code (+91, +1, ...) or a hyphenated
    # STD/area-code prefix -- these are unambiguous phone-shaped strings.
    _HIGH_CONF = re.compile(
        r"(?<!\d)(?:\+\s?\d{1,3}(?:[\s-]?\d){7,11}|0\d{2,4}-\d{6,8})(?!\d)"
    )
    # Lower-confidence: a bare 10-digit Indian mobile-shaped number. Only
    # counted if a phone-ish keyword appears nearby, otherwise this pattern
    # collides with DIN numbers, PIN codes glued together, share counts, etc.
    _BARE_10 = re.compile(r"(?<!\d)[6-9]\d{9}(?!\d)")
    _CONTEXT_RE = re.compile(r"(?i)\b(tel(ephone)?|phone|mobile|contact|fax)\b")
    _CONTEXT_WINDOW = 40

    def find(self, text):
        out = []
        taken = []
        for m in self._HIGH_CONF.finditer(text):
            out.append(Span(m.start(), m.end(), m.group(), self.label))
            taken.append((m.start(), m.end()))
        for m in self._BARE_10.finditer(text):
            if any(s <= m.start() < e for s, e in taken):
                continue
            window = text[max(0, m.start() - self._CONTEXT_WINDOW): m.start()]
            if self._CONTEXT_RE.search(window):
                out.append(Span(m.start(), m.end(), m.group(), self.label))
        return out


# ---------------------------------------------------------------------------
# Context-anchored detectors (need a keyword nearby to fire; keeps precision
# high on a document where bare numbers/dates are usually *not* PII)
# ---------------------------------------------------------------------------

class DateOfBirthDetector:
    label = "DATE_OF_BIRTH"
    _DATE_RE = re.compile(
        r"\b(?:\d{1,2}[/\-. ]\d{1,2}[/\-. ]\d{2,4}"
        r"|(?:January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+\d{1,2},?\s+\d{4})\b"
    )
    _CONTEXT_RE = re.compile(r"(?i)\b(date of birth|d\.?o\.?b\.?|born on)\b")
    _WINDOW = 40

    def find(self, text):
        out = []
        for m in self._DATE_RE.finditer(text):
            window = text[max(0, m.start() - self._WINDOW): m.start()]
            if self._CONTEXT_RE.search(window):
                out.append(Span(m.start(), m.end(), m.group(), self.label))
        return out


class AddressDetector:
    """
    Heuristic: an address block ends in a 6-digit Indian PIN code followed
    (within a short window) by a recognised state name and, usually,
    "India". We walk backwards from the PIN code to the nearest paragraph/
    cell boundary (the caller passes in already-scoped text, e.g. one table
    cell) to capture the rest of the block.
    """
    label = "ADDRESS"
    _STATES = (
        "Maharashtra|Madhya Pradesh|Gujarat|Karnataka|Tamil Nadu|Kerala|Telangana|"
        "Andhra Pradesh|Uttar Pradesh|Bihar|West Bengal|Rajasthan|Punjab|Haryana|"
        "Odisha|Assam|Jharkhand|Chhattisgarh|Uttarakhand|Himachal Pradesh|Goa|Delhi"
    )
    _RE = re.compile(
        r"[^.\n]*?\b\d{3}\s?-{0,2}\s?\d{3}\b[^.\n]*?(?:" + _STATES + r")(?:,?\s*India)?",
        re.IGNORECASE,
    )

    def find(self, text):
        out = []
        for m in self._RE.finditer(text):
            out.append(Span(m.start(), m.end(), m.group(), self.label))
        return out


# ---------------------------------------------------------------------------
# Name / company detectors -- discovered via structural anchors elsewhere
# (see NameRegistry in redact_pii.py); this module also offers a generic
# honorific-based fallback usable directly on free text.
# ---------------------------------------------------------------------------

class HonorificNameDetector:
    """Catches 'Mr./Mrs./Ms./Dr. <Name>' patterns anywhere in free text --
    a recall booster for names not captured by the structural anchors."""
    label = "PERSON"
    _RE = re.compile(
        r"\b(?:Mr|Mrs|Ms|Dr)\.\s+([A-Z][a-zA-Z'.-]+(?:\s+[A-Z][a-zA-Z'.-]+){0,3})"
    )

    def find(self, text):
        out = []
        for m in self._RE.finditer(text):
            out.append(Span(m.start(1), m.end(1), m.group(1), self.label))
        return out


class CompanySuffixDetector:
    """Catches '<Words> Limited/Ltd/LLP/Pvt. Ltd./Inc./Corporation' anywhere
    in free text -- a recall booster alongside the curated company list."""
    label = "COMPANY"
    _RE = re.compile(
        r"\b([A-Z][A-Za-z&,.\-]*(?:\s+[A-Z][A-Za-z&,.\-]*){0,5}\s+"
        r"(?:Limited|Ltd\.?|LLP|Pvt\.?\s?Ltd\.?|Private\s+Limited|Inc\.?|Corporation|Corp\.?))\b"
    )

    def find(self, text):
        out = []
        for m in self._RE.finditer(text):
            out.append(Span(m.start(1), m.end(1), m.group(1), self.label))
        return out
