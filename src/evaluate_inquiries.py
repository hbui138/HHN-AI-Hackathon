# File: src/evaluate_inquiries.py (Phiên bản mới nhất - Offline, Cross-Encoder)
import pandas as pd
import json
import re
import chromadb
from sentence_transformers import SentenceTransformer, CrossEncoder
from rapidfuzz import process, fuzz
import warnings
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

warnings.filterwarnings('ignore')

BASE_DIR = Path(__file__).resolve().parent.parent

# 1. Tải tài nguyên
with open(BASE_DIR / "preprocessed_data" / "exact_match_dict.json", "r", encoding="utf-8") as f:
    exact_match_dict = json.load(f)
all_clean_codes = list(exact_match_dict.keys())

df_master = pd.read_parquet(BASE_DIR / "preprocessed_data" / "master_database.parquet")
MANUFACTURERS = [str(m).strip() for m in df_master['manufacturer'].dropna().unique() if str(m).strip()]
df_master_dict = df_master.set_index('id').to_dict('index') # Tạo dictionary để lấy combined_text nhanh

chroma_client = chromadb.PersistentClient(path=str(BASE_DIR / "chroma_db"))
collection = chroma_client.get_collection(name="boie_products")

# NẠP MODEL ĐÃ FINETUNE ĐỂ TÌM KIẾM VECTOR
# (Nếu bạn chưa nhúng lại ChromaDB bằng model finetune, hãy dùng model gốc tạm)
embedding_model = SentenceTransformer('all-MiniLM-L6-v2') 

# VŨ KHÍ BÍ MẬT: NẠP CROSS-ENCODER ĐỂ XẾP HẠNG LẠI (Chạy local, cực chính xác)
cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

def extract_entities(query):
    detected_brand = None
    query_upper = query.upper()
    for brand in MANUFACTURERS:
        if brand.upper() in query_upper:
            detected_brand = brand
            break
    return detected_brand

def hybrid_search(query):
    brand = extract_entities(query)
    tokens = re.findall(r'[a-zA-Z0-9]+', query)
    potential_codes = set()
    
    # Tạo tổ hợp 2, 3 từ và đơn từ
    for i in range(len(tokens) - 2): potential_codes.add((tokens[i] + tokens[i+1] + tokens[i+2]).lower())
    for i in range(len(tokens) - 1): potential_codes.add((tokens[i] + tokens[i+1]).lower())
    for t in tokens: potential_codes.add(t.lower())
    
    potential_codes = sorted(list(potential_codes), key=len, reverse=True)
    
    for code in potential_codes:
        if len(code) < 3: continue
        # 1. Exact Match
        if code in exact_match_dict: return exact_match_dict[code], 1.0, "Exact_Match"
        # 2 & 3: Prefix/Fuzzy chặn đầu
        has_digit = any(char.isdigit() for char in code)
        if has_digit and len(code) >= 5:
            prefix_matches = [c for c in all_clean_codes if c.startswith(code)]
            if prefix_matches: return exact_match_dict[sorted(prefix_matches, key=len)[0]], 0.9, "Prefix_Match"
            narrow_pool = [c for c in all_clean_codes if c.startswith(code[:2]) and abs(len(c) - len(code)) <= 3]
            if narrow_pool:
                best = process.extractOne(code, narrow_pool, scorer=fuzz.ratio, score_cutoff=85)
                if best: return exact_match_dict[best[0]], round(best[1] / 100.0, 2), "Fuzzy_Match"

    # 4. TRUY XUẤT THÔ (Retrieval - Bi-encoder)
    query_vector = embedding_model.encode([query]).tolist()
    search_kwargs = {"query_embeddings": query_vector, "n_results": 5} # Lấy ra 5 kết quả
    if brand: search_kwargs["where"] = {"manufacturer": brand}
        
    results = collection.query(**search_kwargs)
    
    if results['ids'] and results['ids'][0]:
        top_5_ids = results['ids'][0]
        
        # 5. XẾP HẠNG LẠI TINH TẾ (Re-ranking - Cross-encoder)
        cross_inp = []
        for pid in top_5_ids:
            # Lấy text mô tả sản phẩm tương ứng trong Parquet
            doc_text = df_master_dict[pid]['combined_text']
            cross_inp.append([query, doc_text])
            
        # Cross-encoder đánh giá cẩn thận từng cặp
        cross_scores = cross_encoder.predict(cross_inp)
        
        # Tìm index của sản phẩm có điểm cao nhất
        best_idx = cross_scores.argmax()
        predicted_id = top_5_ids[best_idx]
        
        # Normalize score (Cross-encoder scores are logits, roughly -10 to +10. We normalize to 0-1)
        import math
        logit = cross_scores[best_idx]
        confidence = 1 / (1 + math.exp(-logit))
        
        return predicted_id, round(confidence, 2), "CrossEncoder_Reranked"
        
    return None, 0.0, "Not_Found"

def main():
    # CHỈ ĐỌC TẬP UNSEEN TEST (20% chưa train)
    inquiry_file = BASE_DIR / "preprocessed_data" / "unseen_test_data.csv"
    try:
        df_test = pd.read_csv(inquiry_file)
    except:
        print("Không tìm thấy file unseen_test_data.csv. Hãy chạy get_split.py trước.")
        return

    predictions, confidences, methods = [], [], []

    print(f"Đang kiểm thử trên {len(df_test)} câu chưa bao giờ train...")
    for idx, row in tqdm(df_test.iterrows(), total=len(df_test)):
        q = str(row['CustomerArticleDescription'])
        pred, conf, met = hybrid_search(q)
        predictions.append(pred)
        confidences.append(conf)
        methods.append(met)
        
    df_test['Predicted_ID'] = predictions
    df_test['Confidence'] = confidences
    df_test['Search_Method'] = methods
    
    df_test['Is_Correct'] = df_test['articleid_matched'].astype(str) == df_test['Predicted_ID'].astype(str)
    
    print("\n--- KẾT QUẢ ĐÁNH GIÁ (TEST SET) ---")
    print(f"Độ chính xác: {df_test['Is_Correct'].mean() * 100:.2f}%")
    print(df_test['Search_Method'].value_counts())

    # Calculate business metrics based on Confidence Threshold
    THRESHOLD = 0.85 # You can tune this between 0.80 and 0.95
    
    df_test['Routing'] = df_test['Confidence'].apply(
        lambda x: 'Auto-Matched' if x >= THRESHOLD else 'Manual_Review'
    )
    
    auto_matched_df = df_test[df_test['Routing'] == 'Auto-Matched']
    manual_review_df = df_test[df_test['Routing'] == 'Manual_Review']
    
    automation_rate = (len(auto_matched_df) / len(df_test)) * 100
    
    # Precision: Out of all items the AI confidently auto-matched, how many were actually correct?
    if len(auto_matched_df) > 0:
        auto_match_precision = auto_matched_df['Is_Correct'].mean() * 100
    else:
        auto_match_precision = 0.0
        
    print("\n=== BUSINESS EVALUATION METRICS ===")
    print(f"Total Test Inquiries: {len(df_test)}")
    print(f"1. Automation Rate (AI Confidence >= {THRESHOLD}): {automation_rate:.1f}%")
    print(f"2. Auto-Match Precision (Safety): {auto_match_precision:.2f}%")
    print(f"3. Sent to Manual Review (Human-in-the-loop): {len(manual_review_df)} items")

if __name__ == "__main__":
    main()