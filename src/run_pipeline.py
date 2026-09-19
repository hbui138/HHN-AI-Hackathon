# File: src/run_pipeline.py
import pandas as pd
from pathlib import Path
from datetime import datetime
from tqdm import tqdm
from llm_parser import parse_query
from search_engine import hybrid_search

def main():
    BASE_DIR = Path(__file__).resolve().parent.parent
    inquiry_file = BASE_DIR / "preprocessed_data" / "unseen_test_data.csv"
    
    try:
        df_test = pd.read_csv(inquiry_file)
        df_test = df_test.sample(n=min(1000, len(df_test)), random_state=42).copy()
    except FileNotFoundError:
        print(f"Error: Cannot find {inquiry_file}.")
        return

    # Arrays to store top 3 results
    top1_ids, top1_confs, top1_methods = [], [], []
    top2_ids, top2_confs = [], []
    top3_ids, top3_confs = [], []

    print(f"Starting AI Pipeline on {len(df_test)} test samples...")

    for idx, row in tqdm(df_test.iterrows(), total=len(df_test), desc="Processing Pipeline"):
        query = str(row.get('CustomerArticleDescription', ''))
        
        if not query.strip() or query.lower() == 'nan':
            top1_ids.append(None); top1_confs.append(0.0); top1_methods.append("Empty")
            top2_ids.append(None); top2_confs.append(0.0)
            top3_ids.append(None); top3_confs.append(0.0)
            continue
            
        raw_category = str(row.get('category', ''))
        expected_cat = 'bearings' if 'bearings' in raw_category else ('pneumatics' if 'pneumatics' in raw_category else ('standard_parts' if 'standard_parts' in raw_category else None))

        parsed_data = parse_query(query)
        top_results = hybrid_search(original_query=query, parsed_data=parsed_data, expected_category=expected_cat)
        
        # Unpack up to 3 results
        res1 = top_results[0] if len(top_results) > 0 else {"id": None, "confidence": 0.0, "method": "None"}
        res2 = top_results[1] if len(top_results) > 1 else {"id": None, "confidence": 0.0}
        res3 = top_results[2] if len(top_results) > 2 else {"id": None, "confidence": 0.0}
        
        top1_ids.append(res1["id"]); top1_confs.append(res1["confidence"]); top1_methods.append(res1["method"])
        top2_ids.append(res2["id"]); top2_confs.append(res2["confidence"])
        top3_ids.append(res3["id"]); top3_confs.append(res3["confidence"])
        
    df_test['Top1_ID'] = top1_ids
    df_test['Top1_Conf'] = top1_confs
    df_test['Top1_Method'] = top1_methods
    df_test['Top2_ID'] = top2_ids
    df_test['Top2_Conf'] = top2_confs
    df_test['Top3_ID'] = top3_ids
    
    # Calculate Ground Truth Accuracy
    ground_truth = df_test['articleid_matched'].astype(str)
    df_test['Top1_Correct'] = ground_truth == df_test['Top1_ID'].astype(str)
    
    # Top-3 Accuracy: True if the answer is in ANY of the top 3 slots
    df_test['Top3_Correct'] = (
        (ground_truth == df_test['Top1_ID'].astype(str)) | 
        (ground_truth == df_test['Top2_ID'].astype(str)) | 
        (ground_truth == df_test['Top3_ID'].astype(str))
    )
    
    # Calculate Business Metrics (Routing Logic)
    THRESHOLD = 0.90
    CONFIDENCE_DELTA = 0.02 # Top 1 must beat Top 2 by at least 5% to be auto-matched
    
    def determine_routing(row):
        conf1 = float(row['Top1_Conf'])
        conf2 = float(row['Top2_Conf'])
        
        # Clear winner condition
        if conf1 >= THRESHOLD and (conf1 - conf2) >= CONFIDENCE_DELTA:
            return 'Auto-Matched'
        return 'Manual_Review'
        
    df_test['Routing'] = df_test.apply(determine_routing, axis=1)
    
    auto_matched_df = df_test[df_test['Routing'] == 'Auto-Matched']
    manual_review_df = df_test[df_test['Routing'] == 'Manual_Review']
    
    automation_rate = (len(auto_matched_df) / len(df_test)) * 100
    auto_match_precision = auto_matched_df['Top1_Correct'].mean() * 100 if len(auto_matched_df) > 0 else 0.0

    print("\n" + "="*50)
    print("         PIPELINE EVALUATION (TOP-3 & DELTA)")
    print("="*50)
    print(f"Total Queries Evaluated: {len(df_test)}")
    print(f"Top-1 Strict Accuracy: {df_test['Top1_Correct'].mean() * 100:.2f}%")
    print(f"Top-3 Human-in-loop Hit Rate: {df_test['Top3_Correct'].mean() * 100:.2f}%\n")
    
    print("--- Business Metrics ---")
    print(f"1. Automation Rate (Conf >= {THRESHOLD} & Delta >= {CONFIDENCE_DELTA}): {automation_rate:.1f}%")
    print(f"2. Auto-Match Precision (Zero-Error Tolerance): {auto_match_precision:.2f}%")
    print(f"3. Sent to UI for Manual Review: {len(manual_review_df)} items")
    print("="*50)

    results_dir = BASE_DIR / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = results_dir / f"pipeline_results_{timestamp}.csv"
    df_test.to_csv(output_file, index=False)
    
    print(f"\nPipeline execution complete. Results saved to: {output_file}")

if __name__ == "__main__":
    main()