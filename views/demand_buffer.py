"""H02 — Demand & Buffer Monitoring (PPC utama; Leader Produksi & Supply Planner lihat)."""
import altair as alt
import pandas as pd
import streamlit as st

from engine import config as cfg
from utils import state
from utils.helpers import fmt_dec, fmt_int
from utils.styles import (AMBER_SOFT, NAVY, ORANGE, RED_SOFT, STATUS_SCALE, TEAL, TEAL_SOFT, W, chart, html_table,
                          kpi_card, section)


def render():
    state.header("Demand & Buffer", "Baseline demand per lifecycle → ROP, Max Level, NIP, dan qty rekomendasi.")
    if state.is_view_only("Demand & Buffer", st.session_state.role):
        st.caption("👁 Mode lihat")

    res = state.active_result()
    buf = res["buffer"].copy()
    data = state.get_data()

    f1, f2, f3 = st.columns(3)
    kat = f1.multiselect("Kategori", sorted(buf["Kategori"].unique()), default=sorted(buf["Kategori"].unique()))
    life = f2.multiselect("Lifecycle", ["Matang", "Growing", "Baru"], default=["Matang", "Growing", "Baru"])
    stat = f3.multiselect("Status", ["Normal", "Watch", "Risk"], default=["Normal", "Watch", "Risk"])
    view = buf[buf["Kategori"].isin(kat) & buf["Lifecycle"].isin(life) & buf["Status"].isin(stat)]

    c = st.columns(4)
    with c[0]:
        kpi_card("SKU tampil", len(view), f"{int((view['Status'] == 'Risk').sum())} Risk", NAVY, "layers")
    with c[1]:
        kpi_card("Perlu produksi", int(view["Need_Production"].sum()), "NIP ≤ ROP", ORANGE, "alert")
    with c[2]:
        kpi_card("Qty rekomendasi", fmt_int(view["Recommended_Qty"].sum()), "unit, kelipatan batch", TEAL, "box")
    with c[3]:
        kpi_card("Avg Days of Cover", fmt_dec(view["Days_of_Cover"].mean() if len(view) else 0, 1), "hari", NAVY, "clock")

    if view.empty:
        st.info("Tidak ada SKU sesuai filter.")
        return

    # Buffer zone chart -----------------------------------------------------
    section("Buffer Zone per SKU", "merah = safety stock · kuning = sampai ROP · hijau = sampai Max · garis navy = NIP")
    order = list(view.sort_values("Days_of_Cover")["SKU_ID"])
    zones = pd.concat([
        pd.DataFrame({"SKU_ID": view["SKU_ID"], "Zona": "Safety stock", "a": 0, "b": view["Safety_Stock"]}),
        pd.DataFrame({"SKU_ID": view["SKU_ID"], "Zona": "SS → ROP", "a": view["Safety_Stock"], "b": view["ROP"]}),
        pd.DataFrame({"SKU_ID": view["SKU_ID"], "Zona": "ROP → Max", "a": view["ROP"], "b": view["Max_Level"]}),
    ])
    z = alt.Chart(zones).mark_bar(size=20, cornerRadius=3).encode(
        y=alt.Y("SKU_ID:N", sort=order, title=None), x=alt.X("a:Q", title="Unit", axis=alt.Axis(format="~s")), x2="b:Q",
        color=alt.Color("Zona:N", scale=alt.Scale(domain=["Safety stock", "SS → ROP", "ROP → Max"],
                                                  range=[RED_SOFT, AMBER_SOFT, TEAL_SOFT]), legend=alt.Legend(title=None)),
        tooltip=["SKU_ID", "Zona", alt.Tooltip("a:Q", format=",.0f", title="dari"), alt.Tooltip("b:Q", format=",.0f", title="sampai")])
    nip = alt.Chart(view).mark_bar(size=6, color=NAVY, cornerRadiusEnd=3).encode(
        y=alt.Y("SKU_ID:N", sort=order), x="NIP:Q",
        tooltip=["SKU_ID", alt.Tooltip("NIP:Q", format=",.0f"), alt.Tooltip("ROP:Q", format=",.0f"), "Status"])
    dot = alt.Chart(view).mark_point(filled=True, size=90, stroke="white", strokeWidth=1.5).encode(
        y=alt.Y("SKU_ID:N", sort=order), x="NIP:Q",
        color=alt.Color("Status:N", scale=alt.Scale(**STATUS_SCALE), legend=None))
    st.altair_chart(chart(z + nip + dot, 34 * len(view) + 40), **W)

    # Tabel -------------------------------------------------------------------
    section("Buffer / ROP")
    tbl = view.assign(Variability=view["Sigma"].map(fmt_int) + " · CV " + (view["CV"] * 100).round(0).astype(int).astype(str) + "%")
    tbl = tbl[["SKU_ID", "Nama_Produk", "Lifecycle", "Baseline_B", "Variability", "Campaign_Add_C", "Lead_Time_Total",
               "NIP", "ROP", "Max_Level", "Days_of_Cover", "Recommended_Qty", "Status"]]
    html_table(tbl, badges=("Status",), key_col="SKU_ID", sub_cols=("Nama_Produk",),
               fmt={**{k: fmt_int for k in ("Baseline_B", "Campaign_Add_C", "NIP", "ROP", "Max_Level", "Recommended_Qty")},
                    "Days_of_Cover": lambda v: fmt_dec(v, 1)},
               labels={"SKU_ID": "SKU", "Nama_Produk": "Produk", "Baseline_B": "Baseline/mgg", "Variability": "Variabilitas σ",
                       "Campaign_Add_C": "Campaign C", "Lead_Time_Total": "LT (hari)", "Max_Level": "Max",
                       "Days_of_Cover": "DoC", "Recommended_Qty": "Rekomendasi"})

    # Drill-down --------------------------------------------------------------
    section("Drill-down SKU")
    names = buf.set_index("SKU_ID")["Nama_Produk"]
    sid = st.selectbox("SKU", buf["SKU_ID"], format_func=lambda s: f"{s} — {names[s]}", label_visibility="collapsed")
    r = buf.set_index("SKU_ID").loc[sid]
    c1, c2 = st.columns([1, 1.4])
    with c1:
        steps = pd.DataFrame([
            ("Baseline B", f"{fmt_int(r['Baseline_B'])}/mgg", r["Baseline_Method"]),
            ("σ", fmt_int(r["Sigma"]), f"CV floor {cfg.CV_FLOOR[r['Lifecycle']]:.0%}"),
            ("P", f"{r['P_Days']} hari", f"LT {r['Lead_Time_Total']} + review {cfg.REVIEW_DAYS}"),
            ("Campaign C", fmt_int(r["Campaign_Add_C"]), r["Campaign_Detail"]),
            ("Safety stock", fmt_int(r["Safety_Stock"]), f"Z {r['Z']}"),
            ("ROP", fmt_int(r["ROP"]), "B·P/7 + C + SS"),
            ("Max Level", fmt_int(r["Max_Level"]), f"ROP + {cfg.CYCLE_COVER_WEEKS}B"),
            ("NIP", fmt_int(r["NIP"]), "On hand + WIP − order"),
            ("Rekomendasi", fmt_int(r["Recommended_Qty"]), f"batch {fmt_int(r['Batch_Size'])}" if r["Need_Production"] else "NIP > ROP"),
        ], columns=["Komponen", "Nilai", "Dasar"])
        html_table(steps, key_col="Komponen", sub_cols=("Dasar",))
    with c2:
        hist = data["weekly_demand"][data["weekly_demand"]["SKU_ID"] == sid]
        area = alt.Chart(hist).mark_area(color=TEAL, opacity=0.12, line={"color": TEAL, "strokeWidth": 2}).encode(
            x=alt.X("Week_Start:T", title=None, axis=alt.Axis(format="%d %b")), y=alt.Y("Demand_Units:Q", title="Demand/minggu"),
            tooltip=[alt.Tooltip("Week_Start:T", format="%d %b %Y"), alt.Tooltip("Demand_Units:Q", format=",.0f"), "Campaign_ID"])
        camp = alt.Chart(hist[hist["Is_Campaign"] == 1]).mark_point(color=ORANGE, size=90, filled=True).encode(
            x="Week_Start:T", y="Demand_Units:Q", tooltip=["Campaign_ID"])
        rule = alt.Chart(pd.DataFrame({"B": [r["Baseline_B"]]})).mark_rule(color=NAVY, strokeDash=[5, 4]).encode(y="B:Q")
        st.altair_chart(chart((area + camp + rule).properties(title="Histori demand · ● campaign · --- baseline"), 300), **W)
