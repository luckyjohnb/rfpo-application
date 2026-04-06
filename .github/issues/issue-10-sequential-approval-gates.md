## Summary
Approval workflow runs all stages in parallel. Needs sequential gate logic where each stage must complete before the next begins. Additional approval levels need to be added.

## Customer Report
> "hierarchy of approvals - related to the issue of notifying people that they have something they need to approve - there should be gates that trigger each next round - right now, everything is a full parallel approval process. also, we are missing some approval levels that we need to add"

## Problem Statement
The model supports `stage_order`, `step_order`, and `advance_to_next_step()` (models.py line ~2048), but the execution layer doesn't enforce sequential gating. All approval actions appear to be created and made visible simultaneously. The `advance_to_next_step()` method only advances counters — it does not create new actions or gate visibility.

## Priority
**High** — Sprint 2-3

## Expected Behavior
- Approval flows sequentially through stages
- Each stage's approvers are notified only when the previous stage completes
- Additional approval levels can be configured via admin UI

## Actual Behavior
All approval actions across all stages appear concurrently. No gating between stages.

## Validation Tasks
- [ ] Create multi-stage, multi-step workflow
- [ ] Create approval instance and verify all actions are immediately visible
- [ ] Trace `advance_to_next_step()` — verify it only increments counters, doesn't gate
- [ ] Check how approval instance creation populates actions (all at once vs. per-stage)

## Implementation Approach
1. Modify approval instance creation: only generate actions for Stage 1 / Step 1 initially
2. On step completion via `advance_to_next_step()`: create actions for next step and notify approvers
3. UI: only display actions for current active stage/step (hide future stages)
4. Support "parallel within a stage, sequential across stages" model
5. Add admin UI to configure new approval levels/stages
6. Add budget threshold configuration per stage

## Acceptance Criteria
- [ ] Stage 2 approvers cannot see or act on pending item until Stage 1 is complete
- [ ] Next-stage approvers are notified when their stage becomes active
- [ ] New approval levels can be added via admin UI
- [ ] Existing `stage_order` / `step_order` model fields drive execution sequence
- [ ] Steps within a single stage can run in parallel
- [ ] Existing workflow data is migrated safely

## Open Questions
- What specific approval levels are needed? (Customer to specify)
- Should steps within a stage be parallel or sequential?
- What budget thresholds trigger which approval levels?
- Migration strategy for in-progress approval instances?

## Triage Reference
Customer Triage 2026-04-01 — Issue #10
Epic: Approval Workflow v2
