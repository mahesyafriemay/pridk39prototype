"""H03 — Production Priority Ranking (PPC, Leader Produksi)."""
import altair as alt
import pandas as pd
import streamlit as st

from engine import config as cfg
from engine.priority_engine import criteria_weights_from_matrix
from utils import state
from utils.helpers import fmt_dec, fmt_int
from utils.styles import (AMBER, CLASS_SCALE, NAVY, ORANGE, RED, TEAL, W, chart, html_table, kpi_card,
                          section)

K_COLORS = {"K1 Urgensi Stok": NAVY, "K2 Order Aktual": "#5B7DB8", "K3 Dampak Campaign": ORANGE, "K4 Kontribusi Margin": TEAL}


def render():
    state.header("Priority", "AHP 4 kriteria untuk SKU NIP ≤ ROP, lalu kelas P1/P2/P3 dari Critical Ratio.")
    pri = state.active_result()["priority"]
    if pri.empty:
        st.success("Tidak ada SKU dengan NIP ≤ ROP — tidak ada rekomendasi produksi baru.")
        return
    ahp = criteria_weights_from_matrix()
    median = pri["Median_NonP1"].iloc[0]

    c = st.columns(4)
    cnt = pri["Priority_Class"].value_counts()
    with c[0]:
        kpi_card("P1 · tidak boleh ditunda", int(cnt.get("P1", 0)), "Critical Ratio < 1", RED, "alert")
    with c[1]:
        kpi_card("P2", int(cnt.get("P2", 0)), "CR ≥ 1, skor ≥ median", ORANGE, "layers")
    with c[2]:
        kpi_card("P3", int(cnt.get("P3", 0)), "CR ≥ 1, skor < median", TEAL, "layers")
    with c[3]:
        kpi_card("Consistency Ratio", fmt_dec(ahp["CR"], 3), "CR < 0,1 → konsisten" if ahp["CR"] < 0.1 else "Perlu revisi",
                 TEAL if ahp["CR"] < 0.1 else RED, "check")

    # Matriks klasifikasi --------------------------------------------------------
    left, right = st.columns([1.15, 1])
    with left:
        section("Peta Klasifikasi", f"garis: CR = 1 dan median AHP non-P1 = {fmt_dec(median, 3)}")
        base = alt.Chart(pri)
        pts = base.mark_circle(opacity=0.9, stroke="white", strokeWidth=1.5).encode(
            x=alt.X("Critical_Ratio:Q", title="Critical Ratio (DoC ÷ LT produksi+QC)", scale=alt.Scale(zero=True)),
            y=alt.Y("AHP_Score:Q", title="AHP Score"),
            size=alt.Size("Recommended_Qty:Q", scale=alt.Scale(range=[120, 1400]), legend=None),
            color=alt.Color("Priority_Class:N", scale=alt.Scale(**CLASS_SCALE), legend=alt.Legend(title=None)),
            tooltip=["SKU_ID", "Nama_Produk", "Priority_Class", alt.Tooltip("AHP_Score:Q", format=".3f"),
                     alt.Tooltip("Critical_Ratio:Q", format=".2f"), alt.Tooltip("Recommended_Qty:Q", format=",.0f")])
        lbl = base.mark_text(dy=-16, fontSize=11, fontWeight=600, color=NAVY).encode(
            x="Critical_Ratio:Q", y="AHP_Score:Q", text="SKU_ID:N")
        vx = alt.Chart(pd.DataFrame({"x": [1]})).mark_rule(color=RED, strokeDash=[6, 4]).encode(x="x:Q")
        hy = alt.Chart(pd.DataFrame({"y": [median]})).mark_rule(color=AMBER, strokeDash=[6, 4]).encode(y="y:Q")
        st.altair_chart(chart(vx + hy + pts + lbl, 340), **W)
    with right:
        section("Komposisi Skor AHP", "kontribusi berbobot tiap kriteria")
        long = []
        for _, r in pri.iterrows():
            for k in ("K1", "K2", "K3", "K4"):
                long.append({"SKU_ID": r["SKU_ID"], "Kriteria": f"{k} {cfg.AHP_CRITERIA_LABEL[k]}", "Skor": r[f"{k}_Weighted"]})
        long = pd.DataFrame(long)
        st_bar = alt.Chart(long).mark_bar(size=16).encode(
            y=alt.Y("SKU_ID:N", sort=list(pri["SKU_ID"]), title=None),
            x=alt.X("Skor:Q", title="AHP Score", stack="zero"),
            color=alt.Color("Kriteria:N", scale=alt.Scale(domain=list(K_COLORS), range=list(K_COLORS.values())),
                            legend=alt.Legend(title=None, columns=2)),
            order=alt.Order("Kriteria:N"),
            tooltip=["SKU_ID", "Kriteria", alt.Tooltip("Skor:Q", format=".3f")])
        st.altair_chart(chart(st_bar, 340), **W)

    # Ranking ---------------------------------------------------------------
    section("Ranking Prioritas Produksi")
    tbl = pri[["Rank", "SKU_ID", "Nama_Produk", "Days_of_Cover", "Order_Committed", "Campaign_Add_C",
               "Margin_Contribution", "AHP_Score", "Critical_Ratio", "Priority_Class", "Reason"]]
    html_table(tbl, badges=("Priority_Class",), key_col="SKU_ID", sub_cols=("Nama_Produk", "Reason"),
               fmt={"Days_of_Cover": lambda v: fmt_dec(v, 1), "Order_Committed": fmt_int, "Campaign_Add_C": fmt_int,
                    "Margin_Contribution": lambda v: f"{v / 1e6:,.0f} jt".replace(",", "."),
                    "AHP_Score": lambda v: fmt_dec(v, 3), "Critical_Ratio": lambda v: fmt_dec(v, 2)},
               labels={"Rank": "#", "SKU_ID": "SKU", "Nama_Produk": "Produk", "Days_of_Cover": "DoC",
                       "Order_Committed": "Order", "Campaign_Add_C": "Campaign", "Margin_Contribution": "Margin (Rp)",
                       "AHP_Score": "AHP", "Critical_Ratio": "CR", "Priority_Class": "Kelas", "Reason": "Alasan"})

    with st.expander("Bobot & uji konsistensi AHP"):
        a, b = st.columns([1, 1])
        with a:
            crit = pd.DataFrame({"Kode": list(cfg.AHP_WEIGHTS), "Kriteria": [cfg.AHP_CRITERIA_LABEL[k] for k in cfg.AHP_WEIGHTS],
                                 "Bobot": [f"{w:.1%}" for w in cfg.AHP_WEIGHTS.values()]})
            html_table(crit, key_col="Kode")
        with b:
            m = pd.DataFrame(cfg.AHP_PAIRWISE, columns=list(cfg.AHP_WEIGHTS)).round(3)
            m.insert(0, " ", list(cfg.AHP_WEIGHTS))
            html_table(m, key_col=" ")
            st.caption(f"λmaks {fmt_dec(ahp['lambda_max'], 3)} · CI {fmt_dec(ahp['CI'], 3)} · RI {ahp['RI']} · CR {fmt_dec(ahp['CR'], 3)}")
