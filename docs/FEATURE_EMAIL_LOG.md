# Feature Request: Admin Email Log

**Author:** John Bouchard  
**Date:** 2026-04-06  
**Priority:** High  
**Status:** Revised — Ready for Implementation  
**Review:** Passed with changes (2026-04-06). All critical findings addressed below.  

---

## Problem Statement

There is currently no visibility into outbound email activity. When emails fail (e.g., missing templates, ACS misconfiguration, or delivery errors), the only evidence is buried in container logs that are difficult to search and expire quickly. Administrators need a persistent, searchable record of all email activity to troubleshoot delivery issues and confirm notifications were sent.

## Objective

Add a comprehensive email log to the Admin Panel that records every outbound email attempt with full context linking it back to the relevant RFPO, Project, Consortium, and Team — enabling administrators to quickly identify, search, filter, and diagnose email delivery issues.

---

## Scope

### In Scope
- New `EmailLog` database model
- Logging hook inside `EmailService.send_email()` (single capture point for all email types)
- Admin Panel list view with search, filtering, and pagination
- Admin Panel detail view for individual log entries
- Resend capability for failed emails
- Test-mode awareness (flag + original recipient preservation)
- Context preservation through retry queue

### Out of Scope
- Email template editor/management UI (future feature)
- Inbound email processing
- Real-time delivery status webhooks from ACS (future enhancement)
- `send_user_added_to_project_email` — function exists but is **never called** anywhere in the codebase; excluded from scope until the project-assignment workflow is wired up

---

## Data Model: `EmailLog`

New SQLAlchemy model in `models.py` (model #19):

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `id` | Integer (PK) | No | auto | Auto-increment primary key |
| `message_id` | String(255) | Yes | | Provider message ID (ACS or SMTP) |
| `email_type` | String(64) | No | | Template/type: `approval_notification`, `welcome`, `password_changed`, `approval_complete`, `custom` |
| `subject` | String(512) | No | | Email subject line |
| `from_email` | String(255) | No | | Sender address |
| `to_emails` | Text (JSON) | No | | JSON array of recipient addresses |
| `cc_emails` | Text (JSON) | Yes | | JSON array of CC addresses |
| `bcc_emails` | Text (JSON) | Yes | | JSON array of BCC addresses |
| `status` | String(32) | No | | `sent`, `failed`, `queued`, `retried` |
| `provider` | String(32) | Yes | | `ACS`, `SMTP`, or null |
| `error_message` | String(1024) | Yes | | Error details on failure (**sanitized** — no stack traces, max 1024 chars) |
| `retry_count` | Integer | No | 0 | Number of retry attempts |
| `rfpo_id` | Integer (FK → rfpos.id) | Yes | | Related RFPO (SET NULL on delete) |
| `project_id` | String(32) | Yes | | Related Project ID |
| `consortium_id` | String(32) | Yes | | Related Consortium ID |
| `team_id` | Integer (FK → teams.id) | Yes | | Related Team (SET NULL on delete) |
| `triggered_by_user_id` | Integer (FK → users.id) | Yes | | User whose action triggered the email (SET NULL on delete) |
| `template_name` | String(128) | Yes | | Jinja template used (without `.html`) |
| `body_preview` | Text | Yes | | First 500 chars of plain text body |
| `test_mode` | Boolean | No | False | Whether email was sent in test mode |
| `original_recipients` | Text (JSON) | Yes | | Original TO/CC/BCC before test-mode redirect (JSON object) |
| `created_at` | DateTime | No | utcnow | Timestamp of send attempt (UTC) |

### Indexes
```python
__table_args__ = (
    db.Index("idx_email_log_type", "email_type"),
    db.Index("idx_email_log_status", "status"),
    db.Index("idx_email_log_rfpo", "rfpo_id"),
    db.Index("idx_email_log_project", "project_id"),
    db.Index("idx_email_log_consortium", "consortium_id"),
    db.Index("idx_email_log_created", "created_at"),
    db.Index("idx_email_log_status_created", "status", "created_at"),
    db.Index("idx_email_log_triggered_by", "triggered_by_user_id"),
    db.Index("idx_email_log_template", "template_name"),
)
```

### Foreign Key On-Delete Behavior

All FKs use `SET NULL` on delete — email log entries are **preserved** as audit records even when the related RFPO, Team, or User is deleted. Templates must handle `None` gracefully for all relationship fields.

```python
rfpo_id = db.Column(db.Integer, db.ForeignKey("rfpos.id", ondelete="SET NULL"), nullable=True)
team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
triggered_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
```

### Relationships
```python
rfpo = db.relationship("RFPO", backref=db.backref("email_logs", lazy=True), foreign_keys=[rfpo_id])
team = db.relationship("Team", foreign_keys=[team_id])
triggered_by = db.relationship("User", foreign_keys=[triggered_by_user_id])
```

---

## Method Signature Changes

### `EmailService.send_email()` — Add `context` and `email_type` parameters

```python
def send_email(
    self,
    to_emails: List[str],
    subject: str,
    body_text: Optional[str] = None,
    body_html: Optional[str] = None,
    from_email: Optional[str] = None,
    cc_emails: Optional[List[str]] = None,
    bcc_emails: Optional[List[str]] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
    # ---- NEW PARAMETERS ----
    context: Optional[Dict[str, Any]] = None,   # {rfpo_id, project_id, consortium_id, team_id, triggered_by_user_id}
    email_type: str = "custom",                  # template/type identifier
    template_name: Optional[str] = None,         # Jinja template name
) -> bool:
```

### `EmailService.send_templated_email()` — Add `context` parameter, propagate to `send_email()`

```python
def send_templated_email(
    self,
    to_emails: List[str],
    template_name: str,
    template_data: Optional[Dict[str, Any]] = None,
    subject: Optional[str] = None,
    from_email: Optional[str] = None,
    cc_emails: Optional[List[str]] = None,
    bcc_emails: Optional[List[str]] = None,
    # ---- NEW PARAMETERS ----
    context: Optional[Dict[str, Any]] = None,
    email_type: Optional[str] = None,            # defaults to template_name if not set
) -> bool:
    # ... existing logic ...
    return self.send_email(
        ...,
        context=context,
        email_type=email_type or template_name,
        template_name=template_name,
    )
```

### `EmailService.send_approval_notification()` — Add `context` kwarg

```python
def send_approval_notification(
    self,
    user_email: str,
    user_name: str,
    rfpo_id: str,
    approval_type: str,
    rfpo_db_id: Optional[int] = None,
    context: Optional[Dict[str, Any]] = None,    # NEW
) -> bool:
    return self.send_templated_email(
        ...,
        context=context,
        email_type="approval_notification",
    )
```

### `EmailService.send_welcome_email()` — Add `context` kwarg

```python
def send_welcome_email(
    self, ...,
    context: Optional[Dict[str, Any]] = None,    # NEW
) -> bool:
    return self.send_templated_email(
        ...,
        context=context,
        email_type="welcome",
    )
```

### `EmailService.send_password_changed_email()` — Add `context` kwarg

```python
def send_password_changed_email(
    self, ...,
    context: Optional[Dict[str, Any]] = None,    # NEW
) -> bool:
    return self.send_templated_email(
        ...,
        context=context,
        email_type="password_changed",
    )
```

### Module-level convenience wrappers — Forward `context`

All four wrappers at bottom of `email_service.py` (lines 1069–1124) updated to accept and forward `context=None`:

```python
def send_approval_notification(..., context=None):
    return email_service.send_approval_notification(..., context=context)

def send_welcome_email(..., context=None):
    return email_service.send_welcome_email(..., context=context)

def send_password_changed_email(..., context=None):
    return email_service.send_password_changed_email(..., context=context)
```

---

## FailedEmail Dataclass — Add Context Field

The existing `FailedEmail` dataclass (email_service.py:43) loses context on retry. Fix:

```python
@dataclass
class FailedEmail:
    to_emails: List[str]
    subject: str
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    from_email: Optional[str] = None
    cc_emails: Optional[List[str]] = None
    bcc_emails: Optional[List[str]] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    attempts: int = 0
    last_error: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    # ---- NEW FIELDS ----
    context: Optional[Dict[str, Any]] = None
    email_type: str = "custom"
    template_name: Optional[str] = None
```

The `_enqueue_failed()` method must pass these through, and `retry_failed()` must forward them to `send_email()` so the retry log entry inherits the original context.

---

## `_log_email()` Implementation

Single private method on `EmailService`, called at the end of every `send_email()`:

```python
def _log_email(
    self,
    to_emails: List[str],
    subject: str,
    status: str,                    # "sent", "failed", "queued"
    body_text: Optional[str] = None,
    from_email: Optional[str] = None,
    cc_emails: Optional[List[str]] = None,
    bcc_emails: Optional[List[str]] = None,
    context: Optional[Dict[str, Any]] = None,
    email_type: str = "custom",
    template_name: Optional[str] = None,
    error_message: Optional[str] = None,
    test_mode: bool = False,
    original_recipients: Optional[Dict] = None,
) -> None:
    """Persist email send attempt to database. Never raises — email delivery is not affected."""
    try:
        from flask import has_app_context
        if not has_app_context():
            logger.info("Email log (no app context): status=%s type=%s to=%s subject=%s",
                        status, email_type, to_emails, subject)
            return

        from models import EmailLog
        ctx = context or {}
        log = EmailLog(
            message_id=self.last_message_id,
            email_type=email_type,
            subject=subject,
            from_email=from_email or self.last_sender or "",
            to_emails=json.dumps(to_emails),
            cc_emails=json.dumps(cc_emails) if cc_emails else None,
            bcc_emails=json.dumps(bcc_emails) if bcc_emails else None,
            status=status,
            provider=self.last_provider,
            error_message=str(error_message)[:1024] if error_message else None,
            rfpo_id=ctx.get("rfpo_id"),
            project_id=ctx.get("project_id"),
            consortium_id=ctx.get("consortium_id"),
            team_id=ctx.get("team_id"),
            triggered_by_user_id=ctx.get("triggered_by_user_id"),
            template_name=template_name,
            body_preview=(body_text or "")[:500] if body_text else None,
            test_mode=test_mode,
            original_recipients=json.dumps(original_recipients) if original_recipients else None,
        )
        db.session.add(log)
        db.session.commit()
    except Exception as exc:
        logger.error("Failed to log email to database: %s", exc)
        # Never let logging break email delivery
```

### Where `_log_email()` is called in `send_email()`:

1. **After successful send** (ACS or SMTP): `_log_email(..., status="sent")`
2. **After all retries exhausted** (before enqueue): `_log_email(..., status="failed", error_message=...)`
3. **When enqueued to FailedEmail queue**: `_log_email(..., status="queued", error_message=...)`

### Test-mode awareness:

Inside `send_email()`, before the test-mode redirect block modifies recipients, capture the originals:

```python
# Capture for logging
_original_recipients = None
_is_test_mode = False

test_settings = _get_email_test_settings()
if test_settings["test_mode"] and test_settings["test_recipient"]:
    _is_test_mode = True
    _original_recipients = {
        "to": list(to_emails),
        "cc": list(cc_emails) if cc_emails else [],
        "bcc": list(bcc_emails) if bcc_emails else [],
    }
    # ... existing redirect logic ...
```

Then pass `test_mode=_is_test_mode, original_recipients=_original_recipients` to `_log_email()`.

---

## Complete Call Site Inventory

Every place in the codebase that triggers an outbound email, with the context available:

### `simple_api.py` — 8 call sites

| Line | Function | Email Type | Context Available |
|---|---|---|---|
| 709 | `change_password()` | `password_changed` | `user.id` only (no RFPO) |
| 1017 | `record_approval_action()` — requestor notify | `approval_notification` | `instance.rfpo.id`, `.project_id`, `.consortium_id`, `.team_id` |
| 1044 | `record_approval_action()` — next approver | `approval_notification` | Same as above |
| 1169 | `bulk_approval_action()` — requestor notify | `approval_notification` | `inst.rfpo.id`, `.project_id`, `.consortium_id`, `.team_id` |
| 1182 | `bulk_approval_action()` — next approver | `approval_notification` | Same as above |
| 1383 | `submit_for_approval()` — first approver | `approval_notification` | `rfpo.id`, `.project_id`, `.consortium_id`, `.team_id` |
| 1550 | `reassign_approval_action()` — new approver | `approval_notification` | `action.instance.rfpo.*` |
| — | _future_ `send_user_added_to_project_email()` | `user_added_to_project` | Not wired up — excluded from Phase 1 |

### `custom_admin.py` — 2 call sites

| Line | Function | Email Type | Context Available |
|---|---|---|---|
| 984 | `_notify_pending_approvers()` | `approval_notification` | `rfpo.id`, `.project_id`, `.consortium_id`, `.team_id` |
| 2837 | `_create_user_internal()` | `welcome` | `user.id` only (no RFPO) |

### Context dict pattern for each type:

```python
# Approval notifications (all 8 sites):
context = {
    "rfpo_id": rfpo.id,
    "project_id": rfpo.project_id,
    "consortium_id": rfpo.consortium_id,
    "team_id": rfpo.team_id,
    "triggered_by_user_id": current_user_id,  # from JWT or session
}

# Password changed (1 site):
context = {
    "triggered_by_user_id": user.id,
}

# Welcome email (1 site):
context = {
    "triggered_by_user_id": admin_user_id,  # admin who created the account
}
```

---

## Implementation Plan

### Phase 1: Model & Logging Hook

**File: `models.py`**
- Add `EmailLog` model with all columns, indexes, relationships, `to_dict()`, JSON getter/setters
- Import in `sqlalchemy_db_init.py` (becomes model #19)

**File: `email_service.py`**
1. Add `context`, `email_type`, `template_name` fields to `FailedEmail` dataclass
2. Add `context`, `email_type`, `template_name` parameters to `send_email()` signature
3. Add `context`, `email_type` parameters to `send_templated_email()` — propagate to `send_email()`
4. Add `context` parameter to each typed send method (`send_approval_notification`, `send_welcome_email`, `send_password_changed_email`)
5. Update module-level convenience wrappers to forward `context`
6. Capture test-mode state (original recipients) before redirect
7. Add `_log_email()` private method (see implementation above)
8. Call `_log_email()` in `send_email()` after success, failure, and enqueue
9. Thread `context` through `_enqueue_failed()` → `retry_failed()` → `send_email()`

**File: `simple_api.py`** — Update 8 call sites to pass `context={}`:
- Lines 709, 1017, 1044, 1169, 1182, 1383, 1550 (see inventory above)

**File: `custom_admin.py`** — Update 2 call sites to pass `context={}`:
- Lines 984, 2837 (see inventory above)

**Database migration:**
- `db.create_all()` creates the new `email_logs` table (no existing tables affected)
- For Azure: safe — only adds a new table, no ALTER TABLE needed

### Phase 2: Admin UI

**File: `custom_admin.py`** — Three new routes:

#### Route: `GET /admin/email-log`
- List view with server-side pagination
- Query parameters: `page`, `per_page`, `search`, `status`, `email_type`, `consortium_id`, `project_id`, `date_from`, `date_to`
- Default sort: newest first (`created_at DESC`)
- Display columns: Status icon, Email Type, Subject, To, RFPO ID, Project, Consortium, Timestamp
- Color-coded status badges: green (sent), red (failed), yellow (queued), blue (retried)
- Test-mode indicator icon on redirected emails

#### Route: `GET /admin/email-log/<int:log_id>`
- Detail view showing full email record
- Links to related RFPO, Project, Consortium, Team — with **null checks** (entities may be deleted)
- Body preview display in scrollable container
- Error message display (for failed emails)
- Test-mode section showing original recipients if applicable
- "Resend" button (POST) for failed emails

#### Route: `POST /admin/email-log/<int:log_id>/resend`
- Re-trigger the original email using stored parameters
- Create a new `EmailLog` entry for the retry attempt
- Update `retry_count` on original entry
- Resend uses **original recipients** (not test-mode redirect address)
- Requires `GOD` or `RFPO_ADMIN` permission

#### Route: `GET /admin/email-log/export`
- Export filtered results to CSV
- Respects current filter parameters
- Streams response (no memory issues on large datasets)

**File: `templates/admin/email_log.html`** — New template:
- Table with sortable columns
- Filter panel (collapsible top bar):
  - Status dropdown: All, Sent, Failed, Queued, Retried
  - Email Type dropdown: All, Approval Notification, Welcome, Password Changed, Approval Complete
  - Consortium dropdown (populated from DB)
  - Project dropdown (populated from DB, filtered by consortium)
  - Date range picker (From / To)
  - Free-text search (searches subject, to_emails, RFPO ID)
- Pagination controls (10 / 25 / 50 / 100 per page)
- Export to CSV button
- Summary stats banner: Total Sent, Total Failed, Sent Today

**File: `templates/admin/email_log_detail.html`** — New template:
- Full record display in card layout
- Related entity links (with null guards for deleted entities)
- Body preview in scrollable container
- Action buttons (Resend for failed)

**Navigation:**
- Add "Email Log" link to admin sidebar/nav under a "System" section
- Badge showing count of failed emails in last 24 hours

---

## Search Capabilities

| Search Field | Method |
|---|---|
| Subject line | `ILIKE '%term%'` |
| Recipient email | `ILIKE '%term%'` on `to_emails` text column |
| RFPO ID (display ID) | Join to `rfpos` table, match `rfpo_id` column |
| Sender email | `ILIKE '%term%'` |
| Error message | `ILIKE '%term%'` (failed emails only) |

Combined search: single search box queries subject, to_emails, and RFPO display ID simultaneously using OR conditions.

---

## Filter Combinations

Filters are additive (AND logic). All filters work together:
- Status + Email Type + Consortium + Date Range
- Example: "Show all **failed** **approval_notification** emails for **USCAR** consortium in the **last 7 days**"

---

## API Considerations

The email log is an **admin-only feature**. No API endpoints needed for the user app. All routes are in `custom_admin.py` behind `@login_required`.

If API access is needed later, add to `api/admin_routes.py` with GOD/RFPO_ADMIN permission check.

---

## Testing Checklist

### Phase 1: Model & Logging
- [ ] `EmailLog` model creates table successfully via `db.create_all()`
- [ ] `send_email()` logs successful sends with correct status and provider
- [ ] `send_email()` logs failures with error_message populated and **sanitized** (no stack traces)
- [ ] `send_templated_email()` passes template_name and email_type through to log
- [ ] All 4 active email types populate context fields correctly
- [ ] `_log_email()` gracefully handles missing Flask app context (logs to Python logger instead)
- [ ] `_log_email()` failure does NOT prevent email delivery
- [ ] Test-mode emails record `test_mode=True` and `original_recipients` with real addresses
- [ ] Resend uses original recipients, not test-mode redirect address
- [ ] FailedEmail retry preserves context (rfpo_id, project_id, etc. not NULL on retry log)
- [ ] Error messages truncated to 1024 chars

### Phase 2: Admin UI
- [ ] Admin list view loads with empty database (no errors)
- [ ] Pagination works (verify page 2+ with 50+ records)
- [ ] Each filter (status, type, consortium, project, date range) works independently
- [ ] Combined filters work correctly
- [ ] Free-text search matches subject, recipient, and RFPO ID
- [ ] Detail view displays all fields and links to related entities
- [ ] Detail view handles deleted RFPO/Team/User gracefully (no crashes, shows "Deleted" text)
- [ ] Resend button re-sends a failed email and creates new log entry
- [ ] CSV export works with filters applied
- [ ] Timestamps display in Eastern time (using `|est` filter)
- [ ] Test-mode emails visually distinguished in list view
- [ ] Azure deployment: new table created without affecting existing data

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Logging inside `send_email()` fails and breaks email delivery | `_log_email()` wrapped in try/except — never raises |
| No Flask app context during background retry | `_log_email()` checks `has_app_context()` before DB write; falls back to Python logger |
| Large body_preview bloats database | Truncate to 500 chars; never store full HTML |
| Error messages contain sensitive stack traces | Sanitize: `str(error)[:1024]` — exception message only, no traceback |
| Email log table grows unbounded | Phase 3 (future): admin UI purge for entries older than N days; index on `created_at` |
| In-memory retry queue lost on container restart | Accepted limitation; `_log_email()` records initial failure as `status="queued"` before enqueue, so audit trail exists even if retry never happens |
| Related entity deleted after email sent | FKs use `SET NULL` on delete; templates use null guards; detail view shows "Entity deleted" |
| Test-mode emails confuse audit trail | `test_mode` boolean flag + `original_recipients` JSON column; list view shows test badge |
| Connection pool exhaustion during burst sends | `_log_email()` catches DB errors and falls back to file logger; email delivery unaffected |

---

## Estimated Effort

| Phase | Files Changed | New Files |
|---|---|---|
| Phase 1: Model + Logging | `models.py`, `email_service.py`, `simple_api.py`, `custom_admin.py`, `sqlalchemy_db_init.py` | — |
| Phase 2: Admin UI | `custom_admin.py` | `templates/admin/email_log.html`, `templates/admin/email_log_detail.html` |

---

## Dependencies

- No new Python packages required
- Uses existing admin template patterns (Bootstrap 5)
- Uses existing `|est` Jinja filter for Eastern time display
- Uses existing ACS / SMTP email infrastructure (no provider changes)

---

## Review Resolution Log

| # | Finding | Severity | Resolution |
|---|---|---|---|
| 1 | FailedEmail dataclass loses context on retry | Critical | Added `context`, `email_type`, `template_name` fields to dataclass; thread through retry path |
| 2 | `send_user_added_to_project_email` never called | Critical | Excluded from scope; documented as not wired up; 4 active email types (not 5) |
| 3 | Context dict not passed at any call site | Critical | Full call site inventory added (10 sites); exact signatures specified for all methods |
| 4 | Test-mode email redirect not addressed | Important | Added `test_mode` and `original_recipients` columns; capture before redirect |
| 5 | In-memory retry queue not persisted | Important | Accepted; `_log_email()` records `status="queued"` before enqueue for audit trail |
| 6 | Missing app context handling | Important | `_log_email()` checks `has_app_context()`; falls back to Python logger |
| 7 | Deleted related entities crash detail view | Important | FKs use `SET NULL`; templates use null guards |
| 8 | Missing model fields | Important | Added `test_mode`, `original_recipients`, `triggered_by_user_id` index, `template_name` index |
| 9 | Context passing approach fragile | Important | Accepted with documentation; all call sites enumerated to reduce miss risk |
| 10 | Query performance gaps | Important | Added indexes on `triggered_by_user_id` and `template_name` |
| 11 | Admin UI feasibility | Approved | Existing template patterns confirm feasibility |
| 12 | Error message sanitization | Important | `error_message` capped at `String(1024)`; no stack traces stored |
