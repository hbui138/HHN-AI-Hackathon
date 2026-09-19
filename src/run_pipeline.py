# File: src/run_pipeline.py
import json
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from tqdm import tqdm
from llm_parser import parse_query
from search_engine import hybrid_search, df_master_dict
from normalization import normalize_category

# Routing Logic: Top 1 must reach THRESHOLD and beat Top 2 by at least CONFIDENCE_DELTA to be auto-matched
THRESHOLD = 0.90
CONFIDENCE_DELTA = 0.02

PRODUCT_FIELDS = ["category", "manufacturer", "part_number", "article_number", "searchable_codes",
                  "description", "longtext", "attributes", "images", "link"]


def to_jsonable(value):
    # Parquet returns numpy arrays / numpy scalars for nested columns
    if isinstance(value, np.ndarray):
        return [to_jsonable(v) for v in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, np.generic):
        return value.item()
    return value


def product_info(product_id):
    """Full product record for the result file (label and predictions)."""
    if product_id is None:
        return None
    record = df_master_dict.get(str(product_id))
    if record is None:
        return {"id": str(product_id), "found_in_database": False}
    info = {"id": str(product_id)}
    info.update({field: to_jsonable(record.get(field)) for field in PRODUCT_FIELDS})
    return info


def determine_routing(top_results):
    conf1 = top_results[0]["confidence"] if len(top_results) > 0 else 0.0
    conf2 = top_results[1]["confidence"] if len(top_results) > 1 else 0.0
    # Clear winner condition
    if conf1 >= THRESHOLD and (conf1 - conf2) >= CONFIDENCE_DELTA:
        return "Auto-Matched"
    return "Manual_Review"


def percent(part, total):
    return round(part / total * 100, 2) if total else 0.0


def compute_metrics(records):
    total = len(records)
    auto = [r for r in records if r["routing"] == "Auto-Matched"]
    manual = [r for r in records if r["routing"] == "Manual_Review"]
    return {
        "total_queries": total,
        "top1_accuracy": percent(sum(r["top1_correct"] for r in records), total),
        "top3_accuracy": percent(sum(r["top3_correct"] for r in records), total),
        "automation_rate": percent(len(auto), total),
        "auto_match_precision": percent(sum(r["top1_correct"] for r in auto), len(auto)),
        "auto_matched": len(auto),
        "auto_matched_wrong": sum(not r["top1_correct"] for r in auto),
        "manual_review": len(manual),
        "manual_review_top3_hit_rate": percent(sum(r["top3_correct"] for r in manual), len(manual)),
    }


def main():
    # Usage: python run_pipeline.py [n_samples] [--seed N]
    # --seed only changes WHICH rows of the unseen test set are drawn (the train/test split stays fixed)
    parser = argparse.ArgumentParser()
    parser.add_argument("n_samples", nargs="?", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    BASE_DIR = Path(__file__).resolve().parent.parent
    inquiry_file = BASE_DIR / "preprocessed_data" / "unseen_test_data.csv"

    try:
        df_test = pd.read_csv(inquiry_file)
        df_test = df_test.sample(n=min(args.n_samples, len(df_test)), random_state=args.seed).copy()
    except FileNotFoundError:
        print(f"Error: Cannot find {inquiry_file}.")
        return

    print(f"Starting AI Pipeline on {len(df_test)} test samples...")

    records = []
    for _, row in tqdm(df_test.iterrows(), total=len(df_test), desc="Processing Pipeline"):
        query = str(row.get('CustomerArticleDescription', ''))
        label_id = str(row['articleid_matched'])
        expected_cat = normalize_category(row.get('category', ''))

        if not query.strip() or query.lower() == 'nan':
            parsed_data, top_results = None, []
        else:
            parsed_data = parse_query(query)
            top_results = hybrid_search(original_query=query, parsed_data=parsed_data, expected_category=expected_cat)
        top_results = [r for r in top_results if r.get("id") is not None][:3]

        predicted_ids = [str(r["id"]) for r in top_results]
        records.append({
            "query": query,
            "category": expected_cat,
            "source_file": row.get('category', ''),
            "parsed_query": parsed_data,
            "routing": determine_routing(top_results),
            "top1_correct": bool(predicted_ids[:1] == [label_id]),
            "top3_correct": label_id in predicted_ids,
            "label_rank": predicted_ids.index(label_id) + 1 if label_id in predicted_ids else None,
            "attribute_rules_fired": top_results[0].get("attribute_rules", {}) if top_results else {},
            "confidence_delta": round(top_results[0]["confidence"] - (top_results[1]["confidence"] if len(top_results) > 1 else 0.0), 3) if top_results else None,
            "label": product_info(label_id),
            "predictions": [
                {
                    "rank": rank,
                    "confidence": res["confidence"],
                    "method": res.get("method"),
                    "is_label": str(res["id"]) == label_id,
                    "product": product_info(res["id"]),
                }
                for rank, res in enumerate(top_results, start=1)
            ],
        })

    metrics = compute_metrics(records)
    metrics_by_category = {
        cat: compute_metrics([r for r in records if r["category"] == cat])
        for cat in sorted({r["category"] for r in records if r["category"]})
    }

    print("\n" + "="*50)
    print("         PIPELINE EVALUATION (TOP-3 & DELTA)")
    print("="*50)
    print(f"Total Queries Evaluated: {metrics['total_queries']}")
    print(f"Top-1 Strict Accuracy: {metrics['top1_accuracy']:.2f}%")
    print(f"Top-3 Human-in-loop Hit Rate: {metrics['top3_accuracy']:.2f}%\n")
    print("--- Business Metrics ---")
    print(f"1. Automation Rate (Conf >= {THRESHOLD} & Delta >= {CONFIDENCE_DELTA}): {metrics['automation_rate']:.1f}%")
    print(f"2. Auto-Match Precision (Zero-Error Tolerance): {metrics['auto_match_precision']:.2f}%")
    print(f"3. Sent to UI for Manual Review: {metrics['manual_review']} items")
    print("--- Per category (Top-1 / Top-3) ---")
    for cat, m in metrics_by_category.items():
        print(f"   {cat:<15} {m['top1_accuracy']:6.2f}% / {m['top3_accuracy']:6.2f}%  (n={m['total_queries']})")
    print("="*50)

    results_dir = BASE_DIR / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = results_dir / f"pipeline_results_{timestamp}.json"

    output = {
        "run": {
            "timestamp": timestamp,
            "input_file": str(inquiry_file.relative_to(BASE_DIR)),
            "n_samples": len(records),
            "sample_seed": args.seed,
            "routing": {"threshold": THRESHOLD, "confidence_delta": CONFIDENCE_DELTA},
        },
        "metrics": metrics,
        "metrics_by_category": metrics_by_category,
        "results": records,
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nPipeline execution complete. Results saved to: {output_file}")


if __name__ == "__main__":
    main()
