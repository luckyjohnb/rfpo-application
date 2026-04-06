# RFPO User Application — Issue Tracker (2026-04-05)

## Overview

Four issues identified during SSO testing of the User Application at `https://rfpo.uscar.org`. These affect role-based access control, user messaging, and approvals functionality. Issues 1 and 2 are authorization gaps that allow RFPO_USER role holders to perform admin-only operations.

---

## Issue 1: Line Item CRUD Not Restricted to Admins

**Severity:** HIGH  
**Category:** Authorization / RBAC  
**Affected User Role:** RFPO_USER  

### Current Behavior

Any authenticated user (including RFPO_USER) can add, edit, and delete line items on an RFPO. The "Add Line Item" button and per-row delete buttons are visible to all users. The API endpoints accept mutations from any authenticated user.

### Expected Behavior

Only users with `RFPO_ADMIN` or `GOD` permissions should be able to add, edit, or delete line items. Users with only `RFPO_USER` should see line items as read-only.

### Root Cause

- **Frontend** (`templates/app/rfpo_detail.html`): The "Add Line Item" button (line ~158) and delete buttons (line ~694) render unconditionally — no role check.
- **API** (`api/rfpo_routes.py`): Line item endpoints only use `@require_auth` (authentication), not authorization. Affected routes:
  - `POST /api/rfpos/<id>/line-items` — create (line ~247)
  - `PUT /api/rfpos/<id>/line-items/<id>` — update (line ~317)
  - `DELETE /api/rfpos/<id>/line-items/<id>` — delete (line ~375)

### Fix Plan

1. **API (server-side enforcement):** Add permission check at the top of each line-item mutation endpoint:

   ```python
   user = request.current_user
   if not (user.has_permission('RFPO_ADMIN') or user.has_permission('GOD')):
       return jsonify({"success": False, "message": "Admin access required"}), 403
   ```

2. **User App route:** The `rfpo_detail` route in `app.py` currently does NOT pass any role info to the template. Must fetch user permissions and pass `is_admin` flag.
3. **Frontend (UI gating):** Conditionally render add/edit/delete controls using the new `is_admin` flag:

   ```jinja2
   {% if is_admin %}
   <button class="btn btn-primary" onclick="showAddLineItemModal()">Add Line Item</button>
   {% endif %}
   ```

4. Both server-side AND client-side checks are needed — client-side alone is insufficient.

### Files to Modify

| File                                 | Change                                                                                            |
| ------------------------------------ | ------------------------------------------------------------------------------------------------- |
| `api/rfpo_routes.py`                 | Add admin permission check to 3 line-item endpoints                                               |
| `templates/app/rfpo_detail.html`     | Wrap add/edit/delete buttons in `{% if is_admin %}`                                               |
| `app.py`                             | Fetch user roles and pass `is_admin` to template context in rfpo_detail route                     |

---

## Issue 2: RFPO Creation Not Restricted to Admins

**Severity:** HIGH  
**Category:** Authorization / RBAC  
**Affected User Role:** RFPO_USER  

### Current Behavior — Issue 2

Any authenticated user can navigate to `/rfpos/create` and submit a new RFPO. The "Create RFPO" button appears on the dashboard for all users. The API accepts POST requests from any authenticated user.

### Expected Behavior — Issue 2

Only `RFPO_ADMIN` or `GOD` users should see the "Create RFPO" button and access the creation form. `RFPO_USER` should only be able to view RFPOs assigned to their teams and act on approvals.

### Root Cause — Issue 2

- **User App route** (`app.py` line ~191): `/rfpos/create` renders the form for any logged-in user — no role check.
- **Dashboard** (`app.py` line ~165): "Create RFPO" button visible to all users.
- **API** (`api/rfpo_routes.py` line ~103): `POST /api/rfpos` only checks authentication, not authorization.

### Fix Plan — Issue 2

1. **API (server-side):** Add admin check to RFPO creation endpoint.
2. **User App route:** Check user roles before rendering the create form; redirect RFPO_USER to dashboard with a flash message.
3. **Dashboard template:** Conditionally show "Create RFPO" button only for admin roles.

### Files to Modify — Issue 2

| File                               | Change                                                    |
| ---------------------------------- | --------------------------------------------------------- |
| `api/rfpo_routes.py`               | Add admin permission check to POST `/api/rfpos`           |
| `app.py`                           | Add role check in `rfpo_create()` route                   |
| `templates/app/dashboard.html`     | Wrap "Create RFPO" button in admin-only conditional       |

---

## Issue 3: Misleading "System Permissions" Message on Dashboard

**Severity:** MEDIUM  
**Category:** UX / Messaging  
**Affected User Role:** RFPO_USER  

### Current Behavior — Issue 3

When user John Bouchard (RFPO_USER role) logs in, the dashboard shows:
> "You have system permissions but are not assigned to any teams, projects, or consortiums. Contact your administrator to be added to the appropriate groups."

This is misleading — `RFPO_USER` is not a "system permission" (that term implies GOD or RFPO_ADMIN). The user simply hasn't been assigned to any teams yet.

### Expected Behavior — Issue 3

The message should say something like:
> "Your account is set up, but you are not yet assigned to any teams or consortiums. Contact your administrator to be added to the appropriate groups."

Or, if the user is an approver only:
> "You have approver access. Check 'My Approvals' to review pending RFPOs."

### Root Cause — Issue 3

- **Template** (`templates/app/dashboard.html` line ~96): Condition checks `has_rfpo_access` — but this variable is **never passed** from the route. It's always `undefined` (falsy in Jinja2), so the else-branch always renders.
- **Route** (`app.py` line ~178): Already passes `dashboard_type` to the template, but the template doesn't use it for the Quick Actions conditional — it uses the non-existent `has_rfpo_access` instead.
- **Message text** is inaccurate — says "system permissions" for a user who only has `RFPO_USER` role.

### Fix Plan — Issue 3

1. Replace the template conditional from `{% if has_rfpo_access %}` to use the already-passed `dashboard_type` variable:

   ```jinja2
   {% if dashboard_type in ['admin', 'approver', 'profile_only'] %}
   <!-- Quick Actions -->
   {% else %}
   <!-- No access message -->
   {% endif %}
   ```

2. Rewrite the "Limited Access" message — replace "system permissions" with accurate role-specific language.
3. For RFPO_USER with no team access, show: "Your account is set up, but you are not yet assigned to any teams. Contact your administrator."
4. For approver-only users, direct them to the approvals page.

### Files to Modify — Issue 3

| File                               | Change                                                                        |
| ---------------------------------- | ----------------------------------------------------------------------------- |
| `templates/app/dashboard.html`     | Replace `has_rfpo_access` with `dashboard_type` conditional; rewrite message  |
| No changes needed to `app.py`      | `dashboard_type` is already passed correctly                                  |

---

## Issue 4: "Error Loading Approval Queue" on My Approvals Page

**Severity:** MEDIUM  
**Category:** Bug / Error Handling  
**Affected User Role:** RFPO_USER (approvers)  

### Current Behavior — Issue 4

Clicking "My Approvals" shows "Error loading approval queue. Please try again" with no useful detail.

### Expected Behavior — Issue 4

The page should either:

- Show pending approvals if the user is an approver
- Show an empty state message ("No pending approvals") if there are none
- Show a specific, actionable error if something goes wrong

### Root Cause — Issue 4

- **API endpoint** (`api/user_routes.py` lines ~359-430): The approvals endpoint uses a broad `except Exception` that returns a generic 500 error. Inner `try/except` blocks silently `continue` past individual failures, masking the real issue.
- **Potential causes:** Corrupted `instance_data` JSON, missing RFPO relationships on approval instances, or `record_id` mismatches.
- **Frontend** (`templates/app/approvals.html` line ~310): Catches API errors and shows a generic message with no error detail.

### Fix Plan — Issue 4

1. **API:** Add structured error logging with user context so failures are traceable:

   ```python
   except Exception as e:
       print(f"Approval queue error for user {user.record_id}: {e}", flush=True)
       import traceback; traceback.print_exc()
   ```

2. **API:** Validate each approval instance before processing (skip with warning instead of silent `continue`).
3. **Frontend:** Show the actual error message from the API response if available.
4. **Debug:** Check the specific user's `record_id` and verify it matches entries in `rfpo_approval_actions` table.

### Files to Modify — Issue 4

| File                               | Change                                                                                              |
| ---------------------------------- | --------------------------------------------------------------------------------------------------- |
| `api/user_routes.py`               | Add detailed error logging to `get_user_approver_rfpos()` endpoint                                  |
| `simple_api.py`                    | Fix duplicate `/api/users/approver-rfpos` endpoint (has same silent error handling)                 |
| `templates/app/approvals.html`     | Show API error message instead of generic text                                                      |

---

## Priority Order

| Priority | Issue                      | Rationale                                                        |
| -------- | -------------------------- | ---------------------------------------------------------------- |
| 1        | Issue 2: RFPO Creation     | Authorization gap — blocks non-admin RFPO creation               |
| 2        | Issue 1: Line Item CRUD    | Authorization gap — blocks non-admin line item changes           |
| 3        | Issue 4: Approval Queue    | Blocks core user workflow (approvals)                            |
| 4        | Issue 3: Dashboard Message | UX polish, no functional impact                                  |

## Testing Checklist

After fixes are applied, verify with the RFPO_USER role (John Bouchard, `johnbouchard@icloud.com`):

- [ ] Dashboard does NOT show "Create RFPO" button
- [ ] Navigating to `/rfpos/create` directly redirects to dashboard or shows 403
- [ ] RFPO detail page does NOT show "Add Line Item" or delete buttons
- [ ] API rejects `POST /api/rfpos` with 403 for RFPO_USER
- [ ] API rejects line item POST/PUT/DELETE with 403 for RFPO_USER
- [ ] Dashboard message is accurate (no "system permissions" language)
- [ ] "My Approvals" loads without error (or shows empty state)
- [ ] RFPO_ADMIN user still has full access to all operations
