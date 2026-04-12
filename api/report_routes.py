"""
Report API Routes (FR-0012)
Reporting endpoints for RFPO analytics, approval metrics, vendor stats, and email health.
All endpoints require GOD or RFPO_ADMIN permissions.
"""

from flask import Blueprint, request, jsonify
from sqlalchemy import func, case, text, extract
from datetime import datetime, timedelta
import sys
import os
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    db, RFPO, User, Consortium, Team, Project, Vendor,
    RFPOApprovalAction, RFPOApprovalInstance, EmailLog,
)
from utils import require_auth, error_response

logger = logging.getLogger(__name__)

report_api = Blueprint("report_api", __name__, url_prefix="/api/reports")


def _is_sqlite():
    """Check if we're running against SQLite (for SQL dialect differences)."""
    return "sqlite" in str(db.engine.url)


def _epoch_diff_days(col_end, col_start):
    """Cross-database days between two datetime columns."""
    if _is_sqlite():
        return (
            func.cast(func.strftime("%s", col_end), db.Integer)
            - func.cast(func.strftime("%s", col_start), db.Integer)
        ) / 86400.0
    else:
        # PostgreSQL: EXTRACT(EPOCH FROM (end - start)) / 86400
        return extract("epoch", col_end - col_start) / 86400.0


def _month_label(col):
    """Cross-database month grouping label."""
    if _is_sqlite():
        return func.strftime("%Y-%m", col).label("month")
    else:
        return func.to_char(col, "YYYY-MM").label("month")


# Status constants — RFPO.status uses capitalized values
RFPO_OPEN_STATUSES = ["Draft", "Pending Approval"]
RFPO_CLOSED_STATUSES = ["Approved"]
RFPO_REJECTED_STATUSES = ["Refused"]


def _require_report_admin():
    """Check that current user has GOD or RFPO_ADMIN permission. Returns error tuple or None."""
    user = getattr(request, "current_user", None)
    if not user:
        return jsonify({"success": False, "message": "Authentication required"}), 401
    perms = user.get_permissions() or []
    if "GOD" not in perms and "RFPO_ADMIN" not in perms:
        return jsonify({"success": False, "message": "Reporting requires admin permissions"}), 403
    return None


def _parse_date_range():
    """Parse optional date_from / date_to query params. Returns (from_dt, to_dt) or (None, None)."""
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    from_dt = to_dt = None
    if date_from:
        try:
            from_dt = datetime.strptime(date_from, "%Y-%m-%d")
        except ValueError:
            pass
    if date_to:
        try:
            to_dt = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            pass
    return from_dt, to_dt


def _base_rfpo_query():
    """Base query excluding soft-deleted RFPOs."""
    return db.session.query(RFPO).filter(RFPO.deleted_at.is_(None))


def _apply_date_filter(query, from_dt, to_dt):
    """Apply date range filter to a query on RFPO.created_at."""
    if from_dt:
        query = query.filter(RFPO.created_at >= from_dt)
    if to_dt:
        query = query.filter(RFPO.created_at < to_dt)
    return query


# ---------------------------------------------------------------------------
# RFPO Reports
# ---------------------------------------------------------------------------

@report_api.route("/rfpos", methods=["GET"])
@require_auth
def rfpo_report():
    """
    RFPO reporting endpoint.
    Query params:
      - report_type: summary (default) | drilldown | time_to_fulfill | rejected_by_category
      - group_by: submitter | consortium | department | project | vendor (for drilldown)
      - date_from / date_to: YYYY-MM-DD
    """
    auth_err = _require_report_admin()
    if auth_err:
        return auth_err

    report_type = request.args.get("report_type", "summary")
    allowed_types = ("summary", "drilldown", "time_to_fulfill", "rejected_by_category")
    if report_type not in allowed_types:
        return jsonify({"success": False, "message": f"Invalid report_type. Allowed: {', '.join(allowed_types)}"}), 400

    try:
        from_dt, to_dt = _parse_date_range()

        if report_type == "summary":
            return _rfpo_summary(from_dt, to_dt)
        elif report_type == "drilldown":
            return _rfpo_drilldown(from_dt, to_dt)
        elif report_type == "time_to_fulfill":
            return _rfpo_time_to_fulfill(from_dt, to_dt)
        elif report_type == "rejected_by_category":
            return _rfpo_rejected(from_dt, to_dt)
    except Exception as e:
        return error_response(e)


def _count_and_sum(statuses, from_dt=None, to_dt=None, use_approved_at=False):
    """Count + sum total_amount for RFPOs in given statuses, optionally filtered by date."""
    q = db.session.query(
        func.count(RFPO.id).label("count"),
        func.coalesce(func.sum(RFPO.total_amount), 0).label("total"),
    ).filter(RFPO.status.in_(statuses), RFPO.deleted_at.is_(None))

    date_col = RFPO.approved_at if use_approved_at else RFPO.created_at
    if from_dt:
        q = q.filter(date_col >= from_dt)
    if to_dt:
        q = q.filter(date_col < to_dt)
    row = q.first()
    return {"count": row.count or 0, "total_amount": float(row.total or 0)}


def _rfpo_summary(from_dt, to_dt):
    """Summary cards: open, closed last year, closed YTD, rejected, all, avg time."""
    now = datetime.utcnow()
    year_start = datetime(now.year, 1, 1)
    last_year_start = datetime(now.year - 1, 1, 1)

    open_data = _count_and_sum(RFPO_OPEN_STATUSES, from_dt, to_dt)
    closed_ly = _count_and_sum(RFPO_CLOSED_STATUSES, last_year_start, year_start, use_approved_at=True)
    closed_ytd = _count_and_sum(RFPO_CLOSED_STATUSES, year_start, None, use_approved_at=True)
    rejected = _count_and_sum(RFPO_REJECTED_STATUSES, from_dt, to_dt)

    all_q = db.session.query(
        func.count(RFPO.id), func.coalesce(func.sum(RFPO.total_amount), 0)
    ).filter(RFPO.deleted_at.is_(None))
    all_q = _apply_date_filter(all_q, from_dt, to_dt)
    all_row = all_q.first()

    # Average time to fulfill (days between created_at and approved_at)
    time_diff = _epoch_diff_days(RFPO.approved_at, RFPO.created_at)
    avg_q = db.session.query(
        func.avg(time_diff)
    ).filter(
        RFPO.approved_at.isnot(None), RFPO.deleted_at.is_(None)
    )
    avg_q = _apply_date_filter(avg_q, from_dt, to_dt)
    avg_days = avg_q.scalar()

    return jsonify({
        "success": True,
        "data": {
            "open_rfpos": open_data,
            "closed_last_year": closed_ly,
            "closed_ytd": closed_ytd,
            "rejected": rejected,
            "all_rfpos": {"count": all_row[0] or 0, "total_amount": float(all_row[1] or 0)},
            "avg_time_to_fulfill_days": round(float(avg_days), 1) if avg_days else None,
        },
    })


def _rfpo_drilldown(from_dt, to_dt):
    """Group RFPOs by a dimension and return count + total_amount per group."""
    group_by = request.args.get("group_by", "consortium")
    allowed_groups = ("submitter", "consortium", "department", "project", "vendor")
    if group_by not in allowed_groups:
        return jsonify({"success": False, "message": f"Invalid group_by. Allowed: {', '.join(allowed_groups)}"}), 400

    # Build group column + label join
    if group_by == "submitter":
        group_col = RFPO.requestor_id
        label_col = User.fullname.label("label")
        join = (User, RFPO.requestor_id == User.record_id)
    elif group_by == "consortium":
        group_col = RFPO.consortium_id
        label_col = Consortium.name.label("label")
        join = (Consortium, RFPO.consortium_id == Consortium.consort_id)
    elif group_by == "department":
        group_col = RFPO.team_id
        label_col = Team.name.label("label")
        join = (Team, RFPO.team_id == Team.id)
    elif group_by == "project":
        group_col = RFPO.project_id
        label_col = Project.name.label("label")
        join = (Project, RFPO.project_id == Project.project_id)
    else:  # vendor
        group_col = RFPO.vendor_id
        label_col = Vendor.company_name.label("label")
        join = (Vendor, RFPO.vendor_id == Vendor.id)

    q = db.session.query(
        group_col.label("id"),
        label_col,
        func.count(RFPO.id).label("count"),
        func.coalesce(func.sum(RFPO.total_amount), 0).label("total_amount"),
    ).outerjoin(*join).filter(RFPO.deleted_at.is_(None))

    q = _apply_date_filter(q, from_dt, to_dt)

    # Apply status filter if provided
    status_filter = request.args.get("status")
    if status_filter == "open":
        q = q.filter(RFPO.status.in_(RFPO_OPEN_STATUSES))
    elif status_filter == "closed":
        q = q.filter(RFPO.status.in_(RFPO_CLOSED_STATUSES))
    elif status_filter == "rejected":
        q = q.filter(RFPO.status.in_(RFPO_REJECTED_STATUSES))

    rows = q.group_by(group_col, label_col).order_by(func.sum(RFPO.total_amount).desc()).all()

    groups = []
    total_count = 0
    grand_total = 0.0
    for r in rows:
        amt = float(r.total_amount or 0)
        groups.append({
            "id": str(r.id) if r.id else None,
            "label": r.label or "Unassigned",
            "count": r.count,
            "total_amount": amt,
        })
        total_count += r.count
        grand_total += amt

    return jsonify({
        "success": True,
        "data": {
            "group_by": group_by,
            "groups": groups,
            "total_count": total_count,
            "grand_total": grand_total,
        },
    })


def _rfpo_time_to_fulfill(from_dt, to_dt):
    """Average time to fulfill by month."""
    ml = _month_label(RFPO.approved_at)
    time_diff_days = _epoch_diff_days(RFPO.approved_at, RFPO.created_at)

    q = db.session.query(
        ml,
        func.count(RFPO.id).label("count"),
        func.avg(time_diff_days).label("avg_days"),
        func.min(time_diff_days).label("min_days"),
        func.max(time_diff_days).label("max_days"),
    ).filter(RFPO.approved_at.isnot(None), RFPO.deleted_at.is_(None))
    q = _apply_date_filter(q, from_dt, to_dt)
    rows = q.group_by("month").order_by(ml.desc()).limit(24).all()

    # Overall average
    overall_q = db.session.query(
        func.avg(time_diff_days)
    ).filter(RFPO.approved_at.isnot(None), RFPO.deleted_at.is_(None))
    overall_q = _apply_date_filter(overall_q, from_dt, to_dt)
    overall_avg = overall_q.scalar()

    periods = []
    for r in rows:
        periods.append({
            "month": r.month if r.month else None,
            "count": r.count,
            "avg_days": round(float(r.avg_days), 1) if r.avg_days else None,
            "min_days": round(float(r.min_days), 1) if r.min_days else None,
            "max_days": round(float(r.max_days), 1) if r.max_days else None,
        })

    return jsonify({
        "success": True,
        "data": {
            "average_days": round(float(overall_avg), 1) if overall_avg else None,
            "by_period": periods,
        },
    })


def _rfpo_rejected(from_dt, to_dt):
    """Rejected RFPOs grouped by status (Refused, etc.)."""
    q = db.session.query(
        RFPO.status,
        func.count(RFPO.id).label("count"),
        func.coalesce(func.sum(RFPO.total_amount), 0).label("total_amount"),
    ).filter(RFPO.status.in_(RFPO_REJECTED_STATUSES), RFPO.deleted_at.is_(None))
    q = _apply_date_filter(q, from_dt, to_dt)
    rows = q.group_by(RFPO.status).all()

    categories = []
    for r in rows:
        categories.append({
            "status": r.status,
            "count": r.count,
            "total_amount": float(r.total_amount or 0),
        })

    return jsonify({"success": True, "data": {"categories": categories}})


# ---------------------------------------------------------------------------
# Approval Reports
# ---------------------------------------------------------------------------

@report_api.route("/approvals", methods=["GET"])
@require_auth
def approval_report():
    """
    Approval workflow reporting.
    Query params:
      - report_type: busiest_approvers | stage_timing | pending_queue | overdue | action_breakdown
      - date_from / date_to
    """
    auth_err = _require_report_admin()
    if auth_err:
        return auth_err

    report_type = request.args.get("report_type", "busiest_approvers")
    allowed = ("busiest_approvers", "stage_timing", "pending_queue", "overdue", "action_breakdown")
    if report_type not in allowed:
        return jsonify({"success": False, "message": f"Invalid report_type. Allowed: {', '.join(allowed)}"}), 400

    try:
        from_dt, to_dt = _parse_date_range()

        if report_type == "busiest_approvers":
            return _busiest_approvers(from_dt, to_dt)
        elif report_type == "stage_timing":
            return _stage_timing(from_dt, to_dt)
        elif report_type == "pending_queue":
            return _pending_queue()
        elif report_type == "overdue":
            return _overdue_actions()
        elif report_type == "action_breakdown":
            return _action_breakdown(from_dt, to_dt)
    except Exception as e:
        return error_response(e)


def _busiest_approvers(from_dt, to_dt):
    """Action counts per approver with approval rate."""
    q = db.session.query(
        RFPOApprovalAction.approver_id,
        RFPOApprovalAction.approver_name,
        func.count(RFPOApprovalAction.id).label("total"),
        func.sum(case((RFPOApprovalAction.status == "approved", 1), else_=0)).label("approved"),
        func.sum(case((RFPOApprovalAction.status == "refused", 1), else_=0)).label("refused"),
        func.sum(case((RFPOApprovalAction.status == "conditional", 1), else_=0)).label("conditional"),
        func.avg(
            func.extract("epoch", RFPOApprovalAction.completed_at - RFPOApprovalAction.assigned_at) / 86400
        ).label("avg_days"),
    ).filter(RFPOApprovalAction.status != "pending")

    if from_dt:
        q = q.filter(RFPOApprovalAction.completed_at >= from_dt)
    if to_dt:
        q = q.filter(RFPOApprovalAction.completed_at < to_dt)

    rows = q.group_by(
        RFPOApprovalAction.approver_id, RFPOApprovalAction.approver_name
    ).order_by(func.count(RFPOApprovalAction.id).desc()).all()

    approvers = []
    for r in rows:
        total = r.total or 0
        approved = int(r.approved or 0)
        approvers.append({
            "approver_id": r.approver_id,
            "name": r.approver_name,
            "total_actions": total,
            "approved": approved,
            "refused": int(r.refused or 0),
            "conditional": int(r.conditional or 0),
            "avg_response_days": round(float(r.avg_days), 1) if r.avg_days else None,
            "approval_rate_pct": round(approved / total * 100, 1) if total else 0,
        })

    return jsonify({"success": True, "data": {"approvers": approvers}})


def _stage_timing(from_dt, to_dt):
    """Average time per workflow stage."""
    q = db.session.query(
        RFPOApprovalAction.stage_name,
        func.count(RFPOApprovalAction.id).label("actions_completed"),
        func.avg(
            func.extract("epoch", RFPOApprovalAction.completed_at - RFPOApprovalAction.assigned_at) / 86400
        ).label("avg_days"),
        func.min(
            func.extract("epoch", RFPOApprovalAction.completed_at - RFPOApprovalAction.assigned_at) / 86400
        ).label("min_days"),
        func.max(
            func.extract("epoch", RFPOApprovalAction.completed_at - RFPOApprovalAction.assigned_at) / 86400
        ).label("max_days"),
    ).filter(
        RFPOApprovalAction.status != "pending",
        RFPOApprovalAction.completed_at.isnot(None),
        RFPOApprovalAction.assigned_at.isnot(None),
    )

    if from_dt:
        q = q.filter(RFPOApprovalAction.completed_at >= from_dt)
    if to_dt:
        q = q.filter(RFPOApprovalAction.completed_at < to_dt)

    rows = q.group_by(RFPOApprovalAction.stage_name).order_by(
        func.avg(func.extract("epoch", RFPOApprovalAction.completed_at - RFPOApprovalAction.assigned_at)).desc()
    ).all()

    stages = []
    for r in rows:
        stages.append({
            "stage_name": r.stage_name,
            "actions_completed": r.actions_completed,
            "avg_days": round(float(r.avg_days), 1) if r.avg_days else None,
            "min_days": round(float(r.min_days), 1) if r.min_days else None,
            "max_days": round(float(r.max_days), 1) if r.max_days else None,
        })

    return jsonify({"success": True, "data": {"stages": stages}})


def _pending_queue():
    """Real-time view of pending approval actions grouped by approver."""
    now = datetime.utcnow()
    actions = (
        db.session.query(
            RFPOApprovalAction.approver_id,
            RFPOApprovalAction.approver_name,
            RFPOApprovalAction.due_date,
            RFPOApprovalAction.assigned_at,
            RFPO.rfpo_id,
            RFPO.title,
            RFPO.total_amount,
        )
        .join(RFPOApprovalInstance, RFPOApprovalAction.instance_id == RFPOApprovalInstance.id)
        .join(RFPO, RFPOApprovalInstance.rfpo_id == RFPO.id)
        .filter(
            RFPOApprovalAction.status == "pending",
            RFPOApprovalInstance.overall_status == "waiting",
            RFPO.deleted_at.is_(None),
        )
        .order_by(RFPOApprovalAction.due_date.asc())
        .all()
    )

    # Group by approver
    approver_map = {}
    for a in actions:
        key = a.approver_id
        if key not in approver_map:
            approver_map[key] = {
                "approver_id": a.approver_id,
                "approver_name": a.approver_name,
                "pending_count": 0,
                "overdue_count": 0,
                "oldest_due": None,
                "rfpos": [],
            }
        entry = approver_map[key]
        entry["pending_count"] += 1
        is_overdue = a.due_date and a.due_date < now
        if is_overdue:
            entry["overdue_count"] += 1
        due_str = a.due_date.isoformat() if a.due_date else None
        if due_str and (entry["oldest_due"] is None or due_str < entry["oldest_due"]):
            entry["oldest_due"] = due_str
        days_pending = (now - a.assigned_at).days if a.assigned_at else None
        entry["rfpos"].append({
            "rfpo_id": a.rfpo_id,
            "title": a.title,
            "total_amount": float(a.total_amount) if a.total_amount else 0,
            "due_date": due_str,
            "days_pending": days_pending,
            "overdue": is_overdue,
        })

    result = sorted(approver_map.values(), key=lambda x: x["overdue_count"], reverse=True)
    return jsonify({"success": True, "data": {"pending_actions": result}})


def _overdue_actions():
    """All pending actions past their due date."""
    now = datetime.utcnow()
    actions = (
        db.session.query(
            RFPOApprovalAction.approver_id,
            RFPOApprovalAction.approver_name,
            RFPOApprovalAction.stage_name,
            RFPOApprovalAction.step_name,
            RFPOApprovalAction.due_date,
            RFPOApprovalAction.assigned_at,
            RFPO.rfpo_id,
            RFPO.title,
            RFPO.total_amount,
        )
        .join(RFPOApprovalInstance, RFPOApprovalAction.instance_id == RFPOApprovalInstance.id)
        .join(RFPO, RFPOApprovalInstance.rfpo_id == RFPO.id)
        .filter(
            RFPOApprovalAction.status == "pending",
            RFPOApprovalAction.due_date < now,
            RFPOApprovalInstance.overall_status == "waiting",
            RFPO.deleted_at.is_(None),
        )
        .order_by(RFPOApprovalAction.due_date.asc())
        .all()
    )

    overdue = []
    for a in actions:
        days_overdue = (now - a.due_date).days if a.due_date else 0
        overdue.append({
            "approver_id": a.approver_id,
            "approver_name": a.approver_name,
            "stage_name": a.stage_name,
            "step_name": a.step_name,
            "rfpo_id": a.rfpo_id,
            "title": a.title,
            "total_amount": float(a.total_amount) if a.total_amount else 0,
            "due_date": a.due_date.isoformat() if a.due_date else None,
            "days_overdue": days_overdue,
        })

    return jsonify({"success": True, "data": {"overdue_actions": overdue, "total_overdue": len(overdue)}})


def _action_breakdown(from_dt, to_dt):
    """Distribution of approval decisions."""
    q = db.session.query(
        RFPOApprovalAction.status,
        func.count(RFPOApprovalAction.id).label("count"),
    )
    if from_dt:
        q = q.filter(RFPOApprovalAction.completed_at >= from_dt)
    if to_dt:
        q = q.filter(RFPOApprovalAction.completed_at < to_dt)
    rows = q.group_by(RFPOApprovalAction.status).all()

    total = sum(r.count for r in rows)
    breakdown = []
    for r in rows:
        breakdown.append({
            "status": r.status,
            "count": r.count,
            "pct": round(r.count / total * 100, 1) if total else 0,
        })

    return jsonify({"success": True, "data": {"breakdown": breakdown, "total": total}})


# ---------------------------------------------------------------------------
# Vendor Reports
# ---------------------------------------------------------------------------

@report_api.route("/vendors", methods=["GET"])
@require_auth
def vendor_report():
    """
    Vendor reporting.
    Query params:
      - report_type: top_by_volume (default) | utilization | certifications
      - date_from / date_to
      - limit: max vendors to return (default 20)
    """
    auth_err = _require_report_admin()
    if auth_err:
        return auth_err

    report_type = request.args.get("report_type", "top_by_volume")
    allowed = ("top_by_volume", "utilization", "certifications")
    if report_type not in allowed:
        return jsonify({"success": False, "message": f"Invalid report_type. Allowed: {', '.join(allowed)}"}), 400

    try:
        if report_type == "top_by_volume":
            return _vendor_top_volume()
        elif report_type == "utilization":
            return _vendor_utilization()
        elif report_type == "certifications":
            return _vendor_certifications()
    except Exception as e:
        return error_response(e)


def _vendor_top_volume():
    """Top vendors by total RFPO dollar volume."""
    from_dt, to_dt = _parse_date_range()
    limit = min(request.args.get("limit", 20, type=int), 100)

    q = db.session.query(
        Vendor.id,
        Vendor.company_name,
        func.count(RFPO.id).label("rfpo_count"),
        func.coalesce(func.sum(RFPO.total_amount), 0).label("total_amount"),
    ).join(RFPO, Vendor.id == RFPO.vendor_id).filter(
        RFPO.deleted_at.is_(None), RFPO.status.in_(RFPO_CLOSED_STATUSES)
    )
    q = _apply_date_filter(q, from_dt, to_dt)
    rows = q.group_by(Vendor.id, Vendor.company_name).order_by(
        func.sum(RFPO.total_amount).desc()
    ).limit(limit).all()

    # Totals
    total_q = db.session.query(
        func.count(func.distinct(RFPO.vendor_id)),
        func.coalesce(func.sum(RFPO.total_amount), 0),
    ).filter(RFPO.deleted_at.is_(None), RFPO.status.in_(RFPO_CLOSED_STATUSES))
    total_q = _apply_date_filter(total_q, from_dt, to_dt)
    totals = total_q.first()

    vendors = []
    for r in rows:
        total = float(r.total_amount or 0)
        vendors.append({
            "vendor_id": r.id,
            "name": r.company_name,
            "rfpo_count": r.rfpo_count,
            "total_amount": total,
            "avg_rfpo_value": round(total / r.rfpo_count, 2) if r.rfpo_count else 0,
        })

    return jsonify({
        "success": True,
        "data": {
            "vendors": vendors,
            "total_vendor_count": totals[0] or 0,
            "total_rfpo_amount": float(totals[1] or 0),
        },
    })


def _vendor_utilization():
    """RFPO counts and dollar volume per vendor (all statuses)."""
    from_dt, to_dt = _parse_date_range()
    limit = min(request.args.get("limit", 20, type=int), 100)

    q = db.session.query(
        Vendor.id,
        Vendor.company_name,
        Vendor.status.label("vendor_status"),
        func.count(RFPO.id).label("rfpo_count"),
        func.coalesce(func.sum(RFPO.total_amount), 0).label("total_amount"),
        func.max(RFPO.created_at).label("last_rfpo_date"),
    ).outerjoin(RFPO, db.and_(Vendor.id == RFPO.vendor_id, RFPO.deleted_at.is_(None)))
    if from_dt:
        q = q.filter(db.or_(RFPO.created_at >= from_dt, RFPO.id.is_(None)))
    if to_dt:
        q = q.filter(db.or_(RFPO.created_at < to_dt, RFPO.id.is_(None)))
    rows = q.filter(Vendor.active.is_(True)).group_by(
        Vendor.id, Vendor.company_name, Vendor.status
    ).order_by(func.count(RFPO.id).desc()).limit(limit).all()

    vendors = []
    for r in rows:
        vendors.append({
            "vendor_id": r.id,
            "name": r.company_name,
            "vendor_status": r.vendor_status,
            "rfpo_count": r.rfpo_count,
            "total_amount": float(r.total_amount or 0),
            "last_rfpo_date": r.last_rfpo_date.isoformat() if r.last_rfpo_date else None,
        })

    return jsonify({"success": True, "data": {"vendors": vendors}})


def _vendor_certifications():
    """Vendor certification status overview."""
    now = datetime.utcnow().date()
    soon = now + timedelta(days=30)

    vendors = Vendor.query.filter(Vendor.active.is_(True)).all()
    certified = 0
    expired = 0
    expiring_soon_list = []
    no_cert = 0

    for v in vendors:
        if not v.cert_expire_date:
            no_cert += 1
        elif v.cert_expire_date < now:
            expired += 1
        elif v.cert_expire_date <= soon:
            expiring_soon_list.append({
                "vendor_id": v.id,
                "name": v.company_name,
                "cert_expire_date": v.cert_expire_date.isoformat(),
                "days_remaining": (v.cert_expire_date - now).days,
            })
            certified += 1
        else:
            certified += 1

    return jsonify({
        "success": True,
        "data": {
            "certified": certified,
            "expired": expired,
            "expiring_30_days": len(expiring_soon_list),
            "no_cert": no_cert,
            "expiring_soon": expiring_soon_list,
        },
    })


# ---------------------------------------------------------------------------
# Email Health Report
# ---------------------------------------------------------------------------

@report_api.route("/email-health", methods=["GET"])
@require_auth
def email_health_report():
    """
    Email delivery health.
    Query params: date_from / date_to, email_type
    """
    auth_err = _require_report_admin()
    if auth_err:
        return auth_err

    try:
        from_dt, to_dt = _parse_date_range()
        email_type = request.args.get("email_type")

        base = db.session.query(EmailLog)
        if from_dt:
            base = base.filter(EmailLog.created_at >= from_dt)
        if to_dt:
            base = base.filter(EmailLog.created_at < to_dt)
        if email_type:
            base = base.filter(EmailLog.email_type == email_type)

        # Totals by status
        status_q = db.session.query(
            EmailLog.status, func.count(EmailLog.id)
        )
        if from_dt:
            status_q = status_q.filter(EmailLog.created_at >= from_dt)
        if to_dt:
            status_q = status_q.filter(EmailLog.created_at < to_dt)
        if email_type:
            status_q = status_q.filter(EmailLog.email_type == email_type)
        status_rows = status_q.group_by(EmailLog.status).all()

        totals = {r[0]: r[1] for r in status_rows}
        total_sent = totals.get("sent", 0)
        total_failed = totals.get("failed", 0)
        total_all = sum(totals.values())

        # By type
        type_q = db.session.query(
            EmailLog.email_type,
            func.count(EmailLog.id).label("count"),
            func.sum(case((EmailLog.status == "failed", 1), else_=0)).label("failed"),
        )
        if from_dt:
            type_q = type_q.filter(EmailLog.created_at >= from_dt)
        if to_dt:
            type_q = type_q.filter(EmailLog.created_at < to_dt)
        type_rows = type_q.group_by(EmailLog.email_type).all()

        by_type = []
        for r in type_rows:
            by_type.append({
                "email_type": r.email_type,
                "count": r.count,
                "failed": int(r.failed or 0),
            })

        # Recent failures (last 10)
        failures = (
            EmailLog.query.filter(EmailLog.status == "failed")
            .order_by(EmailLog.created_at.desc())
            .limit(10)
            .all()
        )
        recent_failures = []
        for f in failures:
            recent_failures.append({
                "id": f.id,
                "email_type": f.email_type,
                "to": f.to_emails[:100] if f.to_emails else None,
                "error": f.error_message[:200] if f.error_message else None,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            })

        return jsonify({
            "success": True,
            "data": {
                "total_sent": total_sent,
                "total_failed": total_failed,
                "total_queued": totals.get("queued", 0),
                "success_rate_pct": round(total_sent / total_all * 100, 1) if total_all else 100,
                "by_type": by_type,
                "recent_failures": recent_failures,
            },
        })
    except Exception as e:
        return error_response(e)
