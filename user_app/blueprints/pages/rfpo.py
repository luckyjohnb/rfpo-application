"""RFPO pages — list, create workflow, detail, preview, download."""

from datetime import datetime
from types import SimpleNamespace

from flask import redirect, render_template, request, url_for

from user_app.api_client import get_api_client
from user_app.blueprints.pages import pages_bp
from user_app.decorators import require_admin, require_auth


@pages_bp.route("/rfpos")
@require_auth
def rfpos_list():
    """RFPOs list page."""
    return render_template("app/rfpos.html")


@pages_bp.route("/rfpos/create")
@require_admin
def rfpo_create():
    """Create RFPO — Stage 1: Select Consortium & Project."""
    client = get_api_client()
    consortiums_response = client.get("/consortiums")
    consortiums = (
        consortiums_response.get("consortiums", [])
        if consortiums_response.get("success")
        else []
    )
    return render_template("app/rfpo_create_stage1.html", consortiums=consortiums)


@pages_bp.route("/rfpos/create/details")
@require_admin
def rfpo_create_details():
    """Create RFPO — Stage 2: RFPO Details."""
    client = get_api_client()

    consortium_id = request.args.get("consortium_id")
    project_id = request.args.get("project_id")
    if not consortium_id or not project_id:
        return redirect(url_for("pages.rfpo_create"))

    consortiums_resp = client.get("/consortiums")
    consortium = None
    if consortiums_resp.get("success"):
        for c in consortiums_resp.get("consortiums", []):
            if c.get("consort_id") == consortium_id:
                consortium = c
                break

    projects_resp = client.get(f"/projects/{consortium_id}")
    project = None
    projects = (
        projects_resp.get("projects", [])
        if projects_resp.get("success")
        else projects_resp if isinstance(projects_resp, list) else []
    )
    for p in projects:
        if str(p.get("id")) == str(project_id):
            project = p
            break

    if not consortium or not project:
        return redirect(url_for("pages.rfpo_create"))

    consortium_obj = SimpleNamespace(**consortium)
    project_obj = SimpleNamespace(**project)

    teams_response = client.get("/teams")
    teams = teams_response.get("teams", []) if teams_response.get("success") else []

    vendors_response = client.get("/vendors")
    vendors = vendors_response.get("vendors", []) if vendors_response.get("success") else []

    default_team = None
    team_record_id = project.get("team_record_id")
    if team_record_id:
        for t in teams:
            if t.get("record_id") == team_record_id:
                default_team = t
                break

    return render_template(
        "app/rfpo_create_stage2.html",
        consortium=consortium_obj,
        project=project_obj,
        teams=teams,
        vendors=vendors,
        default_team=default_team,
    )


@pages_bp.route("/rfpos/<int:rfpo_id>/line-items")
@require_admin
def rfpo_create_line_items(rfpo_id):
    """Create RFPO — Stage 3: Line Items."""
    return render_template("app/rfpo_create_stage3.html", rfpo_id=rfpo_id)


@pages_bp.route("/rfpos/<int:rfpo_id>/review")
@require_admin
def rfpo_create_review(rfpo_id):
    """Create RFPO — Stage 4: Review & Submit."""
    return render_template("app/rfpo_create_stage4.html", rfpo_id=rfpo_id)


@pages_bp.route("/rfpos/<int:rfpo_id>")
@require_auth
def rfpo_detail(rfpo_id):
    """RFPO detail page."""
    client = get_api_client()
    user_info = client.get("/auth/verify")
    if user_info.get("error") == "permissions_changed":
        return redirect(url_for("pages.login_page", reason="permissions_changed"))

    is_admin = False
    if user_info.get("authenticated"):
        roles = user_info.get("user", {}).get("roles", [])
        is_admin = "RFPO_ADMIN" in roles or "GOD" in roles

    return render_template("app/rfpo_detail.html", rfpo_id=rfpo_id, is_admin=is_admin)


@pages_bp.route("/rfpos/<int:rfpo_id>/preview")
@require_auth
def rfpo_preview(rfpo_id):
    """Render RFPO preview HTML."""
    client = get_api_client()

    rfpo_response = client.get(f"/rfpos/{rfpo_id}")
    if not rfpo_response.get("success"):
        msg = rfpo_response.get("message", "Unknown error")
        return f"Error loading RFPO: {msg}", 404

    rfpo = rfpo_response["rfpo"]

    project = None
    consortium = None
    vendor = None
    vendor_site = None
    requestor = None

    if rfpo.get("project_id"):
        projects_response = client.get("/projects")
        if projects_response.get("success"):
            for p in projects_response.get("projects", []):
                if p.get("project_id") == rfpo["project_id"]:
                    project = p
                    break

    if rfpo.get("consortium_id"):
        consortiums_response = client.get("/consortiums")
        if consortiums_response.get("success"):
            for c in consortiums_response.get("consortiums", []):
                if c.get("consort_id") == rfpo["consortium_id"]:
                    consortium = c
                    break

    if rfpo.get("vendor_id"):
        vendors_response = client.get("/vendors")
        if vendors_response.get("success"):
            for v in vendors_response.get("vendors", []):
                if v.get("id") == rfpo["vendor_id"]:
                    vendor = v
                    break

    if rfpo.get("vendor_site_id") and vendor:
        vendor_sites_response = client.get(f'/vendor-sites/{vendor["id"]}')
        if isinstance(vendor_sites_response, list):
            for site in vendor_sites_response:
                if site.get("id") == rfpo["vendor_site_id"]:
                    vendor_site = site
                    break

    # Convert date strings for template compatibility
    if rfpo.get("created_at"):
        try:
            if isinstance(rfpo["created_at"], str):
                rfpo["created_at"] = datetime.fromisoformat(
                    rfpo["created_at"].replace("Z", "+00:00")
                )
        except (ValueError, TypeError):
            rfpo["created_at"] = None

    if rfpo.get("delivery_date"):
        try:
            if isinstance(rfpo["delivery_date"], str):
                rfpo["delivery_date"] = datetime.fromisoformat(
                    rfpo["delivery_date"].replace("Z", "+00:00")
                ).date()
        except (ValueError, TypeError):
            rfpo["delivery_date"] = None

    rfpo_obj = SimpleNamespace(**rfpo)
    project_obj = SimpleNamespace(**project) if project else None
    consortium_obj = SimpleNamespace(**consortium) if consortium else None
    vendor_obj = SimpleNamespace(**vendor) if vendor else None
    vendor_site_obj = SimpleNamespace(**vendor_site) if vendor_site else None

    if hasattr(rfpo_obj, "line_items") and rfpo_obj.line_items:
        rfpo_obj.line_items = [SimpleNamespace(**item) for item in rfpo_obj.line_items]
    else:
        rfpo_obj.line_items = []

    # Helper methods for cost calculations
    def get_calculated_cost_share_amount():
        if hasattr(rfpo_obj, "cost_share_amount") and hasattr(rfpo_obj, "subtotal"):
            if rfpo_obj.cost_share_type == "percent":
                return (
                    float(rfpo_obj.subtotal or 0)
                    * float(rfpo_obj.cost_share_amount or 0)
                ) / 100
            else:
                return float(rfpo_obj.cost_share_amount or 0)
        return 0.0

    def get_calculated_total_amount():
        subtotal = float(rfpo_obj.subtotal or 0)
        cost_share = get_calculated_cost_share_amount()
        return subtotal - cost_share

    rfpo_obj.get_calculated_cost_share_amount = get_calculated_cost_share_amount
    rfpo_obj.get_calculated_total_amount = get_calculated_total_amount

    if requestor:
        requestor_obj = SimpleNamespace(**requestor)
        requestor_obj.get_display_name = lambda: requestor.get(
            "fullname", requestor.get("display_name", "Unknown")
        )
    else:
        requestor_obj = None

    return render_template(
        "app/rfpo_preview.html",
        rfpo=rfpo_obj,
        project=project_obj,
        consortium=consortium_obj,
        vendor=vendor_obj,
        vendor_site=vendor_site_obj,
        requestor=requestor_obj,
    )


@pages_bp.route("/rfpos/<int:rfpo_id>/download-pdf", methods=["GET"])
@require_auth
def rfpo_download_pdf(rfpo_id):
    """Redirect to preview page with print mode."""
    return redirect(f"/rfpos/{rfpo_id}/preview?print=1")
