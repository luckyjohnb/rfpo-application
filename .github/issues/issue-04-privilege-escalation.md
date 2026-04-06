## Summary
No authorization guard prevents admin users from editing their own user record and escalating permissions to GOD (super admin).

## Customer Report
> "any user can change their role within the system (an admin can make themselves god)"

## Problem Statement
The `user_edit()` route in `custom_admin.py` (line ~2312) does not check whether `current_user.id == target_user.id`. Any RFPO_ADMIN can navigate to `/user/{own_id}/edit`, check the GOD permission checkbox, and save — granting themselves unrestricted access.

**Additional scope:** There are **4 code paths** calling `set_permissions()` without hierarchy enforcement (lines 2124, 2144, 2244, 2368). All must be fixed.

## Priority
**Critical / Security** — Fix immediately (Sprint 1)

## Expected Behavior
- Users cannot modify their own permission level
- Permission grants are restricted by hierarchy (only GOD can assign GOD)

## Actual Behavior
Any admin can set any permission on any user, including themselves.

## Validation Tasks
- [ ] Reproduce: RFPO_ADMIN edits own profile, checks GOD, saves
- [ ] Audit existing users for unexpected GOD permissions
- [ ] Verify API layer is not similarly affected (confirmed safe — `user_routes.py` excludes permissions from updatable fields)
- [ ] Verify all 4 `set_permissions()` code paths are guarded

## Implementation Approach
1. Add self-edit guard: `if user.id == current_user.id` → skip permission update, flash warning
2. Add permission hierarchy: only GOD users can assign GOD; RFPO_ADMIN can assign RFPO_ADMIN/RFPO_USER only
3. Log all permission changes with `old_permissions` → `new_permissions` + acting user
4. Apply same guards to bulk user import path (line ~2124) and all `set_permissions()` call sites

## Acceptance Criteria
- [ ] RFPO_ADMIN cannot modify own permissions via `/user/<id>/edit`
- [ ] RFPO_ADMIN cannot assign GOD permission to any user
- [ ] Only GOD users can assign GOD permission
- [ ] Permission changes are audit-logged with before/after
- [ ] All 4 `set_permissions()` paths enforce hierarchy
- [ ] Bulk user import respects same hierarchy

## Triage Reference
Customer Triage 2026-04-01 — Issue #4
Epic: RFPO Security Hardening
