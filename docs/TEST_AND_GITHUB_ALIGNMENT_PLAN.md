# RFPO Application — Test Strategy & GitHub Alignment Plan

> **Status:** Draft — Reviewed & approved by DevOps/QA architect agent. Ready for implementation.
> **Date:** April 7, 2026

---

## Part 1: Test Strategy

### Current State
- **51 API endpoints**, **110 admin routes**, **59 user app routes** — ~220 total
- **21 SQLAlchemy models** with complex relationships
- **CI runs only 2 test files** (test_models_typed.py, test_email_retry.py)
- **No conftest.py**, no pytest.ini, no coverage config
- **~90 test files in tests/** — mostly one-off Selenium/positioning scripts, not CI-ready
- **Deploy pipeline has NO test gate** — pushes directly to production

### Testing Pyramid (What We Need)

```
              /‾‾‾‾‾‾‾‾‾‾‾‾‾\
             / E2E / Smoke    \     ← Post-deploy health checks (5 tests)
            /   (Azure live)   \
           /‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾\
          / Integration Tests     \   ← API endpoint + DB round-trips (60 tests)
         /   (pytest + test DB)    \
        /‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾\
       /     Unit Tests              \  ← Models, services, utils (80 tests)
      /   (pytest, mocked deps)       \
     /‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾\
    /        Static Analysis             \  ← Linting, type checks (existing)
   /   (black, flake8, bandit)            \
  ‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾
```

### Test Suite Organization

```
tests/
├── conftest.py                    # Shared fixtures (app, db, client, auth)
├── pytest.ini                     # (or pyproject.toml [tool.pytest])
│
├── unit/                          # Fast, no DB, mocked dependencies
│   ├── test_models.py             # Model to_dict(), get/set JSON fields, permissions
│   ├── test_email_service.py      # Email retry, queue, diagnostics (mock SMTP)
│   ├── test_pdf_generator.py      # PDF overlay logic (mock file I/O)
│   ├── test_utils.py              # generate_next_id, format_response, validators
│   ├── test_env_config.py         # Config validation, URL parsing
│   ├── test_exceptions.py         # Exception hierarchy, payload handling
│   └── test_error_handlers.py     # Error handler registration, response format
│
├── integration/                   # SQLite in-memory DB, real Flask test client
│   ├── test_api_auth.py           # Login, JWT token, token refresh, invalid creds
│   ├── test_api_consortiums.py    # GET/POST consortiums, uniqueness, validation
│   ├── test_api_projects.py       # GET/POST projects, ref format, consortium link
│   ├── test_api_teams.py          # GET/POST teams, abbrev validation
│   ├── test_api_vendors.py        # GET/POST vendors, vendor sites
│   ├── test_api_rfpos.py          # CRUD lifecycle, line items, totals, soft delete
│   ├── test_api_approvals.py      # Workflow create, stage progression, actions
│   ├── test_api_notifications.py  # List, mark read, count
│   ├── test_api_users.py          # Profile, permissions, bulk operations
│   ├── test_api_files.py          # Upload, download, delete
│   ├── test_admin_auth.py         # Admin login, session, flask-login
│   └── test_admin_crud.py         # Admin entity CRUD (consortium, team, project, etc.)
│
├── smoke/                         # Post-deploy verification (runs against live URLs)
│   └── test_health_checks.py      # /api/health, login page loads, admin loads
│
└── _legacy/                       # Existing test files (moved, not deleted)
    └── (all 90 current test files)
```

### Test Fixture Design (conftest.py)

```python
# Key fixtures:
# - app: Flask test app with SQLite :memory:
# - db: Fresh database per test (create_all/drop_all)
# - db_transaction: Autouse fixture — wraps each test in a transaction + rollback
# - api_client: Flask test client for simple_api.py
# - admin_client: Flask test client for custom_admin.py
# - user_client: Flask test client for app.py
# - auth_headers: JWT token for authenticated API requests
# - expired_auth_headers: Expired JWT for testing token expiration
# - admin_user: Pre-created admin user (GOD permission)
# - regular_user: Pre-created regular user (RFPO_USER)
# - sample_consortium: Pre-created consortium
# - sample_project: Pre-created project linked to consortium
# - sample_team: Pre-created team
# - sample_vendor: Pre-created vendor
# - sample_rfpo: Pre-created RFPO with line items
# - mock_email_service: Patched email service (no real SMTP)
# - app_context: Explicit app context for tests that need it
```

### Selective Test Execution (Only Test What Changed)

**pytest markers for targeted runs:**
```ini
[tool:pytest]
markers =
    unit: Fast unit tests (no DB)
    integration: Tests with database
    api: API endpoint tests
    admin: Admin panel tests
    auth: Authentication tests
    models: Model tests
    email: Email service tests
    pdf: PDF generation tests
    approval: Approval workflow tests
    smoke: Post-deploy smoke tests
```

**CI optimization — run tests based on changed files:**
```yaml
# In ci.yml — detect what changed, run minimal test set
- name: Detect changes
  id: changes
  uses: dorny/paths-filter@v2
  with:
    filters: |
      models:
        - 'models.py'
      api:
        - 'simple_api.py'
        - 'api/**'
      admin:
        - 'custom_admin.py'
        - 'templates/admin/**'
        - 'api/**'
      user_app:
        - 'app.py'
        - 'templates/app/**'
        - 'api/**'
      email:
        - 'email_service.py'
      pdf:
        - 'pdf_generator.py'
      config:
        - 'env_config.py'
        - 'config.py'
        - 'requirements*.txt'

- name: Run affected tests
  run: |
    MARKERS=""
    if [ "${{ steps.changes.outputs.models }}" = "true" ]; then MARKERS="$MARKERS or models"; fi
    if [ "${{ steps.changes.outputs.api }}" = "true" ]; then MARKERS="$MARKERS or api"; fi
    if [ "${{ steps.changes.outputs.admin }}" = "true" ]; then MARKERS="$MARKERS or admin"; fi
    if [ "${{ steps.changes.outputs.email }}" = "true" ]; then MARKERS="$MARKERS or email"; fi
    if [ "${{ steps.changes.outputs.pdf }}" = "true" ]; then MARKERS="$MARKERS or pdf"; fi
    if [ "${{ steps.changes.outputs.config }}" = "true" ]; then MARKERS="unit or integration"; fi
    
    # Strip leading " or " and run
    MARKERS="${MARKERS# or }"
    if [ -z "$MARKERS" ]; then
      echo "No test-relevant changes detected, running unit tests only"
      python -m pytest tests/unit/ -v --tb=short
    else
      python -m pytest -m "$MARKERS" -v --tb=short --cov=. --cov-report=term-missing
    fi
```

### Coverage Requirements

| Layer | Target | Enforcement |
|-------|--------|-------------|
| Models (to_dict, permissions, JSON fields) | 90% | CI fail if below |
| API endpoints (simple_api.py) | 85% | CI fail if below |
| Services (email, PDF, utils) | 80% | CI warn |
| Admin panel (custom_admin.py) | 70% | CI warn |
| User app proxy (app.py) | 65% | CI warn |
| **Overall project** | **75%** | **CI fail if below** |

### Test Case Inventory (Priority Order)

#### P0 — Must Have (Block Deploy)
| # | Test File | Cases | What It Validates |
|---|-----------|-------|-------------------|
| 1 | test_models.py | 25 | All 21 models: to_dict(), JSON get/set, relationships, defaults |
| 2 | test_api_auth.py | 12 | Login success/fail, JWT token, expired token, permission checks |
| 3 | test_api_rfpos.py | 15 | RFPO CRUD, line items, total calculations, soft delete |
| 4 | test_api_approvals.py | 10 | Workflow create/assign, approve/reject, stage progression |
| 5 | test_utils.py | 8 | generate_next_id, format_response, validate_required_fields |

#### P1 — Should Have (Block Deploy)
| # | Test File | Cases | What It Validates |
|---|-----------|-------|-------------------|
| 6 | test_api_consortiums.py | 8 | CRUD, uniqueness (name/abbrev), uppercase enforcement |
| 7 | test_api_projects.py | 8 | CRUD, ref format validation, consortium association |
| 8 | test_api_teams.py | 8 | CRUD, abbrev uniqueness, consortium linkage |
| 9 | test_api_vendors.py | 6 | CRUD, vendor sites cascade |
| 10 | test_email_service.py | 10 | Send, retry, queue, ACS fallback, logging |
| 11 | test_api_users.py | 6 | Profile, permissions, first-login detection |
| 12 | test_env_config.py | 6 | URL validation, secret key checks, config singleton |

#### P2 — Nice to Have (Warn Only)
| # | Test File | Cases | What It Validates |
|---|-----------|-------|-------------------|
| 13 | test_pdf_generator.py | 5 | PDF overlay, template combine, positioning |
| 14 | test_api_notifications.py | 4 | List, count, mark read |
| 15 | test_api_files.py | 4 | Upload, download, association |
| 16 | test_admin_auth.py | 5 | Login, session, flask-login |
| 17 | test_admin_crud.py | 20 | Entity CRUD operations (expanded per review) |
| 18 | test_error_handlers.py | 4 | Exception types, status codes |

#### Smoke (Post-Deploy)
| # | Test File | Cases | What It Validates |
|---|-----------|-------|-------------------|
| 19 | test_health_checks.py | 5 | API health, admin login page, user app load, DB connectivity |

**Total: ~165 test cases across 19 files**

---

## Part 2: GitHub & Copilot Alignment

### Current Grade: B-
### Target Grade: A

### Files to Create

#### 2a. Project Configuration
| File | Purpose |
|------|---------|
| `pyproject.toml` | Consolidated tool config (pytest, black, isort, coverage) |
| `Makefile` | Dev workflow commands (test, lint, deploy, docker) |
| `.gitattributes` | Line ending normalization |

#### 2b. GitHub Standards
| File | Purpose |
|------|---------|
| `.github/CODEOWNERS` | Auto-assign reviewers by file path |
| `.github/pull_request_template.md` | Standardized PR format |
| `.github/ISSUE_TEMPLATE/bug_report.md` | Bug report template |
| `.github/ISSUE_TEMPLATE/feature_request.md` | Feature request template |
| `.github/dependabot.yml` | Automated dependency updates |
| `CONTRIBUTING.md` | Developer setup + contribution process |
| `SECURITY.md` | Vulnerability disclosure |

#### 2c. VS Code / Copilot Integration
| File | Purpose |
|------|---------|
| `.vscode/settings.json` | Python, formatting, linting, Copilot settings |
| `.vscode/extensions.json` | Recommended extensions |
| `.vscode/launch.json` | Debug configurations (API, Admin, User App) |
| `.vscode/tasks.json` | Build/test/deploy task definitions |

#### 2d. CI/CD Improvements
| Change | File | Description |
|--------|------|-------------|
| Enhanced CI | `.github/workflows/ci.yml` | Path-based selective tests, coverage reporting |
| Deploy gate | `.github/workflows/deploy-azure.yml` | Require CI pass before deploy |
| CodeQL | `.github/workflows/codeql.yml` | Security scanning |

### Makefile Targets
```makefile
install        # pip install -r requirements.txt + dev
test           # pytest tests/unit/ tests/integration/ -v
test-unit      # pytest tests/unit/ -v
test-integration # pytest tests/integration/ -v
test-changed   # pytest based on git diff
test-coverage  # pytest --cov with HTML report
lint           # black --check + flake8 + isort --check
format         # black + isort (auto-fix)
docker-up      # docker-compose up -d
docker-build   # docker-compose build
deploy         # ./redeploy-phase1.sh
smoke          # pytest tests/smoke/ against live URLs
```

---

## Review Findings Applied

**Verdict: APPROVE WITH CHANGES** — 6 critical, 6 major, 6 minor findings incorporated.

### Key Adjustments Made:
1. Coverage targets raised: API→85%, Services→80%, Admin→70%, User→65%, Overall→75%
2. CI path-filter expanded: admin/user_app filters include `api/**` (cross-dependency)
3. conftest.py expanded: added db_transaction autouse, expired JWT, mock_email_service, app_context
4. Admin test count increased from 10→20 cases
5. Phase 4/5 reordered: GitHub standards before CI pipeline
6. Added: security tests, performance budgets, coverage publishing in future phases

---

## Implementation Order

| Phase | What | Files Created |
|-------|------|---------------|
| **Phase 1** | Test infrastructure | conftest.py, pyproject.toml, Makefile, move legacy tests |
| **Phase 2** | P0 unit tests (block deploy) | 5 test files (~70 cases) |
| **Phase 3** | P1 integration tests (block deploy) | 7 test files (~52 cases) |
| **Phase 4** | GitHub standards | CODEOWNERS, PR/issue templates, dependabot, CONTRIBUTING.md |
| **Phase 5** | CI pipeline upgrade | ci.yml (path-based), deploy gate, coverage reporting |
| **Phase 6** | VS Code / Copilot integration | .vscode/ configs |
| **Phase 7** | P2 + smoke tests | 6 test files (~33 cases) |
| **Phase 8** | Future: Security tests, perf budgets, load tests | (documented, not built yet) |
