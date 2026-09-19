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

warnings.filterwarnings('ignore')

BASE_DIR = Path(__file__).resolve().parent.parent

with open(BASE_DIR / "preprocessed_data" / "exact_match_dict.json", "r", encoding="utf-8") as f:
    exact_match_dict = json.load(f)
all_clean_codes = list(exact_match_dict.keys())

df_master = pd.read_parquet(BASE_DIR / "preprocessed_data" / "master_database.parquet")
df_master_dict = df_master.set_index('id').to_dict('index') 

chroma_client = chromadb.PersistentClient(path=str("chroma_db_finetuned"))
collection = chroma_client.get_collection(name="boie_products")

finetuned_model_path = BASE_DIR / "models" / "finetuned_boie_minilm"
if finetuned_model_path.exists():
    embedding_model = SentenceTransformer(str(finetuned_model_path))
else:
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2') 

cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

def normalize_german_text(text):
    if not text: return ""
    return text.lower().replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')

def clean_part_number(part_number):
    if not part_number: return ""
    return re.sub(r'[^a-z0-9]', '', normalize_german_text(part_number))

def hybrid_search(original_query, parsed_data, expected_category=None):
    brand = parsed_data.get("Manufacturer")
    raw_part_number = parsed_data.get("Part_Number")
    code = clean_part_number(raw_part_number)
    
    # Rổ chứa mọi ứng viên: {id: heuristic_score}
    candidate_pool = {} 
    
    # 1. TÌM ỨNG VIÊN BẰNG HEURISTICS (Quy đổi điểm mã số)
    if code and len(code) >= 3:
        # Exact Match
        if code in exact_match_dict:
            candidate_pool[exact_match_dict[code]] = 1.0
            
        # Prefix & Containment Match
        if len(code) >= 4:
            for c in all_clean_codes:
                if c.startswith(code):
                    db_id = exact_match_dict[c]
                    if db_id not in candidate_pool: candidate_pool[db_id] = 0.95
                elif code in c or c in code:
                    db_id = exact_match_dict[c]
                    if db_id not in candidate_pool: candidate_pool[db_id] = 0.85
                        
        # Fuzzy Match
        valid_codes = [c for c in all_clean_codes if abs(len(c) - len(code)) <= 3]
        if valid_codes:
            best_fuzz = process.extract(code, valid_codes, scorer=fuzz.ratio, limit=5)
            for f_code, score, _ in best_fuzz:
                if score >= 80:
                    db_id = exact_match_dict[f_code]
                    if db_id not in candidate_pool: candidate_pool[db_id] = 0.75

    # 2. TÌM ỨNG VIÊN BẰNG SEMANTIC VECTOR (Dành cho text chung chung)
    expanded_query = normalize_german_text(original_query)
    
    # ================= NEW: DOMAIN KNOWLEDGE INJECTION =================
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
    if results['ids'] and results['ids'][0]:
        for pid in results['ids'][0]:
            if pid not in candidate_pool:
                candidate_pool[pid] = 0.60 # Điểm heuristic nền cho Vector

    # 3. LỌC DANH MỤC & CHẠY QUA CROSS-ENCODER ĐỂ CHẤM ĐIỂM NGỮ NGHĨA
    valid_candidates = [
        pid for pid in candidate_pool.keys() 
        if not expected_category or df_master_dict[pid].get('category') == expected_category
    ]
    
    # Cắt top 20 ứng viên để Cross-Encoder chạy nhanh (< 150ms)
    valid_candidates = sorted(valid_candidates, key=lambda x: candidate_pool[x], reverse=True)[:30]
    
    if not valid_candidates:
        return [{"id": None, "confidence": 0.0, "method": "Not_Found"}]

    cross_inp = [[expanded_query, df_master_dict[pid]['combined_text']] for pid in valid_candidates]
    cross_scores = cross_encoder.predict(cross_inp)

    final_results = []
    
    # 4. CHẤM ĐIỂM TRỌNG SỐ (The Magic Formula)
    for idx, pid in enumerate(valid_candidates):
        heur_score = candidate_pool[pid]
        
        # Sigmoid để ép điểm Cross-Encoder về dạng % (0.0 -> 1.0)
        logit = cross_scores[idx]
        ce_score = 1 / (1 + math.exp(-logit)) 
        
        # Brand Score: Nếu khớp hãng cho 1.0, không nhập hãng cho 0.9, sai hãng cho 0.0
        db_brand = df_master_dict[pid].get('manufacturer', '')
        if brand and brand.upper() in db_brand.upper():
            brand_score = 1.0
        elif not brand:
            brand_score = 0.9
        else:
            brand_score = 0.0
            
        # Công thức Vàng: 50% Ngữ nghĩa AI + 35% Cứng xác Mã + 15% Thương hiệu
        final_conf = (0.50 * ce_score) + (0.35 * heur_score) + (0.15 * brand_score)
        
        final_results.append({
            "id": pid,
            "confidence": round(final_conf, 3),
            "method": f"Unified_Score (H:{heur_score}|CE:{round(ce_score,2)})"
        })
        
    final_results = sorted(final_results, key=lambda x: x['confidence'], reverse=True)
    return final_results[:3]