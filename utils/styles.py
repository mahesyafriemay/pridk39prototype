"""
Design system DECIDE Decision Cockpit.
Font Poppins · navy / white / orange accent / teal (aman).
Komponen: header + kontrol dokumen, process tracker (PDCA), KPI card, badge,
tabel HTML ergonomis, meter, alert, stepper, tema chart Altair.
"""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

NAVY = "#0B1F3A"
NAVY_2 = "#16305A"
NAVY_3 = "#24467D"
ORANGE = "#F07F1E"
ORANGE_SOFT = "#FDEBD9"
TEAL = "#0E9F8A"
TEAL_SOFT = "#DDF3EE"
GREEN = "#2BA36B"
RED = "#D64545"
RED_SOFT = "#FBE3E3"
AMBER = "#E8A33D"
AMBER_SOFT = "#FCF0DA"
BG = "#F3F5F9"
TEXT = "#1B2A41"
MUTED = "#6B7A90"
BORDER = "#E3E8F0"
FONT = "Poppins"


def _stretch_kwargs() -> dict:
    """Kompatibilitas: Streamlit >= 1.49 memakai width="stretch", versi lama use_container_width."""
    try:
        major, minor = (int(x) for x in st.__version__.split(".")[:2])
    except Exception:  # noqa: BLE001
        return {"width": "stretch"}
    return {"width": "stretch"} if (major, minor) >= (1, 49) else {"use_container_width": True}


W = _stretch_kwargs()   # dipakai: st.dataframe(df, **W)

BADGE_COLORS = {
    "P1": RED, "P2": ORANGE, "P3": GREEN,
    "Risk": RED, "Watch": AMBER, "Normal": TEAL,
    "LAYAK": TEAL, "HOLD": RED,
    "Material Shortage": RED, "Supplier ETA Risk": AMBER, "Material Ready": TEAL,
    "On time": TEAL, "Late": RED, "Tercapai": TEAL, "Tidak tercapai": RED,
    "Open": RED, "Closed": TEAL, "Material": RED, "Kapasitas": AMBER, "Delay": ORANGE,
    "Lebih baik": TEAL, "Lebih buruk": RED,
}
CLASS_SCALE = {"domain": ["P1", "P2", "P3"], "range": [RED, ORANGE, GREEN]}
STATUS_SCALE = {"domain": ["Risk", "Watch", "Normal"], "range": [RED, AMBER, TEAL]}

# ---------------------------------------------------------------------------
# Ikon (garis, gaya feather) — inline SVG agar ringan & konsisten
# ---------------------------------------------------------------------------
_ICON_PATHS = {
    "alert": '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    "box": '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "refresh": '<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>',
    "layers": '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>',
    "check": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
    "trend": '<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>',
    "money": '<line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
    "truck": '<rect x="1" y="3" width="15" height="13"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>',
    "stop": '<polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>',
    "zap": '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "doc": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    "list": '<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>',
}


def icon(name: str, color: str = "currentColor", size: int = 18) -> str:
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{_ICON_PATHS.get(name, "")}</svg>')


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap');
html, body, .stApp {{ font-family:'{FONT}', sans-serif; }}
.stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5,
.stApp button, .stApp input, .stApp textarea, .stApp td, .stApp th, .stApp small,
.stApp span:not([data-testid="stIconMaterial"]):not(.material-symbols-rounded),
[data-testid="stMarkdownContainer"] *, [data-testid="stMetricValue"], [data-testid="stMetricLabel"] *,
[data-testid="stMetricDelta"] *, [data-baseweb="select"] *, [data-baseweb="tab"] * {{
    font-family:'{FONT}', sans-serif !important; }}
.stApp {{ background:{BG}; color:{TEXT}; }}
.block-container {{ padding-top:1rem; padding-bottom:2.5rem; max-width:1440px; }}
header[data-testid="stHeader"] {{ background:transparent; }}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {{ background:linear-gradient(180deg,{NAVY} 0%,#0E2748 100%); }}
section[data-testid="stSidebar"] * {{ color:#E8EDF5; }}
section[data-testid="stSidebar"] [data-baseweb="select"] * {{ color:{TEXT} !important; }}
section[data-testid="stSidebar"] [role="radiogroup"] {{ gap:2px; }}
section[data-testid="stSidebar"] [role="radiogroup"] label {{
    padding:8px 12px; border-radius:10px; width:100%; transition:background .15s; }}
section[data-testid="stSidebar"] [role="radiogroup"] label:hover {{ background:{NAVY_2}; }}
section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {{
    background:{NAVY_3}; box-shadow:inset 3px 0 0 {ORANGE}; }}
section[data-testid="stSidebar"] [role="radiogroup"] label > div:first-child {{ display:none; }}
section[data-testid="stSidebar"] hr {{ border-color:#25426C; margin:10px 0; }}
.dc-brand {{ display:flex; align-items:center; gap:10px; margin:0 0 2px 0; }}
.dc-logo {{ width:38px; height:38px; border-radius:11px; background:linear-gradient(135deg,{ORANGE},#F7A55A);
    display:flex; align-items:center; justify-content:center; font-weight:800; color:#fff; font-size:1.1rem; }}
.dc-brand-t {{ font-size:1.35rem; font-weight:800; letter-spacing:.08em; color:#fff; line-height:1; }}
.dc-brand-s {{ font-size:.62rem; letter-spacing:.12em; color:#9FB0CC !important; }}
.dc-role {{ background:{NAVY_2}; border-radius:12px; padding:10px 12px; margin:8px 0 2px; display:flex; gap:10px; align-items:center; }}
.dc-avatar {{ width:34px; height:34px; border-radius:50%; background:{TEAL}; display:flex; align-items:center;
    justify-content:center; font-weight:700; font-size:.8rem; color:#fff !important; }}
.dc-role .lbl {{ font-size:.62rem; text-transform:uppercase; letter-spacing:.1em; color:#9FB0CC !important; }}
.dc-role .val {{ font-size:.86rem; font-weight:600; }}
.dc-side-kv {{ display:flex; justify-content:space-between; font-size:.74rem; padding:5px 2px; border-bottom:1px dashed #25426C; }}
.dc-side-kv b {{ color:#fff; font-weight:600; }}
.dc-side-note {{ font-size:.68rem; color:#F7C99A !important; background:rgba(240,127,30,.12); border-radius:8px; padding:7px 9px; margin-top:10px; }}

/* ---------- Process tracker ---------- */
.dc-flow-wrap {{ overflow-x:auto; margin:0 0 14px 0; }}
.dc-pdca {{ display:flex; gap:4px; margin-bottom:4px; min-width:980px; }}
.dc-pdca div {{ font-size:.6rem; font-weight:700; letter-spacing:.14em; text-align:center; padding:2px 0;
    border-radius:6px; color:{MUTED}; background:#E8ECF3; }}
.dc-flow {{ display:flex; gap:4px; min-width:980px; }}
.dc-st {{ flex:1; position:relative; background:#fff; border:1px solid {BORDER}; border-radius:12px; padding:8px 10px 8px 12px; }}
.dc-st .c {{ font-size:.6rem; font-weight:700; color:{MUTED}; letter-spacing:.1em; display:flex; justify-content:space-between; align-items:center; }}
.dc-st .t {{ font-size:.8rem; font-weight:600; color:{NAVY}; margin-top:1px; white-space:nowrap; }}
.dc-st .v {{ font-size:.7rem; color:{MUTED}; margin-top:1px; white-space:nowrap; }}
.dc-st .dot {{ width:8px; height:8px; border-radius:50%; display:inline-block; }}
.dc-st.on {{ background:{NAVY}; border-color:{NAVY}; box-shadow:0 6px 16px rgba(11,31,58,.18); }}
.dc-st.on .t {{ color:#fff; }} .dc-st.on .c, .dc-st.on .v {{ color:#B9C6DB; }}
.dc-st.on::after {{ content:''; position:absolute; left:12px; right:12px; bottom:-1px; height:3px; border-radius:3px; background:{ORANGE}; }}

/* ---------- Header + kontrol dokumen ---------- */
.dc-head {{ display:flex; justify-content:space-between; align-items:flex-end; gap:16px; margin:2px 0 14px; }}
.dc-code {{ display:inline-block; font-size:.66rem; font-weight:700; color:{ORANGE}; letter-spacing:.14em;
    background:{ORANGE_SOFT}; padding:2px 8px; border-radius:6px; }}
.dc-title {{ font-size:1.65rem; font-weight:700; color:{NAVY}; line-height:1.2; margin-top:6px; }}
.dc-desc {{ font-size:.84rem; color:{MUTED}; margin-top:2px; }}
.dc-docctl {{ display:grid; grid-template-columns:repeat(2, auto); gap:2px 14px; font-size:.66rem; color:{MUTED};
    background:#fff; border:1px solid {BORDER}; border-radius:10px; padding:8px 12px; white-space:nowrap; }}
.dc-docctl b {{ color:{NAVY}; font-weight:600; }}

/* ---------- Cards ---------- */
.dc-card {{ background:#fff; border:1px solid {BORDER}; border-radius:16px; padding:16px 18px;
    box-shadow:0 1px 2px rgba(11,31,58,.04); min-height:104px; box-sizing:border-box; }}
.dc-kpi {{ display:flex; gap:14px; align-items:flex-start; transition:transform .15s, box-shadow .15s; }}
.dc-kpi:hover {{ transform:translateY(-2px); box-shadow:0 10px 22px rgba(11,31,58,.08); }}
.dc-kpi .ic {{ width:42px; height:42px; min-width:42px; border-radius:12px; display:flex; align-items:center; justify-content:center; }}
.dc-kpi .k-label {{ font-size:.7rem; text-transform:uppercase; letter-spacing:.07em; color:{MUTED}; font-weight:600; }}
.dc-kpi .k-value {{ font-size:1.75rem; font-weight:700; color:{NAVY}; line-height:1.15; margin-top:2px; }}
.dc-kpi .k-sub {{ font-size:.74rem; color:{MUTED}; margin-top:1px; }}
.dc-sec {{ display:flex; align-items:center; gap:8px; font-size:.95rem; font-weight:600; color:{NAVY}; margin:20px 0 10px; }}
.dc-sec .bar {{ width:4px; height:18px; border-radius:4px; background:{ORANGE}; }}
.dc-sec .hint {{ font-size:.72rem; font-weight:400; color:{MUTED}; margin-left:4px; }}
.dc-hero {{ background:linear-gradient(120deg,{NAVY} 0%,{NAVY_3} 70%,#2F5A9A 100%); border-radius:20px; padding:20px 24px;
    color:#fff; display:flex; justify-content:space-between; align-items:center; gap:18px; margin-bottom:14px; }}
.dc-hero .h1 {{ font-size:1.45rem; font-weight:700; color:#fff; }}
.dc-hero .h2 {{ font-size:.84rem; color:#C8D4E8; margin-top:2px; }}
.dc-hero .chips {{ display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; }}
.dc-hero .chip {{ background:rgba(255,255,255,.1); border:1px solid rgba(255,255,255,.18); border-radius:12px; padding:8px 12px; min-width:110px; }}
.dc-hero .chip .l {{ font-size:.6rem; letter-spacing:.1em; text-transform:uppercase; color:#B9C6DB; }}
.dc-hero .chip .n {{ font-size:1.05rem; font-weight:700; color:#fff; }}

/* ---------- Badges ---------- */
.dc-badge {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:.7rem; font-weight:600; white-space:nowrap; }}
.dc-pill {{ display:inline-block; padding:3px 10px; border-radius:999px; font-size:.7rem; font-weight:500;
    border:1px solid {BORDER}; background:#fff; color:{MUTED}; }}

/* ---------- HTML table ---------- */
.dc-tw {{ background:#fff; border:1px solid {BORDER}; border-radius:14px; overflow:auto; }}
table.dc-t {{ width:100%; border-collapse:separate; border-spacing:0; font-size:.8rem; }}
table.dc-t th {{ position:sticky; top:0; background:#F7F9FC; color:{MUTED}; font-weight:600; font-size:.68rem;
    text-transform:uppercase; letter-spacing:.05em; text-align:left; padding:10px 12px; border-bottom:1px solid {BORDER}; white-space:nowrap; }}
table.dc-t td {{ padding:9px 12px; border-bottom:1px solid #EEF1F6; color:{TEXT}; vertical-align:middle; }}
table.dc-t tr:last-child td {{ border-bottom:none; }}
table.dc-t tr:hover td {{ background:#FAFBFD; }}
table.dc-t td.num, table.dc-t th.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
table.dc-t td.key {{ font-weight:600; color:{NAVY}; white-space:nowrap; }}
table.dc-t td.sub {{ color:{MUTED}; font-size:.76rem; }}

/* ---------- Alerts, meter, stepper ---------- */
.dc-alert {{ display:flex; gap:10px; align-items:flex-start; padding:10px 12px; border-radius:12px; background:#fff;
    border:1px solid {BORDER}; margin-bottom:8px; font-size:.8rem; }}
.dc-alert .ic {{ min-width:30px; height:30px; border-radius:9px; display:flex; align-items:center; justify-content:center; }}
.dc-alert b {{ color:{NAVY}; font-weight:600; }} .dc-alert .s {{ color:{MUTED}; }}
.dc-meter {{ margin:6px 0 12px; }}
.dc-meter .top {{ display:flex; justify-content:space-between; font-size:.76rem; color:{MUTED}; margin-bottom:4px; }}
.dc-meter .top b {{ color:{NAVY}; font-weight:600; }}
.dc-meter .track {{ height:9px; background:#E8ECF3; border-radius:9px; overflow:hidden; }}
.dc-meter .fill {{ height:100%; border-radius:9px; }}
.dc-steps {{ display:flex; gap:10px; margin:4px 0 14px; }}
.dc-step {{ flex:1; background:#fff; border:1px solid {BORDER}; border-radius:14px; padding:12px 14px; display:flex; gap:10px; align-items:center; }}
.dc-step .n {{ width:30px; height:30px; min-width:30px; border-radius:50%; display:flex; align-items:center; justify-content:center;
    font-weight:700; font-size:.8rem; color:#fff; }}
.dc-step .s-t {{ font-size:.8rem; font-weight:600; color:{NAVY}; line-height:1.2; }}
.dc-step .s-st {{ font-size:.7rem; margin-top:2px; }}
.dc-banner {{ border-radius:14px; padding:12px 16px; font-weight:600; font-size:.95rem; color:#fff; margin:4px 0 12px;
    display:flex; align-items:center; gap:10px; }}
.dc-trig {{ display:grid; grid-template-columns:repeat(5,1fr); gap:10px; }}
.dc-trig .it {{ background:#fff; border:1px solid {BORDER}; border-radius:14px; padding:12px; }}
.dc-trig .it.on {{ border-color:{RED}; background:{RED_SOFT}; }}
.dc-trig .nm {{ font-size:.78rem; font-weight:600; color:{NAVY}; margin-top:6px; }}
.dc-trig .dt {{ font-size:.68rem; color:{MUTED}; }}
.dc-foot {{ margin-top:28px; padding-top:10px; border-top:1px solid {BORDER}; font-size:.68rem; color:{MUTED};
    display:flex; justify-content:space-between; }}

div[data-testid="stMetric"] {{ background:#fff; border:1px solid {BORDER}; border-radius:14px; padding:12px 16px; }}
div[data-testid="stMetricValue"] {{ font-weight:700; color:{NAVY}; }}
.stTabs [data-baseweb="tab-list"] {{ gap:6px; }}
.stTabs [data-baseweb="tab"] {{ background:#fff; border:1px solid {BORDER}; border-radius:10px; padding:6px 14px; font-weight:500; }}
.stTabs [aria-selected="true"] {{ background:{NAVY}; color:#fff !important; }}
.stTabs [aria-selected="true"] * {{ color:#fff !important; }}
.stButton button[kind="primary"], .stFormSubmitButton button[kind="primary"] {{ background:{ORANGE}; border-color:{ORANGE}; font-weight:600; }}
div[data-testid="stExpander"] details {{ background:#fff; border-radius:12px; border:1px solid {BORDER}; }}
@media (max-width: 900px) {{ .dc-trig {{ grid-template-columns:repeat(2,1fr); }} .dc-head {{ flex-direction:column; align-items:flex-start; }} }}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def _md(h: str):
    st.markdown(h, unsafe_allow_html=True)


def _soft(color: str) -> str:
    return {RED: RED_SOFT, ORANGE: ORANGE_SOFT, TEAL: TEAL_SOFT, AMBER: AMBER_SOFT, GREEN: TEAL_SOFT}.get(color, "#E8ECF3")


def badge(text: str, color: str | None = None) -> str:
    c = color or BADGE_COLORS.get(str(text))
    if c is None and str(text).startswith("FLAG"):
        c = RED
    c = c or NAVY
    return f'<span class="dc-badge" style="background:{_soft(c)};color:{c}">{html.escape(str(text))}</span>'


# ---------------------------------------------------------------------------
# Header, tracker, hero
# ---------------------------------------------------------------------------
def page_header(code: str, title: str, desc: str, users: str, rev: int = 0, plan_status: str = "DRAFT"):
    """Header halaman + blok kontrol dokumen (ISO 9001 klausul 7.5 — documented information)."""
    _md(f"""<div class="dc-head"><div><span class="dc-code">{code}</span>
<div class="dc-title">{html.escape(title)}</div><div class="dc-desc">{html.escape(desc)}</div></div>
<div class="dc-docctl"><span>No. Dok <b>DEC-FRM-{code}</b></span><span>Revisi <b>{rev:02d}</b></span>
<span>Snapshot <b>09 Nov 2026</b></span><span>Status <b>{html.escape(plan_status)}</b></span>
<span>User <b>{html.escape(users)}</b></span><span><b style="color:{ORANGE}">Dummy Data</b></span></div></div>""")


def process_tracker(active: str, stages: list[dict]):
    """stages: dict(code, title, value, alert:bool, phase)."""
    phases = []
    for s in stages:
        if not phases or phases[-1][0] != s["phase"]:
            phases.append([s["phase"], 0])
        phases[-1][1] += 1
    pdca = "".join(f'<div style="flex:{n}">{p}</div>' for p, n in phases)
    items = []
    for s in stages:
        dot = RED if s["alert"] else TEAL
        items.append(f'<div class="dc-st {"on" if s["code"] == active else ""}"><div class="c">{s["code"]}'
                     f'<span class="dot" style="background:{dot}"></span></div><div class="t">{html.escape(s["title"])}</div>'
                     f'<div class="v">{html.escape(s["value"])}</div></div>')
    _md(f'<div class="dc-flow-wrap"><div class="dc-pdca">{pdca}</div><div class="dc-flow">{"".join(items)}</div></div>')


def hero(title: str, subtitle: str, chips: list[tuple[str, str]]):
    c = "".join(f'<div class="chip"><div class="l">{html.escape(l)}</div><div class="n">{html.escape(str(v))}</div></div>'
                for l, v in chips)
    _md(f'<div class="dc-hero"><div><div class="h1">{html.escape(title)}</div><div class="h2">{html.escape(subtitle)}</div></div>'
        f'<div class="chips">{c}</div></div>')


def section(title: str, hint: str = ""):
    h = f'<span class="hint">{html.escape(hint)}</span>' if hint else ""
    _md(f'<div class="dc-sec"><span class="bar"></span>{html.escape(title)}{h}</div>')


def kpi_card(label: str, value, sub: str = "", accent: str = NAVY, ico: str = "layers"):
    _md(f'<div class="dc-card dc-kpi"><div class="ic" style="background:{_soft(accent)}">{icon(ico, accent, 20)}</div>'
        f'<div><div class="k-label">{html.escape(label)}</div><div class="k-value">{html.escape(str(value))}</div>'
        f'<div class="k-sub">{sub}</div></div></div>')


def alert_row(title: str, body: str, color: str, ico: str = "alert"):
    _md(f'<div class="dc-alert"><div class="ic" style="background:{_soft(color)}">{icon(ico, color, 16)}</div>'
        f'<div><b>{html.escape(title)}</b><br><span class="s">{html.escape(body)}</span></div></div>')


def meter(label: str, value: float, maximum: float, color: str = TEAL, text: str | None = None):
    pct = 0 if maximum <= 0 else max(0.0, min(1.0, value / maximum))
    _md(f'<div class="dc-meter"><div class="top"><span>{html.escape(label)}</span><b>{html.escape(text or f"{pct:.0%}")}</b></div>'
        f'<div class="track"><div class="fill" style="width:{pct * 100:.1f}%;background:{color}"></div></div></div>')


def banner(text: str, color: str, ico: str = "check"):
    _md(f'<div class="dc-banner" style="background:{color}">{icon(ico, "#fff", 20)}{html.escape(text)}</div>')


def stepper(steps: list[tuple[str, str, str]]):
    parts = []
    for i, (title, st_text, state) in enumerate(steps, 1):
        color = {"done": TEAL, "active": ORANGE, "blocked": RED}.get(state, "#C3CCDA")
        mark = "✓" if state == "done" else ("!" if state == "blocked" else str(i))
        parts.append(f'<div class="dc-step"><div class="n" style="background:{color}">{mark}</div><div>'
                     f'<div class="s-t">{html.escape(title)}</div><div class="s-st" style="color:{color}">{html.escape(st_text)}</div></div></div>')
    _md(f'<div class="dc-steps">{"".join(parts)}</div>')


def triggers_grid(trigs: list[dict]):
    icmap = {"Material berubah": "box", "Demand meningkat": "trend", "Supplier delay": "truck",
             "Kapasitas turun": "zap", "KPI lewat threshold": "target"}
    items = "".join(
        f'<div class="it {"on" if t["on"] else ""}">{icon(icmap.get(t["name"], "alert"), RED if t["on"] else TEAL, 20)}'
        f'<div class="nm">{html.escape(t["name"])}</div><div class="dt">{html.escape(t["detail"])}</div></div>'
        for t in trigs)
    _md(f'<div class="dc-trig">{items}</div>')


def footer():
    _md('<div class="dc-foot"><span>DECIDE Decision Cockpit · Prototype TI4001 Kelompok 39 · Prototype / Dummy Data</span>'
        '<span>Selaras prinsip ISO 9001:2015 — 6.2 · 7.5 · 8.5.6 · 9.1 · 10.2 (bukan klaim sertifikasi)</span></div>')


# ---------------------------------------------------------------------------
# Tabel
# ---------------------------------------------------------------------------
def html_table(df: pd.DataFrame, badges=(), fmt: dict | None = None, labels: dict | None = None,
               key_col: str | None = None, sub_cols=(), max_height: int | None = None):
    """Tabel HTML ringkas: angka rata kanan, badge berwarna, header sticky."""
    fmt, labels = fmt or {}, labels or {}
    cols = list(df.columns)
    num_cols = {c for c in cols if pd.api.types.is_numeric_dtype(df[c]) and c not in badges}
    head = "".join(f'<th class="{"num" if c in num_cols else ""}">{html.escape(labels.get(c, c.replace("_", " ")))}</th>' for c in cols)
    body = []
    for _, r in df.iterrows():
        tds = []
        for c in cols:
            v = r[c]
            if c in badges:
                cell = badge(v) if v not in (None, "", "-") and not (isinstance(v, float) and pd.isna(v)) else "-"
            elif c in fmt:
                cell = html.escape(fmt[c](v) if callable(fmt[c]) else fmt[c].format(v))
            elif isinstance(v, float) and pd.isna(v):
                cell = "-"
            else:
                cell = html.escape(str(v))
            cls = "num" if c in num_cols else ("key" if c in (key_col, "SKU", "SKU_ID") else ("sub" if c in sub_cols else ""))
            tds.append(f'<td class="{cls}">{cell}</td>')
        body.append("<tr>" + "".join(tds) + "</tr>")
    style = f' style="max-height:{max_height}px"' if max_height else ""
    _md(f'<div class="dc-tw"{style}><table class="dc-t"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


def _badge_css(v):
    c = BADGE_COLORS.get(str(v))
    if c is None and str(v).startswith("FLAG TERLAMBAT"):
        c = RED
    return "" if c is None else f"background-color:{_soft(c)}; color:{c}; font-weight:600;"


def style_table(df: pd.DataFrame, badge_cols=(), formats: dict | None = None):
    """Styler untuk st.dataframe (tabel panjang yang perlu sort/scroll)."""
    sty = df.style
    cols = [c for c in badge_cols if c in df.columns]
    if cols:
        sty = sty.map(_badge_css, subset=cols)
    if formats:
        sty = sty.format({k: v for k, v in formats.items() if k in df.columns}, na_rep="-")
    return sty


# ---------------------------------------------------------------------------
# Tema chart Altair
# ---------------------------------------------------------------------------
def chart(c, height: int = 300):
    return (c.properties(height=height)
            .configure(font=FONT, background="transparent")
            .configure_view(strokeWidth=0)
            .configure_axis(labelFont=FONT, titleFont=FONT, labelColor=MUTED, titleColor=MUTED, labelFontSize=11,
                            titleFontSize=11, titleFontWeight=500, gridColor="#EDF0F5", domainColor=BORDER, tickColor=BORDER)
            .configure_legend(labelFont=FONT, titleFont=FONT, labelColor=TEXT, titleColor=MUTED, labelFontSize=11,
                              symbolType="circle", orient="top")
            .configure_title(font=FONT, color=NAVY, fontSize=13, fontWeight=600, anchor="start"))
