# Integrated DECIDE Decision Cockpit
**Dynamic Demand to Production Decision System** — Prototype digital TI4001 Proyek Rekayasa Inter-Disiplin ITB, Kelompok 39.

> ⚠️ **Prototype / Dummy Data.** Seluruh data adalah data dummy yang mengikuti struktur dataset pada dokumen tugas. Aplikasi **tidak** terhubung ke SAP, API supplier, maupun sistem PT Paragon. "Rilis ke SAP" hanya simulasi.

Satu aplikasi Streamlit, tiga role (PPC / Production Planner, Supply Planner, Leader Produksi), delapan halaman H01–H08 mengikuti UI Tree, User Flow, dan TO-BE CFD.

---

## 1. Instalasi

Butuh Python 3.10 atau lebih baru.

```bash
cd decide
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Menjalankan

```bash
streamlit run app.py
```
Browser terbuka di `http://localhost:8501`. Halaman pertama adalah **H01 Overview & Early Warning**. Ganti role melalui **Select Role** di sidebar.

Opsional:
```bash
python -m pytest tests -v        # 13 test (10 functional test + 3 sanity)
python tests/test_engine.py      # alternatif tanpa pytest
python scripts/generate_data.py  # membangkitkan ulang CSV dummy (seed tetap → hasil identik)
```

---

## 3. Struktur folder final

```
decide/
├── app.py                     # entry point: sidebar (role, menu), routing halaman
├── requirements.txt
├── README.md
├── .streamlit/config.toml     # tema (navy / orange / teal)
├── views/                     # 8 halaman (H01–H08), masing-masing punya render()
│   ├── overview.py            # H01 Overview & Early Warning
│   ├── demand_buffer.py       # H02 Demand & Buffer Monitoring
│   ├── priority.py            # H03 Production Priority Ranking
│   ├── feasibility.py         # H04 Feasibility Gate
│   ├── sequencing.py          # H05 Sequencing & ETA
│   ├── scenario.py            # H06 What-if & Replanning
│   ├── approval.py            # H07 Decision Review & Approval
│   └── monitoring.py          # H08 Performance Monitoring
├── engine/                    # decision engine murni (pandas, tanpa Streamlit)
│   ├── config.py              # semua parameter: Z, CV floor, bobot AHP, line rate, dll.
│   ├── buffer_engine.py
│   ├── priority_engine.py
│   ├── feasibility_engine.py
│   ├── sequencing_engine.py
│   ├── eta_engine.py
│   ├── scenario_engine.py     # orkestrasi pipeline + KPI + perbandingan skenario
│   ├── approval_engine.py     # state machine approval (submit/confirm/approve/revise/release)
│   └── quality_engine.py      # sasaran mutu, NC/CAPA, trigger replanning (selaras ISO 9001)
├── data/                      # dummy CSV
│   ├── sku_master.csv  weekly_demand.csv  campaign.csv  stock.csv
│   └── bom.csv  material.csv  supplier.csv  capacity.csv
├── utils/
│   ├── helpers.py             # load & validasi data, format angka Indonesia
│   ├── styles.py              # CSS, kartu KPI, badge, stepper, styling tabel
│   └── state.py               # session state, akses role, cache hasil engine
├── scripts/generate_data.py   # generator dummy data (deterministik)
└── tests/test_engine.py       # functional test
```

**Catatan penyesuaian struktur:** folder halaman dinamai `views/` (bukan `pages/`). Streamlit otomatis menjadikan folder `pages/` sebagai menu multipage bawaan, yang akan bentrok dengan menu sidebar DECIDE yang berubah sesuai role. Dengan `views/` + `render()`, navigasi sepenuhnya dikendalikan `app.py`. Ditambahkan juga `engine/config.py`, `engine/approval_engine.py`, `utils/state.py`, dan `data/supplier.csv` agar tetap modular dan dapat diuji.

---

## Tampilan & elemen mutu
- Font **Poppins**, palet navy / oranye / teal, kartu KPI berikon, tabel ringkas dengan badge status.
- **Process tracker** di atas setiap halaman: H01→H08 dipetakan ke siklus PDCA, titik merah = tahap bermasalah.
- **Kontrol dokumen** di header tiap halaman (No. Dok, revisi, snapshot, status) dan **lembar pengesahan + audit trail** di H07.
- H08: **sasaran mutu** (target vs aktual), **ketidaksesuaian & tindakan korektif** otomatis dari HOLD/delay, dan **trigger replanning**.
- Visual: donut status, Days of Cover vs lead time, buffer zone per SKU, peta klasifikasi CR × AHP, komposisi skor AHP, coverage material, timeline produksi→QC→NDC, perbandingan skenario.
- Elemen mutu *selaras prinsip* ISO 9001:2015 (6.2, 6.3, 7.5, 9.1, 10.2) — bukan klaim sertifikasi.

## 4. Data flow

```
CSV (data/) ──► helpers.load_data ──► validate_data (H01: "Data lengkap & valid?")
                     │
                     ▼
   ┌──────────── scenario_engine.run_pipeline(data, params) ────────────┐
   │ buffer_engine ─► priority_engine ─► feasibility_engine ─►          │
   │   (B, σ, P, C,     (AHP K1–K4,        (MRP BOM × qty,              │
   │    SS, ROP, Max,    CR, P1/P2/P3)      RCCP jam line,              │
   │    NIP, DoC, qty)                      LAYAK / HOLD)               │
   │                       ─► sequencing_engine ─► eta_engine ─► KPI    │
   │                          (P1→P2→P3, CR,      (start, finish,       │
   │                           grup kategori)      QC, ETA NDC, delay)  │
   └────────────────────────────────────────────────────────────────────┘
                     │  (di-cache per kombinasi parameter)
                     ▼
   H01–H05 membaca hasil skenario terpilih · H06 membandingkan Baseline vs Alternative
   H07 menyimpan snapshot proposed schedule di approval_engine (session state)
   H08 membaca KPI approved plan + pemicu replanning ──► kembali ke H06
```

### Dependency antar module
| Module | Bergantung pada |
|---|---|
| `buffer_engine` | `config` |
| `priority_engine` | `config`, output buffer |
| `feasibility_engine` | `config`, `helpers` (format), output priority, `bom`/`material`/`capacity` |
| `sequencing_engine` | `config`, output feasibility + priority |
| `eta_engine` | `config`, output sequencing, `capacity` |
| `scenario_engine` | kelima engine di atas |
| `approval_engine` | — (murni Python) |
| `utils/state` | `scenario_engine`, `approval_engine`, `helpers`, Streamlit |
| `views/*` | `utils/state`, `utils/styles`, `utils/helpers`, engine terkait |

### Input–output tiap engine
| Engine | Input | Output |
|---|---|---|
| Buffer/ROP | SKU master, weekly demand, campaign, stock, *demand multiplier, campaign uplift multiplier, qty override* | Per SKU: B, σ, P, C, SS, ROP, Max Level, NIP, Days of Cover, Recommended Qty, Status Normal/Watch/Risk, flag overstock |
| Priority (AHP) | Output buffer (hanya NIP ≤ ROP), bobot AHP | K1–K4 nilai & skor lokal, AHP Score, Ranking, Critical Ratio, Priority Class, alasan |
| Feasibility | Priority, BOM, material, capacity, *material availability %, supplier ETA shift, line capacity %* | Status LAYAK/HOLD + alasan, detail SKU × komponen, saldo & alert material |
| Sequencing | Feasibility (LAYAK saja) + priority | Urutan produksi, flag changeover |
| ETA | Sequence, kalender kapasitas, line rate, setup, QC, distribusi | Start, Finish Production, Finish QC, ETA NDC, Target, Delay, Status Delay |
| Scenario | Data + parameter skenario | Seluruh output di atas + KPI; tabel perbandingan Baseline vs Scenario |
| Approval | Status workflow + aksi role | Status baru, jumlah revisi, audit trail |

---

## 5. Logic decision engine (ringkas)

**Buffer/ROP** — Matang: rata-rata 8 minggu · Growing: rata-rata 4 minggu × growth ratio (dibatasi 0,8–1,3) · Baru: min(1, n/8) × histori sendiri + sisanya × B analog × analog ratio. σ = max(std, CV floor × B) dengan CV floor 20/30/45%. P = LT produksi + QC + distribusi + 7 hari review. C = Σ B × (uplift − 1) × hari overlap / 7 pada horizon P + 14 hari. SS = Z × σ × √(P/7), Z = 1,645 / 1,881 / 1,645 (service level 95/97/95%). ROP = B×P/7 + C + SS. Max = ROP + 4B. NIP = On Hand + WIP − Order Committed. DoC = NIP / [(B×P/7 + C)/P]. Jika NIP ≤ ROP → qty = Max − NIP dibulatkan ke atas ke kelipatan batch; selain itu 0.

**Priority** — K1 = DoC ÷ P (cost, makin kecil makin urgen), K2 = Order Committed, K3 = C, K4 = margin/unit × qty. Skor lokal tiap kriteria dari matriks perbandingan berpasangan antar SKU (rasio nilai), lalu AHP = 0,519·K1 + 0,201·K2 + 0,201·K3 + 0,079·K4. Bobot ada di `engine/config.py`; uji konsistensi (CR = 0,016) ditampilkan di H03.

**Klasifikasi** — Critical Ratio = DoC / (LT produksi + LT QC). P1 jika CR < 1; P2/P3 dipisah median AHP SKU non-P1.

**Feasibility** — Gross = qty × kebutuhan per unit; Net Shortage = max(0, Gross − stok tersedia − pasokan siap). Shortage > 0 → HOLD; material cukup tetapi jam line tidak cukup → HOLD; selain itu LAYAK. Material & jam dialokasikan berurutan P1 → P3 (CR terkecil dulu).

**Sequencing** — Rule 1 kelas, Rule 2 CR terkecil, Rule 3 SKU sekategori dimajukan bila selisih CR ≤ 0,25 dan tidak melompati kelas.

**ETA** — Durasi = qty / 10.000 unit/jam + setup 2 jam (+1 jam bila ganti kategori). Line 07:00, 2 shift (16 jam), Rabu 18 Nov maintenance 4 jam, akhir pekan libur. ETA NDC = selesai produksi + 1 hari kerja QC + 1 hari kerja distribusi. Target = 9 Nov + Days of Cover; ETA > target → **FLAG TERLAMBAT** + jumlah hari.

### Hasil baseline (cocok dengan dokumen)
- 8 dari 12 SKU perlu produksi; qty rekomendasi identik slide 35 (BB-002 85.000, SS-002 50.000, SS-005 28.000, …).
- AHP: BB-002 0,240 · SS-005 0,158 · SS-002 0,151 · BB-005 0,129 · … (identik slide 32). Kelas P1/P2/P3 identik slide 33.
- Feasibility: **BB-002 HOLD** — "Tube & tutup 20 ml kurang 12.000 set" (pasokan 30.000 set ETA 23 Nov belum siap); **SS-005 HOLD** — botol pump 30 ml kurang 16.000 set.
- 6 order LAYAK disekuensing; BB-005 & BB-006 mendapat FLAG TERLAMBAT (±1,3 hari).

---

## 6. Skenario demo (±5 menit)

1. **PPC** → H01: lihat 8 SKU Risk, 2 HOLD, 2 terlambat, alert material.
2. H02 → filter Lifecycle "Baru", pilih SKU untuk melihat langkah perhitungan ROP.
3. H03 → ranking AHP, consistency test, badge P1/P2/P3.
4. H04 → alasan HOLD BB-002 (tube kurang 12.000 set).
5. H05 → urutan + Gantt + flag terlambat.
6. H06 → set *Supplier ETA shift* = −7 hari → **Run Scenario** → HOLD jadi 0, bandingkan KPI → pilih *Alternative* → **Use Selected Scenario**.
7. H07 → **Submit**. Ganti role **Supply Planner** → Confirm (atau Reject dengan reason + constraint). Ganti role **Leader Produksi** → Approve → status **APPROVED — Ready for SAP Release**. Kembali ke PPC → rilis (simulasi).
8. H08 → KPI approved plan, perbandingan Tanpa rencana / Baseline / Approved, indikator Trigger Replanning.

---

## 7. Functional test

| # | Test | Hasil |
|---|---|---|
| 1 | SKU NIP > ROP tidak masuk production queue | PASS |
| 2 | SKU NIP ≤ ROP menghasilkan recommended qty (kelipatan batch, mencapai Max Level) | PASS |
| 3 | Critical Ratio < 1 → P1 | PASS |
| 4 | Material shortage → HOLD (BB-002 kurang 12.000 set) | PASS |
| 5 | Hanya SKU LAYAK masuk sequencing | PASS |
| 6 | P1 didahulukan sebelum P2 dan P3 | PASS |
| 7 | ETA melewati target → FLAG TERLAMBAT | PASS |
| 8 | Perubahan parameter what-if mengubah rekomendasi (demand, ETA supplier, kapasitas) | PASS |
| 9 | Schedule tidak dapat Approved sebelum material confirmation | PASS |
| 10 | Revision/Reject wajib reason | PASS |

---

## 8. Asumsi prototype
- Snapshot stok NDC 9 Nov 2026; siklus produksi mulai Senin 16 Nov 2026 07:00. Pasokan supplier dianggap "siap" jika ETA ≤ 16 Nov.
- Satu line liquid (LQ-01), satu SKU dalam satu waktu; line rate seragam 10.000 unit/jam; jendela kapasitas siklus = 16–20 Nov.
- Demand historis minggu campaign dinormalisasi dengan faktor uplift sebelum menghitung baseline agar tidak double count dengan C.
- Horizon campaign = P + 14 hari look-ahead (sesuai slide 28).
- Status Watch: ROP < NIP ≤ ROP + 1 minggu baseline. Overstock: NIP > Max Level (sebelum rencana); setelah rencana: posisi > Max + 1 batch (toleransi pembulatan batch).
- Stockout risk setelah rencana = order terlambat + order P1 berstatus HOLD.
- Nilai inventori = (NIP + qty diproduksi) × COGS. Biaya revisi = Rp 2,5 jt per revisi (asumsi dummy).
- Target ETA = tanggal stok NDC diperkirakan habis (snapshot + Days of Cover).
- Data stok SKU yang tidak tercantum di dokumen (BB-006, SS-001…SS-006) dilengkapi agar NIP sama dengan slide 29. BOM, material, supplier, dan kapasitas sepenuhnya dummy.
- Autentikasi disederhanakan menjadi pemilih role; semua keputusan tersimpan di session state (hilang saat browser ditutup / server di-restart).

## 9. Limitation & future development
- **Integrasi data:** belum ada koneksi SAP / SC Collaboration Hub / Brand Insight; berikutnya bisa lewat ekspor terjadwal (CSV/Excel) lalu API.
- **Persistensi:** session state saja; perlu database (mis. SQLite/PostgreSQL) untuk histori versi rencana dan audit trail lintas sesi.
- **Multi-line & multi-pabrik:** sequencing baru satu line; perlu alokasi line per stream, shift calendar per pabrik, dan matriks changeover antar-SKU.
- **Material time-phased:** pasokan dinilai siap/tidak per tanggal butuh tunggal; berikutnya MRP time-phased per slot produksi, termasuk pengiriman parsial.
- **Forecasting:** baseline berbasis rata-rata; dapat ditingkatkan dengan sinyal e-commerce / demand sensing setelah divalidasi.
- **Optimasi:** what-if masih deterministik; pengembangan lanjut dapat memakai heuristik/MILP untuk trade-off delay vs changeover.
- **Validasi bisnis:** parameter (Z, CV floor, bobot AHP, ambang KPI, biaya revisi) perlu dikonfirmasi melalui wawancara dengan PPC / Supply Planner Paragon.
- **Akses & keamanan:** login corporate dan otorisasi per role belum diimplementasikan.
