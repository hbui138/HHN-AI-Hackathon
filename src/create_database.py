import os
import glob
import json
import pandas as pd
import chromadb
from chromadb.errors import NotFoundError
from sentence_transformers import SentenceTransformer
from pathlib import Path

def build_database():
    BASE_DIR = Path(__file__).resolve().parent.parent
    data_dir = BASE_DIR / "preprocessed_data"
    finetuned_model_path = str(BASE_DIR / "models" / "finetuned_boie_minilm")
    
    # Use recursive=True and ** to search inside subdirectories
    all_files = glob.glob(os.path.join(data_dir, "**/*.json"), recursive=True)
    
    # Exclude exact_match_dict if it already exists from a previous run
    all_files = [f for f in all_files if "exact_match" not in f]

    merged_data = []

    # 1. Read all files and build unified data structure
    for file_path in all_files:
        filename = os.path.basename(file_path).lower()
        
        # Determine category based on filename
        if "bearings" in filename:
            category = "bearings"
        elif "pneumatics" in filename:
            category = "pneumatics"
        else:
            category = "standard_parts"

        with open(file_path, 'r', encoding='utf-8') as f:
            file_data = json.load(f)
            
            for item in file_data:
                # Extract parts numbers and normalize them
                p_num = item.get("part_number", "")
                a_num = item.get("article_number", "")
                
                searchable_codes = []
                for code in [p_num, a_num]:
                    if code and code.strip():
                        searchable_codes.append(code.strip())
                
                merged_data.append({
                    "id": item.get("id"),
                    "category": category,
                    "manufacturer": item.get("manufacturer", ""),
                    "searchable_codes": searchable_codes,
                    "combined_text": item.get("combined_text", "")
                })

    # Create DataFrame and save as Parquet for fast tabular operations
    if not merged_data:
        print("No data found. Please check your data_dir path and file structure.")
        return

    df_master = pd.DataFrame(merged_data)
    df_master.to_parquet(os.path.join(data_dir, "master_database.parquet"))
    print(f"Master Database saved: {len(df_master)} items.")

    # 2. Build Exact Match Dictionary for O(1) lookup
    exact_match_dict = {}
    for _, row in df_master.iterrows():
        item_id = row['id']
        for code in row['searchable_codes']:
            # Strip spaces and hyphens, convert to lowercase
            clean_code = str(code).lower().replace(" ", "").replace("-", "")
            if clean_code:
                exact_match_dict[clean_code] = item_id

    with open(os.path.join(data_dir, "exact_match_dict.json"), "w", encoding='utf-8') as f:
        json.dump(exact_match_dict, f, ensure_ascii=False)
    print(f"Exact match dictionary saved: {len(exact_match_dict)} unique codes.")

    # 3. Initialize Vector Database (ChromaDB)
    chroma_client = chromadb.PersistentClient(path="chroma_db_finetuned/")
    
    # Catch NotFoundError specifically for ChromaDB
    try:
        chroma_client.delete_collection(name="boie_products")
    except NotFoundError:
        pass 
        
    collection = chroma_client.create_collection(name="boie_products")
    embedding_model = SentenceTransformer(finetuned_model_path)

    # Batch insertion to optimize memory usage
    batch_size = 500
    total_docs = len(df_master)

    print("Starting vector generation. This may take a few minutes...")
    for i in range(0, total_docs, batch_size):
        batch_df = df_master.iloc[i:i+batch_size]
        
        ids = batch_df['id'].astype(str).tolist()
        documents = batch_df['combined_text'].tolist()
        
        # Prepare metadata for fast filtering during search
        metadatas = [
            {
                "manufacturer": str(row['manufacturer']),
                "category": str(row['category'])
            } 
            for _, row in batch_df.iterrows()
        ]
        
        embeddings = embedding_model.encode(documents).tolist()
        
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        print(f"Inserted vectors: {min(i + batch_size, total_docs)} / {total_docs}")

    print("Database build completed successfully.")

if __name__ == "__main__":
    build_database()