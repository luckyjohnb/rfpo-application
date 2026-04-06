## Summary
No email notifications are sent during the approval lifecycle — approvers aren't notified of pending actions, and requestors aren't notified of outcomes.

## Customer Report
> "the system does not notify approvers that there is something for them to approve, nor does it notify that the process is completed (although since we couldn't actually generate a PO - perhaps that is why?)"

## Problem Statement
The email infrastructure and template (`templates/email/approval_notification.html`) exist, but `send_email()` is never called from the approval workflow code. The only call to `send_email` in `custom_admin.py` is in the email test tool (line 1008). The `advance_to_next_step()` method in `models.py` has no notification hook.

## Priority
**High** — Sprint 2

**Blocked by:** Issue #1 (email deliverability) — notifications are inert if emails don't arrive.

## Expected Behavior
- Approvers receive email when they have a pending action
- Requestors receive email when approval cycle completes (approved/rejected)
- Next-in-line approvers notified when workflow advances to their step

## Actual Behavior
No notification emails are sent at any point in the approval lifecycle.

## Validation Tasks
- [ ] Confirm email service is functional (send test email via admin tool)
- [ ] Trace approval workflow code to verify no `send_email` calls
- [ ] Review `approval_notification.html` template variables and context needs

## Implementation Approach
1. Create `send_approval_notification(action, event_type)` helper function
2. Add notification calls in `approval_action_approve()` after status changes:
   - On instance creation: email designated approver "You have a pending approval"
   - On approval/rejection: email requestor with outcome
   - On workflow completion: email requestor + all approvers with final status
3. Add notification on `advance_to_next_step()`: email next-step approver
4. Render existing `approval_notification.html` template with RFPO/approver/status context
5. Include direct link to approval action page in emails
6. (Phase 2) Make notifications configurable per workflow

## Acceptance Criteria
- [ ] Designated approver receives email when action is assigned to them
- [ ] RFPO requestor receives email on workflow completion (approved/refused)
- [ ] Next approver notified when workflow advances to their step
- [ ] Emails include direct link to approval action page
- [ ] Email failures are logged but don't block workflow progression

## Open Questions
- In-app notifications desired (dashboard badge)?
- Daily digest option for approvers with multiple pending items?

## Triage Reference
Customer Triage 2026-04-01 — Issue #6
Epic: Email & Notifications
