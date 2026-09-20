# File: src/summarize_results.py
# Turns pipeline_results_*.json into a report for the slides: headline metrics, per-category numbers,
# the automation/accuracy trade-off curve, and an AUTOMATIC classification of every wrong decision
# (variant of the same product vs. a different product; customer specified the detail or not).
#
# Usage:
#   python summarize_results.py                    # latest run per seed
#   python summarize_results.py path/to/run.json   # specific runs
import os
import re
import sys
import json
import glob
from collections import Counter
from pathlib import Path
from normalization import normalize_code
from bearing_codes import split_designation

BASE_DIR = Path(__file__).resolve().parent.parent
THRESHOLDS = [0.80, 0.85, 0.90, 0.92, 0.94, 0.96]
DELTAS = [0.02, 0.05]


def latest_run_per_seed():
    runs = {}
    for path in sorted(glob.glob(str(BASE_DIR / "results" / "pipeline_results_*.json"))):
        data = json.load(open(path, encoding="utf-8"))
        run = data.get("run", {})
        runs[(run.get("sample_seed"), run.get("n_samples"))] = path
    best_n = max((n for _, n in runs if n), default=0)
    return [path for (seed, n), path in sorted(runs.items(), key=lambda kv: str(kv[0])) if n == best_n]


def codes_of(product):
    return [normalize_code(c) for c in (product.get("searchable_codes") or []) if normalize_code(c)]


def shared_base(code_a, code_b):
    """Do two codes describe the same product in different variants?"""
    if not code_a or not code_b:
        return False
    if code_a == code_b:
        return True
    bearing_a, bearing_b = split_designation(code_a), split_designation(code_b)
    if bearing_a and bearing_b:
        # Compare bases, also ignoring a letter prefix ('W 61804' is the stainless 61804)
        digits = lambda base: re.sub(r'^[A-Za-z]+', '', base)
        if bearing_a[0] == bearing_b[0] or digits(bearing_a[0]) == digits(bearing_b[0]):
            return True
    shorter = min(len(code_a), len(code_b))
    common = len(os.path.commonprefix([code_a, code_b]))
    return common >= 4 and common >= 0.6 * shorter


def classify_error(record):
    """variant_specified   - same product family, and the customer DID write the distinguishing part
       variant_unspecified - same product family, customer left the variant open
       different_product   - a different article altogether"""
    prediction = record["predictions"][0]["product"]
    label = record["label"]
    predicted_codes, label_codes = codes_of(prediction), codes_of(label)
    query = normalize_code(record["query"])

    is_variant = any(shared_base(p, l) for p in predicted_codes for l in label_codes)
    if not is_variant:
        return "different_product"
    # The label's code, or the part of it the prediction lacks, appears verbatim in the query
    for label_code in label_codes:
        if label_code in query:
            return "variant_specified"
        for predicted_code in predicted_codes:
            extra = label_code[len(os.path.commonprefix([predicted_code, label_code])):]
            if len(extra) >= 2 and extra in query:
                return "variant_specified"
    return "variant_unspecified"


def percent(part, total):
    return round(part / total * 100, 1) if total else 0.0


def report(records, title):
    lines = [f"## {title}", ""]
    total = len(records)
    auto = [r for r in records if r["routing"] == "Auto-Matched"]
    manual = [r for r in records if r["routing"] != "Auto-Matched"]
    auto_wrong = [r for r in auto if not r["top1_correct"]]

    lines += [
        f"- Queries: **{total}**",
        f"- Top-1: **{percent(sum(r['top1_correct'] for r in records), total)}%** · "
        f"Top-3: **{percent(sum(r['top3_correct'] for r in records), total)}%**",
        f"- Automation rate: **{percent(len(auto), total)}%** ({len(auto)} lines)",
        f"- Auto-match precision: **{percent(len(auto) - len(auto_wrong), len(auto))}%** "
        f"({len(auto_wrong)} wrong)",
        f"- Manual review: {len(manual)} lines, label in top-3 for "
        f"{percent(sum(r['top3_correct'] for r in manual), len(manual))}%",
        "",
        "### Per category (top-1 / top-3 / automation / auto precision)",
        "",
        "| Category | n | Top-1 | Top-3 | Automation | Auto precision |",
        "|---|---|---|---|---|---|",
    ]
    for category in sorted({r["category"] for r in records if r["category"]}):
        rows = [r for r in records if r["category"] == category]
        rows_auto = [r for r in rows if r["routing"] == "Auto-Matched"]
        lines.append(
            f"| {category} | {len(rows)} | {percent(sum(r['top1_correct'] for r in rows), len(rows))}% "
            f"| {percent(sum(r['top3_correct'] for r in rows), len(rows))}% "
            f"| {percent(len(rows_auto), len(rows))}% "
            f"| {percent(sum(r['top1_correct'] for r in rows_auto), len(rows_auto))}% |"
        )

    kinds = Counter(classify_error(r) for r in auto_wrong)
    acceptable = kinds["variant_unspecified"]
    lines += [
        "",
        "### What the wrong auto-matches actually are (classified automatically from the codes)",
        "",
        "| Type | Count | Share of wrong |",
        "|---|---|---|",
        f"| Same product, variant the customer left open | {kinds['variant_unspecified']} | {percent(kinds['variant_unspecified'], len(auto_wrong))}% |",
        f"| Same product, but the customer did specify the detail | {kinds['variant_specified']} | {percent(kinds['variant_specified'], len(auto_wrong))}% |",
        f"| Different product | {kinds['different_product']} | {percent(kinds['different_product'], len(auto_wrong))}% |",
        "",
        f"**{percent(len(auto) - len(auto_wrong) + acceptable, len(auto))}%** of auto-matched lines are the labelled "
        f"article or a variant of it that the customer left open. Same family does not always mean acceptable "
        f"(a stainless variant nobody asked for is still wrong), so treat this as an upper bound.",
        "",
        "### Trade-off: threshold and delta",
        "",
        "| Threshold | Delta | Automation | Auto precision |",
        "|---|---|---|---|",
    ]
    for threshold in THRESHOLDS:
        for delta in DELTAS:
            selected = [r for r in records if r["predictions"]
                        and r["predictions"][0]["confidence"] >= threshold
                        and (r["confidence_delta"] or 0) >= delta]
            correct = sum(r["top1_correct"] for r in selected)
            lines.append(f"| {threshold:.2f} | {delta:.2f} | {percent(len(selected), total)}% "
                         f"| {percent(correct, len(selected))}% |")

    lines += ["", "### Wrong auto-matches, one line each", "",
              "| Query | Predicted | Label | Type |", "|---|---|---|---|"]
    for record in auto_wrong[:40]:
        query = record["query"][:60].replace("|", "/").replace("\n", " ")
        lines.append(f"| {query} | {record['predictions'][0]['product'].get('part_number')} "
                     f"| {record['label'].get('part_number')} | {classify_error(record)} |")
    return lines


def main():
    paths = sys.argv[1:] or latest_run_per_seed()
    if not paths:
        print("No result files found.")
        return

    all_records, sections = [], []
    for path in paths:
        data = json.load(open(path, encoding="utf-8"))
        run = data["run"]
        sections += report(data["results"], f"Run {Path(path).stem} — seed {run.get('sample_seed')}, "
                                            f"{run.get('n_samples')} samples") + [""]
        all_records += data["results"]

    header = ["# Evaluation summary", "",
              f"Source: {', '.join(Path(p).name for p in paths)}",
              "All queries come from the held-out test split, never used for training or rule learning.",
              ""]
    combined = report(all_records, "All runs combined") + [""] if len(paths) > 1 else []
    text = "\n".join(header + combined + sections)

    out_path = BASE_DIR / "results" / "evaluation_summary.md"
    out_path.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
