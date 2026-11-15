"""H01 — Overview & Early Warning (PPC, Supply Planner, Leader Produksi)."""
import altair as alt
import pandas as pd
import streamlit as st

from engine import approval_engine as ap
from engine.quality_engine import quality_objectives
from utils import state
from utils.helpers import fmt_dt, fmt_int, fmt_rp
from utils.styles import (AMBER, NAVY, ORANGE, RED, STATUS_SCALE, TEAL, W, alert_row, chart, hero, html_table,
                          kpi_card, meter, section)


def render():
    res = state.active_result()
    kpi, buf, sch, mat, feas = res["kpi"], res["buffer"], res["schedule"], res["material"], res["feasibility"]
    wf = st.session_state.workflow
    issues = state.get_data_issues()
    qo = quality_objectives(kpi, wf["revisions"], len(issues))

    hero("Production Decision Cockpit",
         f"Siklus 16–20 Nov 2026 · skenario {st.session_state.selected_scenario} · "
         f"{'data valid' if not issues else f'{len(issues)} isu data'}",
         [("Qty direncanakan", fmt_int(kpi["planned_qty"])), ("Jam line", f"{kpi['line_hours']:.1f}"),
          ("Nilai inventori", fmt_rp(kpi["inventory_value"])),
          ("Sasaran mutu", f"{(qo['Status'] == 'Tercapai').sum()}/{len(qo)}")])
    if issues:
        st.error("Data issue: " + " · ".join(issues))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Risk of Stockout", kpi["risk_skus"], f"NIP ≤ ROP · {kpi['watch_skus']} Watch", RED, "alert")
    with c2:
        kpi_card("Overstock", kpi["overstock_skus"], "NIP > Max Level", AMBER, "box")
    with c3:
        kpi_card("Potensi Delay", kpi["delayed_orders"] + kpi["hold"],
                 f"{kpi['delayed_orders']} ETA lewat · {kpi['hold']} HOLD", ORANGE, "clock")
    with c4:
        kpi_card("Schedule Revision", wf["revisions"], ap.STATUS_LABEL[wf["status"]].split(" — ")[0], NAVY, "refresh")

    # Early warning ------------------------------------------------------------
    left, right = st.columns([1, 2.1])
    with left:
        section("Status Buffer")
        cnt = buf["Status"].value_counts().reindex(["Risk", "Watch", "Normal"]).fillna(0).reset_index()
        cnt.columns = ["Status", "SKU"]
        donut = alt.Chart(cnt).mark_arc(innerRadius=62, cornerRadius=4, padAngle=0.02).encode(
            theta="SKU:Q", color=alt.Color("Status:N", scale=alt.Scale(**STATUS_SCALE), legend=alt.Legend(title=None)),
            tooltip=["Status", "SKU"])
        center = alt.Chart(pd.DataFrame({"t": [f"{len(buf)} SKU"]})).mark_text(
            fontSize=20, fontWeight=700, color=NAVY).encode(text="t:N")
        st.altair_chart(chart(donut + center, 250), **W)
    with right:
        section("Days of Cover vs Lead Time Produksi + QC", "batang < penanda = stok habis sebelum produksi selesai")
        d = buf.sort_values("Days_of_Cover")
        bars = alt.Chart(d).mark_bar(cornerRadiusEnd=5, size=14).encode(
            y=alt.Y("SKU_ID:N", sort=list(d["SKU_ID"]), title=None),
            x=alt.X("Days_of_Cover:Q", title="Hari"),
            color=alt.Color("Status:N", scale=alt.Scale(**STATUS_SCALE), legend=None),
            tooltip=["SKU_ID", "Nama_Produk", alt.Tooltip("Days_of_Cover:Q", format=".1f"), "Prod_QC_LT", "Status"])
        tick = alt.Chart(d).mark_tick(color=NAVY, thickness=2.5, size=20).encode(
            y=alt.Y("SKU_ID:N", sort=list(d["SKU_ID"])), x="Prod_QC_LT:Q")
        st.altair_chart(chart(bars + tick, 290), **W)

    # Material & jadwal ----------------------------------------------------------
    left, right = st.columns([1, 1.5])
    with left:
        section("Material Alert")
        hold = feas[feas["Status"] == "HOLD"] if not feas.empty else pd.DataFrame()
        for _, h in hold.iterrows():
            alert_row(f"HOLD · {h['SKU_ID']} ({h['Priority_Class']})", h["Reason"], RED, "stop")
        for _, m in mat[mat["Alert"] == "Supplier ETA Risk"].iterrows():
            eta = m["Supplier_ETA"].strftime("%d %b") if pd.notna(m["Supplier_ETA"]) else "-"
            alert_row(f"Supplier ETA Risk · {m['Material_Name']}",
                      f"{fmt_int(m['Incoming_Qty'])} {m['UoM']} · ETA {eta} · belum dikonfirmasi", AMBER, "truck")
        for fb in st.session_state.material_feedback[-2:]:
            alert_row(f"Feedback · {fb['material']}", fb["note"], AMBER, "doc")
        ready = int((mat["Alert"] == "Material Ready").sum())
        meter("Material siap", ready, len(mat), TEAL, f"{ready}/{len(mat)} item")
    with right:
        section("Usulan Jadwal — Top 5")
        if sch.empty:
            st.info("Tidak ada order LAYAK pada skenario ini.")
        else:
            top = sch.head(5).copy()
            top["Status"] = top["Late"].map({True: "Late", False: "On time"})
            top = top[["Sequence", "SKU_ID", "Nama_Produk", "Priority_Class", "Quantity", "ETA_NDC", "Status"]]
            html_table(top, badges=("Priority_Class", "Status"), key_col="SKU_ID", sub_cols=("Nama_Produk",),
                       fmt={"Quantity": fmt_int, "ETA_NDC": fmt_dt},
                       labels={"Sequence": "#", "SKU_ID": "SKU", "Nama_Produk": "Produk", "Priority_Class": "Kelas",
                               "Quantity": "Qty", "ETA_NDC": "ETA NDC"})
