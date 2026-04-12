# FR-0001: Add Search Capabilities to Admin Bug & Feature Log

> **Plan Status:** Approved with Changes  
> **Created:** 2026-04-11  
> **Reviewed By:** AI Code Review Agent  

---

## 1. Feature Request Details

| Field | Value |
|---|---|
| **Ticket** | FR-0001 |
| **Title** | Add Searching capabilities to the admin bug and feature log on the back end |
| **Description** | Add the ability to search existing Bug Logs and feature requests |
| **Submitted By** | John Bouchard |
| **Priority** | Low |
| **Status** | Open |
| **Created** | 2026-04-11 |
| **Page Context** | Admin Bug / Feature Log |

---

## 2. Interpretation

The admin panel currently displays bug reports (`/admin/tickets/bugs`) and feature requests (`/admin/tickets/features`) in a table with only **status** and **priority** dropdown filters. There is **no text search** capability. As the ticket volume grows, admins need the ability to quickly find specific tickets by keyword, ticket number, submitter name, or date range.

This feature targets **both** the admin panel (server-side rendered) and the API layer (for user-app consumption).

---

## 3. Current State Analysis

### Admin Panel (`custom_admin.py`)
- **Routes:** `admin_ticket_bugs()` (line ~8333) and `admin_ticket_features()` (line ~8354) query the `Ticket` model filtered only by `status` and `priority` query params.
- **Template:** `templates/admin/tickets.html` — renders a `<table>` with dropdown selects.
- **No pagination** — loads all tickets at once via `.all()`.
- **Dropdowns auto-submit** via `onchange="this.form.submit()"`.

### API Layer (`simple_api.py`)
- **Route:** `GET /api/tickets` (line ~4398) — filters by `type`, `status` only.
- **No `search` or `q` query parameter** is accepted.
- **Has pagination** via `.paginate()`.

### User App
- Bugs page (`templates/app/bugs.html`) and Feature Requests page (`templates/app/feature_requests.html`) use **client-side JavaScript** that calls the API endpoints — data is fetched via `fetch()`, not server-rendered.

### Existing Search Pattern (Reference)
- The RFPO list endpoint (`simple_api.py` ~line 2733) already implements a mature search with `ilike` across multiple fields. **This should be used as the code template** for consistency.

### Database Indexes (Current)
- `ticket_number`: indexed ✓
- `title`: **NO index** ⚠️
- `description`: **NO index** ⚠️
- `created_at`: indexed ✓

---

## 4. Implementation Plan

### Phase 1: API-Level Search (Backend)

**File: `simple_api.py` — `list_tickets()` endpoint**

1. **Add `q` query parameter** for text search across: `ticket_number`, `title`, `description`
2. **Add `date_from` / `date_to` query parameters** for date range filtering on `Ticket.created_at` (ISO `YYYY-MM-DD` format)
3. **Add `assigned_to` filter** (by user ID) for admin filtering by assignee
4. **Add `sort` parameter** with options: `created_at`, `updated_at`, `priority`, `ticket_number` (default: `created_at` desc)

**Input validation rules:**
- Strip whitespace from search term
- **Truncate** (do not reject) search terms exceeding 200 characters
- Empty `q=` or `q=   ` returns all results (no filter applied)
- SQL wildcard characters (`%`, `_`) in user input are treated as literals by SQLAlchemy's parameterized `ilike()`

**Implementation pattern (match existing RFPO search):**
```python
search_query = request.args.get("q", "").strip()[:200]
if search_query:
    like_term = f"%{search_query}%"
    query = query.filter(
        db.or_(
            Ticket.ticket_number.ilike(like_term),
            Ticket.title.ilike(like_term),
            Ticket.description.ilike(like_term),
        )
    )
```

> **Decision: Creator name search deferred to Phase 2.** Searching by creator name requires a `LEFT JOIN` to the User table. For Phase 1, search across ticket fields only. This avoids the join overhead and simplifies the initial implementation. Creator name search can be added later if needed.

**Example API call:**
```
GET /api/tickets?type=feature_request&q=search&status=open&sort=priority&page=1&per_page=20
```

---

### Phase 2: Admin Panel Search UI

**File: `custom_admin.py` — `admin_ticket_bugs()` and `admin_ticket_features()`**

1. Add `search` query parameter to both routes
2. Apply same `ilike` filter on `ticket_number`, `title`, `description`
3. **Replace `.all()` with `.paginate()`** — 20 tickets per page
4. Pass `search_filter`, `page`, `total` to template context

**File: `templates/admin/tickets.html`**

5. **Add search bar** — separate `<input>` with search button, placed alongside existing dropdowns

**UX Decision: Hybrid approach (Option A)**
- The search bar uses a **submit button** (not auto-submit) since typing requires pressing Enter
- Status/priority dropdowns **retain their `onchange` auto-submit** for quick filtering
- Both live in the same `<form>` using GET method so all params are preserved

```html
<form class="d-flex gap-2" method="GET">
    <!-- Search bar with button -->
    <div class="input-group input-group-sm" style="max-width: 320px;">
        <input type="text" name="search" class="form-control"
               placeholder="Search by ticket #, title..."
               value="{{ search_filter or '' }}">
        <button class="btn btn-outline-secondary" type="submit">
            <i class="fas fa-search"></i>
        </button>
        {% if search_filter %}
        <a href="{{ request.path }}" class="btn btn-outline-danger" title="Clear search">
            <i class="fas fa-times"></i>
        </a>
        {% endif %}
    </div>

    <!-- Existing dropdowns (keep onchange auto-submit) -->
    <!-- Hidden input preserves search term when dropdown changes -->
    <select name="status" class="form-select form-select-sm" onchange="this.form.submit()">
        ...
    </select>
    <select name="priority" class="form-select form-select-sm" onchange="this.form.submit()">
        ...
    </select>
</form>
```

6. **Add result count** above the table: "Showing X of Y tickets"

7. **Add pagination controls** at the bottom of the table:
```html
<nav>
    <ul class="pagination justify-content-center">
        <li class="page-item {{ 'disabled' if page <= 1 }}">
            <a class="page-link" href="?page={{ page - 1 }}&search={{ search_filter }}&status={{ status_filter }}&priority={{ priority_filter }}">
                Previous
            </a>
        </li>
        <li class="page-item disabled">
            <span class="page-link">Page {{ page }} of {{ pages }}</span>
        </li>
        <li class="page-item {{ 'disabled' if page >= pages }}">
            <a class="page-link" href="?page={{ page + 1 }}&search={{ search_filter }}&status={{ status_filter }}&priority={{ priority_filter }}">
                Next
            </a>
        </li>
    </ul>
</nav>
```

**Wireframe:**
```
┌──────────────────────────────────────────────────────────────────────┐
│  🔍 [Search tickets...    ][🔍][✕]  [Status ▾] [Priority ▾]        │
│  Showing 5 of 23 feature requests                                    │
├──────┬──────────────────────┬────────┬──────────┬────────┬──────────┤
│ FR#  │ Title                │ Status │ Priority │ By     │ Created  │
├──────┼──────────────────────┼────────┼──────────┼────────┼──────────┤
│ ...  │ ...                  │ ...    │ ...      │ ...    │ ...      │
├──────┴──────────────────────┴────────┴──────────┴────────┴──────────┤
│                [← Previous]  Page 1 of 2  [Next →]                   │
└──────────────────────────────────────────────────────────────────────┘
```

---

### Phase 3: User App Search (Optional Enhancement)

**Files:** `templates/app/bugs.html`, `templates/app/feature_requests.html`

Since these templates already use client-side `fetch()` calls to `/api/tickets`, adding search is straightforward:
1. Add a search input above the ticket list
2. Pass `q=` parameter to the existing API call
3. Minimal backend work since API search (Phase 1) handles the logic

> **This phase is optional** since the FR specifically says "admin... on the back end." Implement only after Phases 1–2 are validated.

---

## 5. Database Preparation

**Before deploying search, add indexes for PostgreSQL performance:**

```sql
-- Run against Azure PostgreSQL before deploying
CREATE INDEX IF NOT EXISTS idx_ticket_title_search ON tickets (title);
CREATE INDEX IF NOT EXISTS idx_ticket_description_search ON tickets USING gin (to_tsvector('english', description));
```

> **Note:** For `ilike` on `description` (text field), a GIN trigram index would be ideal but requires `pg_trgm` extension. Standard btree index on `title` helps with prefix matches. Test with production data volume to determine if GIN index is needed.

---

## 6. Detailed Task Breakdown

| # | Task | File(s) | Effort | Phase |
|---|------|---------|--------|-------|
| 1 | Add `q`, `date_from`, `date_to`, `assigned_to`, `sort` params to `GET /api/tickets` | `simple_api.py` | Small | 1 |
| 2 | Add input validation (strip, truncate 200 chars) | `simple_api.py` | Small | 1 |
| 3 | Add `search` param + pagination to `admin_ticket_bugs()` | `custom_admin.py` | Small | 2 |
| 4 | Add `search` param + pagination to `admin_ticket_features()` | `custom_admin.py` | Small | 2 |
| 5 | Add search bar UI to `tickets.html` template | `templates/admin/tickets.html` | Medium | 2 |
| 6 | Add pagination controls to `tickets.html` template | `templates/admin/tickets.html` | Medium | 2 |
| 7 | Add result count display | `templates/admin/tickets.html` | Small | 2 |
| 8 | Add database indexes for search fields | Azure PostgreSQL | Small | 2 |
| 9 | Write tests for API search (new file) | `tests/test_ticket_search.py` | Medium | 1-2 |
| 10 | Write tests for admin search routes | `tests/test_ticket_search.py` | Medium | 2 |
| 11 | Deploy and verify on Azure | Build + deploy | Small | 2 |
| 12 | *(Optional)* Add search to user-facing bugs/features pages | `templates/app/bugs.html`, `feature_requests.html` | Small | 3 |

---

## 7. Testing Strategy

**Note:** There are currently **zero** ticket-related tests in the test suite. This plan includes creating the foundational test file.

### New File: `tests/test_ticket_search.py`

| Test | Description |
|------|-------------|
| `test_search_by_ticket_number` | `q=FR-0001` returns exact match |
| `test_search_by_title_partial` | `q=searching` matches title substring |
| `test_search_by_description` | `q=bug logs` matches description |
| `test_search_case_insensitive` | `q=SEARCH` matches lowercase title |
| `test_search_empty_returns_all` | `q=` returns unfiltered results |
| `test_search_with_status_filter` | `q=test&status=open` combines filters |
| `test_search_with_priority_filter` | `q=test&priority=high` combines filters |
| `test_search_no_results` | `q=zzzznonexistent` returns empty list |
| `test_search_special_characters` | `q=%test_` doesn't break SQL |
| `test_search_truncates_long_input` | 500-char query truncated to 200 |
| `test_search_pagination` | Results paginate correctly with search |
| `test_sort_by_priority` | `sort=priority` returns correct order |
| `test_date_range_filter` | `date_from` / `date_to` filters correctly |

### Performance Test (Manual)
- Create 1000+ test tickets via script
- Verify search response time < 500ms on PostgreSQL
- Verify pagination works at scale

---

## 8. Security Considerations

- **SQL Injection:** SQLAlchemy's `ilike()` uses parameterized queries — safe by default
- **Input validation:** Search strings truncated to 200 chars, whitespace stripped
- **XSS:** Search term displayed in template uses Jinja2 auto-escaping (already enabled globally)
- **No new auth requirements:** Existing `@admin_required` and `@jwt_required` decorators apply
- **NULL handling:** `outerjoin` on User table handles deleted/NULL creators gracefully (deferred to Phase 2)

---

## 9. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Performance on large datasets without indexes | Medium | Add indexes before deploying; test with 1000+ tickets |
| Pagination breaks existing filtered bookmark URLs | Low | All filter params preserved via query string |
| Dropdown auto-submit conflicts with search typing | Low | Search uses separate button; dropdowns keep auto-submit |
| No existing test baseline for tickets | Medium | Create test fixtures in Phase 1 |

---

## 10. Review Summary

### Reviewer Verdict: ✅ APPROVED WITH CHANGES (all addressed below)

| Reviewer Finding | Resolution in This Plan |
|---|---|
| Reference existing RFPO search pattern | ✓ Section 4 Phase 1 references RFPO `ilike` pattern |
| Creator name join has performance risk | ✓ Deferred to Phase 2; Phase 1 searches ticket fields only |
| Input validation details missing | ✓ Section 4 Phase 1 specifies truncation to 200 chars |
| Dropdown auto-submit UX conflict | ✓ Hybrid approach: search uses button, dropdowns keep auto-submit |
| No database indexes on title/description | ✓ Section 5 adds index creation SQL |
| No test baseline exists | ✓ Section 7 creates foundational `test_ticket_search.py` |
| NULL creator handling | ✓ Deferred with Phase 2 creator join |
| Date range filtering UI not in admin panel | ✓ Noted as API-only for Phase 1; admin date UI deferred |

---

## 11. Files Changed Summary

| File | Change Type | Phase |
|------|-------------|-------|
| `simple_api.py` | Modified — add search/sort/date params to `list_tickets()` | 1 |
| `custom_admin.py` | Modified — add search + pagination to both ticket routes | 2 |
| `templates/admin/tickets.html` | Modified — add search bar, result count, pagination | 2 |
| `tests/test_ticket_search.py` | **New** — comprehensive search tests | 1-2 |
| Azure PostgreSQL | DDL — add indexes | 2 |
| `templates/app/bugs.html` | Modified — add search input *(optional)* | 3 |
| `templates/app/feature_requests.html` | Modified — add search input *(optional)* | 3 |

---

*No database schema changes required. No new dependencies. No new models.*
