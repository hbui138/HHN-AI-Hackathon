# File: src/normalization.py
# Shared normalization so that the exact-match dictionary and the search engine
# always produce identical keys for the same part number.
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from feature_flags import ABLATE, enabled

INVALID_CODES = {"", "nan", "none", "null"}


def normalize_german_text(text):
    if not text: return ""
    return str(text).lower().replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')


def normalize_code(code):
    """'71802 CD/P4DBA' -> '71802cdp4dba'. Returns '' for empty / NaN-like values."""
    if code is None: return ""
    raw = str(code).strip()
    if raw.lower() in INVALID_CODES: return ""
    return re.sub(r'[^a-z0-9]', '', normalize_german_text(raw))


def normalize_category(raw):
    """Map an inquiry file name / label to a DB category ('standard-parts' -> 'standard_parts')."""
    raw = str(raw or '').lower().replace('-', '_')
    for cat in ('bearings', 'pneumatics', 'standard_parts'):
        if cat in raw:
            return cat
    return None


# Boie prepends an internal supplier prefix to some manufacturers' codes,
# e.g. FAG '2026219-2Z' is really '6219-2Z', INA '101NATV50-X-PP-A' is 'NATV50-X-PP-A'.
# Hand-written fallback only: create_database.py relearns these from the catalog with
# detect_supplier_prefixes() and writes the result to SUPPLIER_PREFIX_PATH.
SUPPLIER_CODE_PREFIXES = {
    'FAG': ('202',),
    'INA': ('101', '102'),
    'GLYCO': ('109',),
}

SUPPLIER_PREFIX_PATH = Path(__file__).resolve().parent.parent / "preprocessed_data" / "supplier_prefixes.json"

PREFIX_LENGTH = 3
# A small supplier whose own numbering happens to be uniform ('Fluid Concept', 59 codes that all
# start with 200) would otherwise look like a prefix and strip real digits off its codes.
MIN_CODES_PER_MANUFACTURER = 100
MIN_PRIMARY_SHARE = 0.50    # a prefix on half of a manufacturer's codes is an internal prefix, not a series
MIN_SECONDARY_SHARE = 0.05  # further prefixes count only next to a primary one (INA 101 -> also 102)


def detect_supplier_prefixes(manufacturers, codes):
    """Learn Boie's internal code prefixes per manufacturer from the catalog itself.

    A real series prefix is spread over many values (SKF's most common one covers 4% of its
    codes), while an internal prefix sits in front of nearly everything a supplier has:
    FAG 202 = 97%, GLYCO 109 = 100%, INA 101 = 68% (+ 102 = 11%). Returns
    {'FAG': ['202'], ...} — the same shape as SUPPLIER_CODE_PREFIXES."""
    per_manufacturer = defaultdict(list)
    for manufacturer, code in zip(manufacturers, codes):
        name = str(manufacturer).strip().upper()
        code = str(code).strip()
        if name and code:
            per_manufacturer[name].append(code)

    detected = {}
    for name, manufacturer_codes in per_manufacturer.items():
        if len(manufacturer_codes) < MIN_CODES_PER_MANUFACTURER:
            continue
        counts = Counter(c[:PREFIX_LENGTH] for c in manufacturer_codes
                         if c[:PREFIX_LENGTH].isdigit() and len(c) > PREFIX_LENGTH + 2)
        shares = [(prefix, n / len(manufacturer_codes)) for prefix, n in counts.most_common()]
        if not shares or shares[0][1] < MIN_PRIMARY_SHARE:
            continue
        detected[name] = [prefix for prefix, share in shares if share >= MIN_SECONDARY_SHARE]
    return detected


def load_supplier_prefixes():
    """Use the learned prefixes instead of the hand-written ones, once create_database.py wrote them."""
    try:
        with open(SUPPLIER_PREFIX_PATH, encoding="utf-8") as f:
            learned = json.load(f)
    except (OSError, ValueError):
        return False
    if learned:
        SUPPLIER_CODE_PREFIXES.clear()
        SUPPLIER_CODE_PREFIXES.update({k: tuple(v) for k, v in learned.items()})
    return bool(learned)


load_supplier_prefixes()


def strip_supplier_prefix(code, manufacturer):
    """Return the code without Boie's supplier prefix, or None if there is none."""
    code = str(code).strip()
    if not enabled("supplier_prefix"):
        return None
    for prefix in SUPPLIER_CODE_PREFIXES.get(str(manufacturer).strip().upper(), ()):
        if code.startswith(prefix) and len(code) > len(prefix) + 2:
            return code[len(prefix):].strip()
    return None
