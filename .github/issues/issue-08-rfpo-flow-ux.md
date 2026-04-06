## Summary
The RFPO creation flow loses coherence after line items — previously completed sections reappear without completion indicators, confusing users.

## Customer Report
> "redundant parts of the building process - process initially starts out with good flow - but once you get to line items, flow is lost - sections that have already been completed come back up"

## Problem Statement
The RFPO creation uses a two-stage wizard (stage1 → stage2) followed by a tabbed edit view. After reaching line items, previously-completed sections (basic info, shipping, vendor) re-appear in the tab interface. No completion indicators exist. Users think they need to re-enter information.

## Priority
**Medium** — Sprint 3

## Expected Behavior
Clear progression through RFPO building steps with visual completion indicators. Previously completed sections shown as summaries or clearly marked as done.

## Actual Behavior
All tabs equally prominent. No completion tracking. Sections filled in stage1/stage2 appear as if they need re-entry.

## Validation Tasks
- [ ] Walk through full creation flow: stage1 → stage2 → edit view
- [ ] Document which sections appear redundantly
- [ ] Compare to customer's expected flow

## Implementation Approach
1. Add completion status indicators (checkmarks/badges) per tab
2. Default to the first incomplete tab after save
3. Show read-only summaries for completed sections (expandable for editing)
4. Add a linear wizard/stepper mode as alternative to tabs for first-time creation
5. Add final "Review & Submit" step (ties into Submit Button issue)

## Acceptance Criteria
- [ ] Completed sections show visual completion indicator
- [ ] After save, user lands on the next incomplete section
- [ ] Clear linear progression is visible throughout building process

## Open Questions
- Desired flow: linear wizard vs. improved tabs?
- Which specific sections are felt as redundant?

## Triage Reference
Customer Triage 2026-04-01 — Issue #8
Epic: UX Improvements
