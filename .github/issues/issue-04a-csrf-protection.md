## Summary
The admin panel has no CSRF protection — no `CSRFProtect`, no `WTF_CSRF` configuration, no token validation on POST forms. Every state-changing operation is vulnerable to cross-site request forgery.

## Problem Statement
All POST forms in `custom_admin.py` (user edit, RFPO delete, permission changes, approval actions) lack CSRF tokens. An attacker could craft a malicious page that submits forms on behalf of an authenticated admin user.

This was identified during the engineering review of the customer triage — not directly reported by the customer, but compounds the severity of Issues #3 and #4.

## Priority
**Critical / Security** — Fix in Sprint 1

## Expected Behavior
All state-changing forms include CSRF tokens. POST requests without valid tokens are rejected.

## Actual Behavior
No CSRF protection exists anywhere in the admin panel.

## Validation Tasks
- [ ] Confirm no `CSRFProtect` or `WTF_CSRF` in codebase
- [ ] Confirm POST forms lack hidden CSRF token fields
- [ ] Demonstrate CSRF attack vector (e.g., cross-origin form submission to approval endpoint)

## Implementation Approach
1. Add `Flask-WTF` CSRFProtect to admin panel app initialization
2. Add `{{ csrf_token() }}` or `{{ form.hidden_tag() }}` to all POST form templates
3. Ensure AJAX POST requests include CSRF token in headers
4. Add `WTF_CSRF_TIME_LIMIT` configuration
5. Test all POST endpoints accept valid tokens and reject missing/invalid ones

## Acceptance Criteria
- [ ] `CSRFProtect` initialized in admin app
- [ ] All POST forms include CSRF token
- [ ] POST requests without valid CSRF token return 400
- [ ] AJAX requests include CSRF token in X-CSRFToken header
- [ ] No functional regression — all forms still work with valid tokens

## Triage Reference
Customer Triage 2026-04-01 — Issue #4a (newly identified during review)
Epic: RFPO Security Hardening
