# File: src/feature_flags.py
# Hand-written domain rules can be switched off to measure what each one is worth:
#   ABLATE=supplier_prefix,suffix_equivalents python run_pipeline.py 100
# (see run_ablation.py). Read once at import time.
import os

ABLATE = {x.strip() for x in os.environ.get("ABLATE", "").split(",") if x.strip()}

HARDCODED_RULES = {
    "supplier_prefix": "Boie supplier prefixes FAG 202 / INA 101,102 / GLYCO 109 (normalization.py)",
    "suffix_equivalents": "Bearing suffix equivalents 2RS1/2RSH/2RSR -> 2RS, ZZ/2ZR -> 2Z (bearing_codes.py)",
    "iso_alias": "Bearing ISO 69xx = SKF 619xx (bearing_codes.py)",
    "norm_prefixes": "Skip numbers after DIN / ISO / EN (bearing_codes.py)",
    "query_expansion": "Slang regex VA/V2A/V4A -> edelstahl, MS, KST, M5x12 -> d=m05 l=12 (search_engine.py)",
    "competitors": "Hand-typed competitor brand list NORELEM, ELESA, KOYO... (build_crossref.py)",
    "norelem": "Norelem number pattern -> Kipp suffix lookup (search_engine.py)",
    "bearing_parser": "Whole bearing base + suffix matcher (bearing_codes.py)",
}
LEARNED_COMPONENTS = {
    "attr_rules": "Learned query word -> attribute rules (attribute_rules.py)",
}


def enabled(name):
    return name not in ABLATE
