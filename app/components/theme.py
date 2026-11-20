"""Look and feel: colours, CSS and the Plotly chart template, for dark and light mode."""

from __future__ import annotations

import streamlit as st

# Series colours (fixed order, colour-blind checked; same as the static report).
REVENUE = "#3b82f6"
PROFIT = "#f97316"
CUSTOMERS = "#10b981"
LOSS = "#ef4444"
GAIN = "#3b82f6"
SERIES = ["#3b82f6", "#f97316", "#10b981", "#eab308", "#ec4899", "#22c55e", "#8b5cf6", "#ef4444"]

THEMES = {
    "dark": {
        "bg": "#0b1020",
        "bg_glow_1": "rgba(99, 102, 241, 0.16)",
        "bg_glow_2": "rgba(59, 130, 246, 0.12)",
        "panel": "#121a2f",
        "panel_2": "#18213b",
        "border": "rgba(148, 163, 184, 0.14)",
        "text": "#e5e7eb",
        "muted": "#94a3b8",
        "grid": "rgba(148, 163, 184, 0.12)",
        "sidebar": "#0d1426",
        "shadow": "0 8px 24px rgba(0, 0, 0, 0.35)",
        "up": "#34d399",
        "down": "#f87171",
    },
    "light": {
        "bg": "#f5f7fb",
        "bg_glow_1": "rgba(99, 102, 241, 0.08)",
        "bg_glow_2": "rgba(59, 130, 246, 0.06)",
        "panel": "#ffffff",
        "panel_2": "#f1f4fa",
        "border": "rgba(15, 23, 42, 0.08)",
        "text": "#0f172a",
        "muted": "#64748b",
        "grid": "rgba(15, 23, 42, 0.08)",
        "sidebar": "#0d1426",          # sidebar stays dark in both modes (its widgets are dark)
        "shadow": "0 6px 18px rgba(15, 23, 42, 0.08)",
        "up": "#059669",
        "down": "#dc2626",
    },
}

ACCENT_GRADIENT = "linear-gradient(135deg, #6366f1 0%, #3b82f6 100%)"


def current_theme() -> str:
    try:
        return "light" if st.session_state.get("light_mode", False) else "dark"
    except Exception:   # outside a running app (e.g. unit tests)
        return "dark"


def palette() -> dict:
    return THEMES[current_theme()]


def inject_css() -> None:
    """Add the app's CSS. Called once per run, before any content."""
    t = palette()
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, .stApp, .stMarkdown, p, label, input, textarea, button {{
    font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
}}
h1, h2, h3, h4, h5, h6 {{
    font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif !important;
}}
/* Keep Streamlit's icon font for icons (menu, buttons), never replace it with Inter */
[data-testid="stIconMaterial"], .material-symbols-rounded, span[class*="material-symbols"] {{
    font-family: 'Material Symbols Rounded' !important;
}}
.stApp {{
    background:
        radial-gradient(1200px 600px at 10% -10%, {t['bg_glow_1']}, transparent 60%),
        radial-gradient(900px 500px at 100% 0%, {t['bg_glow_2']}, transparent 55%),
        {t['bg']};
    color: {t['text']};
}}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1400px; }}
h1, h2, h3, h4, p, li, label, .stMarkdown {{ color: {t['text']}; }}

/* Sidebar */
[data-testid="stSidebar"] {{
    background: {t['sidebar']};
    border-right: 1px solid rgba(148, 163, 184, 0.12);
}}
[data-testid="stSidebar"] * {{ color: #e5e7eb; }}
[data-testid="stSidebarHeader"] {{ padding-top: 1.2rem; }}
[data-testid="stSidebarHeader"] img {{ height: 2.1rem !important; }}
.si-brand {{ display: flex; align-items: center; gap: .65rem; margin: .2rem 0 1rem 0; }}
.si-brand-mark {{
    width: 36px; height: 36px; border-radius: 10px; background: {ACCENT_GRADIENT};
    display: flex; align-items: center; justify-content: center; font-weight: 700; color: white;
    box-shadow: 0 6px 16px rgba(99, 102, 241, .35);
}}
.si-brand-name {{ font-weight: 700; font-size: 1.05rem; letter-spacing: .2px; }}
.si-brand-sub {{ font-size: .75rem; color: #94a3b8 !important; }}
.si-side-title {{
    font-size: .72rem; text-transform: uppercase; letter-spacing: .08em;
    color: #94a3b8 !important; margin: 1rem 0 .3rem 0; font-weight: 600;
}}

/* Page header */
.si-header {{ margin-bottom: 1.1rem; }}
.si-eyebrow {{
    display: inline-block; font-size: .72rem; font-weight: 600; letter-spacing: .08em;
    text-transform: uppercase; color: #a5b4fc; margin-bottom: .35rem;
}}
.si-header h1.si-title {{
    font-size: 1.9rem !important; font-weight: 700 !important; margin: 0 !important;
    padding: 0 !important; color: {t['text']}; line-height: 1.2 !important; letter-spacing: -0.01em;
}}
.si-header h1 a, .si-header [data-testid="stHeaderActionElements"] {{ display: none !important; }}
.si-subtitle {{ color: {t['muted']}; margin-top: .35rem; font-size: .95rem; }}
.si-chips {{ display: flex; flex-wrap: wrap; gap: .4rem; margin-top: .7rem; }}
.si-chip {{
    font-size: .78rem; padding: .22rem .6rem; border-radius: 999px;
    background: {t['panel_2']}; border: 1px solid {t['border']}; color: {t['muted']};
}}
.si-chip-accent {{ background: rgba(99, 102, 241, .15); color: #c7d2fe; border-color: rgba(99,102,241,.35); }}

/* KPI cards */
.si-kpi-grid {{
    display: grid; grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: .9rem; margin: .4rem 0 1.4rem 0;
}}
.si-kpi-grid.si-cols-4 {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
@media (max-width: 1250px) {{
    .si-kpi-grid, .si-kpi-grid.si-cols-4 {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
}}
@media (max-width: 760px) {{
    .si-kpi-grid, .si-kpi-grid.si-cols-4 {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
}}
.si-kpi {{
    position: relative; overflow: hidden;
    background: {t['panel']}; border: 1px solid {t['border']}; border-radius: 16px;
    padding: 1rem 1.1rem; box-shadow: {t['shadow']};
}}
.si-kpi::before {{
    content: ""; position: absolute; inset: 0 0 auto 0; height: 3px; background: {ACCENT_GRADIENT};
}}
.si-kpi-label {{ font-size: .8rem; color: {t['muted']}; font-weight: 500; }}
.si-kpi-value {{
    font-size: 1.55rem; font-weight: 700; color: {t['text']}; margin: .3rem 0 .25rem 0;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}
.si-kpi-delta {{ font-size: .8rem; font-weight: 600; }}
.si-kpi-delta span {{ color: {t['muted']}; font-weight: 400; }}
.si-up {{ color: {t['up']}; }}
.si-down {{ color: {t['down']}; }}
.si-flat {{ color: {t['muted']}; }}

/* Cards around charts: containers created with key="card-..." */
[class*="st-key-card"] {{
    background: {t['panel']}; border: 1px solid {t['border']} !important; border-radius: 16px;
    padding: 1rem 1.1rem .6rem 1.1rem; box-shadow: {t['shadow']};
}}
.si-card-title {{ font-weight: 600; font-size: 1rem; color: {t['text']}; margin: 0; }}
.si-card-sub {{ font-size: .8rem; color: {t['muted']}; margin: .15rem 0 .2rem 0; }}

/* Highlights */
.si-highlight {{
    border-left: 3px solid #6366f1; padding: .55rem .8rem; margin-bottom: .7rem;
    background: {t['panel_2']}; border-radius: 0 10px 10px 0;
}}
.si-highlight b {{ display: block; font-size: .8rem; color: #a5b4fc; margin-bottom: .15rem; }}
.si-highlight p {{ margin: 0; font-size: .9rem; color: {t['text']}; }}

/* Button rows (chart switches) wrap onto a second line instead of being cut off */
[data-testid="stButtonGroup"] > div {{ flex-wrap: wrap; row-gap: .4rem; }}

/* Recommendation cards */
.si-rec {{
    background: {t['panel']}; border: 1px solid {t['border']}; border-radius: 16px;
    padding: 1rem 1.15rem; margin-bottom: .9rem; box-shadow: {t['shadow']};
}}
.si-rec-head {{ display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; margin-bottom: .45rem; }}
.si-badge {{
    font-size: .7rem; font-weight: 600; padding: .15rem .55rem; border-radius: 999px;
    background: {t['panel_2']}; color: {t['muted']}; border: 1px solid {t['border']};
}}
.si-badge-p1 {{ background: {ACCENT_GRADIENT}; color: #fff; border: none; }}
.si-rec-title {{ font-weight: 650; font-size: 1.02rem; color: {t['text']}; }}
.si-rec p {{ margin: .3rem 0; font-size: .9rem; color: {t['text']}; line-height: 1.5; }}
.si-rec p b {{ color: #a5b4fc; font-weight: 600; }}

/* Empty state */
.si-empty {{
    text-align: center; padding: 3rem 1rem; border: 1px dashed {t['border']};
    border-radius: 16px; color: {t['muted']};
}}

footer {{ visibility: hidden; }}
@media (max-width: 640px) {{
    .si-title {{ font-size: 1.45rem; }}
    .si-kpi-value {{ font-size: 1.35rem; }}
    .block-container {{ padding-left: .8rem; padding-right: .8rem; }}
}}
</style>
""",
        unsafe_allow_html=True,
    )


def plotly_layout() -> dict:
    """Shared Plotly layout for the current theme (transparent background, Inter font)."""
    t = palette()
    axis = dict(gridcolor=t["grid"], zerolinecolor=t["grid"], linecolor=t["grid"], automargin=True,
                tickfont=dict(color=t["muted"], size=12), title_font=dict(color=t["muted"], size=12))
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", color=t["text"], size=13),
        colorway=SERIES,
        margin=dict(l=10, r=16, t=16, b=10, pad=4),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    font=dict(color=t["muted"], size=12), bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor=t["panel_2"], bordercolor=t["border"], font=dict(color=t["text"], size=12)),
        xaxis=axis,
        yaxis=axis,
        separators=".,",
    )
