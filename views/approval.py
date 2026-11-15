"""H07 — Decision Review & Approval (PPC, Supply Planner, Leader Produksi)."""
import pandas as pd
import streamlit as st

from engine import approval_engine as ap
from utils import state
from utils.helpers import fmt_dt, fmt_int, fmt_rp
from utils.styles import AMBER, GREEN, NAVY, ORANGE, RED, TEAL, alert_row, banner, html_table, kpi_card, section, stepper


def _plan_records(sch: pd.DataFrame) -> list:
    cols = ["Sequence", "SKU_ID", "Nama_Produk", "Priority_Class", "Quantity", "Start_Time", "Finish_Production",
            "ETA_NDC", "Target_Date", "Status_Delay"]
    recs = sch[cols].copy()
    for c in ("Start_Time", "Finish_Production", "ETA_NDC", "Target_Date"):
        recs[c] = recs[c].map(fmt_dt)
    return recs.to_dict("records")


def _steps(wf):
    s = wf["status"]
    ppc = ("done", "Submitted v%d" % wf["version"]) if s not in (ap.DRAFT,) else ("active", "Menunggu submit")
    if s in (ap.MATERIAL_REJECTED, ap.REVISION_REQUESTED):
        ppc = ("active", "Revisi & submit ulang")
    sup = {ap.SUBMITTED: ("active", "Menunggu konfirmasi"), ap.MATERIAL_REJECTED: ("blocked", "Reject — material")}.get(
        s, ("done", "Material confirmed") if s in (ap.MATERIAL_CONFIRMED, ap.APPROVED, ap.RELEASED, ap.REVISION_REQUESTED)
        else ("todo", "-"))
    lead = {ap.MATERIAL_CONFIRMED: ("active", "Menunggu review"), ap.REVISION_REQUESTED: ("blocked", "Revise"),
            ap.APPROVED: ("done", "Approved"), ap.RELEASED: ("done", "Approved")}.get(s, ("todo", "-"))
    rel = {ap.APPROVED: ("active", "Ready for SAP release"), ap.RELEASED: ("done", "Released (simulasi)")}.get(s, ("todo", "-"))
    return [("Submit · PPC", ppc[1], ppc[0]), ("Material · Supply Planner", sup[1], sup[0]),
            ("Review · Leader", lead[1], lead[0]), ("Rilis SAP · simulasi", rel[1], rel[0])]


def _signoff(wf):
    """Lembar pengesahan (ISO 9001 7.5 — rekaman terdokumentasi)."""
    last = {}
    for h in wf["history"]:
        if h["version"] == wf["version"]:
            last[h["role"]] = h
    rows = []
    for role, act in (("PPC", "Disusun"), ("Supply Planner", "Diverifikasi (material)"), ("Leader Produksi", "Disetujui")):
        h = last.get(role)
        if role == "PPC" and h is None:
            dec = "—"
        else:
            dec = (h["action"] if h else "Menunggu")
        rows.append({"Peran": role, "Fungsi": act, "Keputusan": dec, "Waktu": h["time"] if h else "—"})
    return pd.DataFrame(rows)


def render():
    state.header("Decision Review", "PPC submit → Supply Planner konfirmasi material → Leader approve / revise → rilis.")
    ss = st.session_state
    wf = ss.workflow
    role = ss.role
    res = state.active_result()

    color = {ap.APPROVED: GREEN, ap.RELEASED: GREEN, ap.MATERIAL_REJECTED: RED, ap.REVISION_REQUESTED: RED,
             ap.SUBMITTED: ORANGE, ap.MATERIAL_CONFIRMED: ORANGE}.get(wf["status"], NAVY)
    ico = {ap.APPROVED: "check", ap.RELEASED: "check", ap.MATERIAL_REJECTED: "alert", ap.REVISION_REQUESTED: "alert"}.get(wf["status"], "doc")
    banner(ap.STATUS_LABEL[wf["status"]], color, ico)
    stepper(_steps(wf))

    submitted = wf["plan"] is not None and wf["status"] != ap.DRAFT
    plan = pd.DataFrame(wf["plan"]) if submitted else (pd.DataFrame(_plan_records(res["schedule"]))
                                                       if not res["schedule"].empty else pd.DataFrame())
    kpi = wf["kpi"] if submitted and wf["kpi"] else res["kpi"]
    doc_no = f"DEC-PLN-2026-W47-R{max(wf['version'], 1):02d}"

    c = st.columns(4)
    with c[0]:
        kpi_card("Dokumen rencana", doc_no if submitted else "Draft", f"Skenario {wf['scenario'] or ss.selected_scenario}", NAVY, "doc")
    with c[1]:
        kpi_card("Order dijadwalkan", len(plan), f"{fmt_int(plan['Quantity'].sum()) if len(plan) else 0} unit", TEAL, "list")
    with c[2]:
        kpi_card("HOLD · Terlambat", f"{kpi['hold']} · {kpi['delayed_orders']}", "tidak dijadwalkan · ETA lewat", RED, "alert")
    with c[3]:
        kpi_card("Schedule revision", wf["revisions"], fmt_rp(wf["revisions"] * 2_500_000) + " biaya revisi", ORANGE, "refresh")

    left, right = st.columns([1.7, 1])
    with left:
        section("Proposed Schedule", f"Rev. {wf['version']:02d}" if submitted else "draft dari skenario aktif")
        if plan.empty:
            st.warning("Tidak ada order LAYAK. Revisi di H06 What-if.")
        else:
            html_table(plan, badges=("Priority_Class", "Status_Delay"), key_col="SKU_ID", sub_cols=("Nama_Produk",),
                       fmt={"Quantity": fmt_int},
                       labels={"Sequence": "#", "SKU_ID": "SKU", "Nama_Produk": "Produk", "Priority_Class": "Kelas",
                               "Quantity": "Qty", "Start_Time": "Start", "Finish_Production": "Selesai prod.",
                               "ETA_NDC": "ETA NDC", "Target_Date": "Target", "Status_Delay": "Status"})
    with right:
        section("Lembar Pengesahan")
        html_table(_signoff(wf), key_col="Peran", sub_cols=("Fungsi", "Waktu"))
        if wf["material_confirmation"] and wf["material_confirmation"]["decision"] == "Reject":
            mc = wf["material_confirmation"]
            alert_row("Supply Planner: Need Revision", f"{mc['reason']} — {mc['constraint']}", RED)
        if wf["leader_decision"] and wf["leader_decision"]["decision"] == "Revise":
            alert_row("Leader Produksi: Revise", wf["leader_decision"]["reason"], RED)

        section(f"Aksi · {role.split(' /')[0]}")
        with st.container(border=True):
            try:
                if role == state.PPC:
                    _ppc_panel(wf, res)
                elif role == state.SUPPLY:
                    _supply_panel(wf, res)
                else:
                    _leader_panel(wf)
            except ap.WorkflowError as e:
                st.error(str(e))

    section("Audit Trail")
    if wf["history"]:
        h = pd.DataFrame(wf["history"])[::-1]
        h["version"] = h["version"].map(lambda v: f"Rev. {v:02d}")
        html_table(h, key_col="action", sub_cols=("note",),
                   labels={"time": "Waktu", "version": "Revisi", "role": "Peran", "action": "Aksi", "note": "Catatan"})
    else:
        st.caption("Belum ada aktivitas.")


def _ppc_panel(wf, res):
    ss = st.session_state
    s = wf["status"]
    if s in (ap.DRAFT, ap.MATERIAL_REJECTED, ap.REVISION_REQUESTED):
        if s != ap.DRAFT:
            st.info("Jadwal dikembalikan. Revisi parameter di **H06 What-if**, pilih skenario, lalu submit ulang.")
            st.button("Buka H06 What-if", on_click=state.go_to, args=("What-if",))
        note = st.text_input("Catatan untuk reviewer (opsional)")
        if st.button(f"📤 Submit proposed schedule (skenario {ss.selected_scenario})", type="primary",
                     disabled=res["schedule"].empty):
            new = ap.submit(wf, ss.selected_scenario, _plan_records(res["schedule"]), res["kpi"])
            if note:
                new["history"][-1]["note"] += f" | {note}"
            state.set_workflow(new)
            ss.flash = "Proposed schedule disubmit ke Supply Planner."
            st.rerun()
    elif s == ap.APPROVED:
        st.success("Jadwal APPROVED — Ready for SAP Release. Prototype tidak menulis ke SAP; rilis hanya disimulasikan.")
        if st.button("🚀 Rilis jadwal final (simulasi SAP)", type="primary"):
            state.set_workflow(ap.release(wf))
            ss.flash = "Jadwal dirilis (simulasi). Pantau hasil di H08."
            st.rerun()
    elif s == ap.RELEASED:
        st.success("Jadwal final telah dirilis (simulasi). Lanjut pantau di H08 Performance Monitoring.")
        if st.button("Mulai siklus perencanaan berikutnya"):
            state.set_workflow(ap.reset(wf))
            st.rerun()
    else:
        st.info("Menunggu keputusan Supply Planner / Leader Produksi. Ganti role di sidebar untuk mensimulasikan.")


def _supply_panel(wf, res):
    ss = st.session_state
    if wf["status"] != ap.SUBMITTED:
        st.info("Belum ada jadwal yang menunggu konfirmasi material." if wf["status"] == ap.DRAFT
                else "Konfirmasi material sudah diberikan / tidak diperlukan pada status ini.")
        return
    skus = [r["SKU_ID"] for r in wf["plan"]]
    det = res["feasibility_detail"]
    det = det[det["SKU_ID"].isin(skus)] if not det.empty else det
    if not det.empty:
        agg = det.groupby(["Material_Name", "UoM"], as_index=False)[["Gross_Requirement", "Net_Shortage"]].sum()
        st.markdown("**Kebutuhan material jadwal yang disubmit**")
        html_table(agg, key_col="Material_Name", fmt={"Gross_Requirement": fmt_int, "Net_Shortage": fmt_int},
                   labels={"Material_Name": "Material", "Gross_Requirement": "Kebutuhan", "Net_Shortage": "Shortage"})
    risk = res["material"][res["material"]["Alert"] != "Material Ready"]
    for _, m in risk.iterrows():
        alert_row(f"{m['Alert']} · {m['Material_Name']}", f"Konfirmasi supplier: {m['Supplier_Confirmed']}", AMBER)

    decision = st.radio("Keputusan material", ["Confirm", "Reject / Need Revision"], horizontal=True)
    reason = st.text_area("Reason" + (" (wajib)" if decision != "Confirm" else " (opsional)"))
    constraint = ""
    if decision != "Confirm":
        constraint = st.text_input("Supplier ETA / material constraint (wajib)",
                                   placeholder="Contoh: Tube 20 ml baru tiba 23 Nov, parsial 15.000 set 18 Nov")
    if st.button("Kirim keputusan material", type="primary"):
        try:
            new = ap.supply_decision(wf, "Confirm" if decision == "Confirm" else "Reject", reason, constraint)
        except ap.WorkflowError as e:
            st.error(str(e))
            return
        state.set_workflow(new)
        ss.flash = "Material dikonfirmasi — diteruskan ke Leader Produksi." if decision == "Confirm" \
            else "Jadwal dikembalikan ke PPC untuk revisi."
        st.rerun()


def _leader_panel(wf):
    ss = st.session_state
    if wf["status"] != ap.MATERIAL_CONFIRMED:
        if wf["status"] == ap.SUBMITTED:
            st.warning("Approve belum tersedia: material belum dikonfirmasi Supply Planner.")
            st.button("Approve", disabled=True)
        else:
            st.info("Tidak ada jadwal yang menunggu review Leader.")
        return
    decision = st.radio("Keputusan Leader", ["Approve", "Revise"], horizontal=True)
    reason = st.text_area("Revision Reason (wajib)" if decision == "Revise" else "Catatan (opsional)")
    if st.button("Kirim keputusan", type="primary"):
        try:
            new = ap.leader_decision(wf, decision, reason)
        except ap.WorkflowError as e:
            st.error(str(e))
            return
        state.set_workflow(new)
        ss.flash = "APPROVED — Ready for SAP Release" if decision == "Approve" else "Revisi dikirim ke PPC."
        st.rerun()
