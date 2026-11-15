"""H06 — What-if & Replanning (PPC, Leader Produksi)."""
import altair as alt
import pandas as pd
import streamlit as st

from engine import approval_engine as ap
from engine.scenario_engine import compare_kpis, default_scenario_params
from utils import state
from utils.helpers import fmt_dec, fmt_int, fmt_rp
from utils.styles import ORANGE, W, chart, html_table, section

PRESETS = {
    "Custom": None,
    "Supplier kirim 7 hari lebih cepat": {"supplier_eta_shift_days": -7},
    "Lonjakan demand +30%": {"demand_multiplier": 1.3},
    "Line turun 50% (breakdown)": {"line_capacity_pct": 50.0},
    "Material hanya 70% tersedia": {"material_availability_pct": 70.0},
}


def _fmt_kpi(key, v):
    if v is None:
        return "-"
    if key == "inventory_value":
        return fmt_rp(v)
    if key in ("total_delay_days", "line_hours"):
        return fmt_dec(v, 1)
    return fmt_int(v)


def render():
    state.header("What-if", "Uji perubahan parameter, hitung ulang end-to-end, bandingkan dengan baseline.")
    role = st.session_state.role
    ss = st.session_state
    base = state.baseline_result()
    p = ss.params_alt

    # Editor ----------------------------------------------------------------
    section("Scenario Editor")
    preset = st.selectbox("Preset skenario", list(PRESETS), help="Isi cepat parameter, lalu klik Run Scenario")
    pv = {**default_scenario_params(), **PRESETS[preset]} if PRESETS[preset] else p
    with st.form("scenario_form"):
        c1, c2, c3 = st.columns(3)
        dm = c1.slider("Demand ×", 0.5, 2.0, float(pv["demand_multiplier"]), 0.05)
        cu = c1.slider("Campaign uplift ×", 0.0, 2.0, float(pv["campaign_uplift_multiplier"]), 0.1)
        ma = c2.slider("Material tersedia (%)", 0, 150, int(pv["material_availability_pct"]), 5)
        se = c2.slider("Supplier ETA (± hari)", -14, 14, int(pv["supplier_eta_shift_days"]))
        lc = c3.slider("Kapasitas line (%)", 10, 150, int(pv["line_capacity_pct"]), 5)
        with c3.expander("Override qty produksi"):
            elig = base["priority"][["SKU_ID", "Recommended_Qty"]].copy()
            elig["Qty_Scenario"] = elig["SKU_ID"].map(pv["qty_override"]).fillna(0).astype(int)
            edited = st.data_editor(
                elig, hide_index=True, key="qty_editor", disabled=["SKU_ID", "Recommended_Qty"],
                column_config={"Recommended_Qty": st.column_config.NumberColumn("Rekomendasi", format="%d"),
                               "Qty_Scenario": st.column_config.NumberColumn("Qty baru (0 = default)", min_value=0,
                                                                             step=1000, format="%d")})
        b1, b2, _ = st.columns([1, 1, 2])
        run = b1.form_submit_button("▶ Run Scenario", type="primary", **W)
        reset = b2.form_submit_button("Reset", **W)
    if run:
        override = {r.SKU_ID: int(r.Qty_Scenario) for r in edited.itertuples() if r.Qty_Scenario and r.Qty_Scenario > 0}
        ss.params_alt = {**default_scenario_params(), "demand_multiplier": dm, "campaign_uplift_multiplier": cu,
                         "material_availability_pct": float(ma), "supplier_eta_shift_days": int(se),
                         "line_capacity_pct": float(lc), "qty_override": override}
        ss.alt_ran = True
        st.rerun()
    if reset:
        ss.params_alt = default_scenario_params()
        ss.alt_ran = False
        if ss.selected_scenario == "Alternative":
            ss.selected_scenario = "Baseline"
        st.rerun()

    if not ss.alt_ran:
        st.info("Pilih preset atau atur slider, lalu klik **Run Scenario**.")
        return
    alt_res = state.result_for("Alternative")
    cmp = compare_kpis(base["kpi"], alt_res["kpi"], ("Baseline", "Scenario")).set_index("key")

    # Delta cards ------------------------------------------------------------
    section("Impact Analysis", "Baseline → Scenario · hijau = lebih baik")
    keys = [("stockout_risk", "Stockout risk"), ("delayed_orders", "Order terlambat"), ("hold", "Order HOLD"),
            ("layak", "Order LAYAK"), ("overstock_risk", "Overstock risk"), ("inventory_value", "Nilai inventori")]
    cols = st.columns(len(keys))
    for col, (k, lbl) in zip(cols, keys):
        b, a = cmp.loc[k, "Baseline"], cmp.loc[k, "Scenario"]
        d = a - b
        delta = None if d == 0 else (("-" if d < 0 else "+") + fmt_rp(abs(d)) if k == "inventory_value" else f"{d:+,.0f}".replace(",", "."))
        col.metric(lbl, _fmt_kpi(k, a), delta, delta_color="normal" if k == "layak" else "inverse")

    left, right = st.columns([1.1, 1])
    with left:
        section("KPI Baseline vs Scenario")
        ks = ["stockout_risk", "overstock_risk", "delayed_orders", "hold", "layak", "changeovers"]
        long = cmp.loc[ks].reset_index().melt(id_vars=["key", "KPI"], value_vars=["Baseline", "Scenario"],
                                              var_name="Skenario", value_name="Nilai")
        ch = alt.Chart(long).mark_bar(cornerRadiusEnd=4, size=11).encode(
            y=alt.Y("KPI:N", title=None, sort=[cmp.loc[k, "KPI"] for k in ks]), yOffset="Skenario:N",
            x=alt.X("Nilai:Q", title=None, axis=alt.Axis(tickMinStep=1)),
            color=alt.Color("Skenario:N", scale=alt.Scale(range=["#A9B4C6", ORANGE]), legend=alt.Legend(title=None)),
            tooltip=["KPI", "Skenario", "Nilai"])
        st.altair_chart(chart(ch, 300), **W)
    with right:
        section("Perubahan per SKU")
        b = base["buffer"][["SKU_ID", "Recommended_Qty"]].rename(columns={"Recommended_Qty": "Qty B"})
        a = alt_res["buffer"][["SKU_ID", "Recommended_Qty"]].rename(columns={"Recommended_Qty": "Qty S"})
        m = b.merge(a, on="SKU_ID")
        for name, r, col in (("Gate B", base, "Status"), ("Gate S", alt_res, "Status")):
            f = r["feasibility"]
            m[name] = m["SKU_ID"].map(dict(zip(f["SKU_ID"], f[col])) if not f.empty else {}).fillna("-")
        for name, r in (("Seq B", base), ("Seq S", alt_res)):
            s = r["schedule"]
            m[name] = m["SKU_ID"].map(dict(zip(s["SKU_ID"], s["Sequence"])) if not s.empty else {}).map(
                lambda v: "-" if pd.isna(v) else str(int(v)))
        m = m[(m["Qty B"] > 0) | (m["Qty S"] > 0)]
        html_table(m, badges=("Gate B", "Gate S"), key_col="SKU_ID",
                   fmt={"Qty B": fmt_int, "Qty S": fmt_int}, labels={"SKU_ID": "SKU"})
        st.caption("B = Baseline · S = Scenario")

    # Pilih skenario --------------------------------------------------------
    section("Selected Scenario")
    c1, c2 = st.columns([2, 1])
    choice = c1.radio("Dipakai sebagai proposed schedule", ["Baseline", "Alternative"],
                      index=["Baseline", "Alternative"].index(ss.selected_scenario), horizontal=True)
    if c2.button("✔ Use Selected Scenario", type="primary", disabled=role != state.PPC, **W):
        ss.selected_scenario = choice
        msg = f"Skenario {choice} aktif."
        if ss.workflow["status"] not in (ap.DRAFT, ap.MATERIAL_REJECTED, ap.REVISION_REQUESTED):
            msg += " Submit ulang di H07 bila perlu."
        ss.flash = msg
        st.rerun()
    if role != state.PPC:
        st.caption("Penetapan skenario oleh PPC.")
