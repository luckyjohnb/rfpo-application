## Summary
No explicit "Submit RFPO" action exists. An admin must manually create an approval instance in a separate area to initiate the workflow.

## Customer Report
> "submission of the RFPO happens in approval instances, rather than having a submit button at the end of the RFPO building process"

## Problem Statement
RFPO status remains "Draft" until an admin navigates to a separate approval management area and manually creates an approval instance. There is no "Submit for Approval" button in the RFPO building flow. This is the linchpin issue connecting notifications (#6), UX flow (#8), and sequential approval gates (#10).

## Priority
**High** — Sprint 2 (recommended priority bump from Medium due to dependency impact)

## Expected Behavior
A "Submit for Approval" button is available at the end of the RFPO building process. Clicking it validates completeness and initiates the approval workflow automatically.

## Actual Behavior
RFPO stays as Draft. Admin must separately navigate to approval management and create an instance manually.

## Validation Tasks
- [ ] Confirm no submit button exists on RFPO edit page
- [ ] Document current manual approval instance creation path

## Implementation Approach
1. Add "Submit for Approval" button on RFPO edit page (visible when RFPO has required fields + line items)
2. Create `/rfpo/<id>/submit` route that:
   - Validates completeness (vendor selected, line items present, required docs uploaded)
   - Automatically selects applicable workflow based on project/consortium/amount
   - Creates approval instance
   - Changes RFPO status to "Submitted"
   - Sends notification to first approver (ties into Issue #6)
3. Show clear indication of what's missing if validation fails
4. Disable button for incomplete RFPOs with checklist of remaining items

## Acceptance Criteria
- [ ] "Submit for Approval" button visible when RFPO is complete
- [ ] Button validates: vendor selected, at least one line item, required documents uploaded
- [ ] Creates approval instance and changes status to "Submitted"
- [ ] First approver is notified (after Issue #6 is implemented)
- [ ] Button disabled/hidden for incomplete RFPOs with clear indication of what's missing
- [ ] Cannot re-submit an already-submitted RFPO

## Open Questions
- Completeness validation requirements (minimum fields / documents)?
- Who can submit: any RFPO creator, or only admins?
- Can an RFPO be withdrawn/un-submitted after submission?

## Triage Reference
Customer Triage 2026-04-01 — Issue #9
Epic: Approval Workflow v2
