"""
fake_data.py
------------
Small, dependency-free stand-in for the `Faker` library.

The sandbox this script was built in has no outbound network access, so
`pip install faker` (or spaCy/Presidio models, which download weights from
the internet) is not possible. This module hand-rolls a deterministic
"fake identity" generator that is good enough for redaction purposes:
it produces plausible, obviously-not-real replacement values and is
100% consistent (same input -> same fake output) across a run.

If Faker/Presidio *are* available in the target environment, swap this
module out for `from faker import Faker` and keep the same public
functions (`fake_person_name`, `fake_email`, ...) so the rest of the
codebase does not need to change.
"""

import hashlib
import itertools

# A pool of clearly-fictional names. Index 0 is intentionally "John Doe"
# and index 1 "Peter Parker" to mirror the example given in the assignment.
_NAME_POOL = [
    ("John", "Doe"), ("Peter", "Parker"), ("Jane", "Smith"), ("Priya", "Sharma"),
    ("Michael", "Chen"), ("Emily", "Davis"), ("Amit", "Kumar"), ("Sarah", "Brown"),
    ("David", "Wilson"), ("Anjali", "Rao"), ("Robert", "Johnson"), ("Neha", "Verma"),
    ("James", "Miller"), ("Kavita", "Iyer"), ("Daniel", "Garcia", ), ("Sunita", "Menon"),
    ("Steven", "Clark"), ("Rohit", "Nair"), ("Laura", "Martinez"), ("Arjun", "Reddy"),
    ("Karen", "Lewis"), ("Vikram", "Joshi"), ("Nancy", "Walker"), ("Deepa", "Pillai"),
    ("Kevin", "Hall"), ("Meera", "Bhatt"), ("Brian", "Allen"), ("Ritu", "Kapoor"),
    ("Sanjay", "Desai"), ("Alice", "Young"),
]

_COMPANY_POOL = [
    "Alpha Ventures Limited", "Bluewave Industries Pvt. Ltd.", "Crestline Holdings LLP",
    "Delta Fabrication Limited", "Evergreen Textiles Private Limited", "Falcon Capital Limited",
    "Granite Logistics LLP", "Horizon Chemicals Limited", "Ironclad Engineering Pvt. Ltd.",
    "Junction Retail Limited", "Kestrel Finance Limited", "Lighthouse Foods Private Limited",
    "Meridian Auto Components Limited", "Northgate Bank Limited", "Oakridge Pharma LLP",
    "Pinnacle Steel Limited", "Quantum Softech Private Limited", "Riverside Exports Limited",
    "Summit Realty LLP", "Trident Power Limited",
]

_STREETS = [
    "12 Maple Street", "45 Cedar Avenue", "78 Birch Lane", "23 Oakwood Road",
    "9 Willow Court", "56 Elmwood Drive", "34 Pinehill Street", "67 Riverside Lane",
    "18 Hilltop Avenue", "89 Lakeside Road",
]
_CITIES = [
    ("Springfield", "IL", "62701"), ("Franklin", "TX", "75001"), ("Georgetown", "OH", "45121"),
    ("Clinton", "KS", "67012"), ("Fairview", "CA", "90210"), ("Salem", "OR", "97301"),
    ("Madison", "WI", "53701"), ("Greenville", "NC", "27834"), ("Bristol", "TN", "37620"),
    ("Ashland", "KY", "41101"),
]

_DOMAIN = "example.com"


def _stable_index(key: str, pool_size: int) -> int:
    """Deterministic (not just insertion-order) fallback index, used only if a
    caller looks up a key that was never assigned through the sequential
    counters below (keeps the module safe to call in any order)."""
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest, 16) % pool_size


class FakeIdentityProvider:
    """
    Hands out consistent fake replacements. Each PII *category* has its own
    independent counter, so the Nth unique name seen gets NAME_POOL[N] and,
    separately, the Nth unique email seen gets an email built from
    NAME_POOL[N]. In practice a person's name and email are usually
    discovered in the same order they appear together in the document, so
    the fake name and fake email usually end up "matching" the same pool
    entry -- the same coincidental pairing shown in the assignment's own
    example (Rashi Patil -> John Doe, rashi.patil@... -> john.doe@...).
    """

    def __init__(self):
        self._counters = {"name": 0, "email": 0, "company": 0, "address": 0}
        self._cache = {}  # (category, original.lower()) -> fake value

    def _next(self, category: str) -> int:
        n = self._counters[category]
        self._counters[category] += 1
        return n

    def person_name(self, original: str) -> str:
        key = ("name", original.strip().lower())
        if key not in self._cache:
            idx = self._next("name") % len(_NAME_POOL)
            first, last = _NAME_POOL[idx][:2]
            self._cache[key] = f"{first} {last}"
        return self._cache[key]

    def email(self, original: str) -> str:
        key = ("email", original.strip().lower())
        if key not in self._cache:
            idx = self._next("email") % len(_NAME_POOL)
            first, last = _NAME_POOL[idx][:2]
            self._cache[key] = f"{first.lower()}.{last.lower()}@{_DOMAIN}"
        return self._cache[key]

    def company(self, original: str) -> str:
        key = ("company", original.strip().lower())
        if key not in self._cache:
            idx = self._next("company") % len(_COMPANY_POOL)
            self._cache[key] = _COMPANY_POOL[idx]
        return self._cache[key]

    def address(self, original: str) -> str:
        key = ("address", original.strip().lower())
        if key not in self._cache:
            idx = self._next("address") % len(_CITIES)
            street = _STREETS[idx % len(_STREETS)]
            city, state, zipc = _CITIES[idx]
            self._cache[key] = f"{street}, {city}, {state} {zipc}"
        return self._cache[key]

    def phone(self, original: str) -> str:
        # Keep the same broad shape (leading "+<country>" vs bare) so the
        # redacted text still "reads" like a phone number, but scrub the
        # actual digits to an obviously-fake, consistent sequence.
        key = ("phone", original.strip().lower())
        if key not in self._cache:
            n = self._next("email")  # reuse counter space; value doesn't matter
            fake_digits = f"{(555000000 + n) % 999999999:09d}"
            if original.strip().startswith("+"):
                cc = "".join(itertools.takewhile(lambda c: c.isdigit(), original.strip()[1:]))[:2] or "91"
                self._cache[key] = f"+{cc} {fake_digits[:5]}{fake_digits[5:]}"
            else:
                self._cache[key] = f"({fake_digits[:3]}) {fake_digits[3:6]}-{fake_digits[6:]}"
        return self._cache[key]

    def ssn(self, original: str) -> str:
        key = ("ssn", original.strip().lower())
        if key not in self._cache:
            n = self._stable_index_wrapper(original)
            self._cache[key] = f"{(100+n)%900:03d}-{(10+n)%90:02d}-{(1000+n)%9000:04d}"
        return self._cache[key]

    def credit_card(self, original: str) -> str:
        key = ("cc", original.strip().lower())
        if key not in self._cache:
            n = self._stable_index_wrapper(original)
            self._cache[key] = f"4111 1111 1111 {1111 + (n % 8000):04d}"
        return self._cache[key]

    def ip_address(self, original: str) -> str:
        key = ("ip", original.strip().lower())
        if key not in self._cache:
            n = self._stable_index_wrapper(original)
            self._cache[key] = f"203.0.113.{(n % 254) + 1}"  # TEST-NET-3, RFC 5737
        return self._cache[key]

    def date_of_birth(self, original: str) -> str:
        key = ("dob", original.strip().lower())
        if key not in self._cache:
            n = self._stable_index_wrapper(original)
            day = (n % 28) + 1
            month = (n % 12) + 1
            year = 1960 + (n % 40)
            self._cache[key] = f"{day:02d}-{month:02d}-{year}"
        return self._cache[key]

    def _stable_index_wrapper(self, original: str) -> int:
        return _stable_index(original.strip().lower(), 10_000)
