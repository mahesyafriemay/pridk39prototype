"""
Sequencing Engine

Input : summary feasibility (hanya LAYAK) + skor prioritas
Output: urutan produksi pada satu line liquid (satu SKU satu waktu).

Rule 1: P1 -> P2 -> P3
Rule 2: dalam kelas yang sama, Critical Ratio terkecil lebih dulu
Rule 3: jika aman, SKU sekategori ditempatkan berdekatan untuk mengurangi
        changeover — SKU sekategori dengan kategori SKU sebelumnya boleh
        dimajukan bila selisih CR-nya <= GROUPING_CR_TOLERANCE terhadap
        kandidat CR terkecil (tidak pernah melompati kelas).
"""
from __future__ import annotations

import pandas as pd

from engine import config as cfg
from engine.feasibility_engine import CLASS_ORDER


def run_sequencing_engine(feasibility_df: pd.DataFrame, priority_df: pd.DataFrame,
                          tolerance: float = cfg.GROUPING_CR_TOLERANCE) -> pd.DataFrame:
    cols = ["Sequence", "SKU_ID", "Nama_Produk", "Kategori", "Priority_Class", "AHP_Score",
            "Critical_Ratio", "Quantity", "Changeover", "Days_of_Cover"]
    if feasibility_df is None or feasibility_df.empty:
        return pd.DataFrame(columns=cols)
    ok = feasibility_df[feasibility_df["Status"] == "LAYAK"]
    if ok.empty:
        return pd.DataFrame(columns=cols)
    df = ok[["SKU_ID", "Recommended_Qty"]].merge(
        priority_df[["SKU_ID", "Nama_Produk", "Kategori", "Priority_Class", "AHP_Score", "Critical_Ratio",
                     "Days_of_Cover", "Prod_QC_LT"]], on="SKU_ID")
    df = df.rename(columns={"Recommended_Qty": "Quantity"})

    ordered = []
    prev_cat = None
    for cls in sorted(df["Priority_Class"].unique(), key=CLASS_ORDER.get):
        pool = df[df["Priority_Class"] == cls].sort_values("Critical_Ratio").to_dict("records")
        while pool:
            pick = pool[0]
            if prev_cat is not None and pick["Kategori"] != prev_cat:
                same = [p for p in pool if p["Kategori"] == prev_cat
                        and p["Critical_Ratio"] - pick["Critical_Ratio"] <= tolerance]
                if same:
                    pick = same[0]
            pick["Grouped"] = pick is not pool[0]
            pool.remove(pick)
            pick["Changeover"] = "Ganti kategori" if (prev_cat is not None and pick["Kategori"] != prev_cat) else (
                "Awal line" if prev_cat is None else "Kategori sama")
            prev_cat = pick["Kategori"]
            ordered.append(pick)

    out = pd.DataFrame(ordered)
    out.insert(0, "Sequence", range(1, len(out) + 1))
    return out
