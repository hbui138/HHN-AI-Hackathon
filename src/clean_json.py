import os
import glob
import json

def clean_json_files():
    # Construct absolute path to the preprocessed_data folder
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(current_dir, "..", "preprocessed_data")
    
    # Search recursively for all json files
    all_files = glob.glob(os.path.join(data_dir, "**/*.json"), recursive=True)
    
    total_removed = 0
    total_files_modified = 0

    print("Starting JSON cleanup process...")
    
    for file_path in all_files:
        # Skip the exact_match_dict.json if it exists from previous runs
        if "exact_match" in file_path:
            continue
            
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print(f"Error reading {file_path}. Skipping.")
                continue
        
        if not isinstance(data, list):
            continue

        original_length = len(data)
        
        # Keep only items where 'id' exists and is not an empty/invalid string
        valid_items = []
        for item in data:
            item_id = item.get("id")
            if item_id is not None and str(item_id).strip() not in ("", "None", "nan", "NaN"):
                valid_items.append(item)
                
        removed_count = original_length - len(valid_items)
        
        # If any items were removed, overwrite the file with the clean data
        if removed_count > 0:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(valid_items, f, ensure_ascii=False, indent=4)
            
            filename = os.path.basename(file_path)
            print(f"Removed {removed_count} invalid items from {filename}")
            
            total_removed += removed_count
            total_files_modified += 1

    print("-" * 30)
    print("Cleanup Complete!")
    print(f"Total invalid items removed: {total_removed}")
    print(f"Total files modified: {total_files_modified}")

if __name__ == "__main__":
    clean_json_files()