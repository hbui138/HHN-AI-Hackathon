import os
import sys
import glob
import json
import pandas as pd
import chromadb
from chromadb.errors import NotFoundError
from sentence_transformers import SentenceTransformer
from pathlib import Path
import normalization
from normalization import normalize_code, strip_supplier_prefix, detect_supplier_prefixes

def build_supplier_prefixes(df_master):
    first_codes = [codes[0] if len(codes) else '' for codes in df_master['searchable_codes']]
    detected = detect_supplier_prefixes(df_master['manufacturer'], first_codes)
    with open(normalization.SUPPLIER_PREFIX_PATH, "w", encoding="utf-8") as f:
        json.dump(detected, f, ensure_ascii=False, indent=2)
    normalization.SUPPLIER_CODE_PREFIXES.clear()
    normalization.SUPPLIER_CODE_PREFIXES.update(detected)
    print(f"Detected supplier prefixes: {detected}")

def build_exact_match_dict(df_master, data_dir):
    build_supplier_prefixes(df_master)
    # One normalized code can belong to several products (variants), so keep a list of ids
    exact_match_dict = {}
    for item_id, codes, manufacturer in zip(df_master['id'], df_master['searchable_codes'], df_master['manufacturer']):
        # Also index the code without Boie's supplier prefix (FAG '2026219-2Z' -> '6219-2Z')
        aliases = [strip_supplier_prefix(c, manufacturer) for c in codes]
        for code in list(codes) + [a for a in aliases if a]:
            clean_code = normalize_code(code)
            if clean_code:
                ids = exact_match_dict.setdefault(clean_code, [])
                if item_id not in ids:
                    ids.append(item_id)

    with open(os.path.join(data_dir, "exact_match_dict.json"), "w", encoding='utf-8') as f:
        json.dump(exact_match_dict, f, ensure_ascii=False)
    shared = sum(1 for ids in exact_match_dict.values() if len(ids) > 1)
    print(f"Exact match dictionary saved: {len(exact_match_dict)} unique codes ({shared} shared by >1 product).")

def rebuild_exact_match_dict_only():
    data_dir = Path(__file__).resolve().parent.parent / "preprocessed_data"
    df_master = pd.read_parquet(data_dir / "master_database.parquet")
    build_exact_match_dict(df_master, data_dir)

def build_database(skip_vectors=False):
    BASE_DIR = Path(__file__).resolve().parent.parent
    data_dir = BASE_DIR / "preprocessed_data"
    finetuned_model_path = str(BASE_DIR / "models" / "finetuned_boie_minilm")
    
    # Use recursive=True and ** to search inside subdirectories
    all_files = glob.glob(os.path.join(data_dir, "**/*.json"), recursive=True)
    
    # Catalog data lives in category subfolders; root-level JSONs are lookup tables (exact_match_dict, crossref)
    all_files = [f for f in all_files if Path(f).parent != Path(data_dir)]

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
                    if normalize_code(code):
                        searchable_codes.append(str(code).strip())
                
                merged_data.append({
                    "id": item.get("id"),
                    "category": category,
                    "manufacturer": item.get("manufacturer", ""),
                    "searchable_codes": searchable_codes,
                    "combined_text": item.get("combined_text", ""),
                    # Display-only fields (not embedded): full product info for results / UI
                    "part_number": p_num,
                    "article_number": a_num,
                    "description": item.get("description", ""),
                    "longtext": item.get("longtext", ""),
                    "attributes": item.get("attributes", []),
                    "images": item.get("images", []),
                    "link": item.get("link", ""),
                })

    # Create DataFrame and save as Parquet for fast tabular operations
    if not merged_data:
        print("No data found. Please check your data_dir path and file structure.")
        return

    df_master = pd.DataFrame(merged_data)
    df_master.to_parquet(os.path.join(data_dir, "master_database.parquet"))
    print(f"Master Database saved: {len(df_master)} items.")

    # 2. Build Exact Match Dictionary for O(1) lookup
    build_exact_match_dict(df_master, data_dir)

    # --skip-vectors: embeddings only depend on combined_text, so metadata-only changes need no re-embedding
    if skip_vectors:
        print("Skipping vector generation (--skip-vectors).")
        return

    # 3. Initialize Vector Database (ChromaDB)
    chroma_client = chromadb.PersistentClient(path=str(BASE_DIR / "chroma_db_finetuned"))
    
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
    # --dict-only: rebuild exact_match_dict.json from the existing parquet without re-embedding
    if "--dict-only" in sys.argv:
        rebuild_exact_match_dict_only()
    else:
        build_database(skip_vectors="--skip-vectors" in sys.argv)