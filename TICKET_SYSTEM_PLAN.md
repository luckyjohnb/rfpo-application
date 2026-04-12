# Bug Log & Feature Request System — Implementation Reference

> **Status**: Deployed to Azure Container Apps (April 2026)
> **Last updated**: April 11, 2026

## Overview

A unified **Ticket system** that powers both Bug Log and Feature Request capabilities. Both share the same underlying data model (`type = bug | feature_request`). They use different status workflows and labels but share the same database table, API endpoints, and UI patterns.

---

## 1. Database Models (`models.py`)

### `Ticket` — Core table (`tickets`)

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `id` | Integer PK | Auto | Auto-increment |
| `ticket_number` | String(20) | Yes | Human-readable ID (`BUG-0001`, `FR-0001`), unique indexed |
| `type` | String(20) | Yes | `bug` or `feature_request` (indexed) |
| `title` | String(255) | Yes | Short summary |
| `description` | Text | Yes | Detailed description |
| `status` | String(32) | Yes | Status (default: `open`); see §5 for per-type values |
| `priority` | String(20) | Yes | `low`, `medium` (default), `high`, `critical` |
| `severity` | String(20) | Bug only | `cosmetic`, `minor`, `major`, `blocker` |
| `page_url` | String(512) | No | Auto-captured: page where issue was encountered |
| `browser_info` | String(512) | No | Auto-captured from user-agent |
| `steps_to_reproduce` | Text | No | Bug only: repro steps |
| `created_by` | Integer FK → users | Yes | Who filed it (indexed) |
| `assigned_to` | Integer FK → users | No | Developer assignment (indexed) |
| `internal_notes` | Text | No | Admin-only developer notes (hidden from submitter) |
| `created_at` | DateTime | Auto | Submission timestamp (indexed) |
| `updated_at` | DateTime | Auto | Last modification (auto-updates) |
| `resolved_at` | DateTime | No | When ticket was resolved |
| `closed_at` | DateTime | No | When ticket was closed |

**Composite indexes**: `(type, status)`, `(created_by, type)`

**Key methods**:
- `generate_ticket_number(ticket_type, session)` — creates next sequential `BUG-NNNN` or `FR-NNNN`
- `to_dict()` — full serialization (includes `internal_notes`, all comment/attachment counts)
- `to_dict_public()` — submitter serialization (hides `internal_notes`, counts only public comments)

### `TicketComment` — Conversation thread (`ticket_comments`)

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `id` | Integer PK | Auto | Auto-increment |
| `ticket_id` | Integer FK → tickets | Yes | Parent ticket (cascade delete) |
| `user_id` | Integer FK → users | Yes | Comment author |
| `content` | Text | Yes | The message body |
| `is_internal` | Boolean | No | If `true`, only visible to admins (default: `false`) |
| `created_at` | DateTime | Auto | Timestamp |

**Note**: Author display name is resolved via the `User` relationship (`author.get_display_name()`), not stored as a snapshot.

### `TicketAttachment` — File uploads (`ticket_attachments`)

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `id` | Integer PK | Auto | Auto-increment |
| `file_id` | String(36) | Yes | UUID (unique) |
| `ticket_id` | Integer FK → tickets | Yes | Parent ticket (cascade delete) |
| `original_filename` | String(256) | Yes | Original name as uploaded |
| `stored_filename` | String(256) | Yes | `{uuid}_{filename}` on disk |
| `file_path` | String(512) | Yes | Local storage path |
| `cloud_path` | String(512) | No | DOCUPLOAD remote folder path |
| `file_size` | Integer | Yes | Size in bytes |
| `mime_type` | String(128) | No | Content type |
| `file_extension` | String(10) | No | e.g. `.png`, `.log` |
| `uploaded_by` | Integer FK → users | Yes | Uploader user ID |
| `uploaded_at` | DateTime | Auto | Timestamp |

### Relationships

- `Ticket` → `TicketComment` (one-to-many, cascade delete, ordered by `created_at`)
- `Ticket` → `TicketAttachment` (one-to-many, cascade delete)
- `Ticket.created_by` → `User.tickets_created` (backref)
- `Ticket.assigned_to` → `User.tickets_assigned` (backref, nullable)

### Upload Limits & Storage

- **Max 5 files** per ticket, **10 MB** per file, **50 MB** total per ticket
- File type validation: extension whitelist + MIME type detection + file header checks
- Local storage: `uploads/tickets/{ticket_number}/{bug|feature}/`
- Cloud storage: DOCUPLOAD integration to `tickets/{ticket_number}/{type}/` folders

### Model Imports (`sqlalchemy_db_init.py`)

All three models are imported and included in `db.create_all()`.

---

## 2. API Endpoints (`simple_api.py`)

### Ticket CRUD

| Method | Endpoint | Auth | Who | Purpose |
|--------|----------|------|-----|---------|
| `GET` | `/api/tickets` | JWT | Any authenticated | List tickets (users see own only; admins see all) |
| `POST` | `/api/tickets` | JWT | Any authenticated | Create a bug or feature request |
| `GET` | `/api/tickets/<id>` | JWT | Submitter or Admin | Get ticket detail + comments + attachments |
| `PUT` | `/api/tickets/<id>` | JWT | Submitter or Admin | Update status, priority, severity, assignment, internal notes |

### Comments

| Method | Endpoint | Auth | Who | Purpose |
|--------|----------|------|-----|---------|
| `POST` | `/api/tickets/<id>/comments` | JWT | Submitter or Admin | Add a comment (admins can set `is_internal: true`) |

### Attachments

| Method | Endpoint | Auth | Who | Purpose |
|--------|----------|------|-----|---------|
| `POST` | `/api/tickets/<id>/attachments` | JWT | Submitter or Admin | Upload file (multipart), validated + DOCUPLOAD sync |
| `GET` | `/api/tickets/<id>/attachments/<file_id>/view` | JWT | Submitter or Admin | Stream/download file |

### Filters (GET `/api/tickets`)

| Parameter | Type | Purpose |
|-----------|------|---------|
| `type` | String | `bug` or `feature_request` |
| `status` | String | Filter by status value |
| `page` | Integer | Page number (default: 1) |
| `per_page` | Integer | Results per page (default: 20, max: 50) |

**Default sort**: `created_at` descending.

### Access Control

- Regular users see only their own tickets (`created_by == user.id`)
- Admins (`GOD` permission) see all tickets and `internal_notes`
- Non-admin serialization uses `to_dict_public()` (hides internal data)

---

## 3. Admin Panel (`custom_admin.py`)

### Sidebar Menu (`templates/admin/base.html`)

Under **Management** section:
```
Bug Log          → /admin/tickets/bugs
Feature Requests → /admin/tickets/features
```

### Admin Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/admin/tickets/bugs` | GET | Bug list with status/priority filters |
| `/admin/tickets/features` | GET | Feature request list with status/priority filters |
| `/admin/tickets/<id>` | GET | Ticket detail: full info, comments, attachments, dev controls |
| `/admin/tickets/<id>/update` | POST | Update status, priority, severity, assignment, internal notes |
| `/admin/tickets/<id>/comment` | POST | Add comment (with `is_internal` toggle) |
| `/admin/tickets/<id>/attachments/<file_id>` | GET | Download attachment |

### Admin Templates

- **`templates/admin/tickets.html`** — Shared list view for both types
  - Status & priority dropdown filters
  - Table: ticket number (linked), title, severity/priority badges, status pill, submitter, date, attachment count
- **`templates/admin/ticket_detail.html`** — Two-column detail/triage view
  - Left: ticket info, description, steps to reproduce, attachments, comment thread
  - Right: dev controls (status, priority, severity, assignment, internal notes)

---

## 4. User App

### Architecture

Routes are split across blueprints (refactored from monolithic `app.py`):
- **Page routes**: `user_app/blueprints/pages.py` (Blueprint: `pages`)
- **API proxy routes**: `user_app/blueprints/ticket_proxy.py` (Blueprint: `ticket_proxy`)

### Page Routes

| Route | Method | Blueprint endpoint | Purpose |
|-------|--------|-------------------|---------|
| `/bugs` | GET | `pages.bugs_page` | Bug submit form + my bugs list |
| `/feature-requests` | GET | `pages.feature_requests_page` | Feature request form + my requests list |
| `/tickets/<id>` | GET | `pages.ticket_detail_page` | Ticket detail (submitter view) |

### API Proxy Routes

| Route | Methods | Proxies to |
|-------|---------|-----------|
| `/api/tickets` | GET, POST | `/api/tickets` |
| `/api/tickets/<id>` | GET, PUT | `/api/tickets/<id>` |
| `/api/tickets/<id>/comments` | POST | `/api/tickets/<id>/comments` |
| `/api/tickets/<id>/attachments` | POST | `/api/tickets/<id>/attachments` |
| `/api/tickets/<id>/attachments/<fid>/view` | GET | Stream-through proxy |

### Sidebar Menu (`templates/app/base.html`)

**Support** section visible to all authenticated users:
```
Report Bug       → /bugs
Feature Request  → /feature-requests
```

### User Templates

- **`templates/app/bugs.html`** — Submit form (title, description, steps to reproduce, priority) + "My Bugs" list below
- **`templates/app/feature_requests.html`** — Submit form (title, description, priority) + "My Feature Requests" list below
- **`templates/app/ticket_detail.html`** — Detail view with:
  - Ticket info (title, description, status, severity, dates)
  - Attachments (download)
  - Public comments thread (internal comments hidden)
  - Add follow-up comment form

### Important: Blueprint URL References

All `url_for()` calls in templates use the `pages.` blueprint prefix:
```jinja
{{ url_for('pages.dashboard') }}
{{ url_for('pages.bugs_page') }}
{{ url_for('pages.feature_requests_page') }}
```

---

## 5. Status Workflows

Bugs and feature requests use **separate status values**:

### Bug Statuses
```
open ──→ in_progress ──→ resolved ──→ closed
                │                       ↑
                └── wont_fix ───────────┘
```

| Status | Meaning |
|--------|---------|
| `open` | Just submitted, unreviewed |
| `in_progress` | Actively being worked on |
| `resolved` | Fix deployed |
| `closed` | Confirmed complete |
| `wont_fix` | Acknowledged but will not be fixed |

### Feature Request Statuses
```
open ──→ under_review ──→ planned ──→ in_progress ──→ completed
                │                                       ↑
                └── declined ──────────────────────────┘
```

| Status | Meaning |
|--------|---------|
| `open` | Just submitted |
| `under_review` | Team is evaluating |
| `planned` | Accepted, scheduled for work |
| `in_progress` | Actively being built |
| `completed` | Feature shipped |
| `declined` | Will not be implemented |

---

## 6. Notifications

### Implemented
- **Email on status change**: Background thread sends email when admin updates ticket status via `send_ticket_status_notification()` in `email_service.py`

### Not Yet Implemented
- In-app notifications (via existing `Notification` model)
- Email/in-app notifications on new comments
- Email notifications to assigned developer on ticket creation

---

## 7. Files Changed

| File | Action | Scope |
|------|--------|-------|
| `models.py` | **Edited** | Added `Ticket`, `TicketComment`, `TicketAttachment` classes |
| `sqlalchemy_db_init.py` | **Edited** | Added imports for 3 new models |
| `simple_api.py` | **Edited** | Added ticket CRUD, comment, attachment endpoints |
| `custom_admin.py` | **Edited** | Added admin routes for ticket list + detail + update |
| `templates/admin/base.html` | **Edited** | Added 2 sidebar menu items |
| `templates/admin/tickets.html` | **Created** | Shared list template for bugs/features |
| `templates/admin/ticket_detail.html` | **Created** | Admin detail/triage view |
| `user_app/blueprints/pages.py` | **Edited** | Added bug, feature request, and ticket detail page routes |
| `user_app/blueprints/ticket_proxy.py` | **Created** | API proxy blueprint for ticket operations |
| `templates/app/base.html` | **Edited** | Added Support section with 2 menu items |
| `templates/app/bugs.html` | **Created** | Bug submit form + my bugs list |
| `templates/app/feature_requests.html` | **Created** | Feature request form + my requests list |
| `templates/app/ticket_detail.html` | **Created** | User ticket detail view |

---

## 8. Deployment

All three services were rebuilt and deployed to Azure Container Apps:
1. **API** (`rfpo-api`) — new model tables auto-created via `db.create_all()`, new endpoints
2. **Admin** (`rfpo-admin`) — new routes + templates
3. **User App** (`rfpo-user`) — new blueprints + templates

---

## 9. Future Enhancements

The following items from the original plan were deferred:

| Item | Priority | Notes |
|------|----------|-------|
| `DELETE /api/tickets/<id>` endpoint | Low | Admin ticket deletion (soft or hard) |
| `DELETE /api/tickets/<id>/attachments/<fid>` endpoint | Low | Attachment removal |
| `category` field (`UI`, `API`, `Workflow`, `PDF`, `Login`, `Other`) | Medium | Ticket categorization |
| `expected_behavior` field (bug-only) | Low | "What should have happened" |
| `resolution` field | Medium | How the issue was resolved |
| In-app notifications on status change/comment | Medium | Uses existing `Notification` model |
| Advanced API filters (`mine`, `assigned_to`, `sort`, `priority`) | Low | Currently only `type`, `status`, `page`, `per_page` |
| Floating "Report Bug" button on every page | Low | Currently sidebar-only access |

### Decision Log

| Question | Decision |
|----------|----------|
| Who sees tickets? | Users see only their own; admins (GOD permission) see all |
| Email on status change? | Implemented via background thread |
| Ticket deletion? | Deferred — no delete endpoint yet |
| Max attachments? | 5 files, 10 MB each, 50 MB total per ticket |
| DOCUPLOAD integration? | Yes — attachments also uploaded to cloud storage |
