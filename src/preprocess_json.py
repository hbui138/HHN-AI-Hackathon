import os
import json
import glob
from pathlib import Path

def process_json_file(file_path, output_dir):
    # Read the raw JSON file
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    processed_items = []
    
    # Iterate through items in the JSON array
    for item_wrapper in data.get("Items", []):
        item = item_wrapper.get("ITEM", {})
        
        # Extract basic information
        ext_id = item.get("EXT_PRODUCT_ID", "")
        manufacturer = item.get("MANUFACTNAME", "")
        part_number = item.get("MATNR", "")
        
        # Extract text fields
        descriptions = [d.get("description", "") for d in item.get("DESCRIPTION", [])]
        longtexts = [lt.get("longtext", "") for lt in item.get("LONGTEXT", [])]
        
        # Extract and format attributes
        attributes = []
        for attr in item.get("ATTRIBUTES", []):
            field_name = attr.get("fieldName", "")
            field_value = attr.get("fieldValue", "")
            field_unit = attr.get("fieldUnit", "")
            
            # Combine attribute parts into a single string
            attr_text = f"{field_name} {field_value} {field_unit}".strip()
            attributes.append(attr_text)
            
        # Combine all text into a single document for semantic search embedding
        combined_text_parts = descriptions + longtexts + attributes
        combined_text = " ".join(filter(None, combined_text_parts))
        
        # Append to the processed list
        processed_items.append({
            "id": ext_id,
            "manufacturer": manufacturer,
            "part_number": part_number,
            "combined_text": combined_text
        })
        
    # Determine output file path using the original file name directly
    original_filename = Path(file_path).name
    output_path = Path(output_dir) / original_filename
    
    # Save the processed data
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(processed_items, f, ensure_ascii=False, indent=4)
        
    print(f"Processed: {original_filename} -> {output_path}")

def main():
    # Define relative paths based on project structure (src is sibling to preprocessed_data)
    current_dir = Path(__file__).resolve().parent
    base_dir = current_dir.parent
    
    # Define input and output directories
    # Update 'raw_data_folder' to match the actual name of your unzipped folder
    input_dir = base_dir / "catalogdata_standard_parts"  # Replace with the actual folder name
    output_dir = base_dir / "preprocessed_data/standard_parts"
    
    # Create output directory if it does not exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all JSON files in any subdirectories recursively
    search_pattern = str(input_dir / "**" / "*.json")
    json_files = glob.glob(search_pattern, recursive=True)
    
    if not json_files:
        print(f"No JSON files found in {input_dir}. Please check the folder name.")
        return

    # Process each found JSON file
    for file_path in json_files:
        process_json_file(file_path, output_dir)

if __name__ == "__main__":
    main()