"""
DECIDE — Konfigurasi parameter decision engine.
Seluruh konstanta di sini dapat diubah tanpa menyentuh logic engine.
PROTOTYPE / DUMMY DATA — bukan parameter aktual PT Paragon.
"""
from datetime import datetime

# ---------------------------------------------------------------------------
# Tanggal referensi siklus perencanaan
# ---------------------------------------------------------------------------
SNAPSHOT_DATE = datetime(2026, 11, 9)          # snapshot stok NDC (sesuai dokumen)
PLAN_START = datetime(2026, 11, 16, 7, 0)      # slot awal line pada siklus ini
MATERIAL_NEED_DATE = datetime(2026, 11, 16)    # pasokan dianggap "siap" jika ETA <= tanggal ini

# ---------------------------------------------------------------------------
# Buffer / ROP engine
# ---------------------------------------------------------------------------
REVIEW_DAYS = 7                 # periode review ditambahkan ke horizon P
CAMPAIGN_LOOKAHEAD_DAYS = 14    # horizon campaign = P + look-ahead
CYCLE_COVER_WEEKS = 4           # Max Level = ROP + B x 4 minggu
BASELINE_WEEKS_MATANG = 8
BASELINE_WEEKS_GROWING = 4
GROWTH_RATIO_BOUNDS = (0.8, 1.3)
NEW_SKU_FULL_HISTORY_WEEKS = 8  # bobot histori sendiri SKU baru = min(1, n_minggu / 8)

CV_FLOOR = {"Matang": 0.20, "Growing": 0.30, "Baru": 0.45}
SERVICE_LEVEL = {"Matang": 0.95, "Growing": 0.97, "Baru": 0.95}
Z_VALUE = {"Matang": 1.645, "Growing": 1.881, "Baru": 1.645}

WATCH_BAND_WEEKS = 1.0          # Watch jika ROP < NIP <= ROP + 1 minggu baseline

# ---------------------------------------------------------------------------
# Priority engine (AHP) — bobot hasil AHP dokumen (CR = 0,016)
# ---------------------------------------------------------------------------
AHP_WEIGHTS = {"K1": 0.519, "K2": 0.201, "K3": 0.201, "K4": 0.079}
AHP_CRITERIA_LABEL = {
    "K1": "Urgensi Stok",
    "K2": "Order Aktual",
    "K3": "Dampak Campaign",
    "K4": "Kontribusi Margin",
}
# Matriks perbandingan berpasangan kriteria (dokumen slide 30)
AHP_PAIRWISE = [
    [1, 3, 3, 5],
    [1 / 3, 1, 1, 3],
    [1 / 3, 1, 1, 3],
    [1 / 5, 1 / 3, 1 / 3, 1],
]
AHP_RANDOM_INDEX = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12}

# ---------------------------------------------------------------------------
# Sequencing & ETA engine
# ---------------------------------------------------------------------------
LINE_RATE = 10_000          # unit / jam
SETUP_HOURS = 2.0           # persiapan per SKU
CATEGORY_CHANGEOVER_HOURS = 1.0   # tambahan cleaning jika ganti kategori
QC_WORKING_DAYS = 1
DISTRIBUTION_WORKING_DAYS = 1
GROUPING_CR_TOLERANCE = 0.25      # Rule 3: SKU sekategori boleh dimajukan jika selisih CR <= toleransi

# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------
REVISION_COST_PER_EVENT = 2_500_000     # Rp per revisi jadwal (asumsi dummy)
KPI_THRESHOLDS = {"stockout_risk": 2, "delayed_orders": 2, "overstock": 1}

DUMMY_LABEL = "Prototype / Dummy Data"

# ---------------------------------------------------------------------------
# Sasaran mutu (ISO 9001:2015 klausul 6.2) — target dummy, perlu divalidasi
# ---------------------------------------------------------------------------
QUALITY_OBJECTIVES = {
    "stockout_risk": {"label": "Ketersediaan stok", "indikator": "SKU stockout risk", "target": 1, "op": "<="},
    "delayed_orders": {"label": "Ketepatan waktu", "indikator": "Order ETA > target", "target": 1, "op": "<="},
    "feasibility_rate": {"label": "Kelayakan rencana", "indikator": "Order LAYAK / antrean", "target": 0.80, "op": ">="},
    "overstock_risk": {"label": "Kendali persediaan", "indikator": "SKU overstock", "target": 0, "op": "<="},
    "revisions": {"label": "Stabilitas jadwal", "indikator": "Revisi jadwal / siklus", "target": 2, "op": "<="},
    "data_issues": {"label": "Integritas data", "indikator": "Isu validasi data", "target": 0, "op": "<="},
}
