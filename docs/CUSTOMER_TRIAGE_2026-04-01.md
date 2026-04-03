# RFPO Application — Customer Triage Plan

**Date:** 2026-04-01
**Customer:** USCAR
**Prepared by:** Engineering
**Reviewed by:** Engineering Management

---

## Engineering Review Notes

> The following review was performed by verifying each triage claim against the production codebase. Key findings and corrections are noted below.

### Overall Assessment

The triage is thorough, well-structured, and largely accurate. All 12 issues trace back to real customer pain with verified code-level evidence. The prioritization is sound — security issues (#3, #4) first, followed by core business function (#5), then UX and enhancements. The plan is ready to share with stakeholders with the corrections and additions noted below.

### Corrections

1. **Issue #7 (Orphaned Records) — Behavior mischaracterized.** The triage says approval instances "survive after deletion." In reality, `rfpo_delete()` in `custom_admin.py` only allows deletion when the approval instance `is_complete()`. But the RFPO model has **no cascade to `RFPOApprovalInstance`**, and `rfpo_id` is a `NOT NULL` FK. On PostgreSQL, the delete will **fail with an IntegrityError** (caught silently by the generic `except` block, showing a vague error flash). On SQLite, FK enforcement may be off, causing true orphans. The fix needs both: add cascade delete **and** handle completed instances correctly. Severity should remain Medium but the implementation approach needs updating.

2. **Issue #4 (Privilege Escalation) — Scope is broader than stated.** The triage correctly identifies `user_edit()` at line ~2312, but there are **four** code paths that call `set_permissions()` without hierarchy enforcement (lines 2124, 2144, 2244, 2368). The bulk user import path at line ~2124 is explicitly noted, but lines 2144 and 2244 (user creation flows) also need guards. All four paths must be fixed simultaneously.

3. **Issue #3 (Approval Authorization) — The `is_rfpo_admin()` helper compounds the problem.** `is_rfpo_admin()` returns `True` for both `RFPO_ADMIN` and `GOD` users (line 687 of `models.py`). Any route gated by `is_rfpo_admin()` inherently lets both roles through. The triage correctly identifies the `is_super_admin()` bypass in `approval_action_approve()`, but the broader pattern of `is_rfpo_admin()` gating across all admin routes means RFPO_ADMIN users can reach approval actions regardless.

### Gaps Identified

1. **No CSRF Protection (Missing from triage).** The admin panel has no CSRF protection — no `CSRFProtect`, no `WTF_CSRF` configuration, no token validation on POST forms. Every state-changing operation (user edit, RFPO delete, permission changes, approval actions) is vulnerable to cross-site request forgery. This is a **security vulnerability** that should be added to the Security Hardening epic as Issue #4a or folded into Issue #4. Priority: **Critical**.

2. **Dependency between Issues #6 and #1 is correctly noted but underweighted.** If email deliverability (#1) isn't resolved, the approval notification feature (#6) is completely inert. Recommend hard-blocking #6 on #1 completion, not just noting the dependency.

3. **Issue #10 (Sequential Gates) — Confidence level should be higher.** The triage says "Medium" confidence but the code clearly confirms: `advance_to_next_step()` in `models.py` (line 2048) only advances `current_stage_order` and `current_step_order` counters — it does not create new actions or gate visibility. The model **supports** sequencing in data, but the execution layer doesn't enforce it. Confidence is High.

4. **Missing: Rate limiting / brute-force protection.** Not raised by the customer, but the login endpoints have no rate limiting. Given the privilege escalation finding, this compounds the security posture. Consider adding to the Security Hardening epic.

5. **Issue #5 (PO Generation) effort may be underestimated.** The triage says "Large" for Sprint 1-2, but this involves: new DB column + migration, sequential number generation logic, full PDF field coordinate audit per consortium, and possibly template redesign. This is likely Sprint 2-3 territory unless PO number generation is decoupled from the positioning fix.

### Priority Adjustments

| Issue | Triage Priority | Recommended Adjustment | Rationale |
|-------|----------------|----------------------|-----------|
| #4 | Critical | **Critical — agree** | Confirmed: trivial exploit |
| #3 | Critical | **Critical — agree** | Confirmed: broken access control |
| #9 | Medium | **Consider High** | Submit button is the linchpin connecting Issues #6, #8, #10. Without it, the approval workflow improvements have no clean entry point. |
| CSRF (new) | Not listed | **Critical** | Every POST form is vulnerable |
| #10 | High | **High — agree, bump confidence** | Model supports it but nothing enforces it |

### Sprint Planning Notes

- **Sprint 1 should be security-focused.** Issues #3, #4, and CSRF protection. These are all in `custom_admin.py` and can be shipped together.
- **Issue #5 (PO Generation) should split** into two deliverables: (a) PO number generation (Sprint 2), (b) PDF positioning fix (Sprint 2-3, requires customer screenshots and per-consortium iteration).
- **Issue #2 (SSO)** is correctly sized as X-Large and Sprint 3+. Recommend a discovery spike in Sprint 2 to confirm Entra ID tenant details before committing to implementation.
- **Issue #9 (Submit button)** should move to Sprint 2 alongside #6 — it's the natural trigger for notifications.

---

## Context

A customer (USCAR) submitted an email describing critical and secondary issues with the RFPO application. The triage was performed against the actual codebase with code-level verification of each claim.

## Triage Summary

- **Number of issues identified:** 12 (6 critical/high, 6 medium/low) + 1 newly identified (CSRF)
- **Highest priority issue:** Privilege escalation — any admin user can elevate themselves to GOD (security vulnerability)
- **Key risk areas:** Authorization/access control, CSRF, email deliverability, PO generation, approval workflow correctness
- **Recommended immediate next steps:**
  1. Fix privilege escalation (Issue #4) — security vulnerability, ship immediately
  2. Fix approval authorization (Issue #3) — broken access control, ship with #4
  3. Add CSRF protection (new) — ship with #3 and #4
  4. Investigate email/tenant integration (Issue #1) — blocking user onboarding
  5. Fix PO generation (Issue #5) — core business function broken

**Recommended epic groupings:**

| Epic | Issues | Sprint |
|------|--------|--------|
| **RFPO Security Hardening** | #3, #4, CSRF (new) | Sprint 1 |
| **Email & Notifications** | #1, #6 | Sprint 1-2 |
| **PO Generation Fix** | #5 (split: number gen + positioning) | Sprint 2-3 |
| **Approval Workflow v2** | #9, #10 | Sprint 2-3 |
| **SSO Integration** | #2 | Sprint 3+ (discovery spike in Sprint 2) |
| **UX Improvements** | #7, #8, #11, #12 | Sprint 2-3 |

---

## Detailed Issue Breakdown

### Issue 1: System Email Deliverability & Sender Domain

- **Original customer signal:** "emails from rfpo@spammylookingemail is causing problems with even USCAR users getting the new account email - is it possible to move this app into our Microsoft tenent and avoid the need for a secondary login? and change the system email to a uscar.org email, so that when users get an email from the system, they actually get it?"
- **Normalized issue statement:** System emails are sent from an untrusted/unrecognized sender domain, causing deliverability failures. Customer requests (a) migration to USCAR Microsoft tenant for SSO, and (b) a uscar.org sender address.
- **Category:** Infrastructure / Email
- **Impact:** Critical — new users cannot receive onboarding emails; organizational trust barrier to adoption
- **Likely system/component:** `email_service.py` (sender config), Azure Communication Services or SMTP config
- **Confidence level:** High — code confirms sender falls back to empty string if env vars unset (line 293: `from_email or self.acs_sender_email or self.default_sender or ""`). No Microsoft Entra/SSO integration exists.
- **Priority:** Critical
- **Validation plan:**
  1. Check current `MAIL_DEFAULT_SENDER` / `ACS_SENDER_EMAIL` in production `.env`
  2. Send test email to a USCAR mailbox, check spam folder / rejection headers
  3. Confirm USCAR IT can provision a custom domain in Azure Communication Services or Microsoft 365
- **Recommended approach:** Two-phase delivery:
  - **Phase A (quick win):** Configure Azure Communication Services with a verified `uscar.org` custom domain + sender address. Update `ACS_SENDER_EMAIL` in production `.env`.
  - **Phase B (larger initiative):** Integrate Microsoft Entra ID (Azure AD) SSO — scoped as separate Issue #2.
- **Risks / dependencies:** USCAR IT must provision DNS records (SPF, DKIM, DMARC) for the custom domain.
- **Open questions:**
  - What is the current sender email address in production?
  - Does USCAR have an existing Azure AD / Entra ID tenant?
  - What SSO protocol is preferred (SAML, OIDC)?
- **Suggested labels:** `priority:critical`, `area:email`, `type:infrastructure`

#### GitHub Issue Draft

**Title:** Fix email deliverability: configure verified uscar.org sender domain

**Body:**
> **Summary:** System emails are sent from an unrecognized/spam-flagged domain, preventing users from receiving account invitations and notifications.
>
> **Customer report:** "emails from rfpo@spammylookingemail is causing problems with even USCAR users getting the new account email"
>
> **Problem statement:** The email sender address is not from a trusted domain. Email clients reject or spam-filter these messages.
>
> **Expected behavior:** Emails arrive in users' primary inbox from a recognized `@uscar.org` address.
>
> **Actual behavior:** Emails are blocked or sent to spam.
>
> **Validation tasks:**
> - [ ] Identify current production `MAIL_DEFAULT_SENDER` / `ACS_SENDER_EMAIL` value
> - [ ] Send test email to USCAR mailbox and confirm delivery/spam status
> - [ ] Verify DNS records (SPF, DKIM, DMARC) for chosen sender domain
>
> **Implementation approach:**
> 1. Register and verify a custom `uscar.org` domain in Azure Communication Services
> 2. Update production `ACS_SENDER_EMAIL` to `rfpo@uscar.org` (or appropriate address)
> 3. Coordinate with USCAR IT for DNS record provisioning
> 4. Test delivery to multiple USCAR recipients
>
> **Acceptance criteria:**
> - [ ] Welcome emails arrive in primary inbox for USCAR Microsoft 365 users
> - [ ] Sender shows as `rfpo@uscar.org` (or agreed-upon address)
> - [ ] No SPF/DKIM/DMARC failures in email headers

---

### Issue 2: Microsoft Tenant SSO Integration

- **Original customer signal:** "is it possible to move this app into our Microsoft tenent and avoid the need for a secondary login?"
- **Normalized issue statement:** Customer requests Single Sign-On via their Microsoft Entra ID tenant to eliminate the separate username/password login.
- **Category:** Enhancement / Authentication
- **Impact:** High — UX friction, onboarding barrier, credential fatigue
- **Likely system/component:** `api/auth_routes.py` (JWT auth), `app.py` (session login), `custom_admin.py` (Flask-Login)
- **Confidence level:** High — no SSO/OIDC code exists in the codebase today.
- **Priority:** High
- **Validation plan:**
  1. Confirm USCAR has an Entra ID tenant and can register an app
  2. Determine which apps need SSO (User App, Admin, both?)
  3. Evaluate MSAL Python library integration path
- **Recommended approach:**
  1. Register RFPO as an Entra ID app registration (3 redirect URIs: user, admin, API)
  2. Integrate `msal` Python library for OIDC auth code flow
  3. Map Entra ID user identity to existing User model (match on email)
  4. Keep existing JWT flow as fallback for non-tenant users
  5. Add Entra group → RFPO permission mapping (optional Phase 2)
- **Risks / dependencies:** Multi-sprint effort. Requires USCAR tenant admin cooperation. Must handle users who exist in both systems.
- **Open questions:**
  - Should SSO completely replace password login, or coexist?
  - Are external (non-USCAR) users expected?
  - Which Entra ID groups should map to which RFPO permissions?
- **Suggested labels:** `priority:high`, `area:auth`, `type:enhancement`, `epic:sso-integration`

#### GitHub Issue Draft

**Title:** Integrate Microsoft Entra ID SSO to eliminate secondary login

**Body:**
> **Summary:** Implement OIDC-based SSO with the USCAR Microsoft Entra ID tenant.
>
> **Customer report:** "is it possible to move this app into our Microsoft tenent and avoid the need for a secondary login?"
>
> **Problem statement:** Users must maintain separate RFPO credentials, creating friction and a barrier to adoption.
>
> **Expected behavior:** Users click "Sign in with Microsoft" and authenticate via their organizational account.
>
> **Actual behavior:** Users must create and manage a separate username/password.
>
> **Validation tasks:**
> - [ ] Confirm USCAR Entra ID tenant details and admin availability
> - [ ] Determine user population (all internal? any external?)
> - [ ] Prototype MSAL integration on dev environment
>
> **Implementation approach:**
> 1. Register RFPO app in USCAR Entra ID tenant
> 2. Add `msal` to requirements and implement OIDC auth code flow
> 3. Map Entra ID email to existing `User.email` for account linking
> 4. Add "Sign in with Microsoft" button alongside existing login
> 5. Update session management to support both auth paths
>
> **Acceptance criteria:**
> - [ ] USCAR users can authenticate using organizational Microsoft account
> - [ ] Existing user accounts are matched by email automatically
> - [ ] Traditional login remains available as fallback
> - [ ] JWT tokens continue to work for API consumers

---

### Issue 3: Approval Actions Not Tied to Authorized Approvers

- **Original customer signal:** "the actual approval of an RFPO does not appear to be linked to a user - anyone in admin mode can approve for anyone else - the system does not really differentiate user 'powers'"
- **Normalized issue statement:** The approval authorization check allows any super admin (GOD) to approve on behalf of any designated approver. The system does not enforce that only the assigned primary or backup approver can execute an approval action.
- **Category:** Bug / Security — Broken Access Control
- **Impact:** Critical — approval audit trail is meaningless if unauthorized users can approve; violates separation of duties
- **Likely system/component:** `custom_admin.py` — `approval_action_approve()` function (line ~5831). Guard is: `action.approver_id != current_user.record_id and not current_user.is_super_admin()` — super admins bypass the check entirely. Additionally, `is_rfpo_admin()` (models.py line 687) returns True for both `RFPO_ADMIN` and `GOD` users, meaning route-level gating lets both roles through.
- **Confidence level:** High — confirmed by code review
- **Priority:** Critical
- **Validation plan:**
  1. Log in as RFPO_ADMIN (not the designated approver)
  2. Navigate to an approval instance with pending actions
  3. Confirm the approve button is visible and functional for non-designated users
- **Recommended approach:**
  1. Tighten `approval_action_approve()`: remove super admin bypass — only `action.approver_id` or `step.backup_approver_id` can execute
  2. Add UI-level enforcement: hide approve/reject buttons for non-authorized users
  3. Add audit logging: record `actual_approver_id` vs `designated_approver_id`
  4. GOD users should be able to *reassign* an approval action, not silently approve as someone else
- **Risks / dependencies:** Tightening may lock out recovery for stuck workflows. Add explicit "delegate/reassign" mechanism first.
- **Open questions:**
  - Should GOD users be able to approve on behalf of others, or only reassign?
  - Should backup approvers be auto-activated after a timeout?
- **Suggested labels:** `priority:critical`, `area:approval-workflow`, `type:bug`, `security`

#### GitHub Issue Draft

**Title:** BUG: Approval actions not restricted to designated approvers

**Body:**
> **Summary:** Any user with admin panel access can approve RFPOs on behalf of any designated approver, breaking separation of duties.
>
> **Customer report:** "the actual approval of an RFPO does not appear to be linked to a user - anyone in admin mode can approve for anyone else"
>
> **Problem statement:** `approval_action_approve()` in `custom_admin.py` allows `is_super_admin()` to bypass the approver check. RFPO_ADMIN users can also navigate to approval URLs.
>
> **Expected behavior:** Only the designated primary or backup approver can execute an approval action. Other users see the action as read-only.
>
> **Actual behavior:** Any admin-panel user can approve/reject any pending approval action.
>
> **Validation tasks:**
> - [ ] Reproduce: log in as RFPO_ADMIN, approve for another user's action
> - [ ] Review all routes that modify `RFPOApprovalAction.status`
> - [ ] Check if API layer has similar bypass
>
> **Implementation approach:**
> 1. Remove `is_super_admin()` bypass in `approval_action_approve()`
> 2. Add backup approver check: allow `step.backup_approver_id` as alternative
> 3. Add "Reassign Approver" action for GOD users (separate from approve)
> 4. Hide approve/reject UI controls for non-authorized users
> 5. Add audit field: `approved_by_user_id` (actual actor) alongside `approver_id` (designated)
>
> **Acceptance criteria:**
> - [ ] Only `primary_approver_id` or `backup_approver_id` can execute approval action
> - [ ] GOD users can reassign but not silently approve as someone else
> - [ ] UI hides action buttons for non-authorized users
> - [ ] Audit trail records actual approving user identity

---

### Issue 4: Privilege Escalation — Admin Users Can Edit Their Own Permissions

- **Original customer signal:** "any user can change their role within the system (an admin can make themselves god)"
- **Normalized issue statement:** The admin panel's user edit form (`/user/<id>/edit`) has no guard preventing a user from editing their own record, including permission checkboxes. An RFPO_ADMIN can navigate to their own profile and grant themselves GOD permissions. Additionally, there are four separate code paths that call `set_permissions()` without hierarchy enforcement (lines ~2124, ~2144, ~2244, ~2368 in `custom_admin.py`).
- **Category:** Security Vulnerability — Privilege Escalation
- **Impact:** Critical — complete compromise of authorization model
- **Likely system/component:** `custom_admin.py` — `user_edit()` function (line ~2312), plus bulk import (line ~2124), and user creation (lines ~2144, ~2244). No check for `current_user.id == id`. The API layer (`api/user_routes.py`) is safe — `update_user_profile()` does NOT include permissions in `updatable_fields`.
- **Confidence level:** High — confirmed by code review (all four `set_permissions()` call sites verified)
- **Priority:** Critical (SECURITY — FIX IMMEDIATELY)
- **Validation plan:**
  1. Log in as RFPO_ADMIN
  2. Navigate to `/user/{own_id}/edit`
  3. Check GOD checkbox and save
  4. Confirm permissions are escalated
- **Recommended approach:**
  1. **Immediate fix:** Prevent users from editing their own permissions — `if user.id == current_user.id` → block permission changes
  2. **Deeper fix:** Only GOD users should be able to assign GOD permission; RFPO_ADMIN can only assign at or below own level
  3. Add audit log for permission changes with before/after values
  4. Apply same guards to **all four** `set_permissions()` paths (edit, create, create variant, bulk import)
- **Risks / dependencies:** Must ensure at least one GOD user exists before restricting.
- **Open questions:**
  - Should we implement a permission hierarchy (GOD > RFPO_ADMIN > RFPO_USER)?
  - Should permission changes require a second GOD user approval?
- **Suggested labels:** `priority:critical`, `area:auth`, `type:bug`, `security`, `vulnerability`

#### GitHub Issue Draft

**Title:** SECURITY: Privilege escalation — admin users can grant themselves GOD permissions

**Body:**
> **Summary:** No authorization guard prevents admin users from editing their own user record and escalating permissions to GOD.
>
> **Customer report:** "any user can change their role within the system (an admin can make themselves god)"
>
> **Problem statement:** `user_edit()` in `custom_admin.py` does not check whether `current_user.id == target_user.id`. Any RFPO_ADMIN can navigate to `/user/{own_id}/edit`, check the GOD box, and save. Three additional code paths (bulk import, two user creation flows) also call `set_permissions()` without hierarchy checks.
>
> **Expected behavior:** Users cannot modify their own permission level. Permission grants are restricted by hierarchy.
>
> **Actual behavior:** Any admin can set any permission on any user, including themselves.
>
> **Validation tasks:**
> - [ ] Reproduce: RFPO_ADMIN edits own profile, checks GOD, saves
> - [ ] Audit existing users for unexpected GOD permissions
> - [ ] Verify API layer is not similarly affected (confirmed safe)
> - [ ] Audit all four `set_permissions()` code paths
>
> **Implementation approach:**
> 1. Add self-edit guard: `if user.id == current_user.id` → skip permission update, flash warning
> 2. Add permission hierarchy: only GOD users can assign GOD
> 3. Log all permission changes with `old_permissions` → `new_permissions` + acting user
> 4. Apply same guards to all four `set_permissions()` call sites (lines ~2124, ~2144, ~2244, ~2368)
>
> **Acceptance criteria:**
> - [ ] RFPO_ADMIN cannot modify own permissions
> - [ ] RFPO_ADMIN cannot assign GOD permission to any user
> - [ ] Only GOD users can assign GOD permission
> - [ ] Permission changes are audit-logged
> - [ ] All set_permissions() call sites enforce hierarchy

---

### Issue 5: PO Generation Broken — No PO Number, Garbled Output

- **Original customer signal:** "the system does not correctly generate a PO - there is no PO number created and the PO form is all garbled, not all sections are properly filled out or correct"
- **Normalized issue statement:** The PDF PO generation feature produces incorrect output: missing PO number, misaligned fields, and incomplete data. The system uses `rfpo.rfpo_id` as the PO number instead of generating a proper sequential PO number. PDF field positioning is miscalibrated.
- **Category:** Bug
- **Impact:** Critical — core deliverable (generating a Purchase Order) is non-functional
- **Likely system/component:** `pdf_generator.py` — `RFPOPDFGenerator` class. PO number drawn at line 311 using `rfpo.rfpo_id`. No `po_number` column exists in the RFPO model. Positioning uses hardcoded fallback offsets.
- **Confidence level:** High — code confirms no true PO number field/generator exists
- **Priority:** Critical
- **Validation plan:**
  1. Generate a PO PDF in admin panel for a test RFPO
  2. Compare output against expected PO template format
  3. Check `PDFPositioning` records exist for the relevant consortium
  4. Verify template PDFs exist in `static/po_files/{consortium}/`
- **Recommended approach (split into two deliverables):**
  - **Phase A — PO Number Generation (Sprint 2):**
    1. Add `po_number` field to RFPO model (auto-generated sequential: `PO-{consortium}-{YYYYMMDD}-{seq}`)
    2. Generate PO number on first approval completion, not on RFPO creation
    3. Update `pdf_generator.py` line 311 to use `rfpo.po_number`
  - **Phase B — PDF Positioning Fix (Sprint 2-3):**
    1. Audit all field coordinates against each consortium template
    2. Fix field mappings for empty sections
    3. Build visual PDF preview tool or fix existing coordinate designer
    4. Requires customer screenshots for specific garbled sections
- **Risks / dependencies:** PO number format must be agreed upon. Template PDFs may need redesign. Positioning is per-consortium and labor-intensive to fix blind.
- **Open questions:**
  - What is the required PO number format?
  - Which template PDF is being used?
  - Which specific sections are garbled? (Need screenshots)
  - Should PO number be generated on approval or on explicit "finalize"?
- **Suggested labels:** `priority:critical`, `area:pdf-generation`, `type:bug`

#### GitHub Issue Draft

**Title:** BUG: PO generation produces garbled output with no PO number

**Body:**
> **Summary:** PDF purchase order generation outputs misaligned fields, missing data, and uses internal RFPO ID instead of a proper PO number.
>
> **Customer report:** "the system does not correctly generate a PO - there is no PO number created and the PO form is all garbled, not all sections are properly filled out or correct"
>
> **Problem statement:**
> 1. No `po_number` field exists — `pdf_generator.py` line 311 draws `rfpo.rfpo_id`
> 2. PDF positioning uses hardcoded offsets that don't match templates
> 3. Some data fields not populated or mapped
>
> **Expected behavior:** Generated PO PDF has a sequential PO number, all fields correctly positioned and filled.
>
> **Actual behavior:** PO shows internal RFPO ID, fields are garbled/misaligned, some sections empty.
>
> **Validation tasks:**
> - [ ] Generate test PO PDF and compare against template
> - [ ] Verify PDFPositioning records exist for target consortium
> - [ ] Verify template PDFs exist in `static/po_files/`
> - [ ] Get customer screenshots of specific problems
>
> **Implementation approach:**
> 1. Add `po_number` column to RFPO model with auto-generation logic
> 2. Generate PO number upon first successful approval
> 3. Audit and fix PDF positioning for each consortium template
> 4. Map all required template fields to RFPO model data
>
> **Acceptance criteria:**
> - [ ] PO PDF contains a sequential, formatted PO number
> - [ ] All template fields correctly positioned and filled
> - [ ] PO number generated only after approval
> - [ ] Output matches customer PO format template

---

### Issue 6: Approver Notifications Missing

- **Original customer signal:** "the system does not notify approvers that there is something for them to approve, nor does it notify that the process is completed"
- **Normalized issue statement:** No automated email notifications are sent when an RFPO enters an approval step or when the process completes. The email infrastructure exists but is not wired into approval transitions.
- **Category:** Bug / Missing Feature
- **Impact:** High — approvers don't know they have pending work; requestors don't know outcomes
- **Likely system/component:** `custom_admin.py` — only 1 call to `send_email` exists (in the test tool at line 1008). Template `templates/email/approval_notification.html` exists but is never used. `advance_to_next_step()` in `models.py` (line 2048) has no notification hook.
- **Confidence level:** High — confirmed: zero `send_email` calls in approval workflow code
- **Priority:** High
- **Validation plan:**
  1. Create RFPO, start approval, confirm no email sent
  2. Complete approval, confirm no completion email
  3. Verify email service is operational via test tool
- **Recommended approach:**
  1. Add notification hooks in `approval_action_approve()` after status changes
  2. Add notification on `advance_to_next_step()`: email next-step approver
  3. Use existing `approval_notification.html` template
  4. Make notifications configurable per workflow (optional Phase 2)
- **Risks / dependencies:** **Hard-blocked on Issue #1** (email deliverability) — notifications are useless if emails don't arrive. Do not start implementation until #1 is verified working.
- **Open questions:**
  - In-app notifications desired?
  - Daily digest option?
- **Suggested labels:** `priority:high`, `area:approval-workflow`, `area:email`, `type:bug`

#### GitHub Issue Draft

**Title:** Approval workflow does not send email notifications to approvers or requestors

**Body:**
> **Summary:** No email notifications sent during approval lifecycle.
>
> **Customer report:** "the system does not notify approvers that there is something for them to approve, nor does it notify that the process is completed"
>
> **Problem statement:** Email infrastructure and template exist, but `send_email()` is never called from approval code. Only call is in the test tool.
>
> **Expected behavior:** Approvers notified on pending action; requestors notified on completion.
>
> **Actual behavior:** No notification emails at any point in approval lifecycle.
>
> **Implementation approach:**
> 1. Add `send_approval_notification()` helper
> 2. Call on: instance creation, action completion, step advancement, workflow completion
> 3. Render existing template with RFPO/approver/status context
>
> **Acceptance criteria:**
> - [ ] Designated approver receives email when action assigned
> - [ ] RFPO requestor receives email on workflow completion
> - [ ] Next approver notified when workflow advances
> - [ ] Emails include direct link to action page
>
> **Blocked by:** Issue #1 (email deliverability) — must be resolved first

---

### Issue 7: RFPO Deletion Leaves Orphaned Records

- **Original customer signal:** "just because you delete a RFPO in one place, it still has a ghost existence and it takes deleting it in multiple places"
- **Normalized issue statement:** Deleting an RFPO does not cascade to `RFPOApprovalInstance` records. The RFPO model has cascade delete for `RFPOLineItem` and `UploadedFile`, but the relationship to `RFPOApprovalInstance` uses a simple backref without cascade. Since `RFPOApprovalInstance.rfpo_id` is a `NOT NULL` FK, deletion on PostgreSQL will fail with an IntegrityError (caught by a generic exception handler showing a vague error). On SQLite with unenforced FKs, true orphan records result.
- **Category:** Bug
- **Impact:** Medium — confusing UX, data integrity concern, silent failures on PostgreSQL
- **Likely system/component:** `custom_admin.py` — `rfpo_delete()` (line ~3172). `models.py` — RFPO relationships (line ~207-210 for cascaded; ~1970 for non-cascaded approval instance backref).
- **Confidence level:** High — confirmed by code review
- **Priority:** Medium
- **Validation plan:**
  1. Create RFPO + approval instance, complete the approval
  2. Attempt to delete RFPO
  3. On PostgreSQL: expect IntegrityError. On SQLite: check if approval instance survives
- **Recommended approach:**
  1. Add `cascade="all, delete-orphan"` to the RFPO → approval_instance relationship in `models.py`
  2. Also add explicit orphan cleanup in `rfpo_delete()` before parent deletion as a safety net
  3. Run migration to clean up existing orphaned records
  4. Consider soft-delete pattern for audit trail preservation (future enhancement)
- **Risks / dependencies:** Need to decide if approval history should be preserved (soft-delete pattern).
- **Open questions:** Soft-delete vs hard-delete for audit trail?
- **Suggested labels:** `priority:medium`, `area:data-integrity`, `type:bug`

#### GitHub Issue Draft

**Title:** BUG: Deleting RFPO leaves orphaned approval instances (or fails silently on PostgreSQL)

**Body:**
> **Summary:** RFPO deletion does not cascade to approval instances. On PostgreSQL this causes a silent IntegrityError; on SQLite it creates orphan records.
>
> **Customer report:** "just because you delete a RFPO in one place, it still has a ghost existence and it takes deleting it in multiple places"
>
> **Problem statement:** RFPO model cascades to `RFPOLineItem` and `UploadedFile` but NOT `RFPOApprovalInstance`. The `rfpo_id` FK is `NOT NULL`, causing delete failures on PostgreSQL that are caught by a generic exception handler.
>
> **Expected behavior:** Single delete removes RFPO and all associated records.
>
> **Actual behavior:** Deletion fails silently (PostgreSQL) or creates orphans (SQLite).
>
> **Implementation approach:**
> 1. Add `cascade="all, delete-orphan"` to RFPO → RFPOApprovalInstance relationship
> 2. Add explicit cleanup in `rfpo_delete()` before parent deletion
> 3. Migration to clean up existing orphans
>
> **Acceptance criteria:**
> - [ ] Deleting RFPO removes all associated instances and actions
> - [ ] No orphaned records in any list view
> - [ ] Single delete action sufficient
> - [ ] Works correctly on both SQLite and PostgreSQL

---

### Issue 8: RFPO Building Flow UX — Redundant Sections

- **Original customer signal:** "redundant parts of the building process - process initially starts out with good flow - but once you get to line items, flow is lost - sections that have already been completed come back up"
- **Normalized issue statement:** The RFPO creation flow uses a wizard (stage1 → stage2) followed by a tabbed edit. Previously completed sections reappear in tabs, confusing users.
- **Category:** UX / Enhancement
- **Impact:** Medium — user confusion, potential for accidental overwrites
- **Likely system/component:** `templates/admin/rfpo_edit.html` — all tabs always visible
- **Confidence level:** Medium
- **Priority:** Medium
- **Validation plan:** Walk through full creation flow and document redundant sections
- **Recommended approach:**
  1. Add completion indicators (checkmarks) on tabs
  2. Default to first incomplete tab after save
  3. Show read-only summaries for completed sections
  4. Add final "Review & Submit" step (ties into Issue #9)
- **Suggested labels:** `priority:medium`, `area:ui`, `type:enhancement`, `ux`

#### GitHub Issue Draft

**Title:** UX: RFPO building flow shows redundant completed sections

**Body:**
> **Summary:** Previously completed sections reappear without completion indicators, confusing users.
>
> **Customer report:** "once you get to line items, flow is lost - sections that have already been completed come back up"
>
> **Implementation approach:**
> 1. Add completion indicators per tab
> 2. Default to first incomplete tab after save
> 3. Read-only summaries for completed sections
> 4. Final "Review & Submit" step
>
> **Acceptance criteria:**
> - [ ] Completed sections show visual indicator
> - [ ] After save, user lands on next incomplete section
> - [ ] Clear linear progression visible

---

### Issue 9: Missing RFPO Submit Action

- **Original customer signal:** "submission of the RFPO happens in approval instances, rather than having a submit button at the end of the RFPO building process"
- **Normalized issue statement:** No explicit "Submit RFPO" action exists. An admin must manually create an approval instance to initiate the workflow.
- **Category:** UX / Enhancement
- **Impact:** Medium — confusing handoff between building and approval
- **Likely system/component:** `templates/admin/rfpo_edit.html`, `custom_admin.py`
- **Confidence level:** High — confirmed: RFPO stays "Draft" until manual approval instance creation
- **Priority:** Medium (consider bumping to High — this is the linchpin connecting #6, #8, and #10)
- **Validation plan:** Complete RFPO and confirm no submit button exists
- **Recommended approach:**
  1. Add "Submit for Approval" button (visible when RFPO has required fields + line items)
  2. New route: validates completeness → creates approval instance → changes status → notifies first approver
  3. Add validation: require minimum fields before submission
- **Risks / dependencies:** Ties into Issues #6 and #10.
- **Suggested labels:** `priority:medium`, `area:ui`, `area:approval-workflow`, `type:enhancement`

#### GitHub Issue Draft

**Title:** Add explicit "Submit for Approval" button to RFPO building flow

**Body:**
> **Summary:** Users must manually create an approval instance. Need a clear "Submit for Approval" button.
>
> **Customer report:** "submission of the RFPO happens in approval instances, rather than having a submit button at the end"
>
> **Implementation approach:**
> 1. Add "Submit for Approval" button to RFPO edit page
> 2. Create `/rfpo/<id>/submit` route: validate + create instance + change status + notify
> 3. Button disabled for incomplete RFPOs
>
> **Acceptance criteria:**
> - [ ] Button visible when RFPO complete (vendor, line items, required docs)
> - [ ] Creates instance, changes status to "Submitted"
> - [ ] First approver notified
> - [ ] Button disabled/hidden for incomplete RFPOs with clear indication of what's missing

---

### Issue 10: Approval Workflow Fully Parallel — Needs Sequential Gates

- **Original customer signal:** "hierarchy of approvals - there should be gates that trigger each next round - right now, everything is a full parallel approval process. also, we are missing some approval levels that we need to add"
- **Normalized issue statement:** The workflow does not enforce sequential gate logic between stages. All approval actions appear to be created simultaneously. Customer also needs additional approval levels.
- **Category:** Bug / Enhancement
- **Impact:** High — violates approval governance; higher-level approvers shouldn't act until lower levels complete
- **Likely system/component:** `models.py` — `advance_to_next_step()` (line ~2048). The model data structure supports sequencing (`current_stage_order`, `current_step_order`), but `advance_to_next_step()` only increments counters — it does not gate action creation or UI visibility. Instance creation likely generates all actions at once.
- **Confidence level:** High (upgraded from Medium — code clearly confirms the gap)
- **Priority:** High
- **Validation plan:**
  1. Create multi-stage workflow + approval instance
  2. Check if all actions are immediately visible
  3. Verify `advance_to_next_step()` is called and respects ordering
- **Recommended approach:**
  1. Modify instance creation: only create actions for Stage 1 / Step 1
  2. On step completion: create actions for next step + notify
  3. UI: only show pending actions for current active stage/step
  4. Support parallel within stage, sequential across stages
  5. Add admin UI for new approval levels
- **Risks / dependencies:** Changing execution model may affect in-progress instances. Need migration plan for active workflows.
- **Open questions:**
  - What specific approval levels are missing?
  - Parallel steps within a sequential stage?
  - Budget thresholds?
- **Suggested labels:** `priority:high`, `area:approval-workflow`, `type:enhancement`

#### GitHub Issue Draft

**Title:** Implement sequential approval gates with stage-based gating

**Body:**
> **Summary:** Approval runs all stages in parallel. Need sequential gating. Additional approval levels needed.
>
> **Customer report:** "there should be gates that trigger each next round - right now, everything is a full parallel approval process"
>
> **Implementation approach:**
> 1. Only generate actions for Stage 1 / Step 1 initially
> 2. On completion: create next step actions + notify
> 3. UI: hide future stages, show only current
> 4. Support parallel-within-stage, sequential-across-stages
> 5. Admin UI for new approval levels
>
> **Acceptance criteria:**
> - [ ] Stage 2 approvers cannot see/act until Stage 1 complete
> - [ ] Next-stage approvers notified when activated
> - [ ] New approval levels addable via admin UI
> - [ ] `stage_order` / `step_order` drive execution sequence

---

### Issue 11: Confusing Nomenclature — "Approval Workflows"

- **Original customer signal:** "confusing nomenclature (approval workflows should just be called workflow, as it confuses people who are coming in to approve)"
- **Normalized issue statement:** Rename "Approval Workflows" to "Workflows" in UI.
- **Category:** UX / Enhancement
- **Impact:** Low — cosmetic
- **Priority:** Low
- **Suggested labels:** `priority:low`, `area:ui`, `type:enhancement`, `ux`

#### GitHub Issue Draft

**Title:** UX: Rename "Approval Workflows" to "Workflows" in UI

**Body:**
> Find and replace "Approval Workflow(s)" → "Workflow(s)" in all user-facing templates and navigation. Internal model/variable names unchanged.
>
> **Acceptance criteria:**
> - [ ] No UI element references "Approval Workflow" — changed to "Workflow"
> - [ ] Navigation labels updated
> - [ ] No code-level model renames

---

### Issue 12: User App Purpose Unclear

- **Original customer signal:** "'user' role/platform - I don't understand the purpose of this"
- **Normalized issue statement:** The purpose and value of the separate User App is unclear to the customer.
- **Category:** Clarification / UX
- **Impact:** Low — organizational confusion
- **Priority:** Low
- **Suggested labels:** `priority:low`, `area:architecture`, `type:investigation`

#### GitHub Issue Draft

**Title:** Clarify and document User App purpose; evaluate consolidation

**Body:**
> **Summary:** The User App's purpose is unclear. Evaluate enhancement vs. consolidation.
>
> **Customer report:** "'user' role/platform - I don't understand the purpose of this"
>
> **Validation tasks:**
> - [ ] Document current capabilities vs. Admin Panel
> - [ ] Determine intended user journey for non-admin users
> - [ ] Recommend: enhance, consolidate, or clarify with documentation
>
> **Acceptance criteria:**
> - [ ] Clear documentation of User App purpose
> - [ ] Decision recorded: enhance, consolidate, or maintain as-is

---

## Recommended Execution Plan

| Priority | Issue | Type | Effort | Target Sprint | Notes |
|----------|-------|------|--------|---------------|-------|
| **Critical** | #4 — Privilege escalation | Security fix | Small | Sprint 1 | All 4 `set_permissions()` paths |
| **Critical** | #3 — Approval authorization | Security fix | Medium | Sprint 1 | |
| **Critical** | CSRF (new) — No CSRF protection | Security fix | Medium | Sprint 1 | All POST forms vulnerable |
| **Critical** | #1 — Email deliverability | Infrastructure | Small | Sprint 1 | Requires USCAR IT cooperation |
| **Critical** | #5a — PO number generation | Bug fix | Medium | Sprint 2 | Split from positioning fix |
| **High** | #6 — Approver notifications | Feature gap | Medium | Sprint 2 | Hard-blocked on #1 |
| **High** | #9 — Submit button | Enhancement | Medium | Sprint 2 | Linchpin for #6, #8, #10 |
| **High** | #10 — Sequential approval gates | Enhancement | Large | Sprint 2-3 | |
| **High** | #2 — SSO integration (discovery) | Enhancement | Small | Sprint 2 | Discovery spike only |
| **Critical** | #5b — PDF positioning fix | Bug fix | Large | Sprint 2-3 | Needs customer screenshots |
| **Medium** | #7 — RFPO deletion orphans | Bug fix | Small | Sprint 2 | |
| **Medium** | #8 — RFPO building flow UX | Enhancement | Medium | Sprint 3 | |
| **High** | #2 — SSO integration (implementation) | Enhancement | X-Large | Sprint 3+ | |
| **Low** | #11 — Nomenclature rename | UX polish | Small | Sprint 2 | Low-risk, easy win |
| **Low** | #12 — User App clarity | Investigation | Small | Sprint 3 | |

---

## Dependency Graph

```
Issue #1 (Email) ──────────► Issue #6 (Notifications) ─┐
                                                        ├──► Issue #10 (Sequential Gates)
Issue #9 (Submit Button) ──────────────────────────────┘
                               │
Issue #8 (UX Flow) ◄───────────┘

Issue #4 (Privilege Escalation) ──┐
Issue #3 (Approval Auth) ─────────┤──► Security Hardening (Sprint 1)
CSRF Protection (new) ────────────┘

Issue #5a (PO Number) ──► Issue #5b (PDF Positioning)

Issue #2 (SSO Discovery) ──► Issue #2 (SSO Implementation)
```

---

## Appendix: Code References

| Issue | File | Line(s) | Finding |
|-------|------|---------|---------|
| #3 | `custom_admin.py` | ~5831 | `is_super_admin()` bypasses approver check |
| #4 | `custom_admin.py` | ~2312 | `user_edit()` — no self-edit guard |
| #4 | `custom_admin.py` | ~2124, ~2144, ~2244, ~2368 | Four `set_permissions()` paths without hierarchy |
| #4 | `api/user_routes.py` | ~41 | API layer safe — permissions not in `updatable_fields` |
| #5 | `pdf_generator.py` | ~311 | Uses `rfpo.rfpo_id` instead of PO number |
| #6 | `custom_admin.py` | ~1008 | Only `send_email` call — in test tool |
| #6 | `models.py` | ~2048 | `advance_to_next_step()` — no notification hooks |
| #7 | `models.py` | ~207-210 | RFPO cascades to LineItem/UploadedFile only |
| #7 | `models.py` | ~1970 | Approval instance backref — no cascade |
| #7 | `custom_admin.py` | ~3172 | `rfpo_delete()` — no explicit instance cleanup |
| #10 | `models.py` | ~2048 | `advance_to_next_step()` — increments counters only |
| CSRF | `custom_admin.py` | entire file | No `CSRFProtect` or token validation |