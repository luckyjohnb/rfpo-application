## Summary
Any user with admin panel access can approve RFPOs on behalf of any designated approver, breaking separation of duties.

## Customer Report
> "the actual approval of an RFPO does not appear to be linked to a user - anyone in admin mode can approve for anyone else - the system does not really differentiate user 'powers' in a way that will be effective for us"

## Problem Statement
The `approval_action_approve()` function in `custom_admin.py` (line ~5831) checks `action.approver_id != current_user.record_id` but allows `is_super_admin()` to bypass. Since `is_rfpo_admin()` returns `True` for both RFPO_ADMIN and GOD roles, any admin-panel user can navigate to approval URLs and execute actions meant for specific approvers.

## Priority
**Critical / Security** — Fix in Sprint 1

## Expected Behavior
Only the designated primary approver or backup approver for a given approval action can execute it. Other users see the action as read-only.

## Actual Behavior
Any admin-panel user can approve/reject any pending approval action.

## Validation Tasks
- [ ] Reproduce: log in as RFPO_ADMIN (not the designated approver), approve another user's action
- [ ] Review all routes that modify `RFPOApprovalAction.status`
- [ ] Check if API layer has similar bypass

## Implementation Approach
1. Remove `is_super_admin()` bypass in `approval_action_approve()`
2. Add backup approver check: allow `step.backup_approver_id` as alternative
3. Add "Reassign Approver" action for GOD users (separate from approve)
4. Hide approve/reject UI controls for non-authorized users
5. Add audit field: `approved_by_user_id` (actual actor) alongside `approver_id` (designated)

## Acceptance Criteria
- [ ] Only `primary_approver_id` or `backup_approver_id` can execute approval action
- [ ] GOD users can reassign but not silently approve as someone else
- [ ] UI hides action buttons for non-authorized users
- [ ] Audit trail records actual approving user identity

## Open Questions
- Should backup approver auto-activate after N days of inactivity?
- Delegation/reassignment workflow requirements?

## Triage Reference
Customer Triage 2026-04-01 — Issue #3
Epic: RFPO Security Hardening
