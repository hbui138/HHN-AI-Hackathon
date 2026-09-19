import os
import json
import glob
from pathlib import Path

IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.tif', '.tiff', '.webp')

def extract_images(attachments):
    # Keep every picture of the product (photos 'Bild' and technical drawings 'Zeichnung'), skip PDFs / links
    images = []
    for att in attachments or []:
        url = (att.get("fileName") or "").strip()
        mime = (att.get("mimeType") or "").lower()
        if not url or not (mime.startswith("image/") or url.lower().endswith(IMAGE_EXTENSIONS)):
            continue
        kinds = [d.get("description", "") for d in att.get("descriptions", []) if d.get("description")]
        if url not in [img["url"] for img in images]:
            images.append({"url": url, "type": kinds[0] if kinds else ""})
    return images

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
        attribute_list = []
        for attr in item.get("ATTRIBUTES", []):
            field_name = attr.get("fieldName", "")
            field_value = attr.get("fieldValue", "")
            field_unit = attr.get("fieldUnit", "")
            
            # Combine attribute parts into a single string
            attr_text = f"{field_name} {field_value} {field_unit}".strip()
            attributes.append(attr_text)
            attribute_list.append({"name": field_name, "value": field_value, "unit": field_unit})
            
        # Combine all text into a single document for semantic search embedding
        combined_text_parts = descriptions + longtexts + attributes
        combined_text = " ".join(filter(None, combined_text_parts))
        
        # Append to the processed list
        processed_items.append({
            "id": ext_id,
            "manufacturer": manufacturer,
            "part_number": part_number,
            "combined_text": combined_text,
            "description": " ".join(filter(None, descriptions)),
            "longtext": " ".join(filter(None, longtexts)),
            "attributes": attribute_list,
            "images": extract_images(item.get("ATTACHMENTS", [])),
            "link": item.get("LINK", "")
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
    
    # Raw catalog folder -> preprocessed output folder
    sources = {
        "catalogdata_bearings": "preprocessed_data/bearings",
        "catalogdata_standard_parts": "preprocessed_data/standard_parts",
    }
    for input_name, output_name in sources.items():
        input_dir = base_dir / input_name
        output_dir = base_dir / output_name
        output_dir.mkdir(parents=True, exist_ok=True)

        # Find all JSON files in any subdirectories recursively
        json_files = glob.glob(str(input_dir / "**" / "*.json"), recursive=True)
        if not json_files:
            print(f"No JSON files found in {input_dir}. Please check the folder name.")
            continue

        for file_path in json_files:
            process_json_file(file_path, output_dir)

if __name__ == "__main__":
    main()