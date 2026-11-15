"""
Helper umum: load data, validasi data, format angka.
Tidak bergantung pada Streamlit agar dapat dipakai di unit test.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

REQUIRED_FIELDS = {
    "sku_master": ["SKU_ID", "Nama_Produk", "Brand", "Kategori", "Stream", "Lifecycle", "Launch_Date",
                   "Batch_Size", "Production_LT", "QC_LT", "Distribution_LT", "Analog_SKU", "Analog_Ratio",
                   "COGS", "Selling_Price", "Margin_Pct"],
    "weekly_demand": ["Week_Start", "SKU_ID", "Demand_Units", "Campaign_ID", "Is_Campaign"],
    "campaign": ["Campaign_ID", "Campaign_Name", "Type", "Start", "End", "Uplift_BB_Cream",
                 "Uplift_Sunscreen", "Status"],
    "stock": ["SKU_ID", "Location", "Snapshot_Date", "Stock_OnHand", "Stock_WIP", "WIP_ETA",
              "Order_Committed", "NIP"],
    "bom": ["SKU_ID", "Material_ID", "Qty_per_Unit"],
    "material": ["Material_ID", "Material_Name", "UoM", "Stock_Available", "Incoming_Qty", "Supplier_ETA",
                 "Supplier_ID", "Supplier_Confirmed"],
    "supplier": ["Supplier_ID", "Supplier_Name", "Lead_Time_Days", "OTIF_Rate"],
    "capacity": ["Line_ID", "Date", "Shift_Start", "Shift_Hours", "Planned_Downtime_Hours", "In_Plan_Window"],
}

FILES = {
    "sku_master": "sku_master.csv",
    "weekly_demand": "weekly_demand.csv",
    "campaign": "campaign.csv",
    "stock": "stock.csv",
    "bom": "bom.csv",
    "material": "material.csv",
    "supplier": "supplier.csv",
    "capacity": "capacity.csv",
}


def load_data(data_dir: Path | str = DATA_DIR) -> dict:
    data_dir = Path(data_dir)
    d = {k: pd.read_csv(data_dir / f, keep_default_na=False, na_values=[""]) for k, f in FILES.items()}
    d["sku_master"]["Analog_SKU"] = d["sku_master"]["Analog_SKU"].fillna("")
    d["sku_master"]["Analog_Ratio"] = d["sku_master"]["Analog_Ratio"].fillna(0.0)
    d["weekly_demand"]["Week_Start"] = pd.to_datetime(d["weekly_demand"]["Week_Start"])
    d["weekly_demand"]["Campaign_ID"] = d["weekly_demand"]["Campaign_ID"].fillna("")
    for c in ("Start", "End"):
        d["campaign"][c] = pd.to_datetime(d["campaign"][c])
    d["stock"]["Stock_WIP"] = d["stock"]["Stock_WIP"].fillna(0)
    d["material"]["Supplier_ETA"] = pd.to_datetime(d["material"]["Supplier_ETA"])
    d["material"]["Incoming_Qty"] = d["material"]["Incoming_Qty"].fillna(0)
    d["capacity"]["Date"] = pd.to_datetime(d["capacity"]["Date"])
    d["capacity"]["In_Plan_Window"] = d["capacity"]["In_Plan_Window"].astype(str).str.lower() == "true"
    return d


def validate_data(d: dict) -> list[str]:
    """Validasi sederhana (User Flow: 'Data lengkap dan valid?'). Return list isu; kosong = valid."""
    issues = []
    for name, fields in REQUIRED_FIELDS.items():
        missing = [f for f in fields if f not in d[name].columns]
        if missing:
            issues.append(f"{name}: kolom hilang {missing}")
    skus = set(d["sku_master"]["SKU_ID"])
    for name in ("weekly_demand", "stock", "bom"):
        orphan = set(d[name]["SKU_ID"]) - skus
        if orphan:
            issues.append(f"{name}: SKU tidak ada di master {sorted(orphan)}")
    no_stock = skus - set(d["stock"]["SKU_ID"])
    if no_stock:
        issues.append(f"stock: SKU tanpa posisi stok {sorted(no_stock)}")
    no_bom = skus - set(d["bom"]["SKU_ID"])
    if no_bom:
        issues.append(f"bom: SKU tanpa BOM {sorted(no_bom)}")
    orphan_m = set(d["bom"]["Material_ID"]) - set(d["material"]["Material_ID"])
    if orphan_m:
        issues.append(f"bom: material tidak dikenal {sorted(orphan_m)}")
    orphan_s = set(d["material"]["Supplier_ID"]) - set(d["supplier"]["Supplier_ID"])
    if orphan_s:
        issues.append(f"material: supplier tidak dikenal {sorted(orphan_s)}")
    if (d["stock"][["Stock_OnHand", "Stock_WIP", "Order_Committed"]] < 0).any().any():
        issues.append("stock: terdapat nilai negatif")
    if (d["weekly_demand"]["Demand_Units"] < 0).any():
        issues.append("weekly_demand: demand negatif")
    dup = d["weekly_demand"].duplicated(["Week_Start", "SKU_ID"]).sum()
    if dup:
        issues.append(f"weekly_demand: {dup} baris duplikat")
    nip_calc = d["stock"]["Stock_OnHand"] + d["stock"]["Stock_WIP"] - d["stock"]["Order_Committed"]
    if (nip_calc != d["stock"]["NIP"]).any():
        issues.append("stock: kolom NIP tidak konsisten dengan On Hand + WIP - Order Committed")
    return issues


# ---------------------------------------------------------------------------
# Formatting (gaya Indonesia: titik ribuan, koma desimal)
# ---------------------------------------------------------------------------
def fmt_int(x) -> str:
    try:
        return f"{float(x):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return str(x)


def fmt_dec(x, n=2) -> str:
    try:
        s = f"{float(x):,.{n}f}"
    except (TypeError, ValueError):
        return str(x)
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_rp(x) -> str:
    x = float(x)
    if abs(x) >= 1e9:
        return f"Rp {fmt_dec(x / 1e9, 2)} M"
    if abs(x) >= 1e6:
        return f"Rp {fmt_dec(x / 1e6, 1)} jt"
    return f"Rp {fmt_int(x)}"


def fmt_dt(ts) -> str:
    if ts is None or pd.isna(ts):
        return "-"
    hari = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"][ts.weekday()]
    bulan = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"][ts.month - 1]
    return f"{hari} {ts.day:02d} {bulan} {ts:%H:%M}"


def fmt_date(ts) -> str:
    if ts is None or pd.isna(ts):
        return "-"
    bulan = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"][ts.month - 1]
    return f"{ts.day:02d} {bulan} {ts.year}"
