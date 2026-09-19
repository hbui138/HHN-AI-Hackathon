# File: src/search_engine.py
import pandas as pd
import json
import re
import math
import chromadb
from sentence_transformers import SentenceTransformer, CrossEncoder
from rapidfuzz import process, fuzz
import warnings
from pathlib import Path
from normalization import normalize_german_text, normalize_code
from normalization import strip_supplier_prefix, ABLATE
from build_crossref import find_norelem_codes, split_kipp_code, find_brand_mentions, brand_word
from attribute_rules import attribute_score
from feature_flags import enabled
from bearing_codes import split_designation, base_aliases, suffix_score, query_designations

warnings.filterwarnings('ignore')

BASE_DIR = Path(__file__).resolve().parent.parent

# {normalized_code: [product_id, ...]} - a code may map to several variants
with open(BASE_DIR / "preprocessed_data" / "exact_match_dict.json", "r", encoding="utf-8") as f:
    exact_match_dict = json.load(f)
all_clean_codes = list(exact_match_dict.keys())

df_master = pd.read_parquet(BASE_DIR / "preprocessed_data" / "master_database.parquet")
df_master_dict = df_master.set_index('id').to_dict('index') 

# Kipp suffix index: '4004' -> [(kipp_series, id), ...]  (K0338.4004, K0631.4004, ...)
kipp_suffix_index = {}
for pid, codes in zip(df_master['id'], df_master['searchable_codes']):
    for c in codes:
        kipp = split_kipp_code(c)
        if kipp:
            kipp_suffix_index.setdefault(normalize_code(kipp[1]), []).append((kipp[0], pid))

# Bearing base index: '2205' -> [(id, canonical_suffix), ...] (codes without Boie's supplier prefix)
bearing_base_index = {}
bearing_prefixed_index = {}
LETTER_PREFIX_PENALTY = 0.10
df_bearings = df_master[df_master['category'] == 'bearings']
for pid, codes, manufacturer in zip(df_bearings['id'], df_bearings['searchable_codes'], df_bearings['manufacturer']):
    for c in codes:
        parsed = split_designation(strip_supplier_prefix(c, manufacturer) or c)
        if parsed:
            bearing_base_index.setdefault(parsed[0], []).append((pid, parsed[1]))
            # Same digits with a letter prefix ('W 61802' = stainless 61802): reachable from '61802', with a penalty
            letters = re.match(r'[A-Z]+', parsed[0])
            if letters:
                bearing_prefixed_index.setdefault(parsed[0][letters.end():], []).append((pid, parsed[1]))
BRAND_STOP_WORDS = {str(m).strip().upper() for m in df_master['manufacturer'].dropna().unique()}

# Norelem series -> Kipp series learned from training inquiries (build_crossref.py)
crossref_path = BASE_DIR / "preprocessed_data" / "norelem_kipp_series.json"
norelem_kipp_series = json.load(open(crossref_path, encoding="utf-8")) if crossref_path.exists() else {}

# Brand model learned from training inquiries (build_crossref.py): which manufacturer Boie really delivers
brand_model_path = BASE_DIR / "preprocessed_data" / "brand_model.json"
brand_model = json.load(open(brand_model_path, encoding="utf-8")) if brand_model_path.exists() else {"mention": {}, "category_prior": {}}
if 'competitors' in ABLATE:
    # Keep only brand words derived from catalogue manufacturers, drop the hand-typed competitor list
    from build_crossref import COMPETITOR_BRANDS
    catalogue_words = {brand_word(m) for m in df_master['manufacturer'].dropna().unique()}
    brand_model["mention"] = {w: d for w, d in brand_model["mention"].items() if w in catalogue_words or w not in COMPETITOR_BRANDS}
BRAND_MENTION_WORDS = sorted(brand_model["mention"])

# Query word -> product attribute rules learned from training inquiries (attribute_rules.py)
attribute_rules_path = BASE_DIR / "preprocessed_data" / "attribute_rules.json"
attribute_rules = json.load(open(attribute_rules_path, encoding="utf-8")) if attribute_rules_path.exists() and 'attr_rules' not in ABLATE else {}

# ================= SCORING WEIGHTS =================
W_CODE, W_BRAND, W_TEXT, W_ATTR = 0.55, 0.20, 0.10, 0.15   # candidates found by part-number evidence
VECTOR_CAP = 0.85                             # semantic-only candidates stay below real code matches
BRAND_FLOOR_MENTION = 0.3                     # brand named, but Boie never delivers this manufacturer for it
BRAND_FLOOR_PRIOR = 0.5                       # no brand named: softer penalty from the category prior
BRAND_NEUTRAL = 0.8                           # nothing known (no brand, no category)
MAX_CODE_CANDIDATES = 25
MAX_VECTOR_CANDIDATES = 10
# ===================================================

chroma_client = chromadb.PersistentClient(path=str(BASE_DIR / "chroma_db_finetuned"))
collection = chroma_client.get_collection(name="boie_products")

finetuned_model_path = BASE_DIR / "models" / "finetuned_boie_minilm"
if finetuned_model_path.exists():
    embedding_model = SentenceTransformer(str(finetuned_model_path))
else:
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2') 

cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

def add_candidates(candidate_pool, db_code, score):
    for db_id in exact_match_dict[db_code]:
        add_candidate(candidate_pool, db_id, score)

def add_candidate(candidate_pool, db_id, score):
    # Keep the best heuristic evidence found for a product
    candidate_pool[db_id] = max(candidate_pool.get(db_id, 0.0), score)

QUERY_SPLIT = re.compile(r'[\s;+|()\[\]"»«_]+')

def extract_query_codes(query, max_ngram=3):
    """Candidate part numbers straight from the raw query (does not rely on the LLM).
    Joins up to 3 neighbouring chunks so '4202 ATN 9' -> '4202atn9'.
    Returns {normalized_code: n_chunks_joined}."""
    chunks = [normalize_code(c) for c in QUERY_SPLIT.split(str(query))]
    chunks = [c for c in chunks if c]
    codes = {}
    for n in range(1, max_ngram + 1):
        for i in range(len(chunks) - n + 1):
            joined = ''.join(chunks[i:i + n])
            if len(joined) >= 4 and any(ch.isdigit() for ch in joined) and joined not in codes:
                codes[joined] = n
    return codes

def add_query_code_candidates(candidate_pool, query):
    for q_code, n_chunks in extract_query_codes(query).items():
        if q_code in exact_match_dict:
            # Single token with letters+digits (or long) is a strong signal; joined / short numeric tokens less so
            strong = n_chunks == 1 and (not q_code.isdigit() or len(q_code) >= 6)
            add_candidates(candidate_pool, q_code, 1.0 if strong else 0.9)
        elif n_chunks == 1 and len(q_code) >= 6:
            # DB code is a prefix of the query token: 'T2EE100-100-165-47' -> 'T2EE 100'
            for end in range(len(q_code) - 1, 4, -1):
                if q_code[:end] in exact_match_dict:
                    add_candidates(candidate_pool, q_code[:end], graded_score(0.9, q_code, q_code[:end]))
                    break

def add_bearing_candidates(candidate_pool, query):
    # Match on the bearing base ('6001') and grade the suffix ('2RS1' vs '2RSH', '2RSH/C3', ...)
    best = {}
    for base, suffix_options in query_designations(QUERY_SPLIT.split(str(query)), BRAND_STOP_WORDS):
        for alias in base_aliases(base):
            matches = [(pid, suf, 0.0) for pid, suf in bearing_base_index.get(alias, [])]
            if alias.isdigit():
                matches += [(pid, suf, LETTER_PREFIX_PENALTY) for pid, suf in bearing_prefixed_index.get(alias, [])]
            for pid, db_suffix, penalty in matches:
                score = max(suffix_score(opt, db_suffix) for opt in suffix_options) - penalty
                best[pid] = max(best.get(pid, 0.0), score)
    for pid, score in best.items():
        add_candidate(candidate_pool, pid, score)

def cross_encoder_document(pid):
    # Always put manufacturer + part numbers in front: some catalogue texts contain their own code
    # ('1006208-2RS1N ...') and others don't ('Rillenkugellager ...'), which let the Cross-Encoder
    # prefer variants over the exact product just because the code appeared in their text.
    record = df_master_dict[pid]
    codes = " ".join(str(c) for c in record.get('searchable_codes', []))
    return f"{record.get('manufacturer', '')} {codes} {record.get('combined_text', '')}"

def expected_brand_distribution(query, llm_brand, category):
    """P(manufacturer Boie delivers | brands named in the query) - e.g. 'FAG' -> SKF, 'NORELEM' -> Kipp.
    Falls back to the category prior when no known brand is mentioned."""
    words = set(find_brand_mentions(query, BRAND_MENTION_WORDS))
    llm_word = brand_word(llm_brand) if llm_brand else None
    if llm_word in brand_model["mention"]:
        words.add(llm_word)
    if words:
        dists = [brand_model["mention"][w] for w in words]
        manufacturers = {m for d in dists for m in d}
        return {m: max(d.get(m, 0.0) for d in dists) for m in manufacturers}, BRAND_FLOOR_MENTION
    return brand_model["category_prior"].get(category, {}), BRAND_FLOOR_PRIOR

def brand_score(manufacturer, brand_dist):
    dist, floor = brand_dist
    if not dist:
        return BRAND_NEUTRAL
    return floor + (1 - floor) * dist.get(manufacturer, 0.0) / max(dist.values())

def graded_score(base_score, query_code, db_code):
    # '678' vs '678/A': every extra character of the DB code costs 1 point, never below 0.8
    return max(0.8, base_score - 0.01 * abs(len(db_code) - len(query_code)))

BOIE_ARTICLE_ID = re.compile(r'(?<!\d)(\d{6,10})(?!\d)')
ARTICLE_ID_OTHERS_CAP = 0.90

def find_boie_article_ids(query):
    # Customers often copy Boie's own article number from an old order ('... 6010 2Z / 10004423').
    # Any standalone number that IS a product id in the catalogue counts (92-98% of the time it is the label).
    return [n for n in BOIE_ARTICLE_ID.findall(str(query)) if n in df_master_dict]

def apply_article_id_evidence(candidate_pool, query):
    article_ids = find_boie_article_ids(query)
    if not article_ids:
        return
    # The article number names one exact product: every other code match becomes secondary
    for pid in candidate_pool:
        candidate_pool[pid] = min(candidate_pool[pid], ARTICLE_ID_OTHERS_CAP)
    for pid in article_ids:
        candidate_pool[pid] = 1.0

def add_norelem_crossref_candidates(candidate_pool, query):
    # 'Arretierbolzen 03089-4004 Norelem' -> Kipp K0338.4004 (shared size suffix)
    for norelem_series, suffix in find_norelem_codes(query):
        bucket = kipp_suffix_index.get(normalize_code(suffix), [])
        known_series = norelem_kipp_series.get(norelem_series, {})
        for kipp_series, pid in bucket:
            if kipp_series in known_series:
                add_candidate(candidate_pool, pid, 0.95)
            elif len(bucket) <= 20:
                add_candidate(candidate_pool, pid, 0.8)

def generate_code_candidates(original_query, raw_part_number=None, expected_category=None):
    """All candidates backed by part-number evidence: {id: S_code}.
    Also used offline (build_attribute_rules.py) without the LLM part number."""
    code = normalize_code(raw_part_number)

    # Rổ chứa mọi ứng viên: {id: heuristic_score}
    candidate_pool = {}
    
    # 1. TÌM ỨNG VIÊN BẰNG HEURISTICS (Quy đổi điểm mã số)
    if code and len(code) >= 3:
        # Exact Match
        if code in exact_match_dict:
            add_candidates(candidate_pool, code, 1.0)
            
        # Prefix & Containment Match
        if len(code) >= 4:
            for c in all_clean_codes:
                if c.startswith(code):
                    add_candidates(candidate_pool, c, graded_score(0.95, code, c))
                elif code in c or c in code:
                    add_candidates(candidate_pool, c, graded_score(0.85, code, c))
                        
        # Fuzzy Match
        valid_codes = [c for c in all_clean_codes if abs(len(c) - len(code)) <= 3]
        if valid_codes:
            best_fuzz = process.extract(code, valid_codes, scorer=fuzz.ratio, limit=5)
            for f_code, score, _ in best_fuzz:
                if score >= 80:
                    add_candidates(candidate_pool, f_code, 0.75)

    # 1b. Mã trích trực tiếp từ query bằng regex + đối chiếu chéo Norelem -> Kipp
    add_query_code_candidates(candidate_pool, original_query)
    if 'norelem' not in ABLATE:
        add_norelem_crossref_candidates(candidate_pool, original_query)
    if expected_category in (None, 'bearings') and enabled("bearing_parser"):
        add_bearing_candidates(candidate_pool, original_query)
    apply_article_id_evidence(candidate_pool, original_query)
    return candidate_pool

def hybrid_search(original_query, parsed_data, expected_category=None):
    brand = parsed_data.get("Manufacturer")
    candidate_pool = generate_code_candidates(original_query, parsed_data.get("Part_Number"), expected_category)

    # 2. TÌM ỨNG VIÊN BẰNG SEMANTIC VECTOR (Dành cho text chung chung)
    expanded_query = normalize_german_text(original_query)
    
    # ================= NEW: DOMAIN KNOWLEDGE INJECTION =================
    if 'query_expansion' not in ABLATE:
        # 1. Dịch từ lóng vật liệu sang chuẩn Database
        expanded_query = re.sub(r'\b(va|v2a|v4a)\b', 'edelstahl', expanded_query)
        expanded_query = re.sub(r'\bms\b', 'messing', expanded_query)
        expanded_query = re.sub(r'\bkst\b', 'kunststoff', expanded_query)
    
        # 2. Dịch định dạng kích thước: "m5x12" -> Bơm thêm "d=m05 l=12" vào câu
        dim_matches = re.findall(r'([md])(\d+)[x\*](\d+)', expanded_query)
        for prefix, d, l in dim_matches:
            # Format M5 -> M05 để khớp đúng với Database của Kipp/Norelem
            d_padded = d.zfill(2) 
            expanded_query += f" d={prefix}{d_padded} l={l} {prefix}{d} {l}"
    # ====================================================================

    # # Bơm thêm keyword ngành (giữ nguyên như cũ)
    # if expected_category == 'bearings' and 'lager' not in expanded_query:
    #     expanded_query += " kugellager lager bearing"
    # elif expected_category == 'pneumatics' and 'ventil' not in expanded_query:
    #     expanded_query += " pneumatik ventil schlauch"
        
    query_vector = embedding_model.encode([expanded_query]).tolist()
    
    # TĂNG N_RESULTS LÊN 30! Mở rộng lưới để bắt được nhiều ứng viên hơn.
    search_kwargs = {"query_embeddings": query_vector, "n_results": 30} 
    
    if expected_category: 
        search_kwargs["where"] = {"category": expected_category}
        
    results = collection.query(**search_kwargs)
    vector_ids = results['ids'][0] if results['ids'] and results['ids'][0] else []

    # 3. CHỌN ỨNG VIÊN: ứng viên có bằng chứng mã (heuristics) + ứng viên thuần ngữ nghĩa (vector)
    def in_category(pid):
        return not expected_category or df_master_dict[pid].get('category') == expected_category

    code_candidates = sorted([pid for pid in candidate_pool if in_category(pid)],
                             key=lambda pid: candidate_pool[pid], reverse=True)[:MAX_CODE_CANDIDATES]
    vector_candidates = [pid for pid in vector_ids if pid not in candidate_pool and in_category(pid)][:MAX_VECTOR_CANDIDATES]
    valid_candidates = code_candidates + vector_candidates

    if not valid_candidates:
        return [{"id": None, "confidence": 0.0, "method": "Not_Found"}]

    cross_inp = [[expanded_query, cross_encoder_document(pid)] for pid in valid_candidates]
    cross_scores = cross_encoder.predict(cross_inp)

    brand_dist = expected_brand_distribution(original_query, brand, expected_category)
    # 1.0 for everyone when the query asks for no learned attribute
    attr_scores, fired_rules = attribute_score(original_query, valid_candidates, df_master_dict, attribute_rules)

    # 4. CHẤM ĐIỂM TRỌNG SỐ
    final_results = []
    for idx, pid in enumerate(valid_candidates):
        # Sigmoid để ép điểm Cross-Encoder về dạng % (0.0 -> 1.0)
        s_text = 1 / (1 + math.exp(-cross_scores[idx]))
        s_brand = brand_score(df_master_dict[pid].get('manufacturer', ''), brand_dist)
        s_attr = attr_scores[pid]

        if pid in candidate_pool:
            # A. Có bằng chứng mã: mã quyết định, Cross-Encoder chỉ làm trọng tài giữa các mã ngang điểm
            s_code = candidate_pool[pid]
            final_conf = W_CODE * s_code + W_BRAND * s_brand + W_TEXT * s_text + W_ATTR * s_attr
            method = f"Code(S_code:{round(s_code, 3)}|S_brand:{round(s_brand, 2)}|S_text:{round(s_text, 2)}|S_attr:{round(s_attr, 2)})"
        else:
            # B. Chỉ có ngữ nghĩa: không bao giờ tự tin bằng một mã khớp thật
            final_conf = VECTOR_CAP * s_text * (0.7 * s_brand + 0.3) * (0.7 + 0.3 * s_attr)
            method = f"Semantic(S_text:{round(s_text, 2)}|S_brand:{round(s_brand, 2)}|S_attr:{round(s_attr, 2)})"

        final_results.append({
            "id": pid,
            "confidence": round(final_conf, 3),
            "method": method,
            # Which learned attribute rules fired for this query (explainability in the UI / result file)
            "attribute_rules": {a: w for a, w in fired_rules.items()},
        })

    final_results = sorted(final_results, key=lambda x: x['confidence'], reverse=True)
    return final_results[:3]
