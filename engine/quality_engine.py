"""
Quality Engine — elemen sistem manajemen mutu yang selaras ISO 9001:2015
(bukan klaim sertifikasi):

- Sasaran mutu & pengukuran kinerja        (klausul 6.2, 9.1)
- Ketidaksesuaian & tindakan korektif (NC/CAPA)  (klausul 8.7, 10.2)
- Pemicu replanning / pengendalian perubahan     (klausul 6.3, 8.5.6)
"""
from __future__ import annotations

import pandas as pd

from engine import config as cfg

PDCA = {
    "PLAN": ["H01", "H02", "H03", "H04", "H05", "H06"],
    "DO": ["H07"],
    "CHECK": ["H08"],
    "ACT": ["H06"],
}


def _check(value, target, op):
    return value <= target if op == "<=" else value >= target


def quality_objectives(kpi: dict, revisions: int, data_issues: int) -> pd.DataFrame:
    actual = {
        "stockout_risk": kpi["stockout_risk"],
        "delayed_orders": kpi["delayed_orders"],
        "feasibility_rate": (kpi["layak"] / kpi["eligible"]) if kpi["eligible"] else 1.0,
        "overstock_risk": kpi["overstock_risk"],
        "revisions": revisions,
        "data_issues": data_issues,
    }
    rows = []
    for key, o in cfg.QUALITY_OBJECTIVES.items():
        v = actual[key]
        rows.append({"key": key, "Sasaran": o["label"], "Indikator": o["indikator"],
                     "Target": (("≤ " if o["op"] == "<=" else "≥ ") + (f"{o['target']:.0%}" if key == "feasibility_rate" else f"{o['target']}")),
                     "Aktual": f"{v:.0%}" if key == "feasibility_rate" else f"{v:g}",
                     "value": v, "target": o["target"], "op": o["op"],
                     "Status": "Tercapai" if _check(v, o["target"], o["op"]) else "Tidak tercapai"})
    return pd.DataFrame(rows)


def nonconformities(res: dict) -> pd.DataFrame:
    """Setiap HOLD & order terlambat dicatat sebagai ketidaksesuaian + usulan tindakan korektif."""
    rows = []
    feas, sch = res["feasibility"], res["schedule"]
    n = 1
    if not feas.empty:
        for _, h in feas[feas["Status"] == "HOLD"].iterrows():
            kind = "Material" if not h["Material_OK"] else "Kapasitas"
            action = ("Eskalasi supplier / percepat ETA, alokasi ulang material, atau turunkan qty batch"
                      if kind == "Material" else "Tambah shift / geser slot, atau pecah batch")
            rows.append({"NC_ID": f"NC-{n:03d}", "SKU": h["SKU_ID"], "Kategori": kind,
                         "Temuan": h["Reason"].rstrip("."), "Tindakan korektif": action,
                         "PIC": "Supply Planner" if kind == "Material" else "Leader Produksi",
                         "Kelas": h["Priority_Class"], "Status": "Open"})
            n += 1
    if not sch.empty:
        for _, r in sch[sch["Late"]].iterrows():
            rows.append({"NC_ID": f"NC-{n:03d}", "SKU": r["SKU_ID"], "Kategori": "Delay",
                         "Temuan": f"ETA NDC melewati target {r['Delay_Days']:.1f} hari",
                         "Tindakan korektif": "Majukan urutan / percepat QC release, alokasi stok DC lain",
                         "PIC": "PPC", "Kelas": r["Priority_Class"], "Status": "Open"})
            n += 1
    return pd.DataFrame(rows, columns=["NC_ID", "SKU", "Kategori", "Temuan", "Tindakan korektif", "PIC", "Kelas", "Status"])


def replanning_triggers(res: dict, data: dict, feedback_count: int = 0) -> list[dict]:
    p, mat, k, buf = res["params"], res["material"], res["kpi"], res["buffer"]
    last = data["weekly_demand"].sort_values("Week_Start").groupby("SKU_ID").tail(1).set_index("SKU_ID")["Demand_Units"]
    surge = [s for s, b in zip(buf["SKU_ID"], buf["Baseline_B"]) if s in last and last[s] > 1.25 * b]
    n_short = int((mat["Alert"] == "Material Shortage").sum())
    n_eta = int((mat["Alert"] == "Supplier ETA Risk").sum())
    late_supply = bool((((mat["Incoming_Qty"] - mat["Incoming_Ready"]) > 0) & (mat["Gross_Requirement"] > 0)).any())
    cap_hold = (not res["feasibility"].empty) and bool((~res["feasibility"]["Capacity_OK"]).any())
    th = cfg.KPI_THRESHOLDS
    return [
        {"name": "Material berubah", "icon": "📦",
         "on": feedback_count > 0 or p["material_availability_pct"] != 100 or n_short > 0,
         "detail": f"{n_short} shortage · {feedback_count} feedback"},
        {"name": "Demand meningkat", "icon": "📈",
         "on": p["demand_multiplier"] > 1 or p["campaign_uplift_multiplier"] > 1 or bool(surge),
         "detail": f"×{p['demand_multiplier']:.2f}" + (f" · lonjakan {', '.join(surge)}" if surge else "")},
        {"name": "Supplier delay", "icon": "🚚",
         "on": p["supplier_eta_shift_days"] > 0 or n_eta > 0 or late_supply,
         "detail": f"{n_eta} ETA risk · shift {p['supplier_eta_shift_days']:+d} hari"},
        {"name": "Kapasitas turun", "icon": "🏭",
         "on": p["line_capacity_pct"] < 100 or cap_hold,
         "detail": f"Line {p['line_capacity_pct']:.0f}%"},
        {"name": "KPI lewat threshold", "icon": "🎯",
         "on": k["stockout_risk"] >= th["stockout_risk"] or k["delayed_orders"] >= th["delayed_orders"]
         or k["overstock_risk"] >= th["overstock"],
         "detail": f"stockout {k['stockout_risk']} · delay {k['delayed_orders']} · overstock {k['overstock_risk']}"},
    ]
