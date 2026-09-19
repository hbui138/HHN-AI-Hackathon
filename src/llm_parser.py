import os
import json
from openai import OpenAI

# Initialize the client. Make sure to set your OPENAI_API_KEY environment variable.
# For local LLMs (like LM Studio or Ollama), change the base_url.
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    # base_url="http://localhost:1234/v1" # Uncomment if using local LLM
)

def parse_query(query: str) -> dict:
    """
    Extracts mechanical engineering entities from a messy user query.
    Returns a normalized JSON dictionary.
    """
    prompt = f"""
    You are an expert mechanical engineering assistant.
    Extract the following information from the user query.
    Return ONLY a valid JSON object with these exact keys:
    - "Manufacturer": The brand or manufacturer name (e.g., SKF, FAG, Landefeld). If none, null.
    - "Part_Number": The alphanumeric part code (e.g., 6204-2Z, KR47PPB). Strip out filler words. If none, null.
    - "Attributes": Any other technical specifications (e.g., size, material). If none, null.
    
    User query: "{query}"
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", # Extremely fast and capable of JSON formatting
            messages=[
                {"role": "system", "content": "You output strict JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" },
            temperature=0.1 # Keep it low for deterministic extraction
        )
        
        # Parse the string response into a Python dictionary
        extracted_data = json.loads(response.choices[0].message.content)
        return extracted_data
        
    except Exception as e:
        print(f"LLM Parsing failed: {e}")
        # Fallback dictionary in case of API failure or timeout
        return {
            "Manufacturer": None,
            "Part_Number": None,
            "Attributes": None
        }

# Quick test execution
if __name__ == "__main__":
    test_queries = [
        "Kugellager (SKF) 6016 2Z",
        "Kurvenrolle KR 47 PP-B Fabrikat: SKF",
        "suche ein Rillenkugellager von FAG, nummer 6204 mit gummidichtung",
        "Lager 1313 K/C3 + Spannhülse"
    ]
    
    for q in test_queries:
        print(f"Original: {q}")
        print(f"Parsed: {json.dumps(parse_query(q), indent=2)}\n")