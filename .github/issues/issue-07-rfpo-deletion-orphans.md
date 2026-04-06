## Summary
RFPO deletion does not cascade to approval instances and actions, leaving orphan records or causing silent failures.

## Customer Report
> "just because you delete a RFPO in one place, it still has a ghost existence and it takes deleting it in multiple places"

## Problem Statement
The `rfpo_delete()` route in `custom_admin.py` (line ~3172) relies on SQLAlchemy cascade for line items and files, but `RFPOApprovalInstance` is **not** included in the cascade. The `rfpo_id` column on `RFPOApprovalInstance` is a NOT NULL FK.

**Behavior varies by database:**
- **PostgreSQL (production):** Delete fails with IntegrityError, caught by generic `except` block — user sees vague error, RFPO survives
- **SQLite (local dev):** FK enforcement may be off, creating true orphan records

## Priority
**Medium** — Sprint 2

## Expected Behavior
Single delete action removes the RFPO and all associated records (line items, files, approval instances, actions).

## Actual Behavior
RFPO deletion either fails silently (PostgreSQL) or creates orphan approval records (SQLite).

## Validation Tasks
- [ ] Delete RFPO with an approval instance on PostgreSQL and verify error
- [ ] Delete RFPO with an approval instance on SQLite and verify orphans
- [ ] Audit model relationship cascade settings

## Implementation Approach
1. Add `cascade="all, delete-orphan"` to RFPO → RFPOApprovalInstance relationship
2. OR add explicit deletion of related instances in `rfpo_delete()` before parent deletion
3. Add migration to clean up any existing orphaned records
4. Consider soft-delete pattern (set `status='Deleted'`) for audit trail preservation

## Acceptance Criteria
- [ ] Deleting RFPO removes all associated approval instances and actions
- [ ] No orphaned records remain in any list view
- [ ] Single delete action is sufficient — no need to delete in multiple places
- [ ] Works correctly on both PostgreSQL and SQLite

## Open Questions
- Soft-delete vs hard-delete for audit trail requirements?
- Are there other places where RFPO data lingers?

## Triage Reference
Customer Triage 2026-04-01 — Issue #7
Epic: UX Improvements
