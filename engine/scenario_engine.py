"""
Scenario Engine — orkestrasi pipeline end-to-end + KPI + perbandingan skenario.

Data -> Buffer -> Priority -> Feasibility -> Sequencing -> ETA -> KPI

Deterministic recalculation (tanpa optimization solver).
"""
from __future__ import annotations

import pandas as pd

from engine import config as cfg
from engine.buffer_engine import run_buffer_engine
from engine.eta_engine import run_eta_engine
from engine.feasibility_engine import run_feasibility_engine
from engine.priority_engine import run_priority_engine
from engine.sequencing_engine import run_sequencing_engine


def default_scenario_params() -> dict:
    return {
        "demand_multiplier": 1.0,
        "campaign_uplift_multiplier": 1.0,
        "qty_override": {},
        "material_availability_pct": 100.0,
        "supplier_eta_shift_days": 0,
        "line_capacity_pct": 100.0,
        "line_rate": cfg.LINE_RATE,
        "setup_hours": cfg.SETUP_HOURS,
    }


def run_pipeline(data: dict, params: dict | None = None) -> dict:
    p = {**default_scenario_params(), **(params or {})}
    buffer_df = run_buffer_engine(data, {
        "demand_multiplier": p["demand_multiplier"],
        "campaign_uplift_multiplier": p["campaign_uplift_multiplier"],
        "qty_override": p["qty_override"],
    })
    priority_df = run_priority_engine(buffer_df)
    feas_df, feas_detail, material_df = run_feasibility_engine(priority_df, data, {
        "material_availability_pct": p["material_availability_pct"],
        "supplier_eta_shift_days": p["supplier_eta_shift_days"],
        "line_capacity_pct": p["line_capacity_pct"],
        "line_rate": p["line_rate"],
        "setup_hours": p["setup_hours"],
    })
    seq_df = run_sequencing_engine(feas_df, priority_df)
    eta_df = run_eta_engine(seq_df, data["capacity"], {
        "line_rate": p["line_rate"],
        "setup_hours": p["setup_hours"],
        "line_capacity_pct": p["line_capacity_pct"],
    })
    result = {
        "params": p, "buffer": buffer_df, "priority": priority_df,
        "feasibility": feas_df, "feasibility_detail": feas_detail, "material": material_df,
        "sequence": seq_df, "schedule": eta_df,
    }
    result["kpi"] = compute_kpis(result)
    return result


def compute_kpis(res: dict) -> dict:
    buf, feas, sch, pri = res["buffer"], res["feasibility"], res["schedule"], res["priority"]
    planned = dict(zip(sch["SKU_ID"], sch["Quantity"])) if not sch.empty else {}
    late = set(sch.loc[sch["Late"], "SKU_ID"]) if not sch.empty else set()
    hold = feas[feas["Status"] == "HOLD"] if not feas.empty else pd.DataFrame(columns=["SKU_ID", "Priority_Class"])
    hold_p1 = set(hold.loc[hold["Priority_Class"] == "P1", "SKU_ID"])

    post = buf.copy()
    post["Planned_Qty"] = post["SKU_ID"].map(planned).fillna(0)
    post["Position_After"] = post["NIP"] + post["Planned_Qty"]
    over_post = post["Position_After"] > post["Max_Level"] + post["Batch_Size"]   # toleransi pembulatan batch
    inv_value = float((post["Position_After"].clip(lower=0) * post["COGS"]).sum())

    return {
        "risk_skus": int((buf["Status"] == "Risk").sum()),
        "watch_skus": int((buf["Status"] == "Watch").sum()),
        "normal_skus": int((buf["Status"] == "Normal").sum()),
        "overstock_skus": int(buf["Overstock"].sum()),
        "eligible": int(len(pri)),
        "layak": int((feas["Status"] == "LAYAK").sum()) if not feas.empty else 0,
        "hold": int(len(hold)),
        "delayed_orders": int(len(late)),
        "total_delay_days": float(sch["Delay_Days"].sum()) if not sch.empty else 0.0,
        "stockout_risk": int(len(late | hold_p1)),
        "overstock_risk": int(over_post.sum()),
        "inventory_value": inv_value,
        "planned_qty": float(sum(planned.values())),
        "line_hours": float(sch["Production_Duration_Hours"].sum()) if not sch.empty else 0.0,
        "changeovers": int((sch["Changeover"] == "Ganti kategori").sum()) if not sch.empty else 0,
        "p1": int((pri["Priority_Class"] == "P1").sum()) if not pri.empty else 0,
    }


def no_production_kpis(res: dict) -> dict:
    """Referensi 'tanpa rencana produksi' (as-is) untuk monitoring."""
    buf = res["buffer"]
    return {
        # tanpa replenishment, seluruh SKU dengan NIP <= ROP berisiko stockout
        "stockout_risk": int((buf["Status"] == "Risk").sum()),
        "overstock_risk": int(buf["Overstock"].sum()),
        "delayed_orders": None,     # tidak ada order produksi -> tidak relevan
        "inventory_value": float((buf["NIP"].clip(lower=0) * buf["COGS"]).sum()),
    }


KPI_LABELS = {
    "risk_skus": "SKU Risk (NIP ≤ ROP)",
    "eligible": "SKU masuk antrean",
    "layak": "Order LAYAK",
    "hold": "Order HOLD",
    "stockout_risk": "Stockout risk (setelah rencana)",
    "overstock_risk": "Overstock risk (setelah rencana)",
    "delayed_orders": "Order terlambat",
    "total_delay_days": "Total keterlambatan (hari)",
    "planned_qty": "Total qty diproduksi",
    "line_hours": "Jam line terpakai",
    "changeovers": "Jumlah ganti kategori",
    "inventory_value": "Nilai inventori (Rp)",
}

LOWER_IS_BETTER = {"risk_skus", "hold", "stockout_risk", "overstock_risk", "delayed_orders",
                   "total_delay_days", "line_hours", "changeovers", "inventory_value"}


def compare_kpis(base: dict, alt: dict, names=("Baseline", "Alternative")) -> pd.DataFrame:
    rows = []
    for k, label in KPI_LABELS.items():
        b, a = base.get(k, 0), alt.get(k, 0)
        diff = a - b
        if diff == 0:
            verdict = "="
        elif (diff < 0) == (k in LOWER_IS_BETTER):
            verdict = "Lebih baik"
        else:
            verdict = "Lebih buruk"
        if k in ("eligible", "planned_qty"):
            verdict = "Δ" if diff else "="
        rows.append({"KPI": label, "key": k, names[0]: b, names[1]: a, "Selisih": diff, "Dampak": verdict})
    return pd.DataFrame(rows)


def recommendation_signature(res: dict) -> pd.DataFrame:
    """Ringkasan rekomendasi (dipakai untuk membuktikan what-if mengubah hasil)."""
    return res["buffer"][["SKU_ID", "ROP", "Recommended_Qty", "Status"]].copy()
