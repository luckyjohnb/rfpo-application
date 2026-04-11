#!/usr/bin/env python3
"""
Ticket System Test Suite — Bug Reports & Feature Requests
Tests submission, validation, listing, and detail retrieval against the live API.
"""

import requests
import sys
import time

API_URL = "https://rfpo-api.uscar.org/api"
LOGIN_EMAIL = "admin@rfpo.com"
LOGIN_PASSWORD = "admin123"

passed_count = 0
failed_count = 0


def print_test(name, passed, details=""):
    global passed_count, failed_count
    if passed:
        passed_count += 1
    else:
        failed_count += 1
    status = "PASS" if passed else "FAIL"
    icon = "✅" if passed else "❌"
    print(f"  {icon} [{status}] {name}")
    if details:
        print(f"         {details}")


def get_auth_token():
    """Login and return a JWT token."""
    resp = requests.post(
        f"{API_URL}/auth/login",
        json={"username": LOGIN_EMAIL, "password": LOGIN_PASSWORD},
        timeout=15,
    )
    if resp.status_code != 200 or not resp.json().get("success"):
        print(f"❌ FATAL: Cannot authenticate — {resp.status_code} {resp.text[:200]}")
        sys.exit(1)
    return resp.json()["token"]


def api(method, path, token, json=None, timeout=15):
    """Make an authenticated API request."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    fn = getattr(requests, method.lower())
    return fn(f"{API_URL}{path}", json=json, headers=headers, timeout=timeout)


# ────────────────────────────────────────────────────────────────
# 1. Bug Report Submission
# ────────────────────────────────────────────────────────────────
def test_bug_submission(token):
    print("\n🐛 BUG REPORT SUBMISSION")
    print("─" * 60)

    # 1a. Happy path — minimal required fields
    resp = api("POST", "/tickets", token, json={
        "type": "bug",
        "title": "Test bug — minimal",
        "description": "Automated test: minimal bug submission.",
        "priority": "medium",
    })
    data = resp.json()
    print_test(
        "Submit bug (minimal fields)",
        resp.status_code == 201 and data.get("success"),
        f"Status {resp.status_code}, ticket={data.get('ticket', {}).get('ticket_number', 'N/A')}",
    )
    bug_id = data.get("ticket", {}).get("id")

    # 1b. Happy path — all fields populated
    resp = api("POST", "/tickets", token, json={
        "type": "bug",
        "title": "Test bug — full fields",
        "description": "Automated test: all fields populated.",
        "priority": "high",
        "severity": "major",
        "steps_to_reproduce": "1. Open page\n2. Click submit\n3. See error",
        "page_url": "https://rfpo.uscar.org/dashboard",
        "browser_info": "TestAgent/1.0",
    })
    data = resp.json()
    print_test(
        "Submit bug (all fields)",
        resp.status_code == 201 and data.get("success"),
        f"Status {resp.status_code}, ticket={data.get('ticket', {}).get('ticket_number', 'N/A')}",
    )

    # 1c. Verify ticket number format BUG-XXXX
    ticket_num = data.get("ticket", {}).get("ticket_number", "")
    print_test(
        "Ticket number format (BUG-XXXX)",
        ticket_num.startswith("BUG-") and ticket_num[4:].isdigit(),
        f"Got: {ticket_num}",
    )

    return bug_id


# ────────────────────────────────────────────────────────────────
# 2. Feature Request Submission
# ────────────────────────────────────────────────────────────────
def test_feature_submission(token):
    print("\n💡 FEATURE REQUEST SUBMISSION")
    print("─" * 60)

    # 2a. Happy path — minimal
    resp = api("POST", "/tickets", token, json={
        "type": "feature_request",
        "title": "Test feature — minimal",
        "description": "Automated test: minimal feature request.",
        "priority": "low",
    })
    data = resp.json()
    print_test(
        "Submit feature request (minimal)",
        resp.status_code == 201 and data.get("success"),
        f"Status {resp.status_code}, ticket={data.get('ticket', {}).get('ticket_number', 'N/A')}",
    )
    feat_id = data.get("ticket", {}).get("id")

    # 2b. Happy path — all fields
    resp = api("POST", "/tickets", token, json={
        "type": "feature_request",
        "title": "Test feature — full fields",
        "description": "Automated test: all fields populated for feature request.",
        "priority": "critical",
        "page_url": "https://rfpo.uscar.org/rfpos",
        "browser_info": "TestAgent/1.0",
    })
    data = resp.json()
    print_test(
        "Submit feature request (all fields)",
        resp.status_code == 201 and data.get("success"),
        f"Status {resp.status_code}, ticket={data.get('ticket', {}).get('ticket_number', 'N/A')}",
    )

    # 2c. Verify ticket number format FR-XXXX
    ticket_num = data.get("ticket", {}).get("ticket_number", "")
    print_test(
        "Ticket number format (FR-XXXX)",
        ticket_num.startswith("FR-") and ticket_num[3:].isdigit(),
        f"Got: {ticket_num}",
    )

    return feat_id


# ────────────────────────────────────────────────────────────────
# 3. Validation — Rejections
# ────────────────────────────────────────────────────────────────
def test_validation(token):
    print("\n🚫 VALIDATION (should reject)")
    print("─" * 60)

    # 3a. Missing title
    resp = api("POST", "/tickets", token, json={
        "type": "bug", "title": "", "description": "has desc", "priority": "low",
    })
    print_test(
        "Reject missing title",
        resp.status_code == 400 and not resp.json().get("success"),
        f"Status {resp.status_code}",
    )

    # 3b. Missing description
    resp = api("POST", "/tickets", token, json={
        "type": "bug", "title": "has title", "description": "", "priority": "low",
    })
    print_test(
        "Reject missing description",
        resp.status_code == 400 and not resp.json().get("success"),
        f"Status {resp.status_code}",
    )

    # 3c. Invalid type
    resp = api("POST", "/tickets", token, json={
        "type": "invalid_type", "title": "t", "description": "d",
    })
    print_test(
        "Reject invalid type",
        resp.status_code == 400 and not resp.json().get("success"),
        f"Status {resp.status_code}",
    )

    # 3d. Invalid priority
    resp = api("POST", "/tickets", token, json={
        "type": "bug", "title": "t", "description": "d", "priority": "ultra",
    })
    print_test(
        "Reject invalid priority",
        resp.status_code == 400 and not resp.json().get("success"),
        f"Status {resp.status_code}",
    )

    # 3e. Invalid severity
    resp = api("POST", "/tickets", token, json={
        "type": "bug", "title": "t", "description": "d", "severity": "catastrophic",
    })
    print_test(
        "Reject invalid severity",
        resp.status_code == 400 and not resp.json().get("success"),
        f"Status {resp.status_code}",
    )

    # 3f. Title too long (>255 chars)
    resp = api("POST", "/tickets", token, json={
        "type": "bug", "title": "x" * 256, "description": "d",
    })
    print_test(
        "Reject title > 255 chars",
        resp.status_code == 400 and not resp.json().get("success"),
        f"Status {resp.status_code}",
    )

    # 3g. No body at all
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.post(f"{API_URL}/tickets", headers=headers, timeout=15)
    print_test(
        "Reject empty body",
        resp.status_code == 400 and not resp.json().get("success"),
        f"Status {resp.status_code}",
    )

    # 3h. No auth token
    resp = requests.post(
        f"{API_URL}/tickets",
        json={"type": "bug", "title": "t", "description": "d"},
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    print_test(
        "Reject unauthenticated request",
        resp.status_code == 401,
        f"Status {resp.status_code}",
    )


# ────────────────────────────────────────────────────────────────
# 4. Listing
# ────────────────────────────────────────────────────────────────
def test_listing(token):
    print("\n📋 TICKET LISTING")
    print("─" * 60)

    # 4a. List all tickets
    resp = api("GET", "/tickets", token)
    data = resp.json()
    print_test(
        "List all tickets",
        resp.status_code == 200 and data.get("success") and "tickets" in data,
        f"Status {resp.status_code}, count={data.get('total', '?')}",
    )

    # 4b. Filter by type=bug
    resp = api("GET", "/tickets?type=bug", token)
    data = resp.json()
    all_bugs = all(t["type"] == "bug" for t in data.get("tickets", []))
    print_test(
        "Filter type=bug",
        resp.status_code == 200 and data.get("success") and all_bugs,
        f"Returned {len(data.get('tickets', []))} bugs",
    )

    # 4c. Filter by type=feature_request
    resp = api("GET", "/tickets?type=feature_request", token)
    data = resp.json()
    all_feats = all(t["type"] == "feature_request" for t in data.get("tickets", []))
    print_test(
        "Filter type=feature_request",
        resp.status_code == 200 and data.get("success") and all_feats,
        f"Returned {len(data.get('tickets', []))} feature requests",
    )

    # 4d. Filter by status=open
    resp = api("GET", "/tickets?status=open", token)
    data = resp.json()
    all_open = all(t["status"] == "open" for t in data.get("tickets", []))
    print_test(
        "Filter status=open",
        resp.status_code == 200 and data.get("success") and all_open,
        f"Returned {len(data.get('tickets', []))} open tickets",
    )


# ────────────────────────────────────────────────────────────────
# 5. Detail Retrieval
# ────────────────────────────────────────────────────────────────
def test_detail(token, bug_id, feat_id):
    print("\n🔍 TICKET DETAIL")
    print("─" * 60)

    # 5a. Get bug detail
    if bug_id:
        resp = api("GET", f"/tickets/{bug_id}", token)
        data = resp.json()
        ticket = data.get("ticket", {})
        print_test(
            "Get bug detail",
            resp.status_code == 200 and data.get("success") and ticket.get("type") == "bug",
            f"Status {resp.status_code}, title={ticket.get('title', 'N/A')[:40]}",
        )
    else:
        print_test("Get bug detail", False, "No bug_id from creation step")

    # 5b. Get feature detail
    if feat_id:
        resp = api("GET", f"/tickets/{feat_id}", token)
        data = resp.json()
        ticket = data.get("ticket", {})
        print_test(
            "Get feature request detail",
            resp.status_code == 200 and data.get("success") and ticket.get("type") == "feature_request",
            f"Status {resp.status_code}, title={ticket.get('title', 'N/A')[:40]}",
        )
    else:
        print_test("Get feature request detail", False, "No feat_id from creation step")

    # 5c. Non-existent ticket
    resp = api("GET", "/tickets/999999", token)
    print_test(
        "404 for non-existent ticket",
        resp.status_code == 404 and not resp.json().get("success"),
        f"Status {resp.status_code}",
    )


# ────────────────────────────────────────────────────────────────
# 6. Comments
# ────────────────────────────────────────────────────────────────
def test_comments(token, ticket_id):
    print("\n💬 COMMENTS")
    print("─" * 60)

    if not ticket_id:
        print_test("Add comment", False, "No ticket_id available")
        return

    # 6a. Add comment
    resp = api("POST", f"/tickets/{ticket_id}/comments", token, json={
        "content": "Automated test comment."
    })
    data = resp.json()
    print_test(
        "Add comment to ticket",
        resp.status_code == 201 and data.get("success"),
        f"Status {resp.status_code}",
    )

    # 6b. Verify comment appears in detail
    resp = api("GET", f"/tickets/{ticket_id}", token)
    data = resp.json()
    comments = data.get("ticket", {}).get("comments", [])
    has_comment = any("Automated test comment" in c.get("content", "") for c in comments)
    print_test(
        "Comment visible in ticket detail",
        has_comment,
        f"Found {len(comments)} comment(s)",
    )

    # 6c. Reject empty comment
    resp = api("POST", f"/tickets/{ticket_id}/comments", token, json={"content": ""})
    print_test(
        "Reject empty comment",
        resp.status_code == 400 and not resp.json().get("success"),
        f"Status {resp.status_code}",
    )


# ────────────────────────────────────────────────────────────────
# 7. Priority / Severity Edge Cases
# ────────────────────────────────────────────────────────────────
def test_priority_severity_combinations(token):
    print("\n🎯 PRIORITY / SEVERITY EDGE CASES")
    print("─" * 60)

    # All valid priorities
    for p in ("low", "medium", "high", "critical"):
        resp = api("POST", "/tickets", token, json={
            "type": "bug", "title": f"Priority test {p}",
            "description": f"Testing priority={p}", "priority": p,
        })
        print_test(
            f"Priority '{p}' accepted",
            resp.status_code == 201,
            f"Status {resp.status_code}",
        )

    # All valid severities
    for s in ("cosmetic", "minor", "major", "blocker"):
        resp = api("POST", "/tickets", token, json={
            "type": "bug", "title": f"Severity test {s}",
            "description": f"Testing severity={s}",
            "priority": "low", "severity": s,
        })
        print_test(
            f"Severity '{s}' accepted",
            resp.status_code == 201,
            f"Status {resp.status_code}",
        )

    # Severity on feature request should be ignored (not an error)
    resp = api("POST", "/tickets", token, json={
        "type": "feature_request", "title": "Feature with severity",
        "description": "Severity field should be ignored for features",
        "priority": "low", "severity": "major",
    })
    print_test(
        "Severity ignored for feature_request",
        resp.status_code == 201,
        f"Status {resp.status_code}",
    )


# ────────────────────────────────────────────────────────────────
# Runner
# ────────────────────────────────────────────────────────────────
def run_all_tests():
    print("=" * 60)
    print("🧪 TICKET SYSTEM TEST SUITE")
    print(f"   API: {API_URL}")
    print("=" * 60)

    print("\n🔑 Authenticating...")
    token = get_auth_token()
    print("   Authenticated as admin@rfpo.com")

    bug_id = test_bug_submission(token)
    feat_id = test_feature_submission(token)
    test_validation(token)
    test_listing(token)
    test_detail(token, bug_id, feat_id)
    test_comments(token, bug_id)
    test_priority_severity_combinations(token)

    print("\n" + "=" * 60)
    total = passed_count + failed_count
    print(f"📊 RESULTS: {passed_count}/{total} passed, {failed_count} failed")
    if failed_count == 0:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60)

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
