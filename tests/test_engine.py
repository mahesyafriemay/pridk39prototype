"""
Functional test DECIDE (Step 6). Jalankan dari root project:
    python -m pytest tests -v
atau tanpa pytest:
    python tests/test_engine.py
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import approval_engine as ap  # noqa: E402
from engine.priority_engine import classify, criteria_weights_from_matrix  # noqa: E402
from engine.scenario_engine import recommendation_signature, run_pipeline  # noqa: E402
from utils.helpers import load_data, validate_data  # noqa: E402

DATA = load_data()
BASE = run_pipeline(DATA)


# ---------------------------------------------------------------------------
# Sanity: data & kalibrasi terhadap dokumen
# ---------------------------------------------------------------------------
def test_data_valid():
    assert validate_data(DATA) == []


def test_buffer_matches_document():
    b = BASE["buffer"].set_index("SKU_ID")
    assert abs(b.loc["BB-001", "ROP"] - 59380) < 50
    assert abs(b.loc["BB-002", "Days_of_Cover"] - 16.6) < 0.1
    assert b.loc["BB-002", "Recommended_Qty"] == 85000
    assert b.loc["SS-005", "Recommended_Qty"] == 28000


def test_ahp_weights_consistent():
    res = criteria_weights_from_matrix()
    assert res["CR"] < 0.1
    assert [round(x, 3) for x in res["weights"]] == [0.519, 0.201, 0.201, 0.079]


# ---------------------------------------------------------------------------
# 10 functional tests
# ---------------------------------------------------------------------------
def test_01_nip_above_rop_not_in_queue():
    b = BASE["buffer"]
    above = b[b["NIP"] > b["ROP"]]
    assert len(above) > 0
    assert (above["Recommended_Qty"] == 0).all()
    assert not set(above["SKU_ID"]) & set(BASE["priority"]["SKU_ID"])


def test_02_nip_below_rop_has_recommended_qty():
    b = BASE["buffer"]
    below = b[b["NIP"] <= b["ROP"]]
    assert len(below) > 0
    assert (below["Recommended_Qty"] > 0).all()
    assert (below["Recommended_Qty"] % below["Batch_Size"] == 0).all()   # kelipatan batch
    assert (below["NIP"] + below["Recommended_Qty"] >= below["Max_Level"]).all()


def test_03_cr_below_one_is_p1():
    p = BASE["priority"]
    assert (p.loc[p["Critical_Ratio"] < 1, "Priority_Class"] == "P1").all()
    assert (p.loc[p["Critical_Ratio"] >= 1, "Priority_Class"] != "P1").all()
    cls, _ = classify(pd.Series([0.5, 1.2, 1.5, 2.0]), pd.Series([0.1, 0.4, 0.3, 0.2]))
    # median skor non-P1 = 0.3 -> 0.4 & 0.3 = P2, 0.2 = P3
    assert cls == ["P1", "P2", "P2", "P3"]


def test_04_material_shortage_is_hold():
    f = BASE["feasibility"]
    short = f[~f["Material_OK"]]
    assert len(short) > 0
    assert (short["Status"] == "HOLD").all()
    bb2 = f.set_index("SKU_ID").loc["BB-002"]
    assert bb2["Status"] == "HOLD" and "12.000" in bb2["Reason"]


def test_05_only_layak_in_sequence():
    layak = set(BASE["feasibility"].query("Status == 'LAYAK'")["SKU_ID"])
    seq = set(BASE["sequence"]["SKU_ID"])
    assert seq == layak
    assert not seq & set(BASE["feasibility"].query("Status == 'HOLD'")["SKU_ID"])


def test_06_p1_before_p2_before_p3():
    order = {"P1": 1, "P2": 2, "P3": 3}
    ranks = BASE["sequence"]["Priority_Class"].map(order).tolist()
    assert ranks == sorted(ranks)


def test_07_eta_after_target_is_flagged():
    s = BASE["schedule"]
    late = s[s["ETA_NDC"] > s["Target_Date"]]
    assert len(late) > 0
    assert late["Late"].all() and (late["Delay_Days"] > 0).all()
    assert late["Status_Delay"].str.startswith("FLAG TERLAMBAT").all()
    ontime = s[s["ETA_NDC"] <= s["Target_Date"]]
    assert (~ontime["Late"]).all()


def test_08_whatif_changes_recommendation():
    alt = run_pipeline(DATA, {"demand_multiplier": 1.3})
    a = recommendation_signature(BASE).set_index("SKU_ID")
    b = recommendation_signature(alt).set_index("SKU_ID")
    assert not a["Recommended_Qty"].equals(b["Recommended_Qty"])
    assert (b["ROP"] > a["ROP"]).all()
    # supplier ETA dimajukan -> HOLD material berubah jadi LAYAK
    alt2 = run_pipeline(DATA, {"supplier_eta_shift_days": -7})
    assert alt2["kpi"]["hold"] < BASE["kpi"]["hold"]
    # kapasitas line turun drastis -> muncul HOLD kapasitas
    alt3 = run_pipeline(DATA, {"line_capacity_pct": 20})
    assert alt3["feasibility"]["Capacity_OK"].eq(False).any()


def test_09_cannot_approve_before_material_confirmation():
    wf = ap.submit(ap.new_workflow(), "Baseline", [{"SKU_ID": "BB-005"}])
    try:
        ap.leader_decision(wf, "Approve")
        raise AssertionError("Seharusnya tidak bisa approve")
    except ap.WorkflowError:
        pass
    wf = ap.supply_decision(wf, "Confirm")
    wf = ap.leader_decision(wf, "Approve")
    assert wf["status"] == ap.APPROVED
    assert ap.STATUS_LABEL[wf["status"]].startswith("APPROVED — Ready for SAP Release")


def test_10_revision_requires_reason():
    wf = ap.supply_decision(ap.submit(ap.new_workflow(), "Baseline", [{"SKU_ID": "BB-005"}]), "Confirm")
    for bad in ("", "   "):
        try:
            ap.leader_decision(wf, "Revise", bad)
            raise AssertionError("Revise tanpa reason harus ditolak")
        except ap.WorkflowError:
            pass
    wf2 = ap.leader_decision(wf, "Revise", "Kapasitas line 2 shift saja hari Rabu")
    assert wf2["status"] == ap.REVISION_REQUESTED and wf2["revisions"] == 1
    # Supply Planner reject juga wajib reason + constraint
    wf3 = ap.submit(ap.new_workflow(), "Baseline", [{"SKU_ID": "BB-005"}])
    try:
        ap.supply_decision(wf3, "Reject", "Tube belum datang", "")
        raise AssertionError("Reject tanpa constraint harus ditolak")
    except ap.WorkflowError:
        pass


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    passed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
            passed += 1
        except Exception as e:  # noqa: BLE001
            print(f"FAIL  {name}: {e!r}")
    print(f"\n{passed}/{len(tests)} test lulus")
    sys.exit(0 if passed == len(tests) else 1)
