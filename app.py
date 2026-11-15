"""
Integrated DECIDE Decision Cockpit — Dynamic Demand to Production Decision System
TI4001 Proyek Rekayasa Inter-Disiplin ITB — Kelompok 39

Prototype MVP. Seluruh data adalah Prototype / Dummy Data dan tidak
terhubung ke SAP maupun sistem PT Paragon.

Jalankan:  streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="DECIDE Decision Cockpit", page_icon="🧭", layout="wide",
                   initial_sidebar_state="expanded")

from engine import approval_engine as ap  # noqa: E402
from utils import state  # noqa: E402
from utils.styles import footer, inject_css, process_tracker  # noqa: E402
from views import (approval, demand_buffer, feasibility, monitoring, overview, priority,  # noqa: E402
                   scenario, sequencing)

RENDER = {
    "Overview": overview.render,
    "Demand & Buffer": demand_buffer.render,
    "Priority": priority.render,
    "Feasibility": feasibility.render,
    "Sequencing & ETA": sequencing.render,
    "What-if": scenario.render,
    "Decision Review": approval.render,
    "Performance": monitoring.render,
}
INITIALS = {state.PPC: "PPC", state.SUPPLY: "SP", state.LEADER: "LP"}

state.init_state()
inject_css()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="dc-brand"><div class="dc-logo">D</div><div><div class="dc-brand-t">DECIDE</div>'
                '<div class="dc-brand-s">DEMAND → PRODUCTION COCKPIT</div></div></div>', unsafe_allow_html=True)
    st.markdown("---")
    st.selectbox("Select Role", state.ROLES, key="role")
    role = st.session_state.role
    st.markdown(f'<div class="dc-role"><div class="dc-avatar">{INITIALS[role]}</div><div>'
                f'<div class="lbl">Current Role</div><div class="val">{role}</div></div></div>', unsafe_allow_html=True)

    pages = state.allowed_pages(role)
    if st.session_state.nav not in pages:
        st.session_state.nav = "Overview"
    st.markdown("---")
    st.radio("Menu", pages, key="nav", format_func=lambda p: f"{state.PAGES[p][0]}   {p}",
             label_visibility="collapsed")
    st.markdown("---")

    wf = st.session_state.workflow
    st.markdown(
        f'<div class="dc-side-kv"><span>Skenario aktif</span><b>{st.session_state.selected_scenario}</b></div>'
        f'<div class="dc-side-kv"><span>Status jadwal</span><b>{wf["status"].replace("_", " ").title()}</b></div>'
        f'<div class="dc-side-kv"><span>Revisi dokumen</span><b>Rev. {wf["version"]:02d}</b></div>'
        f'<div class="dc-side-kv"><span>Siklus produksi</span><b>16–20 Nov 2026</b></div>'
        f'<div class="dc-side-note">Prototype / Dummy Data · tidak terhubung SAP</div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Halaman
# ---------------------------------------------------------------------------
if st.session_state.get("flash"):
    st.toast(st.session_state.pop("flash"), icon="✅")
process_tracker(state.PAGES[st.session_state.nav][0], state.tracker_stages())
RENDER[st.session_state.nav]()
footer()
