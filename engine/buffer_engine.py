"""
Buffer / ROP Engine (Demand & Buffer Intelligence)

Input : sku_master, weekly_demand, campaign, stock, params
Output: DataFrame per SKU berisi B, sigma, P, C, SS, ROP, Max Level, NIP,
        Days of Cover, Recommended Production Qty, Status (Normal/Watch/Risk).
"""
from __future__ import annotations

import math
from datetime import timedelta

import numpy as np
import pandas as pd

from engine import config as cfg


# ---------------------------------------------------------------------------
# Campaign helpers
# ---------------------------------------------------------------------------
def _overlap_days(start_a, end_a, start_b, end_b) -> int:
    """Jumlah hari overlap (inklusif) antara dua rentang tanggal."""
    s = max(start_a, start_b)
    e = min(end_a, end_b)
    return max(0, (e - s).days + 1)


def uplift_column(kategori: str) -> str:
    return "Uplift_BB_Cream" if kategori == "BB Cream" else "Uplift_Sunscreen"


def campaign_weekly_factor(week_start, kategori, campaign: pd.DataFrame) -> float:
    """Faktor uplift efektif satu minggu: 1 + sum((uplift-1) * overlap/7)."""
    week_end = week_start + timedelta(days=6)
    col = uplift_column(kategori)
    factor = 1.0
    for _, c in campaign.iterrows():
        ov = _overlap_days(week_start, week_end, c["Start"], c["End"])
        if ov:
            factor += (c[col] - 1) * ov / 7
    return factor


def campaign_addition(baseline, kategori, horizon_start, horizon_days, campaign, uplift_mult=1.0):
    """C = sum[ B x (uplift - 1) x hari overlap / 7 ] dalam horizon campaign."""
    horizon_end = horizon_start + timedelta(days=horizon_days - 1)
    col = uplift_column(kategori)
    total = 0.0
    detail = []
    for _, c in campaign.iterrows():
        ov = _overlap_days(horizon_start, horizon_end, c["Start"], c["End"])
        if ov:
            uplift = 1 + (c[col] - 1) * uplift_mult
            add = baseline * (uplift - 1) * ov / 7
            total += add
            detail.append(f"{c['Campaign_ID']} ({ov} hari)")
    return total, ", ".join(detail)


# ---------------------------------------------------------------------------
# Baseline demand per lifecycle
# ---------------------------------------------------------------------------
def _clean_series(sku_demand: pd.DataFrame) -> pd.Series:
    """Demand dinormalisasi dari efek campaign (agar tidak double count dengan C)."""
    s = sku_demand.sort_values("Week_Start")
    return (s["Demand_Units"] / s["Campaign_Factor"]).reset_index(drop=True)


def baseline_matang(series: pd.Series):
    last = series.tail(cfg.BASELINE_WEEKS_MATANG)
    return last.mean(), last.std(ddof=1) if len(last) > 1 else 0.0, "Rata-rata 8 minggu"


def baseline_growing(series: pd.Series):
    last4 = series.tail(cfg.BASELINE_WEEKS_GROWING)
    prev4 = series.tail(2 * cfg.BASELINE_WEEKS_GROWING).head(cfg.BASELINE_WEEKS_GROWING)
    ratio = last4.mean() / prev4.mean() if prev4.mean() > 0 else 1.0
    lo, hi = cfg.GROWTH_RATIO_BOUNDS
    ratio = float(np.clip(ratio, lo, hi))
    std8 = series.tail(8).std(ddof=1) if len(series) > 1 else 0.0
    return last4.mean() * ratio, std8, f"Rata-rata 4 minggu x growth {ratio:.2f}"


def baseline_baru(series: pd.Series, analog_baseline: float, analog_ratio: float):
    n = len(series)
    w = min(1.0, n / cfg.NEW_SKU_FULL_HISTORY_WEEKS)
    own = series.mean() if n else 0.0
    analog = analog_baseline * analog_ratio
    b = w * own + (1 - w) * analog
    std = series.std(ddof=1) if n > 1 else 0.0
    return b, std, f"{w:.0%} histori ({n} mgg) + {1 - w:.0%} analog"


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------
def default_params() -> dict:
    return {
        "demand_multiplier": 1.0,
        "campaign_uplift_multiplier": 1.0,
        "qty_override": {},          # {SKU_ID: qty}
    }


def classify_status(nip, rop, baseline) -> str:
    if nip <= rop:
        return "Risk"
    if nip <= rop + cfg.WATCH_BAND_WEEKS * baseline:
        return "Watch"
    return "Normal"


def round_up_batch(qty: float, batch: int) -> int:
    if qty <= 0:
        return 0
    return int(math.ceil(qty / batch) * batch)


def run_buffer_engine(data: dict, params: dict | None = None) -> pd.DataFrame:
    params = {**default_params(), **(params or {})}
    sku = data["sku_master"].copy()
    demand = data["weekly_demand"].copy()
    campaign = data["campaign"]
    stock = data["stock"].set_index("SKU_ID")

    # faktor campaign tiap minggu historis -> demand bersih
    kat = sku.set_index("SKU_ID")["Kategori"]
    demand["Campaign_Factor"] = [
        campaign_weekly_factor(ws, kat[s], campaign) for ws, s in zip(demand["Week_Start"], demand["SKU_ID"])
    ]

    dm = params["demand_multiplier"]
    rows = {}
    # Matang & Growing dahulu (dibutuhkan sebagai analog SKU Baru)
    order = sorted(sku.index, key=lambda i: sku.loc[i, "Lifecycle"] == "Baru")
    for i in order:
        r = sku.loc[i]
        series = _clean_series(demand[demand["SKU_ID"] == r["SKU_ID"]]) * dm
        if r["Lifecycle"] == "Matang":
            b, std, method = baseline_matang(series)
        elif r["Lifecycle"] == "Growing":
            b, std, method = baseline_growing(series)
        else:
            analog_b = rows[r["Analog_SKU"]]["Baseline_B"] if r["Analog_SKU"] in rows else 0.0
            b, std, method = baseline_baru(series, analog_b, float(r["Analog_Ratio"] or 0))

        cv_floor = cfg.CV_FLOOR[r["Lifecycle"]]
        sigma = max(std, cv_floor * b)
        P = int(r["Production_LT"] + r["QC_LT"] + r["Distribution_LT"] + cfg.REVIEW_DAYS)
        horizon = P + cfg.CAMPAIGN_LOOKAHEAD_DAYS
        C, camp_detail = campaign_addition(
            b, r["Kategori"], cfg.SNAPSHOT_DATE, horizon, campaign, params["campaign_uplift_multiplier"]
        )
        z = cfg.Z_VALUE[r["Lifecycle"]]
        ss = z * sigma * math.sqrt(P / 7)
        rop = b * P / 7 + C + ss
        max_level = rop + b * cfg.CYCLE_COVER_WEEKS

        st = stock.loc[r["SKU_ID"]]
        nip = float(st["Stock_OnHand"] + st["Stock_WIP"] - st["Order_Committed"])
        daily_need = (b * P / 7 + C) / P
        doc = nip / daily_need if daily_need > 0 else 999.0

        if nip <= rop:
            rec = round_up_batch(max_level - nip, int(r["Batch_Size"]))
        else:
            rec = 0
        # What-if override qty hanya berlaku untuk SKU yang memang masuk antrean (NIP <= ROP)
        if nip <= rop and r["SKU_ID"] in params["qty_override"]:
            rec = int(params["qty_override"][r["SKU_ID"]])

        rows[r["SKU_ID"]] = {
            "SKU_ID": r["SKU_ID"],
            "Nama_Produk": r["Nama_Produk"],
            "Kategori": r["Kategori"],
            "Stream": r["Stream"],
            "Lifecycle": r["Lifecycle"],
            "Baseline_B": b,
            "Baseline_Method": method,
            "Sigma": sigma,
            "CV": sigma / b if b else 0.0,
            "Z": z,
            "P_Days": P,
            "Campaign_Add_C": C,
            "Campaign_Detail": camp_detail or "-",
            "Safety_Stock": ss,
            "ROP": rop,
            "Max_Level": max_level,
            "Stock_OnHand": float(st["Stock_OnHand"]),
            "Stock_WIP": float(st["Stock_WIP"]),
            "Order_Committed": float(st["Order_Committed"]),
            "NIP": nip,
            "Days_of_Cover": doc,
            "Lead_Time_Total": int(r["Production_LT"] + r["QC_LT"] + r["Distribution_LT"]),
            "Prod_QC_LT": int(r["Production_LT"] + r["QC_LT"]),
            "Batch_Size": int(r["Batch_Size"]),
            "Recommended_Qty": rec,
            "Need_Production": bool(nip <= rop and rec > 0),
            "Status": classify_status(nip, rop, b),
            "Overstock": nip > max_level,
            "COGS": float(r["COGS"]),
            "Selling_Price": float(r["Selling_Price"]),
            "Margin_Unit": float(r["Selling_Price"] - r["COGS"]),
        }

    out = pd.DataFrame([rows[s] for s in sku["SKU_ID"]])
    return out
