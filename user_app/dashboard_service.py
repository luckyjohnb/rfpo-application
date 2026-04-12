"""Dashboard data orchestration — separates fetching + role logic from the route handler (SRP)."""

from user_app.api_client import get_api_client


def check_first_login(client):
    """Return True if the user has never logged in before."""
    user_profile = client.get("/users/profile")
    if not user_profile.get("success"):
        return False
    user_data = user_profile["user"]
    last_visit = user_data.get("last_visit")
    created_at = user_data.get("created_at")
    return not last_visit or (last_visit and created_at and last_visit == created_at)


def classify_dashboard_type(roles, is_approver):
    """Determine the dashboard variant from the user's roles."""
    is_rfpo_admin = "RFPO_ADMIN" in roles or "GOD" in roles
    is_rfpo_user = "RFPO_USER" in roles

    if is_rfpo_admin:
        return "admin"
    if is_rfpo_user and is_approver:
        return "approver"
    if is_rfpo_user:
        return "profile_only"
    return "no_access"


def fetch_dashboard_data(client):
    """Fetch all data needed to render the dashboard.

    Returns a dict with keys: recent_rfpos, teams, user_permissions,
    is_approver.
    """
    rfpos_response = client.get("/rfpos")
    recent_rfpos = (
        rfpos_response.get("rfpos", []) if rfpos_response.get("success") else []
    )

    teams_response = client.get("/teams")
    user_teams = (
        teams_response.get("teams", []) if teams_response.get("success") else []
    )

    permissions_response = client.get("/users/permissions-summary")
    user_permissions = (
        permissions_response.get("permissions_summary", {})
        if permissions_response.get("success")
        else {}
    )

    approver_response = client.get("/users/approver-status")
    is_approver = (
        approver_response.get("is_approver", False)
        if approver_response.get("success")
        else False
    )

    return {
        "recent_rfpos": recent_rfpos,
        "teams": user_teams,
        "user_permissions": user_permissions,
        "is_approver": is_approver,
    }
