## Summary
The UI label "Approval Workflows" confuses end-users who associate "approval" with the act of approving, not workflow definitions. Rename to "Workflows."

## Customer Report
> "confusing nomenclature (approval workflows should just be called workflow, as it confuses people who are coming in to approve)"

## Priority
**Low** — Sprint 2 (quick win)

## Implementation Approach
Global find-and-replace "Approval Workflow(s)" → "Workflow(s)" in all user-facing templates and navigation labels. Internal model/variable names remain unchanged.

## Acceptance Criteria
- [ ] No UI element references "Approval Workflow" — changed to "Workflow"
- [ ] Navigation labels updated
- [ ] No code-level model renames (only display strings)

## Triage Reference
Customer Triage 2026-04-01 — Issue #11
Epic: UX Improvements
