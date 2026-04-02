# External Identity Integration — Architecture & Implementation Plan

**Date:** 2026-04-02
**Status:** ALL DECISIONS CONFIRMED — Implementation Phase 1 in progress
**Author:** Engineering
**Audience:** Engineering leadership, USCAR IT, implementation team

---

## Executive Summary

USCAR has requested that their customers — employees of companies like Ford, GM, and Stellantis — be able to log into the RFPO application using their own corporate email addresses and enterprise credentials. USCAR already supports this pattern in other applications.

This is **not a simple SSO integration**. The requirement describes a **multi-organization external identity** pattern where users from *different* identity providers (Ford's Entra ID, GM's Entra ID, Stellantis's Entra ID, etc.) authenticate against the RFPO application, which is hosted in or associated with USCAR's infrastructure.

The correct enterprise identity pattern is **Microsoft Entra External ID (B2B collaboration)** — or equivalently, a **federated multi-tenant application** registered in USCAR's Entra ID tenant that accepts sign-ins from pre-approved external organizations.

This document evaluates the requirement, analyzes the current system, presents implementation options with tradeoffs, identifies all decisions that must be made, and provides an implementation plan suitable for both engineering execution and leadership decision-making.

### Key Findings

1. The current system has **zero external identity support** — all authentication is email/password with self-managed hashes.
2. The requirement involves **multiple external identity providers**, not a single SSO integration.
3. The User model already has `company_code` and `company` fields — a natural basis for organization-aware identity.
4. USCAR's existing multi-org pattern in other apps strongly suggests they already use **Entra External ID (B2B)** or a similar federation model.
5. The RFPO application's 3-tier architecture (User App, Admin Panel, API) requires careful design of the authentication flow to avoid inconsistency.

### Recommendation

**Option D: B2B Collaboration + Password Fallback** via USCAR's Entra ID tenant, implemented with **SAML 2.0** protocol using `python3-saml`. IT has confirmed they use SAML-based Enterprise Applications with B2B guest users and `user.assignedroles` for role-based access. This matches USCAR's existing pattern exactly.

**Protocol update:** The original draft recommended OIDC/MSAL. IT's operational model uses SAML Enterprise Applications for external app integrations (see their existing Meraki and IT Asset Management configurations). The identity pattern (B2B Collaboration) remains unchanged — only the protocol layer shifts from OIDC to SAML. All architectural decisions and the B2B model still apply.

---

## 1. Requirement Restatement

### Raw Customer Signal

> USCAR wants their customers to be able to log into the application using their own company email addresses and enterprise credentials. They already do this in other applications for users from different companies such as @ford.com, @gm.com, and @stellantis.com.

### Decomposed Requirements

| # | Requirement | Category |
|---|-------------|----------|
| R1 | Users log in with their **corporate email** (@ford.com, @gm.com, @stellantis.com) | Authentication |
| R2 | Users authenticate with their **enterprise credentials** (corporate password, MFA) | Authentication |
| R3 | USCAR already supports this pattern in **other applications** | Architecture constraint |
| R4 | Users from **multiple different companies** must be supported | Multi-org |
| R5 | USCAR is the **hosting/managing organization** | Tenant model |

### What This Is NOT

- **Not single-org SSO.** This is not "connect USCAR employees to USCAR's Entra ID." It is "connect employees of USCAR's *customer companies* via their own identity providers."
- **Not self-service registration.** Users don't create their own accounts — USCAR controls who has access.
- **Not social login.** This is enterprise B2B identity, not Google/GitHub/Facebook consumer login.

---

## 2. Current System Analysis

### Authentication Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  User App   │     │ Admin Panel │     │  API Layer  │
│  (Port 5000)│     │ (Port 5111) │     │ (Port 5002) │
│             │     │             │     │             │
│ Flask       │     │ Flask-Login │     │ JWT Auth    │
│ Session     │     │ Session     │     │ (PyJWT)     │
│ + JWT proxy │     │ + werkzeug  │     │             │
│  → API      │     │ direct DB   │     │ direct DB   │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┴───────────────────┘
                           │
                    ┌──────┴──────┐
                    │  PostgreSQL │
                    │  (users)    │
                    └─────────────┘
```

**Current login flows:**

| App | Auth Method | Session | Password Verification |
|-----|-------------|---------|----------------------|
| User App | POST `/api/auth/login` → JWT stored in Flask session | Flask session (`auth_token`) | werkzeug `check_password_hash` (via API) |
| Admin Panel | POST `/login` → Flask-Login session | Flask-Login (server-side) | werkzeug `check_password_hash` (direct DB) |
| API | Bearer JWT in `Authorization` header | Stateless JWT | werkzeug `check_password_hash` |

**User provisioning:** Admin-only. Users are created via:
- Admin Panel → `/user/new` (form + welcome email)
- Admin Panel → `/users/import` (bulk JSON/Excel upload)
- API → `/api/auth/register` (exists but creates inactive users pending approval)

**Authorization model:**
- System permissions: `GOD`, `RFPO_ADMIN`, `RFPO_USER`, `VROOM_ADMIN`, `CAL_MEET_USER` (JSON array on User)
- Team membership: `UserTeam` junction table + JSON arrays on Team/Consortium for viewer/admin lists
- Company identity: `company_code` (e.g., "FORD", "GM") and `company` (full name) — already on User model

### Identity-Relevant Fields on User Model

| Field | Type | Purpose | SSO Relevance |
|-------|------|---------|---------------|
| `email` | String(255), unique | Primary login key | **Match key** — link external identity to local user |
| `password_hash` | String(255) | werkzeug hash | Nullable for SSO-only users |
| `company_code` | String(10) | Company abbreviation | Maps to external org (FORD, GM, STEL) |
| `company` | String(100) | Company full name | Display / audit |
| `active` | Boolean | Account enabled | Gate for SSO users too |
| `permissions` | Text (JSON) | System role array | Must still be assigned by USCAR admin |
| `record_id` | String(32), unique | External user ID | Could store Entra OID |

### What Exists Today That Helps

1. **`company_code` / `company`** — natural organization discriminator, already populated
2. **`email` as unique key** — stable match point between Entra ID UPN and local user
3. **Permissions are decoupled from login** — adding a new auth method doesn't require rethinking authorization
4. **Admin-controlled provisioning** — fits B2B model where access is invitation-based
5. **API already issues JWTs** — external auth can produce the same JWT, making downstream code unaware of auth method

### What's Missing

1. No OIDC/SAML library (msal, authlib, python-jose, etc.)
2. No external identity provider configuration
3. No "Sign in with Microsoft" UI flow
4. No way to mark a user as "SSO-only" vs. "password" vs. "both"
5. No session management for OIDC tokens (access_token, refresh_token, id_token)
6. No JIT (just-in-time) provisioning logic
7. No organization allowlist / guest policy enforcement

---

## 3. Identity Pattern Evaluation

### Pattern Analysis

| Pattern | Description | Fits? | Why / Why Not |
|---------|-------------|-------|---------------|
| **Single-tenant SSO** | One org's IdP authenticates one org's users | **No** | Multiple external orgs, not just USCAR |
| **Multi-tenant OIDC app** | App registration accepts sign-ins from any Entra ID tenant | **Partial** | Technically works but needs allowlisting — don't want *any* tenant |
| **Entra External ID (B2B)** | USCAR invites external users as guests in their tenant; guests auth via home tenant | **Yes** | Matches described pattern exactly. USCAR controls access, users use home credentials |
| **Entra External ID (B2C)** | Consumer identity store with custom policies | **No** | B2C is for consumer apps, not enterprise B2B |
| **SAML Federation** | Each org has a bilateral SAML trust | **Possible but heavyweight** | Would work for Ford/GM/Stellantis but operationally expensive per-org setup |
| **Direct Federation (custom IdP per org)** | RFPO app trusts each org's IdP individually | **No** | Doesn't scale, USCAR doesn't control it, no standard pattern |

### Verdict: Entra External ID (B2B Collaboration)

**This is the correct pattern** for several reasons:

1. **USCAR already does this** — "They already do this in other applications for users from different companies." This almost certainly means USCAR's Entra ID tenant has B2B guest policies configured and their other apps use the same model.
2. **USCAR controls the guest list** — B2B means USCAR invites specific users (or allows specific domains). The external user authenticates against their *home* tenant (ford.com, gm.com) but appears as a guest in USCAR's tenant.
3. **No per-org configuration in RFPO** — the app trusts USCAR's tenant. USCAR's tenant trusts the external orgs. RFPO doesn't need to know about Ford's IdP separately.
4. **Standard Microsoft pattern** — Ford, GM, and Stellantis all use Microsoft Entra ID. B2B collaboration is the default cross-org pattern.

### How B2B Works at the Protocol Level

```
User (@ford.com)           USCAR Entra ID Tenant         RFPO Application
       │                          │                            │
       │  1. Click "Sign in       │                            │
       │     with Microsoft"      │                            │
       │ ─────────────────────────┼───────────────────────────>│
       │                          │   2. Redirect to           │
       │                          │      /authorize            │
       │ <────────────────────────┼────────────────────────────│
       │                          │                            │
       │  3. USCAR tenant sees    │                            │
       │     @ford.com → redirect │                            │
       │     to Ford's IdP        │                            │
       │ <────────────────────────│                            │
       │                          │                            │
       │  4. User authenticates   │                            │
       │     at Ford (password,   │                            │
       │     MFA, etc.)           │                            │
       │ ─────────────────────────>                            │
       │                          │                            │
       │  5. Ford issues token    │                            │
       │     to USCAR tenant      │                            │
       │                          │  6. USCAR issues id_token  │
       │                          │     with guest claims       │
       │                          │ ──────────────────────────>│
       │                          │                            │
       │                          │  7. RFPO validates token,  │
       │                          │     matches User by email, │
       │                          │     issues JWT             │
       │ <────────────────────────┼────────────────────────────│
       │                          │                            │
       │  8. User is logged in    │                            │
```

---

## 4. Options Analysis

### Option A: Multi-Tenant App Registration (Direct)

Register the RFPO app directly in Entra ID as a multi-tenant app. Each org (Ford, GM, Stellantis) consents to the app in their tenant. RFPO app validates tokens from any consented tenant.

**Pros:**
- No dependency on USCAR's Entra ID tenant policies
- Each org manages their own consent
- Simpler token validation (app trusts multiple issuers)

**Cons:**
- USCAR loses control — any org that consents gets access
- Requires per-org app consent (Ford IT, GM IT must each approve)
- Domain allowlisting must be enforced in application code
- Doesn't match USCAR's existing B2B pattern
- RFPO engineering must manage the app registration themselves

**Verdict:** Technically viable but politically and operationally misaligned.

### Option B: Entra External ID (B2B) via USCAR Tenant (Recommended)

Register RFPO as a single-tenant app in USCAR's Entra ID. USCAR invites external users as B2B guests. RFPO app trusts only USCAR's tenant. External users authenticate via their home IdP, redirected automatically by USCAR's tenant.

**Pros:**
- **Matches USCAR's existing pattern** for other applications
- USCAR controls the guest list (invitation-based or domain allowlist)
- Single issuer to trust (USCAR's tenant) — simplest token validation
- External users use their home credentials (Ford password + MFA)
- USCAR IT already has operational knowledge of this model
- Admin portal retains full control over RFPO permissions
- Guest policies, conditional access, and MFA are USCAR-managed

**Cons:**
- Dependency on USCAR IT to manage guest invitations and policies
- USCAR needs an Entra ID P1/P2 license for conditional access on guests (may already have)
- Guest user objects consume directory quota (typically not an issue)
- Requires USCAR IT to register the app or grant admin consent

**Verdict: Recommended.** Aligns with stated requirements, leverages existing patterns, minimizes app-side complexity.

### Option C: SAML 2.0 Federation (Per-Org)

Configure RFPO as a SAML Service Provider. Establish bilateral SAML trusts with each external org's IdP.

**Pros:**
- Works with non-Microsoft IdPs (if any org uses Okta, Ping, etc.)
- Well-understood enterprise pattern

**Cons:**
- Requires per-org metadata exchange and certificate management
- Operationally expensive as orgs are added
- SAML is heavier than OIDC for web apps
- Doesn't match USCAR's existing pattern (they use Entra ID)
- Certificate rotation across multiple orgs is an operational burden

**Verdict:** Overkill given all listed orgs use Microsoft Entra ID.

### Option D: Hybrid (B2B + Password Fallback)

Option B, but with the existing password login preserved as a fallback for users who cannot authenticate via their home organization (contractors, consultants, non-Entra orgs).

**Pros:**
- Covers edge cases (independent consultants, orgs without Entra ID)
- Graceful migration — existing users keep working during rollout
- Allows USCAR to onboard orgs incrementally

**Cons:**
- Two auth paths to maintain
- Must be clear which users use which method (or allow both)
- Password-based users still have deliverability/onboarding friction

**Verdict: This is the practical implementation of Option B.** No production system should hard-cut to SSO-only without a transition period and fallback.

### Recommendation

**Implement Option D (B2B + Password Fallback)** — which is Option B with a password fallback. Register a single-tenant OIDC app in USCAR's Entra ID, implement "Sign in with Microsoft" alongside the existing login form, and map Entra ID users to local User records by email.

---

## 5. Required Decisions

Each decision below must be resolved before implementation can proceed. They are ordered by dependency — later decisions depend on earlier ones.

### Decision 1: Entra ID Tenant and App Registration Ownership

**Question:** Who registers the RFPO application in Entra ID — USCAR IT or RFPO engineering?

**Options:**
- **(a) USCAR IT registers the app** in their tenant and provides client ID, tenant ID, and client secret to RFPO engineering.
- **(b) RFPO engineering gets delegated admin access** to register apps in USCAR's tenant.
- **(c) RFPO engineering registers in their own tenant** and USCAR configures cross-tenant trust.

**Recommendation:** (a) — USCAR IT registers. This is the standard B2B pattern and USCAR retains control.

**Downstream impacts:**
- Determines who manages client credential rotation
- Determines who configures redirect URIs when deployment URLs change
- Affects time-to-first-prototype (dependency on USCAR IT turnaround)

### Decision 2: Guest Provisioning Model

**Question:** How do external users get access — invitation-based, domain allowlist, or admin-provisioned?

**Options:**
- **(a) Explicit invitation** — USCAR admin invites each external user by email in Entra ID. First login creates guest object.
- **(b) Domain allowlist** — USCAR configures "allow @ford.com, @gm.com, @stellantis.com" in B2B collaboration settings. Any user from those domains can attempt sign-in.
- **(c) RFPO admin pre-creates user** in RFPO (existing flow), and the first Microsoft sign-in links to the existing record.

**Recommendation:** (c) with (b) as the Entra ID gate. RFPO admin creates the user record (setting permissions, team, company), USCAR allows the domain in B2B settings, and first Microsoft sign-in links the identities.

**Downstream impacts:**
- Determines whether JIT provisioning is needed (if (b), yes — unknown users may arrive)
- Determines whether RFPO admin must create users before they can log in
- Affects the "what happens if an unknown user signs in" UX flow

### Decision 3: Just-In-Time (JIT) Provisioning

**Question:** If a user from an allowed domain signs in via Microsoft but has no RFPO User record, what happens?

**Options:**
- **(a) Block — require pre-provisioning.** Show "Your account has not been set up. Contact your USCAR administrator."
- **(b) Auto-create with minimal permissions.** Create a User record from the id_token claims (email, name, company from domain), assign RFPO_USER, require admin to complete setup.
- **(c) Auto-create and request approval.** Like (b), but mark `active=False` and notify USCAR admin.

**Recommendation:** (a) for initial release — matches current admin-controlled provisioning model. Consider (b) or (c) as a Phase 2 enhancement.

**Downstream impacts:**
- If (a): No model changes needed for provisioning. Admin workflow unchanged.
- If (b) or (c): Need default permission assignment logic, automatic company_code derivation from email domain, and admin notification workflow.
- Affects how many users USCAR admin must manually create vs. auto-provisioned.

### Decision 4: Auth Method per User

**Question:** Should a user be allowed to use both Microsoft sign-in AND password? Or is it one or the other?

**Options:**
- **(a) SSO-only for federated users.** If a user's email domain is in the allowlist, they MUST use Microsoft sign-in. Password login is disabled for them.
- **(b) Both methods allowed.** Any user can use either method. Useful during transition.
- **(c) User chooses once.** First login method becomes the canonical one.

**Recommendation:** (b) during rollout, transitioning to (a) after validation period. This allows gradual migration and rollback if issues arise.

**Downstream impacts:**
- If (a): Need a field on User indicating auth method (`auth_method: 'password' | 'sso' | 'both'`). Password login must check this field and reject SSO-only users.
- If (b): No blocking field, but audit logging should track which method was used.
- Password hash becomes optional for SSO-only users (migration consideration).

### Decision 5: Admin Panel Access

**Question:** Should the admin panel also support Microsoft sign-in, or remain password-only?

**Options:**
- **(a) Microsoft sign-in for both User App and Admin Panel.**
- **(b) Microsoft sign-in for User App only; Admin Panel remains password-only.**

**Recommendation:** (a) — both apps. If USCAR admins are also external users (or USCAR employees using Entra ID), they'll expect the same experience. The admin panel already gates on `is_rfpo_admin()` / `is_super_admin()` — adding Microsoft sign-in doesn't change the authorization check.

**Downstream impacts:**
- If (a): Need OIDC flow in custom_admin.py (Flask-Login integration with MSAL). Two redirect URIs.
- If (b): No admin panel changes. Limits who can administer via admin panel to password-based users.

### Decision 6: Redirect URIs and Deployment Environment

**Question:** What are the production redirect URIs for the OIDC callback?

This depends on the deployment topology:

| App | Local Dev URI | Azure Production URI |
|-----|---------------|---------------------|
| User App | `http://localhost:5000/auth/callback` | `https://rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io/auth/callback` |
| Admin Panel | `http://localhost:5111/auth/callback` | `https://rfpo-admin.livelyforest-d06a98a0.eastus.azurecontainerapps.io/auth/callback` |

**Note:** All redirect URIs must be registered in the app registration. HTTPS is required for production (Azure Container Apps provides this). HTTP is allowed for `localhost` only.

**Downstream impacts:**
- Number of redirect URIs affects app registration configuration
- Custom domain changes require URI updates in Entra ID

### Decision 7: Permission Mapping from Entra ID

**Question:** Should Entra ID group memberships automatically map to RFPO permissions?

**Options:**
- **(a) No mapping — RFPO admin assigns permissions manually** (current model).
- **(b) Entra ID group → RFPO permission mapping.** e.g., Entra group "RFPO-Admins" → `RFPO_ADMIN` permission.
- **(c) Hybrid — Entra groups set baseline, RFPO admin can override.**

**Recommendation:** (a) for Phase 1. The current permission model (6 permission strings, team-level roles) is too app-specific to map cleanly from Entra ID groups. Phase 2 can explore (c) once the group structure is understood.

**Downstream impacts:**
- If (b) or (c): Need to request `GroupMember.Read.All` or `groups` claim in the token. Need mapping table and conflict resolution logic.
- If (a): No additional API permissions needed. Simplest implementation.

### Decision 8: Session Lifetime and Token Refresh

**Question:** How long should an SSO session last, and should the app use refresh tokens?

**Options:**
- **(a) Match current JWT lifetime** (24 hours standard, 30 days with "remember me").
- **(b) Align with Entra ID session policy** (typically 1 hour access token, refresh token for re-auth).
- **(c) Issue long-lived RFPO JWT after OIDC auth**, ignoring Entra ID token expiry.

**Recommendation:** (c) — After validating the OIDC id_token, issue a standard RFPO JWT with the existing lifetime policy. This keeps the API layer unchanged and avoids coupling API authorization to Entra ID token refresh.

**Downstream impacts:**
- If (c): API layer requires zero changes. User/Admin apps handle OIDC flow and then issue the same JWT.
- No refresh token storage needed on the app side.
- Tradeoff: If a user is disabled in Entra ID, their RFPO JWT remains valid until expiry. Mitigated by admin deactivating the user in RFPO as well.

---

## 6. Decision Impact Review

### Cross-Cutting Concerns

| Concern | Affected Decisions | Resolution |
|---------|--------------------|------------|
| **User deactivation timing** | D3, D4, D8 | If an employee leaves Ford, their Entra ID is disabled (by Ford IT), but their RFPO JWT may still be valid. Mitigated by: (1) Reasonable JWT expiry (24h), (2) Admin can deactivate user in RFPO. No real-time revocation in current architecture — acceptable for this app class. |
| **Email domain → company mapping** | D2, D3 | If JIT provisioning is implemented (Phase 2), need a table mapping email domains to company_code. e.g., `@ford.com → FORD, @gm.com → GM`. Not needed for Phase 1 if admin pre-creates users. |
| **Existing user migration** | D4 | Existing users with @ford.com, @gm.com emails will be able to use "Sign in with Microsoft" if their email matches. No migration script needed — just ensure email uniqueness and matching. |
| **Password hash for SSO users** | D3, D4 | If admin pre-creates users with a temp password, they can migrate to SSO later. If JIT-provisioned, users never have a password — `password_hash` must be nullable or set to a sentinel. Current schema: `nullable=False` — **schema change needed**. |
| **CSRF and SSO callback** | Security | The SAML ACS endpoint must validate `InResponseTo` (matches the original AuthnRequest ID) and verify the XML signature. `python3-saml` handles both. The ACS endpoint only accepts POST requests with valid signed assertions — CSRF is mitigated by the assertion signature and `InResponseTo` binding. |

### Follow-On Decisions (Discovered During Review)

| # | Decision | Triggered By | When Needed |
|---|----------|-------------|-------------|
| F1 | **Custom domain for RFPO?** | D6 (redirect URIs) | Before go-live. If USCAR wants `rfpo.uscar.org` instead of the Azure Container Apps URL, redirect URIs change. |
| F2 | **Which Entra ID API permissions?** | D7 (group mapping) | During app registration. Minimum: `openid`, `profile`, `email`. If group mapping: add `GroupMember.Read.All`. |
| F3 | **Client credential type?** | D1 (app registration) | During app registration. Client secret (simpler) vs. certificate (more secure, rotates differently). |
| F4 | **Conditional Access policies for guests?** | D2 (provisioning) | Before go-live. Should USCAR require MFA for all external guests? Require compliant devices? This is USCAR IT's decision, not ours. |
| F5 | **`password_hash` nullable migration** | D3, D4 | Before Phase 2 (JIT provisioning) or when SSO-only users exist. ALTER TABLE to make nullable. |
| F6 | **Entra ID object ID storage** | D2, D3 | Phase 1 implementation. Store `oid` claim from id_token on User for stable identity matching (email can change, OID cannot). |

---

## 7. IT Stakeholder Input — Decisions Resolved

*Updated 2026-04-01 after receiving SAML configuration examples and process details from IT.*

### What IT Communicated

1. **Protocol:** IT uses **SAML 2.0 Enterprise Applications** in Entra ID for external app integrations (not OIDC app registrations). Reference configurations provided for LandX Motors Meraki and LandX IT Asset Management System.
2. **External user process:** Invite user as B2B guest into Entra ID → Add guest account to a security group → Assign the group to the Enterprise Application with an App Role → User authenticates via SAML.
3. **Role claim:** IT will use `user.assignedroles` to pass App Roles to the application. This claim carries the Entra ID App Roles assigned to the user (either directly or via group membership).
4. **IT needs from engineering:** Entity ID, Reply URL (ACS), Sign on URL, Logout URL, and any custom claim URLs the application requires.

### Decision Resolution Summary

| Decision | Original Recommendation | Resolved As | Evidence |
|----------|------------------------|-------------|----------|
| **D1: App Registration** | (a) USCAR IT registers | **Confirmed (a)** — IT is requesting our SAML endpoints to configure. | IT asked for Entity ID and URLs |
| **D2: Guest Provisioning** | (c) Admin pre-creates + domain allowlist | **Confirmed** — "inviting the user as a guest...adding the guest account to the required group" | IT's stated process |
| **D3: JIT Provisioning** | (a) Block — require pre-provisioning | **Confirmed (a)** — Admin creates RFPO user first, IT invites as guest separately. **Owner confirmed 2026-04-02.** | Matches invitation-based model |
| **D4: Auth Method** | (b) Both methods allowed during rollout | **Confirmed (b)** — Password fallback preserved. SSO users can also use password if pre-created with one. **Owner confirmed 2026-04-02.** | Hybrid approach per Option D |
| **D5: Admin Panel** | (a) Both apps support SSO | **Confirmed: Phase 1 User App only.** Admin panel remains password-only initially. **Owner confirmed 2026-04-02.** | Simpler rollout; admin users are internal |
| **D6: Redirect URIs** | Azure Container Apps URLs | **Confirmed** — see SAML configuration table below | Known deployment URLs |
| **D7: Permission Mapping** | (a) No mapping — manual assignment | **Updated to (b/c hybrid** — `user.assignedroles` carries App Roles from Entra ID. RFPO maps these to permissions. Admin can still override. **Owner confirmed 2026-04-02.** | IT's explicit requirement to use `user.assignedroles` |
| **D8: Session Lifetime** | (c) Issue RFPO JWT after auth | **Confirmed (c)** — After validating SAML assertion, issue standard RFPO JWT. API layer unchanged. | Same principle regardless of SAML vs OIDC |

### Protocol Change: OIDC → SAML

The original plan recommended OIDC via MSAL. IT operates with SAML Enterprise Applications. This changes:

| Aspect | Original (OIDC) | Updated (SAML) |
|--------|-----------------|----------------|
| **Protocol** | OpenID Connect | SAML 2.0 |
| **Python library** | `msal>=1.28.0` | `python3-saml>=1.16.0` |
| **Auth initiation** | Redirect to `/authorize` endpoint | SP-initiated SAML AuthnRequest |
| **Callback endpoint** | `/auth/callback` (authorization code exchange) | `/saml/acs` (Assertion Consumer Service) |
| **Logout** | Local session clear only | `/saml/sls` (Single Logout Service) |
| **Token format received** | JWT id_token + access_token | XML SAML Assertion |
| **User identity extraction** | JWT claims (`preferred_username`, `oid`, `email`) | SAML NameID + Attribute Statements |
| **CSRF protection** | `state` parameter (MSAL handles) | `RelayState` + `InResponseTo` validation (`python3-saml` handles) |
| **What RFPO issues after auth** | Same RFPO JWT (unchanged) | Same RFPO JWT (unchanged) |

**What does NOT change:** The identity pattern (B2B), the user matching logic (email → `entra_oid`), the JWT issuance, the API layer, the permission model, or the provisioning flow.

### SAML Configuration — Values for IT

#### Basic SAML Configuration (User App)

| Setting | Value |
|---------|-------|
| **Identifier (Entity ID)** | `https://rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io` |
| **Reply URL (Assertion Consumer Service URL)** | `https://rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io/saml/acs` |
| **Sign on URL** | `https://rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io/` |
| **Relay State (Optional)** | *(leave empty)* |
| **Logout URL (Optional)** | `https://rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io/saml/sls` |

#### Attributes & Claims — Required Claims

| Claim Name | Type | Source Attribute | Purpose |
|------------|------|------------------|---------|
| **Unique User Identifier (Name ID)** | SAML | `user.userprincipalname` | Primary identity — maps to `email` in RFPO User model |
| `https://rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io/saml/attributes/role` | SAML | `user.assignedroles` | App Roles — maps to RFPO permissions (`RFPO_USER`, `RFPO_ADMIN`) |

#### Attributes & Claims — Additional Claims (Standard)

| Claim Name | Type | Source Attribute | Purpose |
|------------|------|------------------|---------|
| `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress` | SAML | `user.mail` | Email address for matching |
| `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname` | SAML | `user.givenname` | First name for display |
| `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname` | SAML | `user.surname` | Last name for display |
| `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name` | SAML | `user.userprincipalname` | Full display name |

#### App Roles to Define (on the Enterprise Application)

These roles must be defined on the App Registration in Entra ID. IT assigns users/groups to these roles. The `user.assignedroles` claim carries the role `Value` to the application.

| Display Name | Value | Description | Assigned To |
|-------------|-------|-------------|-------------|
| RFPO User | `RFPO_USER` | Standard RFPO user — can view and create RFPOs | Users and/or Groups |
| RFPO Admin | `RFPO_ADMIN` | RFPO administrator — full CRUD operations | Users and/or Groups |

**Mapping logic in RFPO:** When a SAML assertion arrives with `user.assignedroles` containing `RFPO_ADMIN`, the application grants the user `RFPO_ADMIN` permission (plus inherits `RFPO_USER`). Admin can further elevate to `GOD` or assign additional permissions (`VROOM_ADMIN`, `CAL_MEET_USER`) within RFPO if needed.

### What IT Needs to Do

1. **Create Enterprise Application** in Entra ID → SAML-based Sign-on
2. **Configure Basic SAML** using the Entity ID, Reply URL, Sign on URL, and Logout URL above
3. **Configure Attributes & Claims** — add the custom role claim URL and keep standard additional claims
4. **Define App Roles** (`RFPO_USER`, `RFPO_ADMIN`) on the App Registration
5. **Create security group(s)** (e.g., "RFPO Users", "RFPO Admins") and assign to the Enterprise Application with appropriate App Roles
6. **Invite external users** as B2B guests and add them to the appropriate group(s)
7. **Provide to engineering:** IdP Entity ID, IdP SSO URL, IdP SLS URL, and the Base64 X.509 signing certificate (from the SAML Signing Certificate section of the Enterprise Application)

---

## 8. Detailed Implementation Plan

### Phase 1: Core SAML Integration

#### Prerequisites (USCAR IT — Before Engineering Starts)

- [ ] **USCAR IT:** Create SAML Enterprise Application in Entra ID using configuration values from Section 7
- [ ] **USCAR IT:** Configure Attributes & Claims (Name ID, role claim URL, standard claims)
- [ ] **USCAR IT:** Define App Roles (`RFPO_USER`, `RFPO_ADMIN`) on the App Registration
- [ ] **USCAR IT:** Create security group(s) and assign to the Enterprise Application with App Roles
- [ ] **USCAR IT:** Provide to engineering: IdP Entity ID, IdP SSO URL, IdP SLS URL, X.509 signing certificate (Base64)
- [ ] **USCAR IT:** Configure B2B collaboration settings → allow @ford.com, @gm.com, @stellantis.com domains
- [ ] **USCAR IT:** Invite at least one test guest user and assign to the RFPO group

#### Step 1: Dependencies and Configuration

**Add Python dependencies:**

```
# requirements.txt additions
python3-saml>=1.16.0
```

**Add environment variables (env.example):**

```bash
# SAML SSO Configuration
SAML_IDP_ENTITY_ID=              # From IT: Azure AD Identifier
SAML_IDP_SSO_URL=                # From IT: Login URL
SAML_IDP_SLS_URL=                # From IT: Logout URL
SAML_IDP_X509_CERT=              # From IT: Base64 signing certificate (single-line, no headers)
SAML_SP_ENTITY_ID=https://rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io
SAML_SP_ACS_URL=https://rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io/saml/acs
SAML_SP_SLS_URL=https://rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io/saml/sls
```

#### Step 2: SAML Authentication Module

Create `auth_saml.py` — a shared module used by both User App and Admin Panel:

**Responsibilities:**
- Configure `python3-saml` with SP and IdP settings (from env vars)
- Generate SAML AuthnRequest and redirect to IdP SSO URL
- Handle ACS callback (validate SAML Response, extract assertion attributes)
- Extract user identity from SAML assertion (NameID, email, name, roles)
- Match external identity to local User by email
- Map `user.assignedroles` claim values to RFPO permissions
- Issue RFPO JWT (same format as existing password-based login)
- Handle SLS (Single Logout Service) requests

**Key design decisions in code:**
- **Single module** shared by both Flask apps (imported, not duplicated)
- **`RelayState`** used for CSRF protection and post-login redirect (python3-saml handles validation)
- **SAML Response validation** includes signature verification against IdP X.509 certificate, audience restriction, and time window checks
- **Email matching** is case-insensitive (`User.query.filter(func.lower(User.email) == email.lower())`)
- **Role mapping:** assertion attribute `user.assignedroles` values (`RFPO_USER`, `RFPO_ADMIN`) mapped directly to RFPO permission strings
- **Token issuance** uses the same `jwt.encode()` call as existing `auth_routes.py`, ensuring downstream code is unaffected

#### Step 3: User App Integration

**New routes in `app.py`:**

| Route | Method | Purpose |
|-------|--------|---------|
| `/auth/login-microsoft` | GET | Redirect to Microsoft login (via MSAL) |
| `/auth/callback` | GET | OIDC callback — exchange code, match user, issue JWT, redirect to dashboard |

**Login page changes:**
- Add "Sign in with Microsoft" button alongside existing email/password form
- Button links to `/auth/login-microsoft`
- Existing form continues to work unchanged

**Callback flow:**
1. Validate `state` parameter (CSRF protection)
2. Exchange authorization code for tokens via MSAL
3. Extract `email` (preferred_username or email claim) from id_token
4. Query `User.query.filter_by(email=email, active=True).first()`
5. If found: issue JWT, store in session, redirect to dashboard
6. If not found: render error page — "Your account has not been set up. Contact your USCAR administrator."
7. Update `last_visit` timestamp

#### Step 4: Admin Panel Integration (Phase 2)

**Deferred to Phase 2.** Admin Panel remains password-only in Phase 1 per resolved Decision D5. When implemented:

**New routes in `custom_admin.py`:**

| Route | Method | Purpose |
|-------|--------|----------|
| `/saml/login` | GET | Generate SAML AuthnRequest, redirect to IdP SSO URL |
| `/saml/acs` | POST | Validate SAML Response, match user, Flask-Login login_user, redirect to dashboard |

**Callback flow:**
1. Same SAML validation as User App
2. After matching user, check `user.is_rfpo_admin()` or `user.is_super_admin()`
3. If admin: `login_user(user)`, redirect to dashboard
4. If not admin: flash error, redirect to login

**Note:** Admin Panel will need a separate Reply URL registered in the Enterprise Application: `https://rfpo-admin.livelyforest-d06a98a0.eastus.azurecontainerapps.io/saml/acs`

#### Step 5: Model Changes

**User model additions (`models.py`):**

```python
# New field on User model
entra_oid = db.Column(db.String(36), unique=True, nullable=True)  # Entra ID Object ID
auth_method = db.Column(db.String(20), default='password')  # 'password', 'sso', 'both'
```

**Migration:** `ALTER TABLE users ADD COLUMN entra_oid VARCHAR(36) UNIQUE;`
`ALTER TABLE users ADD COLUMN auth_method VARCHAR(20) DEFAULT 'password';`

**Note:** `password_hash` remains non-nullable in Phase 1. Admin pre-creates all users with temp passwords. SSO users can ignore the password.

#### Step 6: Security Hardening

- **SAML Response signature verification** against IdP X.509 certificate (`python3-saml` handles this)
- **Audience restriction validation** — verify assertion is intended for RFPO SP Entity ID
- **`InResponseTo` validation** — prevent assertion replay by matching to the original AuthnRequest ID
- **Time window validation** — reject assertions outside the `NotBefore`/`NotOnOrAfter` window
- **HTTPS enforcement** on ACS URL (Azure Container Apps provides TLS)
- **Issuer validation** — verify assertion issuer matches configured IdP Entity ID
- **Email domain validation** — optional secondary check that NameID domain is in allowed list
- **Rate limiting on ACS endpoint** — protect against assertion replay attempts
- **XML signature wrapping attack protection** — `python3-saml` validates against known XSW attack patterns

### Phase 2: Enhanced Provisioning (Sprint 4-5)

- JIT user provisioning from id_token claims
- Domain → company_code mapping table
- `password_hash` made nullable for SSO-only users
- Optional: Entra ID group → RFPO permission mapping
- Admin UI to view/manage SSO-linked users
- "Link Microsoft account" flow for existing password users

### Phase 3: SSO-Only Mode (Sprint 6+)

- Optional enforcement: SSO-required for specific domains
- Password login disabled for federated domains
- Entra ID conditional access integration recommendations for USCAR IT

---

## 9. Testing Strategy

### Unit Tests

| Test | Validates |
|------|-----------|
| `test_msal_auth_url_generation` | Authorization URL contains correct tenant, client_id, redirect_uri, scope, state |
| `test_callback_state_validation` | Callback rejects mismatched or missing state parameter |
| `test_email_matching_case_insensitive` | `John.Doe@Ford.com` matches `john.doe@ford.com` in User table |
| `test_unknown_user_rejected` | Callback with valid token but no matching User returns error |
| `test_inactive_user_rejected` | Callback with valid token for inactive User returns error |
| `test_jwt_issued_on_success` | Successful callback issues JWT with same structure as password login |
| `test_admin_panel_non_admin_rejected` | Admin callback rejects users without admin permissions |

### Integration Tests

| Test | Validates |
|------|-----------|
| `test_full_oidc_flow_mock` | MSAL mocked — full login→callback→JWT→dashboard flow |
| `test_password_login_still_works` | Existing password flow unaffected by SSO code |
| `test_both_auth_methods_same_user` | Same user can log in via either method, gets same JWT |
| `test_entra_oid_stored_on_first_sso_login` | First SSO login stores `entra_oid` on User record |

### Manual / QA Tests

| Test | Validates |
|------|-----------|
| End-to-end with real Entra ID test tenant | Full redirect flow, MFA prompt, token exchange |
| External user from @ford.com test account | B2B guest authentication via home tenant |
| Login from allowed domain (User App) | Correct redirect and JWT issuance |
| Login from allowed domain (Admin Panel) | Correct redirect, admin permission check |
| Login from disallowed domain | Error message, no User created |
| Existing user first-time SSO login | Matches by email, stores entra_oid |
| Session expiry and re-auth | JWT expires, user must re-authenticate |

---

## 10. Open Questions

| # | Question | Audience | Status |
|---|----------|----------|--------|
| Q1 | What is USCAR's Entra ID tenant ID? | USCAR IT | **Resolved** — IT will provide IdP Entity ID, SSO URL, SLS URL, and X.509 cert when Enterprise App is created |
| Q2 | Does USCAR already have B2B collaboration enabled with Ford, GM, Stellantis? | USCAR IT | **Partially resolved** — IT confirmed B2B guest invitation process. Domain allowlisting to be verified. |
| Q3 | Who is the USCAR IT contact for app registration and B2B configuration? | USCAR PM | **Resolved** — IT contact established (provided screenshots and process details) |
| Q4 | Are there users from organizations beyond Ford, GM, and Stellantis? | USCAR business | No — affects allowlist but doesn't block architecture |
| Q5 | Does USCAR want a custom domain (e.g., `rfpo.uscar.org`) for the application? | USCAR IT | No — but affects redirect URIs if yes |
| Q6 | Are there any compliance requirements (FedRAMP, ITAR, etc.) on the identity integration? | USCAR compliance | No — but could constrain data residency |
| Q7 | Does USCAR currently use Entra ID P1 or P2? | USCAR IT | No — affects conditional access options |
| Q8 | Should the sender address for account setup emails change from `rfpo@uscar.org` to something else for federated users? | USCAR business | No — email deliverability (Issue #1) is a parallel track |

---

## 11. Peer Review Findings

*The following review was conducted as a second-pass architectural challenge of this plan.*

### Challenge 1: Is B2B Really the Right Pattern?

**Challenge:** "You assumed Entra External ID B2B because USCAR 'does this in other applications.' But what if their other apps use a multi-tenant registration, not B2B guests?"

**Response:** The key distinguishing signal is *USCAR controls access*. In a multi-tenant app, each org independently consents. In B2B, USCAR manages the guest list. The customer requirement says USCAR wants *their* customers to access *their* application — this is B2B by definition. However, the implementation approach (MSAL + OIDC) works for both patterns with minimal code change: the difference is tenant ID configuration (`organizations` vs. specific tenant ID) and who does the app registration.

**Mitigation:** During the discovery conversation with USCAR IT, explicitly ask: "Is RFPO being registered in your Entra ID tenant, or should it trust multiple tenants independently?" This confirms the pattern before coding.

### Challenge 2: Email Matching is Fragile

**Challenge:** "Email addresses change. Marriages, corporate rebranding, M&A. Matching by email is a foot-gun."

**Response:** Valid concern. Entra ID provides a stable `oid` (Object ID) claim — a GUID that never changes for a given user in a given tenant. The plan stores `entra_oid` on the User model. The matching logic should be:

1. First, try matching by `entra_oid` (if the user has logged in via SSO before).
2. Fall back to email matching (for first-time SSO login).
3. On successful first-time match, store the `entra_oid` for future stable matching.

This is already captured in Step 5 but worth emphasizing: **`entra_oid` is the primary match key after first login. Email is only the bootstrap key.**

### Challenge 3: What About the API Layer?

**Challenge:** "The API layer uses JWT with its own secret. How does SSO affect API consumers? What if someone calls the API directly?"

**Response:** SSO does not change the API layer at all. The OIDC flow happens in User App / Admin Panel, which then issue a standard RFPO JWT (same signing key, same claims). The API sees the same Bearer token regardless of whether the user authenticated via password or Microsoft. This is by design (Decision 8).

External API consumers (if any) would continue using the existing `/api/auth/login` password-based flow. If API-level SSO is needed in the future, that's a separate concern (OAuth2 client_credentials or on-behalf-of flow).

### Challenge 4: Secret Management

**Challenge:** "The plan adds ENTRA_CLIENT_SECRET as an env var. Client secrets in env vars are a security concern."

**Response:** The current system already manages `JWT_SECRET_KEY`, `ACS_CONNECTION_STRING`, `ADMIN_SECRET_KEY`, and database credentials as env vars via `.env` and Container Apps secrets. The SAML integration adds the IdP X.509 certificate and URLs (no client secret needed — SAML uses certificate-based trust, not shared secrets). For a tighter approach, use Azure Key Vault and Managed Identity — but that's an infrastructure improvement that benefits ALL secrets, not just this one.

**Recommendation:** Note as a Phase 2 improvement to move all secrets to Key Vault. Not a blocker for SSO.

### Challenge 5: Race Condition on First Login

**Challenge:** "If two SSO logins for the same user happen simultaneously (e.g., two browser tabs), both try to store `entra_oid`. One will fail with a unique constraint violation."

**Response:** Edge case but real. Mitigate with:
1. Use `INSERT ... ON CONFLICT` / upsert semantics when writing `entra_oid`
2. Or wrap the `entra_oid` assignment in a try/except for IntegrityError and retry the lookup

This is a standard concurrent-write pattern and should be handled in the implementation.

### Challenge 6: Logout Behavior

**Challenge:** "If a user signs in via Microsoft and then clicks 'logout' in RFPO, should they be signed out of Microsoft too? Or just RFPO?"

**Response:** **RFPO-only logout** — clear the local session/JWT. Do NOT redirect to Microsoft's logout endpoint. Signing out of Microsoft has implications beyond RFPO (signs them out of Outlook, Teams, etc.). This matches how most B2B apps behave.

Document this as a known design decision. If USCAR explicitly requests "full federation logout," that's a Phase 3 feature requiring front-channel or back-channel logout support.

---

## 12. Final Recommendation

### Pattern

**Entra External ID (B2B Collaboration)** with **SAML 2.0 protocol** and **password fallback**.

### Implementation Summary

| Component | Change Required |
|-----------|----------------|
| **User App (app.py)** | Add `/saml/login`, `/saml/acs`, `/saml/sls`, `/saml/metadata` routes. Add "Sign in with Microsoft" button on login page. |
| **Admin Panel (custom_admin.py)** | **Phase 2.** No changes in Phase 1. |
| **API Layer (api/)** | **No changes.** JWT format unchanged. |
| **Models (models.py)** | Add `entra_oid` (String, unique, nullable) and `auth_method` (String, default 'password'). |
| **Database** | Two ALTER TABLE statements. No data migration needed. |
| **New module (auth_saml.py)** | Shared SAML wrapper — SP/IdP config, AuthnRequest generation, ACS handling, user matching, role mapping, JWT issuance. |
| **Dependencies** | Add `python3-saml>=1.16.0` to requirements.txt. |
| **Configuration** | Add 7 SAML env vars (4 from IT, 3 SP self-configured). |
| **Templates** | Update login.html with Microsoft sign-in button. |
| **USCAR IT** | Create SAML Enterprise App, configure claims/roles, provide IdP metadata to engineering. |

### Next Steps

1. **Send this document to USCAR PM** for review of Decisions 1-8 and Open Questions Q1-Q8.
2. **Schedule discovery call with USCAR IT** to confirm tenant details, B2B configuration, and app registration ownership.
3. **Resolve blocking decisions** (D1, D2, D3) before Sprint 3 planning.
4. **Prototype** MSAL flow with USCAR's dev/test tenant during Sprint 2 discovery spike.
5. **Implement Phase 1** in Sprint 3 after prerequisites are met.

### Risk Summary

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| USCAR IT delays app registration | Medium | Blocks Phase 1 | Start discovery now; provide prerequisites list upfront |
| External org (Ford, GM) blocks B2B guest access | Low | Blocks specific org | USCAR likely already has this configured; verify early |
| Email mismatch between RFPO User and Entra ID | Low | Login fails for individual users | Admin tooling to update email; `entra_oid` fallback after first match |
| Existing security issues (#3, #4, CSRF) interact with SSO | Medium | Privilege escalation via SSO-authenticated session | Fix security issues (Sprint 1) before shipping SSO (Sprint 3) |
| USCAR's other apps use a different pattern than assumed | Low | Architecture rework | Confirm pattern in discovery call before implementation |

---

*End of document. Ready for stakeholder review and decision-making.*
