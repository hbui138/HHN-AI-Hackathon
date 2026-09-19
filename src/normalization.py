# File: src/normalization.py
# Shared normalization so that the exact-match dictionary and the search engine
# always produce identical keys for the same part number.
import re
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
SUPPLIER_CODE_PREFIXES = {
    'FAG': ('202',),
    'INA': ('101', '102'),
    'GLYCO': ('109',),
}


def strip_supplier_prefix(code, manufacturer):
    """Return the code without Boie's supplier prefix, or None if there is none."""
    code = str(code).strip()
    if not enabled("supplier_prefix"):
        return None
    for prefix in SUPPLIER_CODE_PREFIXES.get(str(manufacturer).strip().upper(), ()):
        if code.startswith(prefix) and len(code) > len(prefix) + 2:
            return code[len(prefix):].strip()
    return None
