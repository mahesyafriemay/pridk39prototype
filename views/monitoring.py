"""H08 — Performance Monitoring (PPC, Leader Produksi) + elemen mutu ISO 9001 (6.2, 9.1, 10.2)."""
import altair as alt
import pandas as pd
import streamlit as st

from engine import approval_engine as ap
from engine import config as cfg
from engine.quality_engine import nonconformities, quality_objectives, replanning_triggers
from engine.scenario_engine import no_production_kpis
from utils import state
from utils.helpers import fmt_dec, fmt_rp
from utils.styles import (AMBER, GREEN, NAVY, ORANGE, RED, TEAL, W, banner, chart, html_table, kpi_card, section,
                          triggers_grid)


def render():
    state.header("Performance", "Check & Act: KPI rencana, sasaran mutu, ketidaksesuaian, dan pemicu replanning.")
    ss = st.session_state
    wf = ss.workflow
    res = state.active_result()
    base = state.baseline_result()
    approved = wf["status"] in (ap.APPROVED, ap.RELEASED) and ss.approved_kpi
    k = ss.approved_kpi if approved else res["kpi"]
    st.caption(f"KPI untuk: **{'Approved Plan Rev. %02d' % wf['version'] if approved else f'rencana aktif ({ss.selected_scenario}) — belum approved'}**")

    rev_cost = wf["revisions"] * cfg.REVISION_COST_PER_EVENT
    c = st.columns(6)
    cards = [("Stockout Risk", k["stockout_risk"], "terlambat / HOLD P1", RED, "alert"),
             ("Overstock Risk", k["overstock_risk"], "posisi > Max", AMBER, "box"),
             ("Delay", k["delayed_orders"], f"{fmt_dec(k['total_delay_days'], 1)} hari", ORANGE, "clock"),
             ("Inventory Value", fmt_rp(k["inventory_value"]), "(NIP + produksi) × COGS", NAVY, "money"),
             ("Revision Cost", fmt_rp(rev_cost), f"{wf['revisions']} revisi", NAVY, "refresh"),
             ("Revisions", wf["revisions"], f"Rev. dokumen {wf['version']:02d}", TEAL, "doc")]
    for col, (lbl, v, sub, color, ico) in zip(c, cards):
        with col:
            kpi_card(lbl, v, sub, color, ico)

    # Sasaran mutu ------------------------------------------------------------
    qo = quality_objectives(k, wf["revisions"], len(state.get_data_issues()))
    left, right = st.columns([1.25, 1])
    with left:
        section("Sasaran Mutu", "ISO 9001 · 6.2 & 9.1 — target dummy, perlu divalidasi")
        html_table(qo[["Sasaran", "Indikator", "Target", "Aktual", "Status"]], badges=("Status",), key_col="Sasaran",
                   sub_cols=("Indikator",))
    with right:
        section("Pencapaian")
        n_ok = int((qo["Status"] == "Tercapai").sum())
        dd = pd.DataFrame({"Status": ["Tercapai", "Tidak tercapai"], "n": [n_ok, len(qo) - n_ok]})
        donut = alt.Chart(dd).mark_arc(innerRadius=70, cornerRadius=4, padAngle=0.03).encode(
            theta="n:Q", color=alt.Color("Status:N", scale=alt.Scale(domain=["Tercapai", "Tidak tercapai"], range=[TEAL, RED]),
                                         legend=alt.Legend(title=None)), tooltip=["Status", "n"])
        txt = alt.Chart(pd.DataFrame({"t": [f"{n_ok}/{len(qo)}"]})).mark_text(fontSize=26, fontWeight=700, color=NAVY).encode(text="t:N")
        st.altair_chart(chart(donut + txt, 260), **W)

    # Scenario comparison ----------------------------------------------------
    section("Scenario Comparison")
    cols = {"Tanpa rencana": no_production_kpis(base), "Baseline": base["kpi"]}
    if approved:
        cols["Approved Plan"] = ss.approved_kpi
    elif ss.alt_ran:
        cols["Alternative"] = state.result_for("Alternative")["kpi"]
    metrics = [("Stockout", "stockout_risk"), ("Overstock", "overstock_risk"), ("Delayed orders", "delayed_orders")]
    long = pd.DataFrame([{"Skenario": n, "KPI": lbl, "Nilai": d.get(key) or 0} for n, d in cols.items() for lbl, key in metrics])
    inv = pd.DataFrame([{"Skenario": n, "Nilai": d["inventory_value"] / 1e9} for n, d in cols.items()])
    palette = alt.Scale(domain=list(cols), range=["#C3CCDA", NAVY, ORANGE][:len(cols)])
    l2, r2 = st.columns([1.3, 1])
    with l2:
        ch = alt.Chart(long).mark_bar(cornerRadiusEnd=4, size=12).encode(
            y=alt.Y("KPI:N", title=None), yOffset=alt.YOffset("Skenario:N", sort=list(cols)),
            x=alt.X("Nilai:Q", title="Jumlah SKU / order", axis=alt.Axis(tickMinStep=1)),
            color=alt.Color("Skenario:N", scale=palette, sort=list(cols), legend=alt.Legend(title=None)),
            tooltip=["Skenario", "KPI", "Nilai"])
        st.altair_chart(chart(ch, 260), **W)
    with r2:
        ch = alt.Chart(inv).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6, size=46).encode(
            x=alt.X("Skenario:N", sort=list(cols), title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Nilai:Q", title="Nilai inventori (Rp miliar)"),
            color=alt.Color("Skenario:N", scale=palette, legend=None),
            tooltip=["Skenario", alt.Tooltip("Nilai:Q", format=".2f")])
        st.altair_chart(chart(ch, 260), **W)

    # NC / CAPA -----------------------------------------------------------------
    section("Ketidaksesuaian & Tindakan Korektif", "ISO 9001 · 10.2")
    nc = nonconformities(res)
    if nc.empty:
        st.success("Tidak ada ketidaksesuaian pada rencana aktif.")
    else:
        html_table(nc, badges=("Kategori", "Kelas", "Status"), key_col="NC_ID", sub_cols=("Tindakan korektif",),
                   labels={"NC_ID": "No. NC"})

    # Trigger replanning --------------------------------------------------------
    section("Trigger Replanning", "ISO 9001 · 6.3 pengendalian perubahan")
    trig = replanning_triggers(res, state.get_data(), len(ss.material_feedback))
    fired = sum(t["on"] for t in trig)
    banner(f"PERLU REPLANNING — {fired} pemicu aktif" if fired else "Tidak perlu replanning",
           RED if fired else GREEN, "alert" if fired else "check")
    triggers_grid(trig)
    if fired and ss.role == state.PPC:
        st.write("")
        st.button("↻ Mulai replanning di H06 What-if", type="primary", on_click=state.go_to, args=("What-if",))
