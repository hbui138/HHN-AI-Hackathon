import pandas as pd
import json
from pathlib import Path

def process_pneumatics_csv(input_csv, output_json):
    # Read the CSV file using pandas
    try:
        df = pd.read_csv(input_csv, engine='python', on_bad_lines='skip')
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return
            
    processed_items = []
    
    # Iterate through each row in the dataframe
    for _, row in df.iterrows():
        # Extract basic information and convert to string
        ext_id = str(row.get('articleid', ''))
        manufacturer = str(row.get('manufacturer', ''))
        part_number = str(row.get('manufacturer_articlenumber', ''))
        article_number = str(row.get('articlenumber', ''))
        
        # Extract text fields
        short_desc = str(row.get('article_shortdescription', ''))
        long_desc = str(row.get('article_longdescription', ''))
        note = str(row.get('article_note', ''))
        
        # Clean up 'nan' strings that pandas might generate for empty columns
        text_parts = [
            article_number if article_number != 'nan' else '', # Add to text for embedding
            part_number if part_number != 'nan' else '',
            short_desc if short_desc != 'nan' else '',
            long_desc if long_desc != 'nan' else '',
            note if note != 'nan' else ''
        ]
        
        # Combine all text components into a single document
        combined_text = " ".join(filter(None, text_parts)).strip()
        
        # Append to the processed list using the unified schema
        processed_items.append({
            "id": ext_id,
            "manufacturer": manufacturer,
            "article_number": article_number, # Included in output
            "part_number": part_number,
            "combined_text": combined_text
        })
            
    # Save the processed data into a JSON file
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(processed_items, f, ensure_ascii=False, indent=4)
            
    print(f"Processed CSV and saved to {output_json}")

def main():
    # Define paths
    current_dir = Path(__file__).resolve().parent
    base_dir = current_dir.parent
    
    input_csv = base_dir / "articledata_pneumatics" / "articledata_pneumatics.csv"
    output_dir = base_dir / "preprocessed_data/pneumatics"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_json = output_dir / "articledata_pneumatics.json"
    
    # Execute the processing function
    if input_csv.exists():
        process_pneumatics_csv(input_csv, output_json)
    else:
        print(f"CSV file not found at: {input_csv}")

if __name__ == "__main__":
    main()