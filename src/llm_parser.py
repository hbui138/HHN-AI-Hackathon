import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
import pandas as pd

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY"),
)

# 1. Load Data and Extract Whitelist ONE TIME globally to save compute
BASE_DIR = Path(__file__).resolve().parent.parent
master_db_path = BASE_DIR / "preprocessed_data" / "master_database.parquet"

try:
    df_master = pd.read_parquet(master_db_path)
    # Get unique manufacturers, clean them, and sort alphabetically
    MANUFACTURERS = sorted(list(set([str(m).strip() for m in df_master['manufacturer'].dropna() if str(m).strip()])))
    # Create a comma-separated string of valid brands
    VALID_BRANDS_STRING = ", ".join(MANUFACTURERS)
except Exception as e:
    print(f"Failed to load manufacturers: {e}")
    VALID_BRANDS_STRING = "SKF, FAG, INA, NORELEM" # Fallback just in case

# Persistent cache: identical queries are never sent to the API twice (cheaper, and makes
# evaluation runs reproducible so scoring changes can be compared fairly)
CACHE_PATH = BASE_DIR / "preprocessed_data" / "llm_parse_cache.json"
try:
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        _parse_cache = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    _parse_cache = {}

def parse_query(query: str) -> dict:
    if query in _parse_cache:
        return dict(_parse_cache[query])
    result = _parse_query_llm(query)
    # Only cache successful parses so transient API errors are retried next run
    if not result.get("_error"):
        _parse_cache[query] = result
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(_parse_cache, f, ensure_ascii=False, indent=1)
    return {k: v for k, v in result.items() if k != "_error"}

def _parse_query_llm(query: str) -> dict:
    prompt = f"""
    You are an expert data extractor for a mechanical engineering B2B distributor.
    Extract information from the user query into a strict JSON object with keys: "Manufacturer", "Part_Number", "Attributes".
    
    RULES:
    1. "Manufacturer": MUST be one of the brands from this exact valid list: [{VALID_BRANDS_STRING}]. 
       If the text contains words like 'Edelstahl' (Stainless steel), 'Rastbolzen' (Plunger), or 'Kugellager' (Bearing), DO NOT classify them as manufacturers. If no brand from the list is present, return null.
    2. "Part_Number": The alphanumeric part code (e.g., 6204-2Z, 06090-05x10). If none, return null.
    3. "Attributes": Any other technical specifications (dimensions, materials, etc.). Return as a single string. If none, return null.
    
    User query: "{query}"
    """
    
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You output strict JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" },
            temperature=0.0 # Set to 0.0 for maximum strictness in constrained extraction
        )
        
        extracted_data = json.loads(response.choices[0].message.content)
        return extracted_data
        
    except Exception as e:
        print(f"LLM Parsing failed: {e}")
        return {"Manufacturer": None, "Part_Number": None, "Attributes": None, "_error": True}

# Quick test execution
if __name__ == "__main__":
    test_queries = [
        "Kugellager (SKF) 6016 2Z",
        "Kurvenrolle KR 47 PP-B Fabrikat: SKF",
        "suche ein Rillenkugellager von FAG, nummer 6204 mit gummidichtung",
        "Anschlagschraube GN 251-M4-20-AK    Ganter"
    ]
    
    for q in test_queries:
        print(f"Original: {q}")
        print(f"Parsed: {json.dumps(parse_query(q), indent=2)}\n")