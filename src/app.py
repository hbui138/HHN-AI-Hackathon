# File: src/app.py
# Boie product matching — demo UI (Human-in-the-Loop).
#
#   streamlit run src/app.py
#
# Four modes:
#   "Order automation" (use case 1) runs a fresh batch of inquiries that arrived by mail/CSV:
#     confident lines are matched automatically, the rest are flagged for the clerk.
#   "Shop search" (use case 2) is the customer's view: matches while they type and, when nothing
#     fits, sends the free text to the clerk as an inquiry.
#   "Results" reads a results/pipeline_results_*.json produced by run_pipeline.py and needs
#     nothing but streamlit — use it on any laptop, also for the pitch.
#   "Clerk inbox" is the employee's view of those inquiries: accept the match, pick another
#     one from the ranked list, or type the article number by hand. Every decision is stored
#     as a new training label.
#   search_engine is imported lazily, so the results mode still works without torch / Chroma.
import json
import re
from datetime import datetime
from pathlib import Path

import streamlit as st

try:  # as-you-type input; without it the search runs on Enter instead
    from st_keyup import st_keyup
except ImportError:
    st_keyup = None

BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BASE_DIR / "results"
QUEUE_PATH = RESULTS_DIR / "inquiry_queue.jsonl"
TEST_CSV = BASE_DIR / "preprocessed_data" / "unseen_test_data.csv"
# The batch demo draws from inquiries that were not part of the evaluated seed-2026 run either.
EVALUATED_SEED, EVALUATED_N = 2026, 1000
DECISIONS_PATH = RESULTS_DIR / "clerk_decisions.jsonl"

# Routing colours: green = the system decided on its own, amber = a human has to look.
AUTO, MANUAL = "Auto-Matched", "Manual_Review"
COLORS = {AUTO: "#1a7f37", MANUAL: "#bf8700"}
GREEN, AMBER, NEUTRAL = "#1a7f37", "#bf8700", "rgba(128,128,128,.45)"

# Same rule as run_pipeline.py, plus a middle band for "probably in the top 3".
AUTO_CONF, AUTO_DELTA, LIKELY_CONF = 0.90, 0.02, 0.75

SOURCE_LABELS = {"shop": "Shop search", "email": "Mail / CSV inbox"}

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


def read_jsonl(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def append_jsonl(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def write_queue(records):
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


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


def safe_list(val):
    """Ép kiểu an toàn các Numpy Array từ Parquet về dạng list chuẩn của Python."""
    if val is None or str(val) == "nan":
        return []
    if hasattr(val, "tolist"):
        return val.tolist()
    return list(val)


def product_title(product):
    return f"{product.get('manufacturer','')} {product.get('part_number','')}".strip() or product.get("id", "")


def product_card(product, confidence, method, is_label=None, highlight=False, accent=GREEN):
    kind, scores = parse_method(method)
    border = accent if highlight else "rgba(128,128,128,.35)"
    with st.container(border=True):
        image_col, text_col, score_col = st.columns([1, 4, 2])

        with image_col:
            # FIX: Dùng safe_list thay vì "or []"
            images = safe_list(product.get("images"))
            if len(images) > 0:
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

            # FIX: Dùng safe_list cho attributes để tránh lỗi tương tự
            attributes = safe_list(product.get("attributes"))
            if len(attributes) > 0:
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


# ---------------------------------------------------------------- engine


@st.cache_resource(show_spinner="Loading models and vector database …")
def load_engine():
    # Imported here on purpose: this pulls torch, Chroma and the fine-tuned model.
    import search_engine
    from llm_parser import parse_query
    return search_engine, parse_query


@st.cache_data(show_spinner=False)
def run_search(query, category, use_llm, top_k):
    """Cached so that every extra keystroke only costs a search for the new prefix."""
    search_engine, parse_query = load_engine()
    parsed = parse_query(query) if use_llm else {}
    results = search_engine.hybrid_search(
        original_query=query, parsed_data=parsed,
        expected_category=None if category == "auto-detect" else category,
        top_k=top_k,
    )
    suggestions = [
        {"rank": i + 1, "id": r["id"], "confidence": r["confidence"], "method": r["method"],
         "attribute_rules": r.get("attribute_rules", {}),
         "product": {**search_engine.df_master_dict.get(r["id"], {}), "id": r["id"]}}
        for i, r in enumerate(results) if r.get("id")
    ]
    return parsed, suggestions


def confidence_band(suggestions):
    """exact   - one clear winner, same rule as the automated pipeline
       likely  - the right article is probably in the list, but a human should confirm
       unsure  - only loosely related hits"""
    if not suggestions:
        return "unsure", 0.0
    top = suggestions[0]["confidence"]
    delta = top - (suggestions[1]["confidence"] if len(suggestions) > 1 else 0.0)
    if top >= AUTO_CONF and delta >= AUTO_DELTA:
        return "exact", delta
    if top >= LIKELY_CONF:
        return "likely", delta
    return "unsure", delta


@st.cache_data(show_spinner=False)
def test_pool():
    """Held-out inquiries, minus the 1000 rows already used for the published evaluation."""
    import pandas as pd
    frame = pd.read_csv(TEST_CSV)
    evaluated = frame.sample(n=min(EVALUATED_N, len(frame)), random_state=EVALUATED_SEED).index
    fresh = frame.drop(index=evaluated)
    return [
        {"query": str(row["CustomerArticleDescription"]),
         "category": normalized_category(row.get("category", "")),
         "label_id": str(row["articleid_matched"])}
        for _, row in fresh.iterrows()
    ]


def normalized_category(raw):
    raw = str(raw or "").lower().replace("-", "_")
    for category in ("bearings", "pneumatics", "standard_parts"):
        if category in raw:
            return category
    return ""


def process_batch(rows, use_llm, progress=None):
    processed = []
    for index, row in enumerate(rows):
        try:
            parsed, suggestions = run_search(row["query"], row["category"] or "auto-detect", use_llm, 3)
        except Exception as e:
            st.error(f"Engine not available: {e}")
            return []
        band, delta = confidence_band(suggestions)
        top = suggestions[0] if suggestions else None
        processed.append({
            **row,
            "parsed_query": parsed,
            "suggestions": suggestions,
            "band": band,
            "delta": delta,
            "matched_id": top["id"] if band == "exact" and top else None,
            "correct": bool(top and band == "exact" and top["id"] == row["label_id"]),
        })
        if progress is not None:
            progress.progress((index + 1) / len(rows), text=f"Matching line {index + 1} of {len(rows)} …")
    return processed


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


def batch_mode():
    st.caption("Use case 1 — a batch of inquiries as they arrive by mail or CSV. "
               "The customer never saw a suggestion, so confident lines are matched automatically.")

    controls = st.columns([1, 1, 2])
    size = controls[0].number_input("Lines in this batch", 5, 100, 25, step=5)
    use_llm = controls[1].toggle("Use LLM parser", value=True, key="batch_use_llm")
    if controls[2].button("Run a fresh batch", type="primary"):
        import random
        pool = test_pool()
        st.session_state["batch_rows"] = random.sample(pool, min(int(size), len(pool)))
        st.session_state.pop("batch_done", None)

    rows = st.session_state.get("batch_rows")
    if not rows:
        st.info("Press “Run a fresh batch”. The lines are drawn at random from the held-out test data, "
                f"excluding the {EVALUATED_N} inquiries of the published evaluation run.")
        return

    processed = st.session_state.get("batch_done")
    if processed is None:
        progress = st.progress(0.0, text="Matching …")
        processed = process_batch(rows, use_llm, progress)
        progress.empty()
        if not processed:
            return
        st.session_state["batch_done"] = processed

    auto = [r for r in processed if r["band"] == "exact"]
    flagged = [r for r in processed if r["band"] != "exact"]
    correct = sum(r["correct"] for r in auto)

    columns = st.columns(4)
    columns[0].metric("Lines", len(processed))
    columns[1].metric("Matched automatically", f"{len(auto) / len(processed):.0%}")
    columns[2].metric("Of those, correct", f"{correct / len(auto):.0%}" if auto else "–",
                      help="Compared with the article a Boie clerk picked for this inquiry.")
    columns[3].metric("Flagged for a clerk", len(flagged))

    table = [{
        "Decision": "Auto-matched" if r["band"] == "exact" else "Clerk",
        "Inquiry": r["query"][:70],
        "Matched article": product_title(r["suggestions"][0]["product"]) if r["suggestions"] else "–",
        "Confidence": r["suggestions"][0]["confidence"] if r["suggestions"] else 0.0,
        "Margin": r["delta"],
        "Matches clerk's choice": ("yes" if r["correct"] else "no") if r["band"] == "exact" else "",
    } for r in processed]

    st.dataframe(
        table, width="stretch", hide_index=True,
        column_config={
            "Confidence": st.column_config.ProgressColumn("Confidence", min_value=0.0, max_value=1.0,
                                                          format="%.0f%%"),
            "Margin": st.column_config.NumberColumn("Margin over rank 2", format="%.2f"),
        },
    )
    st.caption("Green path: the line goes straight into the quote. Everything else waits for a clerk — "
               "no article list is needed here, only the decision.")

    if flagged and st.button(f"Send {len(flagged)} flagged lines to the clerk inbox"):
        for row in flagged:
            append_jsonl(QUEUE_PATH, {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "query": row["query"],
                "note": "",
                "category": row["category"],
                "source": "email",
                "status": "open",
            })
        st.success("Sent. Open the clerk inbox.")


def shop_mode():
    st.caption("Customer view — matches appear while you type. "
               "If nothing fits, the text goes to a clerk as an inquiry.")

    left, right = st.columns([3, 1])
    with left:
        if st_keyup is not None:
            query = st_keyup("What are you looking for?", debounce=400, key="shop_query",
                             placeholder="e.g. Kugellager SKF 6016 2Z")
        else:
            query = st.text_input("What are you looking for?", key="shop_query",
                                  placeholder="e.g. Kugellager SKF 6016 2Z")
            st.caption("Install `streamlit-keyup` for matching while typing.")
    with right:
        category = st.selectbox("Product group", ["auto-detect", "bearings", "pneumatics", "standard_parts"])

    use_llm = st.sidebar.toggle("Use LLM parser while typing", value=False,
                                help="Off: part numbers are read with rules only — fast enough for every keystroke.")

    query = (query or "").strip()
    if len(query) < 3:
        st.info("Type at least three characters.")
        return

    try:
        with st.spinner("Searching …"):
            parsed, suggestions = run_search(query, category, use_llm, 5)
    except Exception as e:
        st.error(f"Engine not available: {e}")
        st.caption("Needs chromadb, sentence-transformers and models/finetuned_boie_minilm.")
        return

    band, delta = confidence_band(suggestions)
    if band == "exact":
        st.success(f"Best match found · {suggestions[0]['confidence']:.0%} confidence")
    elif band == "likely":
        st.warning("Several articles fit — please check the list.")
    else:
        st.info("Only loosely related articles. Send us the text and a colleague will look into it.")

    for suggestion in suggestions:
        product_card(suggestion["product"], suggestion["confidence"], suggestion["method"],
                     highlight=(suggestion["rank"] == 1 and band == "exact"),
                     accent=GREEN if band == "exact" else AMBER)

    st.divider()
    st.markdown("**None of these is what you need?**")
    note = st.text_area("Anything else we should know? (drawing number, quantity, application)",
                        key="shop_note", height=80)
    if st.button("Send as inquiry", type="primary"):
        append_jsonl(QUEUE_PATH, {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "query": query,
            "note": note,
            "category": "" if category == "auto-detect" else category,
            "source": "shop",
            "parsed_query": parsed,
            "suggestions_shown": [{"id": s["id"], "confidence": s["confidence"]} for s in suggestions],
            "status": "open",
        })
        st.success("Sent. A clerk will get back to you with a quote.")


def clerk_decision_form(inquiry, index):
    """One inquiry in the clerk's inbox: accept, pick another article, or type a number."""
    try:
        parsed, suggestions = run_search(inquiry["query"], inquiry.get("category") or "auto-detect",
                                         st.session_state.get("clerk_use_llm", True), 10)
    except Exception as e:
        st.error(f"Engine not available: {e}")
        return

    band, delta = confidence_band(suggestions)
    source = inquiry.get("source", "email")
    rejected = {s["id"] for s in inquiry.get("suggestions_shown", [])}
    if source == "shop" and band == "exact":
        # The customer already saw the engine's favourite and asked for a human anyway.
        band = "likely"
    accent = {"exact": GREEN, "likely": AMBER, "unsure": NEUTRAL}[band]
    headline = {
        "exact": "Clear match — accept or replace",
        "likely": "Probably in this list — please confirm",
        "unsure": "No confident match — related articles only",
    }[band]

    st.markdown(
        f"<div style='border-left:5px solid {accent};padding:.4rem 0 .4rem .8rem'>"
        f"<div style='color:{accent};font-weight:600'>{headline}</div>"
        f"<div style='font-size:1.05rem'>{inquiry['query']}</div></div>",
        unsafe_allow_html=True,
    )
    meta = [SOURCE_LABELS.get(source, source), f"Received {inquiry.get('created_at','')}"]
    if inquiry.get("category"):
        meta.append(f"Product group: {inquiry['category']}")
    if suggestions:
        meta.append(f"Margin over rank 2: {delta:.0%}")
    st.caption(" · ".join(meta))
    if inquiry.get("note"):
        st.info(f"Customer note: {inquiry['note']}")
    if rejected:
        st.warning("The customer saw these suggestions in the shop and still asked for a quote — "
                   "they are marked below.")
    bits = [f"**{k}:** {v}" for k, v in (parsed or {}).items() if v]
    if bits:
        st.markdown("Extracted from the text — " + " · ".join(bits))

    if not suggestions:
        st.warning("The engine found nothing at all.")

    visible = suggestions[:1] if band == "exact" else suggestions[:3]
    for suggestion in visible:
        seen = suggestion["id"] in rejected
        if seen:
            st.caption("↓ already shown to the customer")
        product_card(suggestion["product"], suggestion["confidence"], suggestion["method"],
                     highlight=(suggestion["rank"] == 1 and band != "unsure" and not seen),
                     accent=NEUTRAL if seen else accent)

    rest = suggestions[len(visible):]
    if rest:
        with st.expander(f"Show {len(rest)} more suggestions (top {len(suggestions)})"):
            for suggestion in rest:
                product_card(suggestion["product"], suggestion["confidence"], suggestion["method"],
                             accent=NEUTRAL)

    options = [f"#{s['rank']} · {product_title(s['product'])} · {s['confidence']:.0%}"
               + (" · customer saw this" if s["id"] in rejected else "") for s in suggestions]
    options.append("Enter a different article number")
    choice = st.radio("Decision", options, index=0 if options else None, key=f"choice_{index}")

    manual_id = ""
    if choice == options[-1]:
        manual_id = st.text_input("Boie article number", key=f"manual_{index}",
                                  placeholder="e.g. 10004423")

    accept_label = "Accept match" if band == "exact" and choice == options[0] else "Confirm selection"
    columns = st.columns([1, 1, 4])
    if columns[0].button(accept_label, type="primary", key=f"accept_{index}"):
        if choice == options[-1] and not manual_id.strip():
            st.error("Enter an article number first.")
            return
        chosen = None if choice == options[-1] else suggestions[options.index(choice)]
        append_jsonl(DECISIONS_PATH, {
            "decided_at": datetime.now().isoformat(timespec="seconds"),
            "query": inquiry["query"],
            "category": inquiry.get("category", ""),
            "band": band,
            "source": source,
            "suggested_id": suggestions[0]["id"] if suggestions else None,
            "chosen_id": chosen["id"] if chosen else manual_id.strip(),
            "chosen_rank": chosen["rank"] if chosen else None,
            "source": "suggestion" if chosen else "manual",
        })
        resolve_inquiry(inquiry)
        st.success("Saved. This decision becomes a new training label.")
        st.rerun()

    if columns[1].button("Skip for now", key=f"skip_{index}"):
        st.rerun()


def resolve_inquiry(inquiry):
    queue = read_jsonl(QUEUE_PATH)
    for record in queue:
        if record.get("created_at") == inquiry.get("created_at") and record.get("query") == inquiry.get("query"):
            record["status"] = "done"
    write_queue(queue)


DEMO_INQUIRIES = [
    "Kugellager SKF 6016 2Z",
    "Positionsfuss Form B SW13x10 M8 02041-208010 NORELEM",
    "Rillenkugellager d=15 D=24 B=5 Edelstahl geschlossen 15x24x5",
]


def clerk_mode():
    st.caption("Clerk view — lines the automation did not decide, plus inquiries customers sent "
               "from the shop. The source is shown on every card.")
    st.sidebar.toggle("Use LLM parser", value=True, key="clerk_use_llm")

    queue = read_jsonl(QUEUE_PATH)
    open_inquiries = [record for record in queue if record.get("status") != "done"]

    top = st.columns([2, 1, 1])
    top[0].metric("Open inquiries", len(open_inquiries))
    top[1].metric("Handled", len(queue) - len(open_inquiries))
    top[2].metric("Decisions logged", len(read_jsonl(DECISIONS_PATH)))

    if not open_inquiries:
        st.info("Inbox is empty. Send one from the shop search, or load the demo inquiries.")
        if st.button("Load demo inquiries"):
            for query in DEMO_INQUIRIES:
                append_jsonl(QUEUE_PATH, {
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                    "query": query, "note": "", "category": "", "status": "open",
                })
            st.rerun()
        return

    st.divider()
    for index, inquiry in enumerate(open_inquiries):
        clerk_decision_form(inquiry, index)
        st.divider()


# ---------------------------------------------------------------- main

st.title("Article matching from free text")
mode = st.sidebar.radio("Mode", ["Order automation", "Shop search", "Clerk inbox", "Results"])
st.sidebar.divider()
if mode == "Order automation":
    batch_mode()
elif mode == "Results":
    results_mode()
elif mode == "Shop search":
    shop_mode()
else:
    clerk_mode()
