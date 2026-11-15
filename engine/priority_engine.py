"""
Priority Engine (AHP) + Klasifikasi P1/P2/P3

Input : output buffer engine
Output: DataFrame SKU eligible (NIP <= ROP) dengan nilai kriteria K1-K4,
        skor lokal tiap kriteria (perbandingan berpasangan antar SKU),
        AHP Score, Ranking, Critical Ratio, Priority Class, alasan.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from engine import config as cfg

CRITERIA_DIRECTION = {"K1": "cost", "K2": "benefit", "K3": "benefit", "K4": "benefit"}


# ---------------------------------------------------------------------------
# AHP helpers
# ---------------------------------------------------------------------------
def criteria_weights_from_matrix(matrix=None):
    """Bobot kriteria (normalisasi kolom, rata-rata baris) + uji konsistensi."""
    A = np.array(matrix if matrix is not None else cfg.AHP_PAIRWISE, dtype=float)
    n = A.shape[0]
    norm = A / A.sum(axis=0)
    w = norm.mean(axis=1)
    lam = float(((A @ w) / w).mean())
    ci = (lam - n) / (n - 1)
    ri = cfg.AHP_RANDOM_INDEX.get(n, 1.12)
    cr = ci / ri if ri else 0.0
    return {"weights": w, "lambda_max": lam, "CI": ci, "RI": ri, "CR": cr, "normalized": norm}


def sku_pairwise_matrix(values, direction="benefit"):
    """Matriks perbandingan berpasangan antar SKU berbasis rasio nilai kriteria."""
    v = np.asarray(values, dtype=float)
    v = np.where(v <= 0, 1e-6, v)
    if direction == "cost":
        v = 1.0 / v               # makin kecil nilai, makin penting
    return v[:, None] / v[None, :]


def local_priority(values, direction="benefit"):
    """Skor lokal = rata-rata baris matriks perbandingan yang dinormalisasi kolom."""
    A = sku_pairwise_matrix(values, direction)
    return (A / A.sum(axis=0)).mean(axis=1)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
def classify(cr_values: pd.Series, ahp: pd.Series):
    """P1: CR < 1.  P2/P3: dipisah median AHP dari SKU non-P1."""
    is_p1 = cr_values < 1
    non_p1 = ahp[~is_p1]
    median = float(non_p1.median()) if len(non_p1) else float("nan")
    cls = []
    for crit, score in zip(cr_values, ahp):
        if crit < 1:
            cls.append("P1")
        elif score >= median:
            cls.append("P2")
        else:
            cls.append("P3")
    return cls, median


def _reason(r) -> str:
    if r["Priority_Class"] == "P1":
        return (f"Stok habis ±{r['Days_of_Cover']:.1f} hari, sebelum produksi+QC selesai "
                f"({r['Prod_QC_LT']} hari)")
    lead = max(("K1", "K2", "K3", "K4"), key=lambda k: r[f"{k}_Weighted"])
    return f"Stok masih cukup (CR {r['Critical_Ratio']:.2f}); pendorong skor: {cfg.AHP_CRITERIA_LABEL[lead]}"


def run_priority_engine(buffer_df: pd.DataFrame, weights: dict | None = None) -> pd.DataFrame:
    w = weights or cfg.AHP_WEIGHTS
    df = buffer_df[buffer_df["Need_Production"]].copy().reset_index(drop=True)
    cols_out = ["Rank", "SKU_ID", "Nama_Produk", "Kategori", "Days_of_Cover", "Order_Committed",
                "Campaign_Add_C", "Margin_Contribution", "AHP_Score", "Critical_Ratio", "Priority_Class",
                "Recommended_Qty", "Prod_QC_LT", "Median_NonP1", "Reason"]
    if df.empty:
        return pd.DataFrame(columns=cols_out)

    df["K1_Value"] = df["Days_of_Cover"] / df["P_Days"]
    df["K2_Value"] = df["Order_Committed"]
    df["K3_Value"] = df["Campaign_Add_C"]
    df["Margin_Contribution"] = df["Margin_Unit"] * df["Recommended_Qty"]
    df["K4_Value"] = df["Margin_Contribution"]

    df["AHP_Score"] = 0.0
    for k, direction in CRITERIA_DIRECTION.items():
        df[f"{k}_Score"] = local_priority(df[f"{k}_Value"], direction)
        df[f"{k}_Weighted"] = w[k] * df[f"{k}_Score"]
        df["AHP_Score"] += df[f"{k}_Weighted"]

    df["Critical_Ratio"] = df["Days_of_Cover"] / df["Prod_QC_LT"]
    df["Priority_Class"], median = classify(df["Critical_Ratio"], df["AHP_Score"])
    df["Median_NonP1"] = median

    df = df.sort_values("AHP_Score", ascending=False).reset_index(drop=True)
    df.insert(0, "Rank", range(1, len(df) + 1))
    df["Reason"] = df.apply(_reason, axis=1)
    return df
