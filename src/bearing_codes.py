# File: src/bearing_codes.py
# Bearing designations = base + suffix, e.g. '2205 E-2RS1TN9' -> base '2205', suffix 'E2RS1TN9'.
# Customers usually get the base right but write the suffix loosely ('2205E-2RS', '6001-2RS1'
# for SKF '6001-2RSH', '61907-ZZ' for '61907-2Z'), so we match on the base and grade the suffix.
import re
from rapidfuzz import fuzz
from feature_flags import enabled

# Optional letter prefix (NU, NJ, W, KR ...) + 3-6 digits, followed by a separator, a letter or the end
BASE_PATTERN = re.compile(r'^((?:[A-Z]{1,4}\s?)?\d{3,6})(?=[\s\-/.]|[A-Z]|$)(.*)$')

NORM_PREFIXES = {'DIN', 'ISO', 'EN', 'NR', 'NO', 'ART'}

# Manufacturer-specific names for the same feature
SUFFIX_EQUIVALENTS = [
    (re.compile(r'2RS[1HR]?'), '2RS'),   # SKF 2RS1 / 2RSH, FAG 2RSR: seals on both sides
    (re.compile(r'ZZ|2ZR'), '2Z'),       # shields on both sides
]


def canonical_suffix(suffix):
    s = re.sub(r'[^A-Z0-9]', '', str(suffix).upper())
    for pattern, replacement in (SUFFIX_EQUIVALENTS if enabled("suffix_equivalents") else []):
        s = pattern.sub(replacement, s)
    return s


def split_designation(code):
    """'NU 2216 ECP' -> ('NU2216', 'ECP'); None if the code does not look like a bearing designation."""
    m = BASE_PATTERN.match(str(code).strip().upper())
    if not m:
        return None
    return re.sub(r'\s', '', m.group(1)), canonical_suffix(m.group(2))


def base_aliases(base):
    # ISO 69xx is the same series as SKF 619xx ('6901' -> '61901')
    aliases = [base]
    m = re.fullmatch(r'69(\d{2,3})', base)
    if m and enabled("iso_alias"):
        aliases.append('619' + m.group(1))
    return aliases


def is_subsequence(needle, haystack):
    it = iter(haystack)
    return all(ch in it for ch in needle)


def suffix_score(query_suffix, db_suffix):
    """How well the customer's suffix fits a DB variant. Extra DB characters are penalised so the
    plain variant ('6008-2RS1') beats special ones ('6008-2RS1/VP233F7')."""
    if not query_suffix:
        # Suffix ignored / not given: only a weak fallback, never as good as a real suffix match
        return max(0.80, 0.88 - 0.01 * len(db_suffix))
    if query_suffix == db_suffix:
        return 0.97
    if is_subsequence(query_suffix, db_suffix):
        return max(0.82, 0.95 - 0.01 * (len(db_suffix) - len(query_suffix)))
    return max(0.60, 0.85 * fuzz.ratio(query_suffix, db_suffix) / 100)


def query_designations(raw_chunks, stop_words=()):
    """Find (base, [possible suffixes]) in the query chunks.
    The suffix may continue in the next chunks ('6007 2Z', '4202 ATN 9'), so offer several options."""
    chunks = [c.strip('.,:;').upper() for c in raw_chunks]
    chunks = [c for c in chunks if c]
    results = []
    for i, chunk in enumerate(chunks):
        # 'DIN 625' / 'ISO 15' are standards, not bearing '625'
        if i > 0 and chunks[i - 1] in NORM_PREFIXES and enabled("norm_prefixes"):
            continue
        starts = [(chunk, i + 1)]
        # Letter prefix written as its own word: 'NU 2216'
        if re.fullmatch(r'[A-Z]{1,4}', chunk) and chunk not in NORM_PREFIXES and i + 1 < len(chunks):
            starts.append((chunk + ' ' + chunks[i + 1], i + 2))
        for text, next_idx in starts:
            parsed = split_designation(text)
            if not parsed:
                continue
            base, own_suffix = parsed
            options = ['', own_suffix]
            extra = own_suffix
            for nxt in chunks[next_idx:next_idx + 2]:
                if len(nxt) > 6 or nxt in stop_words:
                    break
                extra += canonical_suffix(nxt)
                options.append(extra)
            results.append((base, options))
    return results
