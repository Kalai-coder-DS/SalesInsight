"""Data Source page: use the demo data or upload your own sales file (Phase 14B).

Steps for a custom file:  1 Upload  ->  2 Preview  ->  3 Match columns  ->  4 Check & analyse
"""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from components import data_source as ds
from components.kpi_cards import render_stat_cards
from components.layout import card, card_title, page_header
from salesinsight import config
from salesinsight.upload import UploadError, excel_sheets, prepare_sales, read_upload, suggest_mapping
from salesinsight.upload.detect import sales_like_problem
from salesinsight.upload.parsing import detect_currency
from salesinsight.upload.prepare import CAPABILITY_LABELS
from salesinsight.upload.reader import ALLOWED_TYPES, MAX_FILE_MB, MAX_ROWS
from salesinsight.upload.schema import FIELDS, SALES_ALTERNATIVE

CHOICES = ["Demo data", "My own sales file"]
CURRENCIES = ["$", "₹", "€", "£", "¥", "No symbol"]
SAMPLES = [("indian_retail_sales.csv", "Indian retail (CSV, ₹, day/month dates)"),
           ("online_store_orders.xlsx", "Online store (Excel, with cost)"),
           ("cafe_daily_sales.csv", "Café (price x quantity only)")]
LEVEL_ICON = {"error": ":material/error:", "warning": ":material/warning:", "fixed": ":material/build:",
              "info": ":material/info:"}
# What to add to the file to unlock a missing capability
UNLOCK_HINT = {"orders": "an order or invoice ID", "customers": "a customer name or ID",
               "products": "a product name", "quantity": "a quantity column", "profit": "a profit or cost column",
               "discount": "a discount column", "category": "a category column",
               "sub_category": "a sub-category column", "region": "a region column", "state": "a state column",
               "us_map": "US state names", "city": "a city column", "segment": "a customer segment column",
               "shipping": "a ship date"}


# --------------------------------------------------------------------------------------
# Callbacks (run before the next rerun, so the whole app switches data at once)
# --------------------------------------------------------------------------------------
def _on_choice() -> None:
    if st.session_state.get("ds_choice") == "Demo data":
        ds.use_demo()
    else:
        ds.use_custom()


def _mapping() -> dict[str, str | None]:
    return {f.key: (None if st.session_state.get(f"map_{f.key}") in (None, ds.NOT_IN_FILE)
                    else st.session_state.get(f"map_{f.key}")) for f in FIELDS}


def _on_analyse() -> None:
    raw = st.session_state.get("ds_raw")
    if raw is None:
        return
    order = st.session_state.get("ds_dayfirst")
    dayfirst = None if order is None else order.startswith("Day")
    result = prepare_sales(raw, _mapping(), dayfirst=dayfirst,
                           remove_duplicates=bool(st.session_state.get("ds_dedupe", False)))
    st.session_state["ds_last_result"] = result
    if result.ok:
        symbol = st.session_state.get("ds_currency_choice") or result.currency or "$"
        st.session_state["ds_currency"] = "" if symbol == "No symbol" else symbol
        st.session_state["ds_result"] = result
        st.session_state["ds_active_name"] = st.session_state.get("ds_file_name", "your file")
        st.session_state["ds_mode"] = "demo"      # force use_custom() to switch and clear filters
        ds.use_custom()


# --------------------------------------------------------------------------------------
# Reading a new upload
# --------------------------------------------------------------------------------------
def _load_upload(uploaded) -> None:
    data = uploaded.getvalue()
    sheet = None
    if uploaded.name.lower().endswith((".xlsx", ".xlsm")):
        try:
            sheets = excel_sheets(data)
        except UploadError as exc:
            st.error(str(exc), icon=":material/error:")
            return
        st.session_state["ds_sheets"] = sheets
        if len(sheets) > 1:
            sheet = st.selectbox("Which sheet holds the sales?", sheets, key="ds_sheet")
        else:
            sheet = sheets[0]
    else:
        st.session_state.pop("ds_sheets", None)
    file_key = f"{uploaded.name}|{len(data)}|{sheet}"
    if st.session_state.get("ds_file_key") == file_key:
        return
    try:
        with st.spinner("Reading your file..."):
            raw = read_upload(uploaded.name, data, sheet)
            mapping, _ = suggest_mapping(raw)
    except UploadError as exc:
        st.error(str(exc), icon=":material/error:")
        return
    st.session_state.update({"ds_raw": raw, "ds_file_name": uploaded.name, "ds_file_key": file_key})
    st.session_state.pop("ds_last_result", None)
    for f in FIELDS:
        st.session_state[f"map_{f.key}"] = mapping.get(f.key) or ds.NOT_IN_FILE
    st.session_state.pop("ds_dayfirst", None)
    money_col = mapping.get("sales") or mapping.get("unit_price")
    symbol = detect_currency(raw[money_col]) if money_col else None
    st.session_state["ds_currency_choice"] = symbol if symbol in CURRENCIES else "$"


# --------------------------------------------------------------------------------------
# Page sections
# --------------------------------------------------------------------------------------
def _demo_panel() -> None:
    with card("ds-demo"):
        card_title("Demo data is active", "Superstore: US retail sales 2014-2017 (Kaggle sample data)")
        st.markdown("All pages show the demo data. To analyse your own sales, choose **My own sales file** "
                    "above - the demo stays one click away.")


def _upload_section() -> None:
    with card("ds-upload"):
        card_title("1. Upload your sales file",
                   f"CSV or Excel (.xlsx), up to {MAX_FILE_MB} MB and {MAX_ROWS:,} rows. "
                   "One row per sale or order line; the first row holds the column names.")
        uploaded = st.file_uploader("Sales file", type=[t.lstrip(".") for t in ALLOWED_TYPES],
                                    key="ds_uploader", label_visibility="collapsed")
        st.caption(":material/lock: Your file stays in this browser session only. It is not saved, not "
                   "shared with other visitors, and disappears when you close the tab or click "
                   "'Remove my file'.")
        if uploaded is not None:
            _load_upload(uploaded)
        with st.expander("No file at hand? Download a sample to try"):
            cols = st.columns(len(SAMPLES))
            for col, (name, label) in zip(cols, SAMPLES):
                path = config.PROJECT_ROOT / "data" / "samples" / name
                with col:
                    if path.is_file():
                        st.download_button(label, path.read_bytes(), file_name=name,
                                           icon=":material/download:", key=f"ds_sample_{name}")


def _preview_section(raw: pd.DataFrame) -> None:
    with card("ds-preview"):
        card_title("2. Preview", f"{st.session_state.get('ds_file_name')}: {len(raw):,} rows x "
                                 f"{raw.shape[1]} columns (first 10 rows shown)")
        st.dataframe(raw.head(10), hide_index=True, width="stretch")
        problem = sales_like_problem(raw)
        if problem:
            st.warning(problem, icon=":material/warning:")


def _example(raw: pd.DataFrame, column: str | None) -> str:
    if not column or column == ds.NOT_IN_FILE or column not in raw:
        return ""
    values = raw[column].dropna().astype(str).str.strip()
    values = values[values != ""]
    return f"e.g. {values.iloc[0][:40]}" if len(values) else "(empty column)"


def _mapping_row(raw: pd.DataFrame, f, options: list[str]) -> None:
    left, right = st.columns([1.15, 1])
    with left:
        st.selectbox(f.label, options, key=f"map_{f.key}", help=f.help)
    with right:
        st.markdown(f"<div class='si-map-example'>{escape(_example(raw, st.session_state.get(f'map_{f.key}')))}"
                    "</div>", unsafe_allow_html=True)


def _mapping_section(raw: pd.DataFrame) -> None:
    options = [ds.NOT_IN_FILE] + list(raw.columns)
    with card("ds-map"):
        card_title("3. Match your columns",
                   "SalesInsight guessed which column is which. Check each one and change it if needed.")
        groups = [("required", "Needed", True), ("recommended", "Recommended (unlock more analysis)", True),
                  ("optional", "Optional (more pages and charts)", False)]
        for level, title, open_ in groups:
            fields = [f for f in FIELDS if f.level == level]
            if level == "required":
                st.markdown(f"**{title}**")
                for f in fields:
                    _mapping_row(raw, f, options)
                st.caption(f"No sales column? Choose {SALES_ALTERNATIVE[0].replace('_', ' ')} and quantity "
                           "under Optional - sales will be calculated as price x quantity.")
            else:
                with st.expander(title, expanded=open_):
                    for f in fields:
                        _mapping_row(raw, f, options)

        st.markdown("**Options**")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.radio("Dates like 05/03/2024 mean", ["Day/Month/Year", "Month/Day/Year"], key="ds_dayfirst",
                     index=None, help="Leave empty to let SalesInsight decide from the data.")
        with c2:
            st.session_state.setdefault("ds_currency_choice", "$")
            st.selectbox("Currency shown", CURRENCIES, key="ds_currency_choice",
                         help="Detected from the sales column when it holds a currency mark.")
        with c3:
            st.checkbox("Remove exact duplicate rows", key="ds_dedupe",
                        help="Rows with the same order ID, date, customer, product, amount and quantity.")
        st.button("Check & analyse", type="primary", icon=":material/play_arrow:", key="ds_analyse",
                  on_click=_on_analyse)


def _report_section() -> None:
    result = st.session_state.get("ds_last_result")
    if result is None:
        return
    with card("ds-report"):
        card_title("4. Data check", "What was found and fixed - nothing is changed in your original file")
        removed = result.rows_in - result.rows_out if result.ok else 0
        stats = [{"label": "Rows ready", "value": f"{result.rows_out:,}", "sub": f"of {result.rows_in:,} in the file"},
                 {"label": "Rows removed", "value": f"{removed:,}", "sub": "no valid date or amount"}]
        if result.ok:
            d = result.data
            stats += [{"label": "Period", "value": f"{d['order_date'].min():%b %Y}",
                       "sub": f"to {d['order_date'].max():%b %Y}"},
                      {"label": "Analyses available", "value": f"{len(result.capabilities)} of {len(CAPABILITY_LABELS)}",
                       "sub": "see the list below"}]
        render_stat_cards(stats)
        for m in result.messages:
            show = {"error": st.error, "warning": st.warning, "fixed": st.success, "info": st.info}[m.level]
            show(m.text, icon=LEVEL_ICON[m.level])
        if result.ok:
            have = [CAPABILITY_LABELS[c] for c in CAPABILITY_LABELS if c in result.capabilities]
            missing = [f"{CAPABILITY_LABELS[c]} - add {UNLOCK_HINT[c]}" for c in CAPABILITY_LABELS
                       if c not in result.capabilities]
            left, right = st.columns(2)
            with left:
                st.markdown("**Available for your data**")
                st.markdown("\n".join(f"- {x}" for x in ["Sales, trends and seasonality", *have]))
            with right:
                st.markdown("**Not available (hidden in the pages)**")
                st.markdown("\n".join(f"- {x}" for x in missing) or "- Nothing - all analyses are available")


def render() -> None:
    page_header("Data Source", "Analyse the demo data or your own sales file", eyebrow="Data",
                chips=[f"Active: {ds.source_name()}"])
    st.session_state.setdefault("ds_choice", "My own sales file" if ds.mode() == "custom" else "Demo data")
    st.radio("Which data do you want to analyse?", CHOICES, key="ds_choice", horizontal=True,
             on_change=_on_choice)

    if st.session_state["ds_choice"] == "Demo data":
        _demo_panel()
        if st.session_state.get("ds_raw") is not None:
            st.caption(f"Your file {st.session_state.get('ds_file_name')} is still loaded in this session.")
            st.button("Remove my file", icon=":material/delete:", key="ds_remove_demo", on_click=ds.remove_file)
        return

    if ds.mode() == "custom":
        st.success(f"Your data is active: {ds.source_name()}. Open any page in the sidebar.",
                   icon=":material/check_circle:")
        c1, c2, _ = st.columns([1, 1, 3])
        with c1:
            pages = st.session_state.get("_si_pages", {})
            if "overview" in pages and st.button("Open Executive Overview", icon=":material/space_dashboard:",
                                                 key="ds_go"):
                st.switch_page(pages["overview"])
        with c2:
            st.button("Remove my file", icon=":material/delete:", key="ds_remove", on_click=ds.remove_file)

    _upload_section()
    raw = st.session_state.get("ds_raw")
    if raw is None:
        return
    _preview_section(raw)
    _mapping_section(raw)
    _report_section()
