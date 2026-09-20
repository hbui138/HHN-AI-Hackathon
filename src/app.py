# File: src/app.py
# Boie product matching — demo UI (Human-in-the-Loop).
#
#   streamlit run src/app.py
#
# Two modes:
#   "Results" reads a results/pipeline_results_*.json produced by run_pipeline.py and needs
#     nothing but streamlit — use it on any laptop, also for the pitch.
#   "Live search" calls the real engine (llm_parser.parse_query + search_engine.hybrid_search).
#     search_engine is imported lazily, so the results mode still works without torch / Chroma.
import json
import re
from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BASE_DIR / "results"

# Routing colours: green = the system decided on its own, amber = a human has to look.
AUTO, MANUAL = "Auto-Matched", "Manual_Review"
COLORS = {AUTO: "#1a7f37", MANUAL: "#bf8700"}
SCORE_LABELS = {  # the weighted formula of search_engine.py, 5.2 in challenge2.md
    "S_code": "Part number",
    "S_brand": "Manufacturer",
    "S_text": "Description (cross-encoder)",
    "S_attr": "Technical attributes",
}

st.set_page_config(page_title="Boie · Article Matching", page_icon="🔩", layout="wide")


# ---------------------------------------------------------------- data


@st.cache_data(show_spinner=False)
def load_run(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def result_files():
    return sorted(RESULTS_DIR.glob("pipeline_results_*.json"), reverse=True)


def parse_method(method):
    """'Code(S_code:0.83|S_brand:1.0|...)' -> ('Code', {'S_code': 0.83, ...})."""
    kind = method.split("(", 1)[0]
    parts = dict(re.findall(r"(S_\w+):([0-9.]+)", method))
    return kind, {k: float(v) for k, v in parts.items()}


def format_attribute(attribute):
    """'Bolzen-Ø 8.000 mm' -> 'Bolzen-Ø 8 mm' (the catalog pads every number to three decimals)."""
    value = str(attribute.get("value", "")).strip()
    if re.fullmatch(r"-?\d+\.\d+", value):
        value = value.rstrip("0").rstrip(".")
    unit = str(attribute.get("unit", "")).strip()
    return f"{attribute.get('name','')} {value}{(' ' + unit) if unit else ''}".strip()


# ---------------------------------------------------------------- pieces


def metric_row(metrics, by_category):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Top-1 accuracy", f"{metrics['top1_accuracy']:.1f}%",
              help="The first suggestion is exactly the article a human confirmed.")
    c2.metric("Top-3 hit rate", f"{metrics['top3_accuracy']:.1f}%",
              help="The correct article is among the three suggestions.")
    c3.metric("Automation rate", f"{metrics['automation_rate']:.1f}%",
              help=f"{metrics['auto_matched']} of {metrics['total_queries']} inquiries handled without asking.")
    c4.metric("Auto-match precision", f"{metrics['auto_match_precision']:.1f}%",
              delta=f"-{metrics['auto_matched_wrong']} wrong", delta_color="inverse",
              help="Share of the automatically matched inquiries that are correct.")

    st.caption("By product group")
    cols = st.columns(len(by_category))
    for col, (category, m) in zip(cols, by_category.items()):
        col.metric(category.replace("_", " ").title(),
                   f"{m['top1_accuracy']:.1f}%",
                   help=f"Top-3 {m['top3_accuracy']:.1f}% · n={m['total_queries']}")


def product_card(product, confidence, method, is_label=None, highlight=False):
    kind, scores = parse_method(method)
    border = "#1a7f37" if highlight else "rgba(128,128,128,.35)"
    with st.container(border=True):
        image_col, text_col, score_col = st.columns([1, 4, 2])

        with image_col:
            images = product.get("images") or []
            if images:
                st.image(images[0]["url"], width=90)
            else:
                st.markdown("<div style='height:90px;display:flex;align-items:center;"
                            "justify-content:center;opacity:.35'>no image</div>",
                            unsafe_allow_html=True)

        with text_col:
            mark = ""
            if is_label is True:
                mark = " ✅"
            elif is_label is False:
                mark = " ✗"
            st.markdown(f"**{product.get('manufacturer','')} {product.get('part_number','')}**{mark}")
            st.markdown(f"<span style='opacity:.8'>{product.get('description','')}</span>",
                        unsafe_allow_html=True)
            st.caption(f"Boie article no.: {product.get('id','')} · {product.get('category','')}")
            attributes = product.get("attributes") or []
            if attributes:
                st.caption(" · ".join(format_attribute(a) for a in attributes[:6]))
            if product.get("link"):
                st.markdown(f"[Open in shop]({product['link']})")

        with score_col:
            st.markdown(f"<div style='font-size:1.6rem;font-weight:600;color:{border}'>"
                        f"{confidence:.0%}</div><div style='opacity:.6;font-size:.8rem'>"
                        f"{'Part number matched' if kind == 'Code' else 'Semantic search'}</div>",
                        unsafe_allow_html=True)
            # Why this product: the four parts of the score, in plain words.
            for key, value in scores.items():
                st.caption(f"{SCORE_LABELS.get(key, key)} · {value:.0%}")


def inquiry_view(record):
    routing = record["routing"]
    color = COLORS[routing]
    badge = "Auto-matched" if routing == AUTO else "Manual review"

    st.markdown(
        f"<div style='border-left:5px solid {color};padding:.4rem 0 .4rem .8rem'>"
        f"<div style='color:{color};font-weight:600'>{badge}</div>"
        f"<div style='font-size:1.05rem'>{record['query']}</div></div>",
        unsafe_allow_html=True,
    )

    parsed = record.get("parsed_query") or {}
    bits = [f"**{k}:** {v}" for k, v in parsed.items() if v]
    meta = [f"Product group: {record.get('category','–')}",
            f"Margin over rank 2: {record.get('confidence_delta', 0):.0%}"]
    st.caption(" · ".join(meta))
    if bits:
        st.markdown("Extracted from the text — " + " · ".join(bits))

    fired = record.get("attribute_rules_fired") or {}
    if fired:
        st.caption("Learned attribute rules: " + ", ".join(f"`{k}`" for k in fired))

    for prediction in record["predictions"]:
        product_card(prediction["product"], prediction["confidence"], prediction["method"],
                     is_label=prediction.get("is_label"),
                     highlight=prediction["rank"] == 1 and routing == AUTO)

    if routing == MANUAL:
        st.info("The clerk picks one suggestion — that choice becomes a new training label.")


# ---------------------------------------------------------------- modes


def results_mode():
    files = result_files()
    if not files:
        st.warning(f"No results file in {RESULTS_DIR}. Run `python src/run_pipeline.py 1000` first.")
        return

    with st.sidebar:
        chosen = st.selectbox("Test run", files, format_func=lambda p: p.stem.replace("pipeline_results_", ""))
        data = load_run(chosen)
        run = data["run"]
        st.caption(f"{run['n_samples']} inquiries · seed {run['sample_seed']}")
        st.caption(f"Threshold {run['routing']['threshold']} · delta {run['routing']['confidence_delta']}")

        only = st.radio("Show", ["All", "Auto-matched", "Manual review", "Errors only"])
        categories = sorted({r["category"] for r in data["results"] if r.get("category")})
        category = st.selectbox("Product group", ["All"] + categories)
        search = st.text_input("Search inquiry text")

    metric_row(data["metrics"], data["metrics_by_category"])
    st.divider()

    records = data["results"]
    if only == "Auto-matched":
        records = [r for r in records if r["routing"] == AUTO]
    elif only == "Manual review":
        records = [r for r in records if r["routing"] == MANUAL]
    elif only == "Errors only":
        records = [r for r in records if not r["top1_correct"]]
    if category != "All":
        records = [r for r in records if r.get("category") == category]
    if search:
        records = [r for r in records if search.lower() in r["query"].lower()]

    st.caption(f"{len(records)} inquiries")
    page_size = 20
    pages = max(1, (len(records) + page_size - 1) // page_size)
    page = st.number_input("Page", 1, pages, 1, disabled=pages == 1) if pages > 1 else 1
    for record in records[(page - 1) * page_size: page * page_size]:
        inquiry_view(record)
        st.write("")


@st.cache_resource(show_spinner="Loading models and vector database …")
def load_engine():
    # Imported here on purpose: this pulls torch, Chroma and the fine-tuned model.
    import search_engine
    from llm_parser import parse_query
    return search_engine, parse_query


def live_mode():
    st.caption("Free-text customer inquiry — the same engine as in the test run.")
    query = st.text_input("Customer inquiry", placeholder="e.g. Kugellager (SKF) 6016 2Z")
    category = st.selectbox("Product group (optional)", ["auto-detect", "bearings", "pneumatics", "standard_parts"])
    if not query:
        return

    try:
        search_engine, parse_query = load_engine()
    except Exception as e:
        st.error(f"Engine not available: {e}")
        st.caption("Needs chromadb, sentence-transformers, models/finetuned_boie_minilm "
                   "and an OPENROUTER_API_KEY in .env.")
        return

    parsed = parse_query(query)
    results = search_engine.hybrid_search(
        original_query=query, parsed_data=parsed,
        expected_category=None if category == "auto-detect" else category,
    )

    top = results[0]
    delta = top["confidence"] - (results[1]["confidence"] if len(results) > 1 else 0)
    auto = top["confidence"] >= 0.90 and delta >= 0.02
    record = {
        "query": query,
        "category": category if category != "auto-detect" else "",
        "parsed_query": parsed,
        "routing": AUTO if auto else MANUAL,
        "confidence_delta": delta,
        "attribute_rules_fired": {},
        "predictions": [
            {"rank": i + 1, "confidence": r["confidence"], "method": r["method"],
             "product": search_engine.df_master_dict.get(r["id"], {"id": r["id"]})}
            for i, r in enumerate(results) if r.get("id")
        ],
    }
    inquiry_view(record)


# ---------------------------------------------------------------- main

st.title("Article matching from free text")
mode = st.sidebar.radio("Mode", ["Results", "Live search"])
st.sidebar.divider()
if mode == "Results":
    results_mode()
else:
    live_mode()
