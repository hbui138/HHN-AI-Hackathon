import pandas as pd
import json
import re
import chromadb
from sentence_transformers import SentenceTransformer
from rapidfuzz import process, fuzz
import warnings
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

warnings.filterwarnings('ignore')

# 1. Define paths and load resources
BASE_DIR = Path(__file__).resolve().parent.parent

dict_path = BASE_DIR / "preprocessed_data" / "exact_match_dict.json"
with open(dict_path, "r", encoding="utf-8") as f:
    exact_match_dict = json.load(f)

all_clean_codes = list(exact_match_dict.keys())

# Dynamically extract unique manufacturers from the master database
master_db_path = BASE_DIR / "preprocessed_data" / "master_database.parquet"
df_master = pd.read_parquet(master_db_path)

# Filter out empty or null values to create a clean whitelist
MANUFACTURERS = [str(m).strip() for m in df_master['manufacturer'].dropna().unique() if str(m).strip()]

print("All manufacturers loaded for entity extraction:", MANUFACTURERS)

# 2. Initialize ChromaDB and Embedding Model
chroma_path = "chroma_db"
chroma_client = chromadb.PersistentClient(path=str(chroma_path))
collection = chroma_client.get_collection(name="boie_products")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

def extract_entities(query):
    # Extract brand dynamically using the generated whitelist
    detected_brand = None
    query_upper = query.upper()
    
    for brand in MANUFACTURERS:
        if brand.upper() in query_upper:
            detected_brand = brand
            break
            
    return detected_brand, None

def extract_potential_codes(query):
    tokens = re.findall(r'[a-zA-Z0-9]+', query)
    codes_to_test = set()
    
    for i in range(len(tokens) - 2):
        codes_to_test.add((tokens[i] + tokens[i+1] + tokens[i+2]).lower())
        
    for i in range(len(tokens) - 1):
        codes_to_test.add((tokens[i] + tokens[i+1]).lower())
        
    for token in tokens:
        codes_to_test.add(token.lower())
        
    # Always prioritize longer strings during testing
    return sorted(list(codes_to_test), key=len, reverse=True)

def hybrid_search(query, expected_category=None):
    brand, _ = extract_entities(query)
    potential_codes = extract_potential_codes(query)
    
    # VERTICAL EVALUATION: Prioritize longer tokens. 
    # Check Exact, Prefix, and Fuzzy for a long token BEFORE testing shorter tokens.
    for code in potential_codes:
        if len(code) < 3: 
            continue
            
        # 1. Exact Match
        if code in exact_match_dict:
            return exact_match_dict[code], 1.0, "Exact_Match"
            
        # Safeguard: Only allow Prefix/Fuzzy matching if the token contains at least one number.
        # This prevents pure dictionary words (e.g., 'kugellager', 'und') from falsely matching part numbers.
        has_digit = any(char.isdigit() for char in code)
            
        if has_digit and len(code) >= 5:
            # 2. Prefix Match (Solves missing suffixes like user: '6262rs' -> DB: '6262rsh')
            prefix_matches = [db_code for db_code in all_clean_codes if db_code.startswith(code)]
            if prefix_matches:
                # If multiple exist, pick the shortest difference
                best_prefix = sorted(prefix_matches, key=len)[0]
                return exact_match_dict[best_prefix], 0.9, "Prefix_Match"
                
            # 3. Fuzzy Match (Solves typos like user: '60042zr' -> DB: '60042z')
            best_match = process.extractOne(
                code, 
                all_clean_codes, 
                scorer=fuzz.ratio, 
                score_cutoff=85
            )
            if best_match:
                matched_code, score, _ = best_match
                return exact_match_dict[matched_code], round(score / 100.0, 2), "Fuzzy_Match"

    # 4. Semantic Search Fallback (Vector Search)
    query_vector = embedding_model.encode([query]).tolist()
    search_kwargs = {
        "query_embeddings": query_vector,
        "n_results": 1
    }
    
    # Filter conditionally based on detected brand or expected category
    where_conditions = {}
    if brand:
        where_conditions["manufacturer"] = brand
    if expected_category:
        where_conditions["category"] = expected_category
        
    if len(where_conditions) == 1:
        search_kwargs["where"] = where_conditions
    elif len(where_conditions) > 1:
        search_kwargs["where"] = {"$and": [{"manufacturer": brand}, {"category": expected_category}]}
        
    results = collection.query(**search_kwargs)
    
    if results['ids'] and results['ids'][0]:
        predicted_id = results['ids'][0][0]
        distance = results['distances'][0][0]
        confidence = max(0.0, 1.0 - (distance / 2.0))
        
        if brand:
            confidence = min(0.95, confidence + 0.2)
            
        return predicted_id, round(confidence, 2), "Semantic_Search"
        
    return None, 0.0, "Not_Found"

def main():
    file_name = "customerinquiry_bearings.csv"
    inquiry_file = BASE_DIR / "customerinquiry" / file_name
    
    expected_category = None
    if "bearings" in file_name:
        expected_category = "bearings"
    elif "pneumatics" in file_name:
        expected_category = "pneumatics"
    elif "standard_parts" in file_name:
        expected_category = "standard_parts"
    
    try:
        df_inquiry = pd.read_csv(inquiry_file, on_bad_lines='skip', engine='python')
    except FileNotFoundError:
        print(f"Cannot find {inquiry_file}. Please check the path.")
        return

    predictions = []
    confidences = []
    methods = []

    print(f"Processing inquiries for category: {expected_category.upper()}...")
    
    for index, row in tqdm(df_inquiry.iterrows(), total=df_inquiry.shape[0], desc="Matching Inquiries"):
        query = str(row['CustomerArticleDescription'])
        pred_id, conf, method = hybrid_search(query, expected_category)
        
        predictions.append(pred_id)
        confidences.append(conf)
        methods.append(method)
        
    df_inquiry['Predicted_ID'] = predictions
    df_inquiry['Confidence'] = confidences
    df_inquiry['Search_Method'] = methods
    
    # Robust numeric conversion to bypass Pandas .0 float issues and NaNs
    df_inquiry['articleid_matched'] = pd.to_numeric(df_inquiry['articleid_matched'], errors='coerce').fillna(0).astype(int).astype(str)
    df_inquiry['Predicted_ID'] = pd.to_numeric(df_inquiry['Predicted_ID'], errors='coerce').fillna(0).astype(int).astype(str)
    
    df_inquiry['Is_Correct'] = df_inquiry['articleid_matched'] == df_inquiry['Predicted_ID']
    
    accuracy = df_inquiry['Is_Correct'].mean() * 100
    exact_match_count = (df_inquiry['Search_Method'] == 'Exact_Match').sum()
    semantic_count = (df_inquiry['Search_Method'] == 'Semantic_Search').sum()
    
    print("\n--- EVALUATION RESULTS ---")
    print(f"Total Inquiries: {len(df_inquiry)}")
    print(f"Overall Accuracy: {accuracy:.2f}%")
    print(f"Matched by Regex/Exact: {exact_match_count}")
    print(f"Matched by Semantic AI: {semantic_count}")
    
    results_dir = BASE_DIR / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = results_dir / f"evaluation_results_{timestamp}.csv"
    
    df_inquiry.to_csv(output_file, index=False)
    print(f"\nDetailed results saved to: {output_file}")

if __name__ == "__main__":
    main()