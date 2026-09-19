# File: src/attribute_rules.py
# Learns "query word -> product attribute" rules from the labelled TRAINING inquiries, instead of
# hand-written synonym lists. Example of what it should discover:
#   'a2' / 'edelstahl' / 'va'  ->  Lagerwerkstoff = rostfreier Stahl
#
# Contrastive idea: for each training query we take the label plus the confusable candidates our own
# candidate generator returns (mostly variants of the same code). Only attributes that DIFFER inside
# that set are informative. For every query word we count how often the label had such an attribute
# (positive) vs. a confusable candidate had it but the label did not (negative).
# A rule is kept only if the word LIFTS that rate well above the attribute's baseline; otherwise every
# word would be linked to the label's own dimensions (sizes almost always differ between candidates).
#
# Usage: python attribute_rules.py   -> preprocessed_data/attribute_rules.json
import re
import math
import json
from collections import Counter, defaultdict
from pathlib import Path
from normalization import normalize_german_text

MIN_SUPPORT = 15       # rule must be seen as positive at least this often
MIN_PRECISION = 0.75   # Wilson lower bound of P(label has attribute | word in query, attribute is discriminative)
MIN_LIFT = 0.40        # that bound must beat the attribute's baseline (no word condition) by this much
MIN_SCORE = 0.8        # only siblings with real code evidence count as "confusable"
MAX_SIBLINGS = 25


def wilson_lower_bound(successes, total, z=1.96):
    # Conservative precision: small samples (5/5) score much lower than large ones (95/100)
    if total == 0:
        return 0.0
    p = successes / total
    denom = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return (centre - margin) / denom


def query_tokens(query):
    words = re.findall(r'[a-z0-9]+', normalize_german_text(query))
    tokens = {w for w in words if 2 <= len(w) <= 20}
    # Adjacent pairs keep short but meaningful options: 'Form A' -> 'form_a'
    tokens |= {f"{a}_{b}" for a, b in zip(words, words[1:]) if len(a) + len(b) <= 20 and not (a.isdigit() and b.isdigit())}
    return tokens


NUMERIC_VALUE = re.compile(r'[\d.,\s/x-]+[a-z°%"]{0,3}', re.IGNORECASE)


def attribute_keys(record):
    keys = set()
    attributes = record.get('attributes')
    for attr in (attributes if attributes is not None else []):  # numpy array when read from parquet
        name, value = str(attr.get('name', '')).strip(), str(attr.get('value', '')).strip()
        # Only categorical attributes (material, form, sealing, clearance...). Numeric values such as
        # 'Höhe=20 mm' are dimensions: words only correlate with them by accident.
        if name and value and not NUMERIC_VALUE.fullmatch(value):
            keys.add(f"{name}={value}".lower())
    return keys


def attribute_score(query, candidate_ids, records, rules):
    """S_attr for each candidate in [0, 1]; 1.0 for everyone when no learned rule applies.
    - A rule only fires when its word is in the query AND some candidate has the attribute.
    - One value per attribute name (a query cannot ask for 'Gewindelänge=16' and '=20' at once):
      the strongest rule wins.
    - Relative: the best-fitting candidate gets 1.0, so attributes arbitrate between variants
      instead of lowering the confidence of the whole pool."""
    tokens = query_tokens(query)
    cand_attrs = {pid: attribute_keys(records[pid]) for pid in candidate_ids}
    present = set().union(*cand_attrs.values()) if cand_attrs else set()
    by_name = {}
    for token in tokens:
        for attr, weight in rules.get(token, {}).items():
            if attr in present:
                name = attr.split("=", 1)[0]
                if weight > by_name.get(name, ("", 0.0))[1]:
                    by_name[name] = (attr, weight)
    fired = dict(by_name.values())
    raw = {pid: sum(w for a, w in fired.items() if a in cand_attrs[pid]) for pid in candidate_ids}
    best = max(raw.values()) if raw else 0.0
    if best <= 0:
        return {pid: 1.0 for pid in candidate_ids}, {}
    return {pid: raw[pid] / best for pid in candidate_ids}, fired


def main():
    # Heavy imports only for offline learning (search_engine loads models / DB)
    from tqdm import tqdm
    import pandas as pd
    import search_engine as se
    from build_crossref import load_train_split
    from normalization import normalize_category

    base_dir = Path(__file__).resolve().parent.parent
    train_df = load_train_split(base_dir, se.df_master)
    records = se.df_master_dict

    pos, neg = defaultdict(Counter), defaultdict(Counter)
    base_pos, base_neg = Counter(), Counter()
    used_rows = 0
    for query, label, source in tqdm(zip(train_df['CustomerArticleDescription'], train_df['articleid_matched'], train_df['category']),
                                     total=len(train_df), desc="Learning attribute rules"):
        if label not in records:
            continue
        category = normalize_category(source)
        pool = se.generate_code_candidates(str(query), None, category)
        siblings = [pid for pid, score in sorted(pool.items(), key=lambda x: -x[1])
                    if score >= MIN_SCORE and pid != label and records[pid].get('category') == category][:MAX_SIBLINGS]
        if not siblings:
            continue
        label_attrs = attribute_keys(records[label])
        sibling_attrs = [attribute_keys(records[pid]) for pid in siblings]
        everyone = [label_attrs] + sibling_attrs
        # Discriminative = present in some but not all products of this confusable set
        discriminative = set().union(*everyone) - set.intersection(*everyone)
        if not discriminative:
            continue
        used_rows += 1
        tokens = query_tokens(query)
        for attr in discriminative:
            (base_pos if attr in label_attrs else base_neg)[attr] += 1
            counter = pos if attr in label_attrs else neg
            for token in tokens:
                counter[token][attr] += 1

    rules = defaultdict(dict)
    for token, attrs in pos.items():
        for attr, p in attrs.items():
            n = neg[token][attr]
            precision = wilson_lower_bound(p, p + n)
            baseline = base_pos[attr] / (base_pos[attr] + base_neg[attr])
            if p >= MIN_SUPPORT and precision >= MIN_PRECISION and precision - baseline >= MIN_LIFT:
                # Weight = how much the word adds on top of the baseline
                rules[token][attr] = round(precision - baseline, 3)

    out_path = base_dir / "preprocessed_data" / "attribute_rules.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=1, sort_keys=True)
    n_rules = sum(len(v) for v in rules.values())
    print(f"Learned {n_rules} rules for {len(rules)} query words from {used_rows} training rows with confusable variants.")
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
