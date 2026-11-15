"""
Generator dummy dataset DECIDE (deterministik, seed tetap).

Struktur & angka acuan mengikuti dokumen TugasPekan10_39 (slide 26-29):
SKU master, campaign calendar, posisi stok, dan target ROP per SKU.
Demand mingguan 26 minggu dibangkitkan sehingga baseline engine
mendekati angka ROP pada dokumen.

PROTOTYPE / DUMMY DATA — bukan data aktual PT Paragon.

Jalankan dari root project:  python scripts/generate_data.py
"""
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import config as cfg  # noqa: E402
from engine.buffer_engine import campaign_addition, campaign_weekly_factor  # noqa: E402

DATA = ROOT / "data"
rng = np.random.default_rng(39)

# ---------------------------------------------------------------------------
# 1. SKU Master (dokumen slide 26)
# ---------------------------------------------------------------------------
sku_rows = [
    # id, nama, kategori, lifecycle, launch, ukuran, batch, ltP, ltQC, ltD, analog, ratio, cogs, price
    ("BB-001", "BB Cream Light 20 ml", "BB Cream", "Matang", "2023-03-06", 20, 5000, 12, 5, 4, "", None, 22000, 38000),
    ("BB-002", "BB Cream Natural 20 ml", "BB Cream", "Matang", "2023-03-06", 20, 5000, 12, 5, 4, "", None, 22000, 38000),
    ("BB-003", "BB Cream Medium 20 ml", "BB Cream", "Growing", "2025-11-03", 20, 5000, 12, 5, 4, "", None, 22000, 38000),
    ("BB-004", "BB Cream Tan 20 ml", "BB Cream", "Matang", "2023-03-06", 20, 2000, 14, 5, 4, "", None, 22000, 38000),
    ("BB-005", "BB Cream Light 30 ml (varian baru)", "BB Cream", "Baru", "2026-09-28", 30, 3000, 14, 6, 4, "BB-001", 0.28, 31000, 52000),
    ("BB-006", "BB Cream Deep 20 ml (varian baru)", "BB Cream", "Baru", "2026-10-05", 20, 1000, 14, 6, 4, "BB-004", 0.40, 22000, 38000),
    ("SS-001", "Sunscreen Gel SPF30 40 ml", "Sunscreen", "Matang", "2022-08-01", 40, 10000, 10, 6, 4, "", None, 18000, 32000),
    ("SS-002", "Sunscreen Gel SPF50 40 ml", "Sunscreen", "Growing", "2025-09-01", 40, 10000, 10, 6, 4, "", None, 19000, 34000),
    ("SS-003", "Sunscreen Serum SPF50 30 ml", "Sunscreen", "Growing", "2025-12-01", 30, 5000, 12, 6, 4, "", None, 24000, 42000),
    ("SS-004", "Sunscreen Milk SPF35 60 ml", "Sunscreen", "Matang", "2022-08-01", 60, 3000, 12, 6, 4, "", None, 23000, 40000),
    ("SS-005", "Tinted Sunscreen SPF50 30 ml (baru)", "Sunscreen", "Baru", "2026-09-21", 30, 4000, 14, 7, 4, "SS-002", 0.50, 25000, 44000),
    ("SS-006", "Sunscreen Gel SPF30 15 ml Travel (baru)", "Sunscreen", "Baru", "2026-10-12", 15, 2000, 12, 6, 4, "SS-001", 0.08, 11000, 20000),
]
sku = pd.DataFrame(sku_rows, columns=[
    "SKU_ID", "Nama_Produk", "Kategori", "Lifecycle", "Launch_Date", "Size_ml", "Batch_Size",
    "Production_LT", "QC_LT", "Distribution_LT", "Analog_SKU", "Analog_Ratio", "COGS", "Selling_Price"])
sku.insert(2, "Brand", "Wardah")
sku.insert(4, "Stream", "Liquid")
sku["Margin_Pct"] = ((sku["Selling_Price"] - sku["COGS"]) / sku["Selling_Price"]).round(3)

# ---------------------------------------------------------------------------
# 2. Campaign calendar 2026 (dokumen slide 27)
# ---------------------------------------------------------------------------
campaign = pd.DataFrame([
    ("C01", "6.6 Mid-Year Sale", "Mega sale", "2026-06-04", "2026-06-07", 1.70, 1.60),
    ("C02", "7.7 Sale", "Mega sale", "2026-07-06", "2026-07-09", 1.50, 1.45),
    ("C03", "8.8 Beauty Sale", "Mega sale", "2026-08-05", "2026-08-09", 1.85, 1.70),
    ("C04", "9.9 Sale", "Mega sale", "2026-09-08", "2026-09-10", 1.60, 1.50),
    ("C05", "10.10 Sale", "Mega sale", "2026-10-08", "2026-10-11", 1.70, 1.60),
    ("C06", "11.11 Sale", "Mega sale", "2026-11-09", "2026-11-12", 1.80, 1.70),
    ("C07", "Gajian Nov", "Payday", "2026-11-25", "2026-11-30", 1.20, 1.20),
    ("C08", "12.12 Harbolnas", "Mega sale", "2026-12-09", "2026-12-13", 1.90, 1.75),
], columns=["Campaign_ID", "Campaign_Name", "Type", "Start", "End", "Uplift_BB_Cream", "Uplift_Sunscreen"])
for c in ("Start", "End"):
    campaign[c] = pd.to_datetime(campaign[c])
snap = pd.Timestamp(cfg.SNAPSHOT_DATE)
campaign["Status"] = np.where(campaign["End"] < snap, "Selesai",
                              np.where(campaign["Start"] <= snap, "Berjalan", "Akan datang"))

# ---------------------------------------------------------------------------
# 3. Stock position (dokumen slide 27 & 29; SKU yang tidak tercantum dilengkapi)
# ---------------------------------------------------------------------------
stock = pd.DataFrame([
    ("BB-001", 78330, 0, "", 3080),
    ("BB-002", 43570, 0, "", 5140),
    ("BB-003", 18090, 0, "", 3270),
    ("BB-004", 20350, 4770, "2026-11-21", 1250),
    ("BB-005", 2580, 450, "2026-11-13", 790),
    ("BB-006", 1100, 0, "", 200),
    ("SS-001", 64200, 0, "", 4200),
    ("SS-002", 23500, 0, "", 3500),
    ("SS-003", 9900, 0, "", 900),
    ("SS-004", 4700, 0, "", 700),
    ("SS-005", 3500, 0, "", 500),
    ("SS-006", 3150, 0, "", 150),
], columns=["SKU_ID", "Stock_OnHand", "Stock_WIP", "WIP_ETA", "Order_Committed"])
stock.insert(1, "Location", "NDC")
stock.insert(2, "Snapshot_Date", cfg.SNAPSHOT_DATE.strftime("%Y-%m-%d"))
stock["NIP"] = stock["Stock_OnHand"] + stock["Stock_WIP"] - stock["Order_Committed"]

# ROP acuan dokumen (slide 29) untuk kalibrasi demand
ROP_TARGET = {"BB-001": 59380, "BB-002": 72940, "BB-003": 15245, "BB-004": 18715, "BB-005": 10886,
              "BB-006": 4355, "SS-001": 50493, "SS-002": 39604, "SS-003": 8177, "SS-004": 9507,
              "SS-005": 18153, "SS-006": 5405}

# ---------------------------------------------------------------------------
# 4. Weekly demand (26 minggu, 11 Mei - 2 Nov 2026)
# ---------------------------------------------------------------------------
weeks = [datetime(2026, 5, 11) + timedelta(weeks=i) for i in range(26)]


def target_baseline(r):
    P = r.Production_LT + r.QC_LT + r.Distribution_LT + cfg.REVIEW_DAYS
    camp_factor, _ = campaign_addition(1.0, r.Kategori, cfg.SNAPSHOT_DATE, P + cfg.CAMPAIGN_LOOKAHEAD_DAYS, campaign)
    f = P / 7 + camp_factor + cfg.Z_VALUE[r.Lifecycle] * cfg.CV_FLOOR[r.Lifecycle] * math.sqrt(P / 7)
    return ROP_TARGET[r.SKU_ID] / f


B_target = {r.SKU_ID: target_baseline(r) for r in sku.itertuples()}
clean = {}
for r in sku.itertuples():
    B = B_target[r.SKU_ID]
    if r.Lifecycle == "Matang":
        s = B * (1 + rng.normal(0, 0.08, 26))
        s = s * B / s[-8:].mean()
        clean[r.SKU_ID] = list(zip(weeks, s))
    elif r.Lifecycle == "Growing":
        g = 1.10 ** (1 / 4)
        s = np.array([g ** t for t in range(26)]) * (1 + rng.normal(0, 0.05, 26))
        ratio = np.clip(s[-4:].mean() / s[-8:-4].mean(), *cfg.GROWTH_RATIO_BOUNDS)
        s = s * B / (s[-4:].mean() * ratio)
        clean[r.SKU_ID] = list(zip(weeks, s))

for r in sku[sku.Lifecycle == "Baru"].itertuples():
    launch = pd.Timestamp(r.Launch_Date)
    w_list = [w for w in weeks if w >= launch]
    n = len(w_list)
    w = min(1.0, n / cfg.NEW_SKU_FULL_HISTORY_WEEKS)
    analog = B_target[r.Analog_SKU] * r.Analog_Ratio
    own = max((B_target[r.SKU_ID] - (1 - w) * analog) / w, 0.25 * B_target[r.SKU_ID])
    s = own * (1 + rng.normal(0, 0.12, n))
    s = s * own / s.mean()
    clean[r.SKU_ID] = list(zip(w_list, s))

dem_rows = []
kat = sku.set_index("SKU_ID")["Kategori"]
for sid, series in clean.items():
    for ws, val in series:
        f = campaign_weekly_factor(ws, kat[sid], campaign)
        cid = ""
        for c in campaign.itertuples():
            if c.Start <= ws + timedelta(days=6) and c.End >= ws:
                cid = c.Campaign_ID
        dem_rows.append((ws.strftime("%Y-%m-%d"), ws.isocalendar()[1], sid, int(round(val * f)), cid, int(bool(cid))))
demand = pd.DataFrame(dem_rows, columns=["Week_Start", "ISO_Week", "SKU_ID", "Demand_Units", "Campaign_ID", "Is_Campaign"])
demand = demand.sort_values(["Week_Start", "SKU_ID"]).reset_index(drop=True)

# ---------------------------------------------------------------------------
# 5. Supplier, Material, BOM, Capacity (dummy untuk H04 & H05)
# ---------------------------------------------------------------------------
supplier = pd.DataFrame([
    ("SUP-01", "PT Bahan Kimia Nusantara (dummy)", "Bulk / bahan baku", 14, 0.95),
    ("SUP-02", "PT Kemasan Tube Prima (dummy)", "Tube & tutup", 21, 0.85),
    ("SUP-03", "PT Botol Plastik Jaya (dummy)", "Botol", 21, 0.80),
    ("SUP-04", "PT Karton Cetak Mandiri (dummy)", "Karton", 10, 0.97),
], columns=["Supplier_ID", "Supplier_Name", "Supply_Type", "Lead_Time_Days", "OTIF_Rate"])

material = pd.DataFrame([
    # id, nama, uom, stok, incoming, eta, supplier, confirmed
    ("M-BULK-BB", "Bulk BB Cream", "L", 3800, 1500, "2026-11-13", "SUP-01", "Ya"),
    ("M-BULK-SG", "Bulk Sunscreen Gel", "L", 2200, 1200, "2026-11-12", "SUP-01", "Belum"),
    ("M-BULK-SM", "Bulk Sunscreen Milk", "L", 900, 0, "", "SUP-01", "Ya"),
    ("M-BULK-SS", "Bulk Sunscreen Serum", "L", 400, 0, "", "SUP-01", "Ya"),
    ("M-BULK-TS", "Bulk Tinted Sunscreen", "L", 1000, 0, "", "SUP-01", "Ya"),
    ("M-TUBE-20", "Tube & tutup 20 ml", "set", 79000, 30000, "2026-11-23", "SUP-02", "Belum"),
    ("M-TUBE-30", "Tube & tutup 30 ml", "set", 22000, 0, "", "SUP-02", "Ya"),
    ("M-BTL-40", "Botol & tutup 40 ml", "set", 30000, 40000, "2026-11-14", "SUP-03", "Ya"),
    ("M-BTL-60", "Botol & tutup 60 ml", "set", 15000, 0, "", "SUP-03", "Ya"),
    ("M-BTL-30", "Botol pump 30 ml", "set", 12000, 30000, "2026-11-20", "SUP-03", "Belum"),
    ("M-BTL-15", "Botol travel 15 ml", "set", 8000, 0, "", "SUP-03", "Ya"),
    ("M-CTN-S", "Karton satuan kecil", "pcs", 150000, 50000, "2026-11-12", "SUP-04", "Ya"),
    ("M-CTN-M", "Karton satuan sedang", "pcs", 90000, 0, "", "SUP-04", "Ya"),
], columns=["Material_ID", "Material_Name", "UoM", "Stock_Available", "Incoming_Qty", "Supplier_ETA",
            "Supplier_ID", "Supplier_Confirmed"])

bom_map = {
    "BB-001": [("M-BULK-BB", 0.020), ("M-TUBE-20", 1), ("M-CTN-S", 1)],
    "BB-002": [("M-BULK-BB", 0.020), ("M-TUBE-20", 1), ("M-CTN-S", 1)],
    "BB-003": [("M-BULK-BB", 0.020), ("M-TUBE-20", 1), ("M-CTN-S", 1)],
    "BB-004": [("M-BULK-BB", 0.020), ("M-TUBE-20", 1), ("M-CTN-S", 1)],
    "BB-005": [("M-BULK-BB", 0.030), ("M-TUBE-30", 1), ("M-CTN-S", 1)],
    "BB-006": [("M-BULK-BB", 0.020), ("M-TUBE-20", 1), ("M-CTN-S", 1)],
    "SS-001": [("M-BULK-SG", 0.040), ("M-BTL-40", 1), ("M-CTN-M", 1)],
    "SS-002": [("M-BULK-SG", 0.040), ("M-BTL-40", 1), ("M-CTN-M", 1)],
    "SS-003": [("M-BULK-SS", 0.030), ("M-BTL-30", 1), ("M-CTN-S", 1)],
    "SS-004": [("M-BULK-SM", 0.060), ("M-BTL-60", 1), ("M-CTN-M", 1)],
    "SS-005": [("M-BULK-TS", 0.030), ("M-BTL-30", 1), ("M-CTN-S", 1)],
    "SS-006": [("M-BULK-SG", 0.015), ("M-BTL-15", 1), ("M-CTN-S", 1)],
}
bom = pd.DataFrame([(s, m, q) for s, comps in bom_map.items() for m, q in comps],
                   columns=["SKU_ID", "Material_ID", "Qty_per_Unit"])

cap_rows = []
for d in range(14):
    day = datetime(2026, 11, 16) + timedelta(days=d)
    working = day.weekday() < 5
    hours = 16 if working else 0
    downtime = 4 if day.strftime("%Y-%m-%d") == "2026-11-18" else 0
    note = "Preventive maintenance 4 jam" if downtime else ("Libur" if not working else "2 shift")
    cap_rows.append(("LQ-01", "Liquid Line 1", day.strftime("%Y-%m-%d"), "07:00", hours, downtime, note))
capacity = pd.DataFrame(cap_rows, columns=["Line_ID", "Line_Name", "Date", "Shift_Start", "Shift_Hours",
                                           "Planned_Downtime_Hours", "Note"])
# Jendela kapasitas siklus ini = 1 minggu kerja pertama (16-20 Nov); minggu berikutnya sebagai cadangan ETA
capacity["In_Plan_Window"] = pd.to_datetime(capacity["Date"]) <= pd.Timestamp("2026-11-20")

# ---------------------------------------------------------------------------
# Simpan
# ---------------------------------------------------------------------------
DATA.mkdir(exist_ok=True)
for c in ("Start", "End"):
    campaign[c] = campaign[c].dt.strftime("%Y-%m-%d")
sku.to_csv(DATA / "sku_master.csv", index=False)
demand.to_csv(DATA / "weekly_demand.csv", index=False)
campaign.to_csv(DATA / "campaign.csv", index=False)
stock.to_csv(DATA / "stock.csv", index=False)
bom.to_csv(DATA / "bom.csv", index=False)
material.to_csv(DATA / "material.csv", index=False)
supplier.to_csv(DATA / "supplier.csv", index=False)
capacity.to_csv(DATA / "capacity.csv", index=False)
print("Dummy data tersimpan di", DATA)
for f in sorted(DATA.glob("*.csv")):
    print(f"  {f.name:20s} {len(pd.read_csv(f)):>4d} baris")
