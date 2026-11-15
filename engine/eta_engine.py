"""
ETA Engine

Input : sequence_df, kalender kapasitas line, params (line rate, setup, QC, distribusi)
Output: Start, Finish Production, Finish QC, ETA NDC, Target, Delay, Status Delay.

Production Time = Quantity / Line Rate + Setup (+ changeover jika ganti kategori)
ETA NDC         = Finish Production + QC (hari kerja) + Distribusi (hari kerja)
Target          = tanggal stok NDC diperkirakan habis (Snapshot + Days of Cover)
"""
from __future__ import annotations

from datetime import timedelta

import pandas as pd

from engine import config as cfg


def default_params() -> dict:
    return {
        "line_rate": cfg.LINE_RATE,
        "setup_hours": cfg.SETUP_HOURS,
        "changeover_hours": cfg.CATEGORY_CHANGEOVER_HOURS,
        "qc_days": cfg.QC_WORKING_DAYS,
        "distribution_days": cfg.DISTRIBUTION_WORKING_DAYS,
        "line_capacity_pct": 100.0,
    }


def add_working_days(ts: pd.Timestamp, n: int) -> pd.Timestamp:
    d = ts
    added = 0
    while added < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d


def _build_slots(capacity: pd.DataFrame, capacity_pct: float):
    """Daftar slot kerja (start, end) per hari dari kalender kapasitas."""
    slots = []
    cap = capacity.sort_values("Date")
    for _, c in cap.iterrows():
        hours = max(0.0, float(c["Shift_Hours"]) - float(c["Planned_Downtime_Hours"])) * capacity_pct / 100
        if hours <= 0:
            continue
        hh, mm = map(int, str(c["Shift_Start"]).split(":"))
        start = pd.Timestamp(c["Date"]) + timedelta(hours=hh, minutes=mm)
        slots.append([start, start + timedelta(hours=hours)])
    # cadangan: perpanjang hari kerja default jika kalender habis
    last = slots[-1][0] if slots else pd.Timestamp(cfg.PLAN_START)
    for i in range(1, 60):
        d = last + timedelta(days=i)
        if d.weekday() < 5:
            slots.append([d, d + timedelta(hours=16 * capacity_pct / 100)])
    return slots


def _consume(slots, cursor, hours):
    """Mulai dari cursor, habiskan `hours` jam di slot kerja. Return (start, finish, cursor)."""
    remaining = hours
    start = None
    for s in slots:
        s_start, s_end = s
        if s_end <= cursor:
            continue
        t = max(cursor, s_start)
        if start is None:
            start = t
        avail = (s_end - t).total_seconds() / 3600
        if avail >= remaining - 1e-9:
            finish = t + timedelta(hours=remaining)
            return start, finish, finish
        remaining -= avail
        cursor = s_end
    raise RuntimeError("Kalender kapasitas tidak cukup")


def run_eta_engine(sequence_df: pd.DataFrame, capacity: pd.DataFrame, params: dict | None = None,
                   snapshot=cfg.SNAPSHOT_DATE, plan_start=cfg.PLAN_START) -> pd.DataFrame:
    params = {**default_params(), **(params or {})}
    if sequence_df is None or sequence_df.empty:
        return pd.DataFrame(columns=["Sequence", "SKU_ID", "ETA_NDC", "Late"])
    slots = _build_slots(capacity, params["line_capacity_pct"])
    cursor = pd.Timestamp(plan_start)
    rows = []
    for _, r in sequence_df.iterrows():
        setup = params["setup_hours"] + (params["changeover_hours"] if r["Changeover"] == "Ganti kategori" else 0)
        duration = r["Quantity"] / params["line_rate"] + setup
        start, finish, cursor = _consume(slots, cursor, duration)
        finish_qc = add_working_days(finish, params["qc_days"])
        eta = add_working_days(finish_qc, params["distribution_days"])
        target = pd.Timestamp(snapshot) + timedelta(days=float(r["Days_of_Cover"]))
        delay_days = max(0.0, (eta - target).total_seconds() / 86400)
        rows.append({**r.to_dict(),
                     "Setup_Hours": setup,
                     "Production_Duration_Hours": duration,
                     "Start_Time": start, "Finish_Production": finish, "Finish_QC": finish_qc,
                     "ETA_NDC": eta, "Target_Date": target,
                     "Late": eta > target, "Delay_Days": delay_days,
                     "Status_Delay": f"FLAG TERLAMBAT ({delay_days:.1f} hari)" if eta > target else "On time"})
    return pd.DataFrame(rows)
