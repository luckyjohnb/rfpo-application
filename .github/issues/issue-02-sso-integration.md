## Summary
Implement OIDC-based SSO with the USCAR Microsoft Entra ID tenant so users authenticate with their organizational credentials instead of maintaining separate RFPO credentials.

## Customer Report
> "is it possible to move this app into our Microsoft tenent and avoid the need for a secondary login?"

## Problem Statement
Users must maintain separate RFPO credentials, creating friction and a barrier to adoption. No SSO/OIDC code exists in the codebase today.

## Priority
**High** — Sprint 3+ (discovery spike in Sprint 2)

## Expected Behavior
Users click "Sign in with Microsoft" and are authenticated via their USCAR organizational account. Existing user accounts matched by email automatically.

## Actual Behavior
Users must create and manage a separate username/password for RFPO.

## Validation Tasks
- [ ] Confirm USCAR Entra ID tenant details and admin availability
- [ ] Determine user population (all internal? any external?)
- [ ] Prototype MSAL integration on dev environment

## Implementation Approach
1. Register RFPO app in USCAR Entra ID tenant (3 redirect URIs: user, admin, API)
2. Add `msal` to requirements and implement OIDC auth code flow
3. Map Entra ID email to existing `User.email` for account linking
4. Add "Sign in with Microsoft" button alongside existing login
5. Update session management to support both auth paths
6. Keep existing JWT flow as fallback for non-tenant users
7. (Phase 2) Add Entra group → RFPO permission mapping

## Acceptance Criteria
- [ ] USCAR users can authenticate using organizational Microsoft account
- [ ] Existing user accounts matched by email automatically
- [ ] Traditional login remains available as fallback
- [ ] JWT tokens continue to work for API consumers
- [ ] Both User App and Admin Panel support SSO

## Open Questions
- Entra ID tenant ID and admin contact?
- Should SSO completely replace password login, or coexist?
- Are external (non-USCAR) users expected?
- Which Entra ID groups should map to which RFPO permissions?

## Triage Reference
Customer Triage 2026-04-01 — Issue #2
Epic: SSO Integration
