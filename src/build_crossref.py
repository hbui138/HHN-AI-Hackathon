# File: src/build_crossref.py
# Customers often order Kipp parts using the competitor's (Norelem) number, e.g.
#   "Arretierbolzen 03089-4004"  ->  Kipp K0338.4004
# Both share the size suffix ("4004"); only the series differs (03089 <-> K0338).
# This script learns the series mapping from the TRAINING split of labelled inquiries
# (same split/seed as train_embeddings.py / get_split.py, so the test set is never seen).
#
# It also learns a brand model: which manufacturer Boie actually delivers when a customer
# mentions a brand (FAG / INA / KOYO -> SKF, NORELEM -> Kipp, ELESA -> Ganter) and, when no brand
# is mentioned, the manufacturer distribution per category.
import re
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path
import pandas as pd
from sklearn.model_selection import train_test_split

NORELEM_PATTERN = re.compile(r'(?<![0-9A-Za-z])(\d{5})\s*-\s*([A-Za-z0-9][A-Za-z0-9.,\-]*[A-Za-z0-9])')
KIPP_PATTERN = re.compile(r'^(K\d{4})\.(.+)$', re.IGNORECASE)

# Brands customers mention that are not (or not only) in the catalogue
COMPETITOR_BRANDS = ['NORELEM', 'ELESA', 'KOYO', 'NTN', 'NSK', 'TIMKEN', 'NACHI', 'ZKL', 'SNR', 'IKO', 'FESTO', 'SMC', 'HALDER']
GENERIC_BRAND_WORDS = {'GMBH', 'CO', 'KG', 'AG', 'DER', 'UND', 'THE', 'INC'}
MIN_MENTIONS = 5


def brand_word(manufacturer):
    """'Riegler & Co. KG' -> 'RIEGLER' (the word customers actually write)."""
    for word in re.findall(r'[A-Za-zÄÖÜäöü]+', str(manufacturer)):
        if len(word) >= 3 and word.upper() not in GENERIC_BRAND_WORDS:
            return word.upper()
    return None


def find_brand_mentions(query, brand_words):
    text = str(query).upper()
    return [w for w in brand_words if re.search(r'(?<![A-Z])' + re.escape(w) + r'(?![A-Z])', text)]


def find_norelem_codes(query):
    """Return [(series, suffix), ...] for Norelem-style numbers like '03089-4004'."""
    return NORELEM_PATTERN.findall(str(query))


def split_kipp_code(code):
    """'K0338.4004' -> ('K0338', '4004'); None if not a Kipp K-code."""
    m = KIPP_PATTERN.match(str(code).strip())
    return (m.group(1).upper(), m.group(2)) if m else None


def load_train_split(base_dir, df_master):
    # Reproduce the exact split from get_split.py
    df_list = []
    for file in glob.glob(str(base_dir / "customerinquiry" / "*.csv")):
        df = pd.read_csv(file, on_bad_lines='skip', engine='python')
        df['category'] = Path(file).name
        df_list.append(df)
    df_inquiry = pd.concat(df_list, ignore_index=True)
    df_inquiry = df_inquiry.dropna(subset=['articleid_matched', 'CustomerArticleDescription'])
    df_inquiry['articleid_matched'] = pd.to_numeric(df_inquiry['articleid_matched'], errors='coerce').fillna(0).astype(int).astype(str)
    merged_df = pd.merge(df_inquiry, df_master[['id']], left_on='articleid_matched', right_on='id', how='inner')
    train_df, _ = train_test_split(merged_df, test_size=0.2, random_state=42)
    return train_df


def learn_brand_model(train_df, df_master):
    info = df_master.set_index('id')[['manufacturer', 'category']]
    train_df = train_df.join(info, on='articleid_matched', rsuffix='_db')

    # P(delivered manufacturer | category) when the customer names no brand
    category_prior = {
        cat: {m: round(p, 4) for m, p in group['manufacturer'].value_counts(normalize=True).items()}
        for cat, group in train_df.groupby('category_db')
    }

    # P(delivered manufacturer | brand word in the query)
    brand_words = sorted({w for w in map(brand_word, df_master['manufacturer'].dropna().unique()) if w} | set(COMPETITOR_BRANDS))
    mention_counts = defaultdict(Counter)
    for query, manufacturer in zip(train_df['CustomerArticleDescription'], train_df['manufacturer']):
        for word in find_brand_mentions(query, brand_words):
            mention_counts[word][manufacturer] += 1
    mention = {
        word: {m: round(n / sum(c.values()), 4) for m, n in c.most_common()}
        for word, c in mention_counts.items() if sum(c.values()) >= MIN_MENTIONS
    }
    return {"category_prior": category_prior, "mention": mention, "brand_words": brand_words}


def main():
    base_dir = Path(__file__).resolve().parent.parent
    df_master = pd.read_parquet(base_dir / "preprocessed_data" / "master_database.parquet")
    df_master['id'] = df_master['id'].astype(str).str.strip()
    train_df = load_train_split(base_dir, df_master)

    codes_by_id = dict(zip(df_master['id'], df_master['searchable_codes']))
    series_map = defaultdict(Counter)
    for query, truth in zip(train_df['CustomerArticleDescription'], train_df['articleid_matched']):
        kipp = [split_kipp_code(c) for c in codes_by_id.get(truth, [])]
        kipp = [k for k in kipp if k]
        if not kipp:
            continue
        for norelem_series, _ in find_norelem_codes(query):
            for kipp_series, _ in kipp:
                series_map[norelem_series][kipp_series] += 1

    output = {s: dict(c) for s, c in series_map.items()}
    out_path = base_dir / "preprocessed_data" / "norelem_kipp_series.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Learned {len(output)} Norelem series -> Kipp series mappings from {len(train_df)} training rows.")
    print(f"Saved to {out_path}")

    brand_model = learn_brand_model(train_df, df_master)
    brand_path = base_dir / "preprocessed_data" / "brand_model.json"
    with open(brand_path, "w", encoding="utf-8") as f:
        json.dump(brand_model, f, ensure_ascii=False, indent=2)
    print(f"Learned brand model: {len(brand_model['mention'])} brand words, priors for {len(brand_model['category_prior'])} categories -> {brand_path}")


if __name__ == "__main__":
    main()
