"""
Approval Engine — state machine Decision Review & Approval (H07).

PPC submit  ->  Supply Planner confirm / reject  ->  Leader approve / revise  ->  PPC rilis (simulasi SAP)

Aturan:
- Leader tidak dapat Approve sebelum material dikonfirmasi Supply Planner.
- Reject (Supply Planner) wajib reason + supplier ETA / material constraint.
- Revise (Leader) wajib Revision Reason.
- Setiap reject / revise menambah jumlah schedule revision.
Tidak ada penulisan ke SAP — status RELEASED hanya simulasi.
"""
from __future__ import annotations

import copy
from datetime import datetime

DRAFT = "DRAFT"
SUBMITTED = "SUBMITTED"
MATERIAL_CONFIRMED = "MATERIAL_CONFIRMED"
MATERIAL_REJECTED = "MATERIAL_REJECTED"
REVISION_REQUESTED = "REVISION_REQUESTED"
APPROVED = "APPROVED"
RELEASED = "RELEASED"

STATUS_LABEL = {
    DRAFT: "DRAFT — Belum disubmit",
    SUBMITTED: "SUBMITTED — Menunggu konfirmasi material (Supply Planner)",
    MATERIAL_CONFIRMED: "MATERIAL CONFIRMED — Menunggu review Leader Produksi",
    MATERIAL_REJECTED: "NEED REVISION — Material belum siap (kembali ke PPC)",
    REVISION_REQUESTED: "NEED REVISION — Diminta revisi oleh Leader (kembali ke PPC)",
    APPROVED: "APPROVED — Ready for SAP Release",
    RELEASED: "RELEASED — Jadwal final dirilis (simulasi SAP)",
}


class WorkflowError(Exception):
    pass


def new_workflow() -> dict:
    return {
        "status": DRAFT, "scenario": None, "plan": None, "kpi": None,
        "material_confirmation": None, "leader_decision": None,
        "revision_reason": None, "revisions": 0, "version": 0, "history": [],
    }


def _log(wf, role, action, note=""):
    wf["history"].append({"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "version": wf["version"],
                          "role": role, "action": action, "note": note})


def submit(wf: dict, scenario_name: str, plan_records: list, kpi: dict | None = None) -> dict:
    wf = copy.deepcopy(wf)
    if wf["status"] not in (DRAFT, MATERIAL_REJECTED, REVISION_REQUESTED):
        raise WorkflowError(f"Tidak dapat submit pada status {wf['status']}.")
    if not plan_records:
        raise WorkflowError("Proposed schedule kosong — tidak ada order LAYAK untuk disubmit.")
    wf.update(status=SUBMITTED, scenario=scenario_name, plan=plan_records, kpi=kpi,
              material_confirmation=None, leader_decision=None)
    wf["version"] += 1
    _log(wf, "PPC", "Submit proposed schedule", f"Skenario: {scenario_name}, {len(plan_records)} order")
    return wf


def supply_decision(wf: dict, decision: str, reason: str = "", constraint: str = "") -> dict:
    wf = copy.deepcopy(wf)
    if wf["status"] != SUBMITTED:
        raise WorkflowError("Konfirmasi material hanya dapat dilakukan setelah PPC submit schedule.")
    if decision == "Confirm":
        wf["status"] = MATERIAL_CONFIRMED
        wf["material_confirmation"] = {"decision": "Confirm", "reason": reason, "constraint": constraint}
        _log(wf, "Supply Planner", "Confirm material", reason)
    elif decision == "Reject":
        if not reason.strip() or not constraint.strip():
            raise WorkflowError("Reject wajib mengisi reason dan supplier ETA / material constraint.")
        wf["status"] = MATERIAL_REJECTED
        wf["material_confirmation"] = {"decision": "Reject", "reason": reason, "constraint": constraint}
        wf["revisions"] += 1
        _log(wf, "Supply Planner", "Reject / Need Revision", f"{reason} | {constraint}")
    else:
        raise WorkflowError(f"Keputusan tidak dikenal: {decision}")
    return wf


def leader_decision(wf: dict, decision: str, reason: str = "") -> dict:
    wf = copy.deepcopy(wf)
    if wf["status"] != MATERIAL_CONFIRMED:
        raise WorkflowError("Leader belum dapat memutuskan: material belum dikonfirmasi Supply Planner.")
    if decision == "Approve":
        wf["status"] = APPROVED
        wf["leader_decision"] = {"decision": "Approve", "reason": reason}
        _log(wf, "Leader Produksi", "Approve", reason)
    elif decision == "Revise":
        if not reason.strip():
            raise WorkflowError("Revise wajib mengisi Revision Reason.")
        wf["status"] = REVISION_REQUESTED
        wf["leader_decision"] = {"decision": "Revise", "reason": reason}
        wf["revision_reason"] = reason
        wf["revisions"] += 1
        _log(wf, "Leader Produksi", "Revise", reason)
    else:
        raise WorkflowError(f"Keputusan tidak dikenal: {decision}")
    return wf


def release(wf: dict) -> dict:
    wf = copy.deepcopy(wf)
    if wf["status"] != APPROVED:
        raise WorkflowError("Rilis hanya dapat dilakukan setelah jadwal APPROVED.")
    wf["status"] = RELEASED
    _log(wf, "PPC", "Rilis jadwal final (simulasi SAP)", "Tidak ada koneksi SAP — prototype")
    return wf


def reset(wf: dict) -> dict:
    fresh = new_workflow()
    fresh["revisions"] = wf.get("revisions", 0)
    fresh["history"] = wf.get("history", [])
    return fresh
