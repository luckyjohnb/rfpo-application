## Summary
The separate User App's purpose is unclear to the customer. Evaluate whether it should be enhanced as the primary user-facing interface or consolidated into the admin panel with role-based views.

## Customer Report
> "'user' role/platform - I don't understand the purpose of this"

## Problem Statement
The User App (port 5000) provides read-only RFPO views, team listings, and profile management — but these functions overlap with or are less capable than the admin panel. The customer doesn't understand its value proposition.

## Priority
**Low** — Sprint 3

## Validation Tasks
- [ ] Document current User App capabilities vs. Admin Panel
- [ ] Determine intended user journey for non-admin users (RFPO_USER role, approvers)
- [ ] Survey customer: do they want a separate read-only portal or single interface?

## Recommended Options
1. **Enhance User App** — make it the primary interface for non-admin users (approvers, RFPO_USER), with admin panel reserved for GOD/RFPO_ADMIN configuration tasks
2. **Consolidate** — merge into single app with role-based views (hide admin features from non-admins)
3. **Clarify** — add clear onboarding/landing page explaining what users can do here

## Acceptance Criteria
- [ ] Clear documentation of User App purpose and target audience
- [ ] Decision recorded: enhance, consolidate, or maintain as-is
- [ ] If maintaining: add "What can I do here?" landing page

## Triage Reference
Customer Triage 2026-04-01 — Issue #12
Epic: UX Improvements
