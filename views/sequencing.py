"""H05 — Sequencing & ETA (PPC, Leader Produksi)."""
import altair as alt
import pandas as pd
import streamlit as st

from engine import config as cfg
from utils import state
from utils.helpers import fmt_dec, fmt_dt, fmt_int
from utils.styles import NAVY, ORANGE, RED, TEAL, W, alert_row, chart, html_table, kpi_card, section

PHASE_SCALE = {"domain": ["Produksi", "QC release", "Distribusi"], "range": [NAVY, TEAL, "#F5B26B"]}


def render():
    state.header("Sequencing & ETA", "Urutan produksi line liquid LQ-01 dan estimasi tiba di NDC.")
    res = state.active_result()
    sch, feas, p = res["schedule"], res["feasibility"], res["params"]
    if sch.empty:
        st.warning("Tidak ada order LAYAK. Revisi di H06 What-if.")
        return

    c = st.columns(4)
    with c[0]:
        kpi_card("Order terjadwal", len(sch), f"{fmt_int(sch['Quantity'].sum())} unit", NAVY, "list")
    with c[1]:
        kpi_card("Jam line", fmt_dec(sch["Production_Duration_Hours"].sum(), 1),
                 f"{int((sch['Changeover'] == 'Ganti kategori').sum())}× ganti kategori", ORANGE, "zap")
    with c[2]:
        kpi_card("Flag terlambat", int(sch["Late"].sum()), f"{fmt_dec(sch['Delay_Days'].sum(), 1)} hari total", RED, "clock")
    with c[3]:
        kpi_card("ETA terakhir", fmt_dt(sch["ETA_NDC"].max()), "tiba di NDC", TEAL, "truck")

    # Gantt end-to-end -----------------------------------------------------------
    section("Timeline Produksi → QC → NDC", "◆ merah = target (perkiraan stok NDC habis)")
    rows = []
    for _, r in sch.iterrows():
        lab = f"{r['Sequence']}. {r['SKU_ID']} · {r['Priority_Class']}"
        rows += [{"Label": lab, "Fase": "Produksi", "a": r["Start_Time"], "b": r["Finish_Production"], "SKU": r["SKU_ID"]},
                 {"Label": lab, "Fase": "QC release", "a": r["Finish_Production"], "b": r["Finish_QC"], "SKU": r["SKU_ID"]},
                 {"Label": lab, "Fase": "Distribusi", "a": r["Finish_QC"], "b": r["ETA_NDC"], "SKU": r["SKU_ID"]}]
    g = pd.DataFrame(rows)
    order = list(dict.fromkeys(g["Label"]))
    bars = alt.Chart(g).mark_bar(size=18, cornerRadius=3).encode(
        y=alt.Y("Label:N", sort=order, title=None),
        x=alt.X("a:T", title=None, axis=alt.Axis(format="%a %d %b", tickCount="day")), x2="b:T",
        color=alt.Color("Fase:N", scale=alt.Scale(**PHASE_SCALE), legend=alt.Legend(title=None)),
        tooltip=["SKU", "Fase", alt.Tooltip("a:T", format="%d %b %H:%M", title="mulai"),
                 alt.Tooltip("b:T", format="%d %b %H:%M", title="selesai")])
    horizon_end = sch["ETA_NDC"].max() + pd.Timedelta(days=1)
    tg = sch[sch["Target_Date"] <= horizon_end].assign(
        Label=lambda d: d["Sequence"].astype(str) + ". " + d["SKU_ID"] + " · " + d["Priority_Class"])
    tgt = alt.Chart(tg).mark_point(shape="diamond", size=130, filled=True, color=RED).encode(
        y=alt.Y("Label:N", sort=order), x="Target_Date:T",
        tooltip=["SKU_ID", alt.Tooltip("Target_Date:T", format="%d %b %H:%M", title="target"), "Status_Delay"])
    st.altair_chart(chart(bars + tgt, 46 * len(sch) + 50), **W)

    # Tabel -----------------------------------------------------------------
    section("Production Sequence")
    tbl = sch[["Sequence", "SKU_ID", "Nama_Produk", "Priority_Class", "AHP_Score", "Critical_Ratio", "Quantity",
               "Production_Duration_Hours", "Start_Time", "Finish_Production", "Finish_QC", "ETA_NDC", "Status_Delay"]]
    html_table(tbl, badges=("Priority_Class", "Status_Delay"), key_col="SKU_ID", sub_cols=("Nama_Produk",),
               fmt={"AHP_Score": lambda v: fmt_dec(v, 3), "Critical_Ratio": lambda v: fmt_dec(v, 2), "Quantity": fmt_int,
                    "Production_Duration_Hours": lambda v: f"{fmt_dec(v, 1)} j", "Start_Time": fmt_dt,
                    "Finish_Production": fmt_dt, "Finish_QC": fmt_dt, "ETA_NDC": fmt_dt},
               labels={"Sequence": "#", "SKU_ID": "SKU", "Nama_Produk": "Produk", "Priority_Class": "Kelas",
                       "AHP_Score": "AHP", "Critical_Ratio": "CR", "Quantity": "Qty", "Production_Duration_Hours": "Durasi",
                       "Start_Time": "Start", "Finish_Production": "Selesai prod.", "Finish_QC": "Selesai QC",
                       "ETA_NDC": "ETA NDC", "Status_Delay": "Status"})

    hold = feas[feas["Status"] == "HOLD"] if not feas.empty else pd.DataFrame()
    if len(hold):
        alert_row("Tidak dijadwalkan (HOLD)", ", ".join(f"{r.SKU_ID} ({r.Priority_Class})" for r in hold.itertuples()), RED, "stop")

    with st.expander("Parameter & aturan"):
        st.markdown(
            f"**Rule** P1 → P2 → P3 · CR terkecil dulu · SKU sekategori digabung bila selisih CR ≤ {cfg.GROUPING_CR_TOLERANCE}  \n"
            f"**ETA** qty ÷ {fmt_int(p['line_rate'])} unit/jam + setup {fmt_dec(p['setup_hours'], 1)} j "
            f"(+{fmt_dec(cfg.CATEGORY_CHANGEOVER_HOURS, 1)} j ganti kategori) → QC {cfg.QC_WORKING_DAYS} hari kerja → "
            f"distribusi {cfg.DISTRIBUTION_WORKING_DAYS} hari kerja  \n"
            "**Kalender** mulai 16 Nov 07:00 · 2 shift · Rabu maintenance 4 jam")
