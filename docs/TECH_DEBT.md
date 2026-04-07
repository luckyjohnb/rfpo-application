# Technical Debt Tracker

## TD-001: Migrate Admin Panel from Direct DB Access to API Calls

**Priority:** High
**Status:** Not Started
**Identified:** 2026-04-06

### Problem

The admin panel (`custom_admin.py`) has ~100 routes that access the database directly via SQLAlchemy instead of going through the API layer. This violates the intended architecture where only `simple_api.py` and `api/` should have direct DB access.

### Current State

| Component | Direct DB Access | Correct? |
|---|---|---|
| User App (`app.py`) | None — uses `make_api_request()` | ✅ |
| API Layer (`simple_api.py`, `api/`) | Yes | ✅ Expected |
| Admin Panel (`custom_admin.py`) | ~100 routes | ❌ |
| Email Service (`email_service.py`) | 1 cached read | ⚠️ Minor |
| PDF Generator (`pdf_generator.py`) | 2 read-only queries | ⚠️ Minor |

### Affected Admin Routes by Entity

- **Users & Permissions** — 6 routes (list, create, edit, delete, export, import)
- **Consortiums** — 7 routes (list, create, edit, delete, export, import, file uploads)
- **Teams** — 7 routes (list, create, edit, delete, export, import)
- **Projects** — 7 routes (list, create, edit, delete, export, import)
- **Vendors** — 7 routes (list, create, edit, delete, export, import)
- **RFPOs** — 15+ routes (list, create stages, edit, delete, line items, files, PDFs)
- **Approval Workflows** — 12+ routes (list, create, edit, delete, stages, steps, instances)
- **Dashboard** — 1 route (aggregate counts across all models)
- **Configuration/Tools** — 3 routes (email test, health, API test)

### Migration Plan

1. Create ~24 new admin API endpoints in `api/admin_routes.py` (full CRUD for each entity plus file uploads, imports, exports)
2. Add an `admin_make_api_request()` helper to `custom_admin.py` (similar to `app.py`'s `make_api_request()`)
3. Rewrite each admin route to call the API instead of `db.session` directly
4. Migrate `email_service.py` config read and `pdf_generator.py` queries to API calls
5. Remove SQLAlchemy model imports from admin panel

### Recommended Phased Approach

| Phase | Entity Group | Routes | New API Endpoints |
|---|---|---|---|
| 1 | Users & Permissions | 6 | 5 (list, create, update, delete, permissions) |
| 2 | Consortiums | 7 | 5 (list, create, update, delete, logo/terms upload) |
| 3 | Teams | 7 | 4 (list, create, update, delete) |
| 4 | Projects | 7 | 4 (list, create, update, delete) |
| 5 | Vendors | 7 | 4 (list, create, update, delete) |
| 6 | RFPOs | 15+ | Mostly covered — wire admin to existing API |
| 7 | Approval Workflows | 12+ | 6 (CRUD, activate, instances) |
| 8 | Dashboard & Tools | 4 | 2 (dashboard stats, email settings) |
| 9 | Imports/Exports | 10 | 10 (bulk import/export per entity) |

### Auth Strategy: Pass-through JWT (Decided 2026-04-06)

**Decision:** Option B — forward the logged-in admin user's JWT to the API on every request.

**Rationale:**
- User app already uses this exact pattern (`make_api_request()` + `session['auth_token']`)
- API already has JWT auth, permission checks (`GOD`, `RFPO_ADMIN`), and per-user audit logging
- Login endpoints already exist (`/api/auth/login`, `/api/auth/saml-match`)
- No new auth mechanisms needed — reuse what's there

**Implementation:**
1. On admin login success, also call `/api/auth/login` to obtain a JWT, store in `session['auth_token']`
2. Add `admin_make_api_request()` helper (same pattern as `app.py`'s `make_api_request()`)
3. Keep Flask-Login session for template rendering (current user context), but route all data operations through the API

**Rejected alternatives:**
- Service token: loses per-user audit trail, single point of compromise, API can't enforce per-user permissions
- Service token + user header: API must blindly trust a header — leaked token allows impersonation of any admin
