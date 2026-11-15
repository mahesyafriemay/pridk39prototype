"""H04 — Feasibility Gate (PPC, Supply Planner)."""
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

from utils import state
from utils.helpers import fmt_date, fmt_dec, fmt_int
from utils.styles import (AMBER, NAVY, ORANGE, RED, TEAL, W, alert_row, chart, html_table, kpi_card, meter,
                          section)

ALERT_SCALE = {"domain": ["Material Shortage", "Supplier ETA Risk", "Material Ready"], "range": [RED, AMBER, TEAL]}


def render():
    state.header("Feasibility", "Gate material (MRP) dan kapasitas line (RCCP) sebelum order boleh dijadwalkan.")
    res = state.active_result()
    feas, detail, mat = res["feasibility"], res["feasibility_detail"], res["material"]
    if feas.empty:
        st.info("Tidak ada SKU di antrean produksi.")
        return

    hrs_av = feas.attrs.get("hours_available", 0.0)
    used = hrs_av - feas.attrs.get("hours_left", 0.0)
    c = st.columns([1, 1, 1.4])
    with c[0]:
        kpi_card("LAYAK", int((feas["Status"] == "LAYAK").sum()), "lanjut ke sequencing", TEAL, "check")
    with c[1]:
        kpi_card("HOLD", int((feas["Status"] == "HOLD").sum()), "material / kapasitas", RED, "stop")
    with c[2], st.container(border=True):
        meter("Kapasitas line LQ-01 (16–20 Nov)", used, hrs_av, ORANGE if used / max(hrs_av, 1) > 0.85 else TEAL,
              f"{fmt_dec(used, 1)} / {fmt_dec(hrs_av, 1)} jam")
        n_ready = int((mat["Alert"] == "Material Ready").sum())
        meter("Material siap", n_ready, len(mat), TEAL, f"{n_ready}/{len(mat)} item")

    # Gate ----------------------------------------------------------------------
    section("Hasil Gate", "urutan alokasi: P1 → P3, Critical Ratio terkecil dulu")
    tbl = feas[["SKU_ID", "Priority_Class", "Recommended_Qty", "Required_Hours", "Material_Shortage", "Supplier_ETA", "Status"]].copy()
    tbl["Material_Shortage"] = tbl["Material_Shortage"].replace("0", "—")
    html_table(tbl, badges=("Priority_Class", "Status"), key_col="SKU_ID", sub_cols=("Supplier_ETA",),
               fmt={"Recommended_Qty": fmt_int, "Required_Hours": lambda v: f"{fmt_dec(v, 1)} jam"},
               labels={"SKU_ID": "SKU", "Priority_Class": "Kelas", "Recommended_Qty": "Qty", "Required_Hours": "Kapasitas",
                       "Material_Shortage": "Material shortage", "Supplier_ETA": "Supplier ETA"})
    for _, h in feas[feas["Status"] == "HOLD"].iterrows():
        alert_row(f"HOLD · {h['SKU_ID']} {h['Nama_Produk']}", h["Reason"], RED, "stop")

    # Coverage material ----------------------------------------------------------
    left, right = st.columns([1.2, 1])
    with left:
        section("Coverage Material", "(stok + pasokan siap) ÷ kebutuhan rencana")
        m = mat[mat["Gross_Requirement"] > 0].copy()
        m["Coverage"] = ((m["Stock_Available"] + m["Incoming_Ready"]) / m["Gross_Requirement"]).clip(upper=2.0)
        bars = alt.Chart(m).mark_bar(size=14, cornerRadiusEnd=4).encode(
            y=alt.Y("Material_Name:N", sort="x", title=None), x=alt.X("Coverage:Q", title=None, axis=alt.Axis(format="%")),
            color=alt.Color("Alert:N", scale=alt.Scale(**ALERT_SCALE), legend=alt.Legend(title=None)),
            tooltip=["Material_Name", alt.Tooltip("Coverage:Q", format=".0%"), alt.Tooltip("Gross_Requirement:Q", format=",.0f"),
                     alt.Tooltip("Stock_Available:Q", format=",.0f"), alt.Tooltip("Incoming_Ready:Q", format=",.0f")])
        rule = alt.Chart(pd.DataFrame({"x": [1.0]})).mark_rule(color=NAVY, strokeDash=[5, 4]).encode(x="x:Q")
        st.altair_chart(chart(bars + rule, 30 * len(m) + 50), **W)
    with right:
        section("Detail BOM per SKU")
        sid = st.selectbox("SKU", feas["SKU_ID"], label_visibility="collapsed",
                           format_func=lambda s: f"{s} · {feas.set_index('SKU_ID').loc[s, 'Status']}")
        d = detail[detail["SKU_ID"] == sid][["Material_Name", "Gross_Requirement", "Available_Stock", "Ready_Incoming", "Net_Shortage", "UoM"]]
        html_table(d, key_col="Material_Name", sub_cols=("UoM",),
                   fmt={k: fmt_int for k in ("Gross_Requirement", "Available_Stock", "Ready_Incoming", "Net_Shortage")},
                   labels={"Material_Name": "Komponen", "Gross_Requirement": "Bruto", "Available_Stock": "Stok*",
                           "Ready_Incoming": "Siap*", "Net_Shortage": "Shortage"})
        st.caption("*sisa setelah alokasi ke SKU prioritas lebih tinggi")

    # Supplier readiness ---------------------------------------------------------
    section("Supplier Readiness")
    sup = state.get_data()["supplier"].set_index("Supplier_ID")
    s = mat[(mat["Incoming_Qty"] > 0)].copy()
    s["Supplier"] = s["Supplier_ID"].map(sup["Supplier_Name"]).str.replace(" (dummy)", "", regex=False)
    s["OTIF"] = s["Supplier_ID"].map(sup["OTIF_Rate"])
    s = s[["Material_Name", "Supplier", "Incoming_Qty", "Supplier_ETA", "Supplier_Confirmed", "OTIF", "Alert"]]
    html_table(s, badges=("Alert",), key_col="Material_Name",
               fmt={"Incoming_Qty": fmt_int, "Supplier_ETA": fmt_date, "OTIF": lambda v: f"{v:.0%}"},
               labels={"Material_Name": "Material", "Incoming_Qty": "Incoming", "Supplier_ETA": "ETA",
                       "Supplier_Confirmed": "Konfirmasi", "OTIF": "OTIF"})

    # Feedback Supply Planner -------------------------------------------------
    if st.session_state.role == state.SUPPLY:
        section("Feedback Material ke PPC")
        with st.form("material_feedback", clear_on_submit=True):
            c1, c2 = st.columns([1, 2])
            mname = c1.selectbox("Material", mat["Material_Name"])
            new_eta = c1.date_input("ETA baru (opsional)", value=None)
            note = c2.text_area("Catatan kendala", placeholder="Contoh: kirim parsial 15.000 set tanggal 18 Nov")
            if st.form_submit_button("Kirim feedback", type="primary"):
                if not note.strip():
                    st.error("Catatan wajib diisi.")
                else:
                    st.session_state.material_feedback.append({
                        "time": datetime.now().strftime("%d %b %H:%M"), "material": mname,
                        "eta": str(new_eta) if new_eta else "-", "note": note.strip()})
                    st.success("Feedback terkirim.")
    if st.session_state.material_feedback:
        section("Log Feedback Supply Planner")
        for fb in reversed(st.session_state.material_feedback):
            alert_row(f"{fb['time']} · {fb['material']} · ETA {fb['eta']}", fb["note"], AMBER, "doc")
