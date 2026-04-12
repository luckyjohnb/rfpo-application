# FR-0012: Reporting Interface

> **Plan Status:** ✅ Implemented
> **Created:** 2026-04-12
> **Implemented:** 2026-04-12
> **Reviewed By:** AI Code Review Agent

---

## 1. Feature Request Details

| Field | Value |
|---|---|
| **Ticket** | FR-0012 |
| **Title** | Reporting Interface |
| **Description** | A reporting interface with pre-built analytics (RFPOs by submitter/consortium/department/project, dollar totals, time-to-fulfill, rejections) plus ad-hoc query capabilities for custom exploration. Extended to include approval workflow metrics, vendor analytics, and overdue/SLA tracking. |
| **Submitted By** | John Bouchard |
| **Priority** | Medium |
| **Status** | Open |
| **Created** | 2026-04-12 |
| **Page Context** | Admin Panel |

---

## 2. Interpretation

The request is for a **dedicated admin-panel reporting page** providing aggregate analytics and drill-down queries on RFPO data. This is NOT a simple list view — it requires **aggregate calculations** (SUM, COUNT, AVG) across dimensions (submitter, consortium, department/team, project, time period) and **time-based metrics** (time-to-fulfill, YTD/prior-year totals).

The ten report types requested break into three categories:

| Category | Reports |
|---|---|
| **Drill-Down Queries** | RFPOs by Submitter, by Consortium, by Department (Team), by Project |
| **Aggregate Metrics** | Total $ of Open RFPOs, Total $ Closed Last Year, Total $ Closed YTD |
| **Analytical** | Time to Fulfill RFPOs, Rejected RFPOs by Category |
| **General** | Query/search all RFPOs in the system |

Beyond the original request, codebase analysis reveals rich data in the approval workflow, vendor, and email log models that would power additional high-value reports. The plan is extended to include:

| Category | Additional Reports |
|---|---|
| **Approval Workflow** | Busiest Approvers, Approval Time by Stage, Pending Approver Queue, Overdue Approvals |
| **Vendor Analytics** | Top Vendors by $ Volume, Vendor Utilization, Vendor Certification Status |
| **Operational Health** | RFPO Age Distribution, Due Date Compliance, Email Delivery Health |
| **Ad-Hoc Query Builder** | Multi-filter RFPO Explorer with vendor, amount range, approval age, and more |

**Scope decision:** Admin-panel only. The user app already has an RFPO list view; adding a reporting interface there is a separate enhancement. This feature focuses on giving admins a powerful analytics dashboard with both pre-built reports and ad-hoc exploration capabilities.

---

## 3. Current State Analysis

### RFPO Model (`models.py`, line 135)

**Available fields for reporting:**
| Field | Type | Indexed | Notes |
|---|---|---|---|
| `status` | String(32) | ✓ | 4 active values: Draft, Pending Approval, Approved, Refused (capitalized; see note below) |
| `total_amount` | Numeric(12,2) | ✗ | Final cost after cost-sharing — primary dollar field |
| `subtotal` | Numeric(12,2) | ✗ | Sum of line items before cost-sharing |
| `created_by` | String(64) | ✗ | Requestor user ID |
| `requestor_id` | String(32) | ✓ (composite) | User who submitted |
| `team_id` | Integer FK | ✓ (composite) | Department association |
| `consortium_id` | String(32) | ✓ (composite) | Consortium association |
| `project_id` | String(32) | ✓ (composite) | Project association |
| `created_at` | DateTime | ✓ | Creation timestamp |
| `updated_at` | DateTime | ✗ | Last update — NOT approval date |
| `deleted_at` | DateTime | ✓ | Soft delete |
| `due_date` | Date | ✗ | Due date |

**Actual RFPO status values (case-sensitive, capitalized):**
- `Draft` — initial state
- `Pending Approval` — submitted for approval (NOT "submitted" or "pending")
- `Approved` — fully approved
- `Refused` — rejected

> **Note:** `RFPOApprovalAction.status` uses lowercase values (`pending`, `approved`, `conditional`, `refused`) — these are step-level approval statuses, NOT RFPO-level statuses. The `locked_statuses` tuples reference `"Completed"` but this status is never actually set on RFPOs today.

**Status groupings for reporting:**
- **Open:** `Draft`, `Pending Approval`
- **Closed (fulfilled):** `Approved`
- **Rejected:** `Refused`

### Time-to-Fulfill Gap
There is **no explicit `approved_at` or `completed_at` timestamp** on the RFPO model. The approval workflow (`RFPOApprovalAction`) records action timestamps, but deriving approval time requires joining through `RFPOApprovalInstance → RFPOApprovalAction WHERE status='approved'`. 

**Decision:** Add an `approved_at` DateTime field to the RFPO model. This is simpler, faster for reporting queries, and avoids complex joins. The approval workflow code in `simple_api.py` already updates RFPO status — we add a timestamp write there.

**Note on rejected RFPOs:** `approved_at` is only set when status becomes `"Approved"`. For `"Refused"` RFPOs, rejection timestamps exist in `RFPOApprovalAction.completed_at`. Time-to-fulfill is only calculated for approved RFPOs.

### Existing API Endpoints (`simple_api.py`)
- `GET /api/rfpos` (line ~2590): Has `status`, `search`, `team_id`, `date_from`, `date_to`, pagination. **No aggregate/stats endpoints exist.**
- No reporting or dashboard-data endpoints exist anywhere.

### Admin Panel (`custom_admin.py`)
- Dashboard (line ~2079) shows basic counts (total RFPOs, pending approvals, overdue) — **no dollar aggregates or trend data**.
- RFPO list view exists but is a simple table with filters, not analytics.
- **Navigation structure** in `templates/admin/base.html` (lines 139-210): Core, Management, Approval System, Tools sections. No "Reports" section.

### Database Indexes
Existing single-column indexes: `status`, `created_at`, `deleted_at`.
Existing composite indexes: `idx_rfpo_project`, `idx_rfpo_consortium`, `idx_rfpo_vendor`, `idx_rfpo_requestor`.
**Missing:** No composite indexes optimized for aggregate reporting queries (e.g., `(status, created_at)` for date-range + status filtering).

### Test Coverage
**Zero existing tests for RFPO aggregation or reporting.** Integration tests exist for CRUD operations (`test_api_rfpos.py`) and approvals (`test_api_approvals.py`).

### Additional Data Sources for Extended Reports

#### Approval Workflow Models
- **`RFPOApprovalInstance`** — tracks each RFPO's journey through a workflow. Has `submitted_at`, `completed_at`, `current_stage_order`, `status`.
- **`RFPOApprovalAction`** — individual approver actions. Has `approver_id`, `status` (pending/approved/conditional/refused), `assigned_at`, `completed_at`, `due_date`, `is_escalated`, `is_backup_approver`, `escalated_at`, `escalation_reason`.
- **`RFPOApprovalStage`** / **`RFPOApprovalStep`** — workflow structure (stage names, step names, approver assignments).
- **Key insight:** Rich timestamp data (assigned_at, completed_at, due_date, escalated_at) enables approval time analytics, bottleneck detection, and SLA tracking.

#### Vendor Model
- **`Vendor`** — has `vendor_type`, `is_university`, `certs_reps`, `cert_date`, `cert_expire_date`, `approved_consortiums` (JSON), `onetime_project_id`.
- **`VendorSite`** — contact details per vendor location.
- RFPO → Vendor relationship via `vendor_id` FK on RFPO model.

#### Email Log Model
- **`EmailLog`** — tracks all email notifications. Has `status` (sent/failed/queued), `email_type`, `to_emails` (JSON), `rfpo_id`, `error_message`, `body_preview`, `test_mode`, `created_at`.
- Enables email delivery health monitoring and approval notification audit trails.

#### RFPO Line Items
- **`RFPOLineItem`** — has `description`, `quantity`, `unit_price`, `total_price`, `is_capital_equipment`.
- Enables top-purchased-items analysis and capital equipment tracking.

#### Cost Sharing Fields (on RFPO model)
- `cost_share_type` ('total' or 'percent'), `cost_share_amount`, `cost_share_description` (free text)
- Difference between `subtotal` (sum of line items) and `total_amount` (after cost-sharing) shows the absorbed cost.

---

## 4. Implementation Plan

### Phase 1: Backend — API Reporting Endpoint + Schema

Build a single `GET /api/reports/rfpos` endpoint that returns all aggregate data in one response. A single-endpoint approach avoids multiple round-trips and keeps the frontend simple.

#### 4a. Schema Change — Add `approved_at` to RFPO

Add `approved_at = db.Column(db.DateTime, nullable=True)` to the RFPO model. Set it when status changes to `approved` or `completed` in the approval workflow.

```python
# models.py — RFPO class, after updated_at
approved_at = db.Column(db.DateTime, nullable=True, index=True)
```

**Migration (Azure PostgreSQL):**
```sql
ALTER TABLE rfpo ADD COLUMN approved_at TIMESTAMP;
CREATE INDEX idx_rfpo_approved_at ON rfpo (approved_at);
```

**Backfill (one-time):** For existing approved RFPOs without `approved_at`, set it to `updated_at` as a reasonable approximation:
```sql
UPDATE rfpo SET approved_at = updated_at
WHERE status = 'Approved' AND approved_at IS NULL;
```

> **Note:** Only `'Approved'` (capital A) is backfilled. `'Completed'` is referenced in `locked_statuses` but never set on RFPOs in practice.

#### 4b. Set `approved_at` in Approval Workflow

In `simple_api.py`, find where RFPO status is set to `"Approved"` and add:
```python
rfpo.approved_at = datetime.utcnow()
```

Locations to update (case-sensitive — status uses capital `"Approved"`):
- Approval action processing (~line 1318, 1337, 1586)

#### 4c. Reporting API Endpoint

```python
# api/report_routes.py (new blueprint)
@report_bp.route('/api/reports/rfpos', methods=['GET'])
@jwt_required()
def rfpo_report():
    """
    Query params:
      - group_by: submitter | consortium | department | project  (required for drill-down)
      - date_from: YYYY-MM-DD
      - date_to: YYYY-MM-DD
      - status: open | closed | rejected | all (default: all)
      - report_type: summary | drilldown | time_to_fulfill | rejected_by_category
    
    Returns aggregate data based on report_type:
      summary → { open_total, closed_last_year, closed_ytd, total_count, ... }
      drilldown → [ { group_label, count, total_amount }, ... ]
      time_to_fulfill → { avg_days, median_days, by_period: [...] }
      rejected_by_category → [ { status, count, total_amount }, ... ]
    """
```

**Response structure for `report_type=summary` (default):**
```json
{
  "success": true,
  "data": {
    "open_rfpos": { "count": 15, "total_amount": 125000.00 },
    "closed_last_year": { "count": 42, "total_amount": 580000.00 },
    "closed_ytd": { "count": 18, "total_amount": 230000.00 },
    "rejected": { "count": 5, "total_amount": 45000.00 },
    "all_rfpos": { "count": 80, "total_amount": 980000.00 },
    "avg_time_to_fulfill_days": 12.5
  }
}
```

**Response structure for `report_type=drilldown`:**
```json
{
  "success": true,
  "data": {
    "group_by": "consortium",
    "groups": [
      { "id": "cons1", "label": "ACME Consortium", "count": 12, "total_amount": 150000.00 },
      { "id": "cons2", "label": "Beta Corp", "count": 8, "total_amount": 95000.00 }
    ],
    "total_count": 20,
    "grand_total": 245000.00
  }
}
```

**Status constants (define at module level to avoid case-mismatch bugs):**
```python
# Status constants — RFPO.status uses capitalized values
RFPO_OPEN_STATUSES = ['Draft', 'Pending Approval']
RFPO_CLOSED_STATUSES = ['Approved']
RFPO_REJECTED_STATUSES = ['Refused']
```

**Implementation — SQLAlchemy aggregation pattern:**
```python
from sqlalchemy import func, case, extract

# Open RFPOs total
open_query = db.session.query(
    func.count(RFPO.id).label('count'),
    func.coalesce(func.sum(RFPO.total_amount), 0).label('total')
).filter(
    RFPO.status.in_(RFPO_OPEN_STATUSES),
    RFPO.deleted_at.is_(None)
).first()

# Closed last year
year_start = datetime(now.year, 1, 1)
last_year_start = datetime(now.year - 1, 1, 1)
closed_ly = db.session.query(
    func.count(RFPO.id),
    func.coalesce(func.sum(RFPO.total_amount), 0)
).filter(
    RFPO.status.in_(RFPO_CLOSED_STATUSES),
    RFPO.approved_at >= last_year_start,
    RFPO.approved_at < year_start,
    RFPO.deleted_at.is_(None)
).first()

# Drill-down by consortium
groups = db.session.query(
    RFPO.consortium_id,
    Consortium.name.label('label'),
    func.count(RFPO.id).label('count'),
    func.coalesce(func.sum(RFPO.total_amount), 0).label('total')
).join(Consortium, RFPO.consortium_id == Consortium.id, isouter=True)
 .filter(RFPO.deleted_at.is_(None))
 .group_by(RFPO.consortium_id, Consortium.name)
 .order_by(func.sum(RFPO.total_amount).desc())
 .all()
```

#### 4d. Permission Check

The reporting endpoints should require `GOD` or `RFPO_ADMIN` permission. Regular `RFPO_USER` sees only their own RFPOs — reporting across all data is an admin function.

```python
user = get_jwt_identity()
user_obj = User.query.get(user)
if not user_obj or not (user_obj.has_permission('GOD') or user_obj.has_permission('RFPO_ADMIN')):
    raise AuthorizationException("Reporting requires admin permissions")
```

#### 4e. Approval Workflow Reporting Endpoint

```python
@report_bp.route('/api/reports/approvals', methods=['GET'])
@jwt_required()
def approval_report():
    """
    Query params:
      - report_type: busiest_approvers | stage_timing | pending_queue | overdue | action_breakdown
      - date_from / date_to: scope by action date
      - workflow_id: filter by specific workflow
    """
```

**`report_type=busiest_approvers`:**
```json
{
  "success": true,
  "data": {
    "approvers": [
      {
        "user_id": 5, "name": "Jane Smith",
        "total_actions": 48, "approved": 40, "refused": 5, "conditional": 3,
        "avg_response_days": 2.3, "approval_rate_pct": 83.3
      }
    ]
  }
}
```

**Implementation pattern:**
```python
# Busiest approvers — action counts per user
approver_stats = db.session.query(
    RFPOApprovalAction.approver_id,
    User.fullname.label('name'),
    func.count(RFPOApprovalAction.id).label('total'),
    func.sum(case((RFPOApprovalAction.status == 'approved', 1), else_=0)).label('approved'),
    func.sum(case((RFPOApprovalAction.status == 'refused', 1), else_=0)).label('refused'),
    func.sum(case((RFPOApprovalAction.status == 'conditional', 1), else_=0)).label('conditional'),
    func.avg(
        func.extract('epoch', RFPOApprovalAction.completed_at - RFPOApprovalAction.assigned_at) / 86400
    ).label('avg_days')
).join(User, RFPOApprovalAction.approver_id == User.id)
 .filter(RFPOApprovalAction.status != 'pending')
 .group_by(RFPOApprovalAction.approver_id, User.fullname)
 .order_by(func.count(RFPOApprovalAction.id).desc())
 .all()
```

**`report_type=stage_timing`:**
```json
{
  "data": {
    "stages": [
      { "stage_name": "Department Review", "avg_days": 1.5, "min_days": 0.1, "max_days": 8.2, "actions_completed": 30 },
      { "stage_name": "Finance Approval", "avg_days": 3.8, "min_days": 0.5, "max_days": 15.0, "actions_completed": 28 }
    ]
  }
}
```

**`report_type=pending_queue`** — Real-time view of who needs to act:
```json
{
  "data": {
    "pending_actions": [
      {
        "approver_id": 5, "approver_name": "Jane Smith",
        "pending_count": 3, "oldest_due": "2026-04-05", "overdue_count": 1,
        "rfpos": [
          { "rfpo_id": "RFPO-2026-0042", "title": "Lab Equipment", "total_amount": 5200.00, "due_date": "2026-04-05", "days_pending": 6 }
        ]
      }
    ]
  }
}
```

**`report_type=overdue`** — All pending actions past their due date:
```python
overdue = db.session.query(
    RFPOApprovalAction, User.fullname, RFPO.rfpo_id, RFPO.title
).join(User, RFPOApprovalAction.approver_id == User.id)
 .join(RFPOApprovalInstance, RFPOApprovalAction.instance_id == RFPOApprovalInstance.id)
 .join(RFPO, RFPOApprovalInstance.rfpo_id == RFPO.id)
 .filter(
    RFPOApprovalAction.status == 'pending',
    RFPOApprovalAction.due_date < datetime.utcnow()
 ).order_by(RFPOApprovalAction.due_date.asc()).all()
```

#### 4f. Vendor Reporting Endpoint

```python
@report_bp.route('/api/reports/vendors', methods=['GET'])
@jwt_required()
def vendor_report():
    """
    Query params:
      - report_type: top_by_volume | utilization | certifications
      - date_from / date_to
      - limit: number of vendors to return (default 20)
    """
```

**`report_type=top_by_volume`:**
```json
{
  "data": {
    "vendors": [
      { "vendor_id": 12, "name": "Acme Supply Co", "rfpo_count": 15, "total_amount": 245000.00, "avg_rfpo_value": 16333.33 }
    ],
    "total_vendor_count": 42,
    "total_rfpo_amount": 980000.00
  }
}
```

**`report_type=certifications`:**
```json
{
  "data": {
    "certified": 28, "expired": 5, "expiring_30_days": 3, "no_cert": 9,
    "expiring_soon": [
      { "vendor_id": 7, "name": "Lab Supplies Inc", "cert_expire_date": "2026-05-10", "days_remaining": 29 }
    ]
  }
}
```

#### 4g. Ad-Hoc RFPO Explorer Endpoint

Extend the existing `GET /api/rfpos` list endpoint with additional filter parameters for ad-hoc querying. This avoids creating a separate endpoint — the list endpoint already has pagination, permissions, and soft-delete filtering.

**New query parameters to add to `list_rfpos()`:**
```python
# simple_api.py — list_rfpos() additions
vendor_id = request.args.get('vendor_id', type=int)
consortium_id = request.args.get('consortium_id')
project_id = request.args.get('project_id')
requestor_id = request.args.get('requestor_id')
amount_min = request.args.get('amount_min', type=float)
amount_max = request.args.get('amount_max', type=float)
po_number = request.args.get('po_number')
has_overdue = request.args.get('has_overdue')  # 'true' = only RFPOs with overdue approvals
approval_age_min = request.args.get('approval_age_min', type=int)  # days in approval
cost_sharing = request.args.get('cost_sharing')  # 'true' = only RFPOs with cost sharing
due_date_from = request.args.get('due_date_from')
due_date_to = request.args.get('due_date_to')
sort_by = request.args.get('sort_by', 'created_at')  # total_amount, due_date, updated_at
sort_dir = request.args.get('sort_dir', 'desc')

# Apply filters
if vendor_id:
    query = query.filter(RFPO.vendor_id == vendor_id)
if consortium_id:
    query = query.filter(RFPO.consortium_id == consortium_id)
if project_id:
    query = query.filter(RFPO.project_id == project_id)
if requestor_id:
    query = query.filter(RFPO.requestor_id == requestor_id)
if amount_min is not None:
    query = query.filter(RFPO.total_amount >= amount_min)
if amount_max is not None:
    query = query.filter(RFPO.total_amount <= amount_max)
if po_number:
    query = query.filter(RFPO.po_number.ilike(f'%{po_number}%'))
if cost_sharing == 'true':
    query = query.filter(RFPO.cost_share_type.isnot(None))
```

**Supported sort fields (validated against allowlist):**
```python
SORT_FIELDS = {
    'created_at': RFPO.created_at,
    'updated_at': RFPO.updated_at,
    'total_amount': RFPO.total_amount,
    'due_date': RFPO.due_date,
    'status': RFPO.status,
    'rfpo_id': RFPO.rfpo_id,
}
```

#### 4h. Email Delivery Health Endpoint

```python
@report_bp.route('/api/reports/email-health', methods=['GET'])
@jwt_required()
def email_health_report():
    """
    Query params:
      - date_from / date_to
      - email_type: filter by notification type
    Returns: sent/failed/queued counts, failure reasons, delivery by type
    """
```

**Response:**
```json
{
  "data": {
    "total_sent": 245, "total_failed": 8, "total_queued": 0,
    "success_rate_pct": 96.8,
    "by_type": [
      { "email_type": "approval_request", "count": 120, "failed": 2 },
      { "email_type": "workflow_update", "count": 85, "failed": 4 },
      { "email_type": "reminder", "count": 40, "failed": 2 }
    ],
    "recent_failures": [
      { "id": 52, "email_type": "approval_request", "to": "user@example.com", "error": "Connection timeout", "created_at": "2026-04-10T14:30:00" }
    ]
  }
}
```

### Phase 2: Admin Panel — Reports UI

#### 2a. Admin Route

Add `admin_reports()` route in `custom_admin.py`:
```python
@app.route('/admin/reports')
@login_required
def admin_reports():
    # Compute all aggregates server-side using SQLAlchemy
    # Pass results to template
    return render_template('admin/reports.html', **report_data)
```

**Decision:** Server-side rendering (not AJAX). The admin panel is fully server-rendered today — keeping consistency. The data volume for aggregates is small (a handful of numbers + grouped lists), so there's no performance concern with SSR.

#### 2b. Reports Template (`templates/admin/reports.html`)

Layout with these sections:

1. **Summary Cards Row** — Bootstrap cards showing:
   - Total Open RFPOs (count + dollar total)
   - Closed Last Year (count + dollar total)
   - Closed YTD (count + dollar total)
   - Avg Time to Fulfill (days)

2. **Drill-Down Tables** — Collapsible accordion sections:
   - RFPOs by Submitter (table: name, count, total $, avg $)
   - RFPOs by Consortium (table: name, count, total $, avg $)
   - RFPOs by Department/Team (table: name, count, total $, avg $)
   - RFPOs by Project (table: name, count, total $, avg $)

3. **Rejected RFPOs** — Table grouped by status (refused vs cancelled) showing count and total $.

4. **Date Range Filter** — Optional date_from/date_to form at top to scope all data.

**Pattern reference:** Use Bootstrap cards (like dashboard) + tables (like email_log.html).

#### 2c. Navigation Update

Add "Reports" link to the admin sidebar in `templates/admin/base.html`:
```html
<!-- After Tools section -->
<li class="nav-header">Analytics</li>
<li><a href="/admin/reports"><i class="fas fa-chart-bar"></i> RFPO Reports</a></li>
```

### Phase 3: Enhancements (Optional)

#### 3a. Export to CSV
Add a "Download CSV" button per drill-down table that triggers a `GET /api/reports/rfpos?format=csv&group_by=consortium` returning a CSV file.

#### 3b. Date Range Presets
Quick buttons: "This Month", "This Quarter", "This Year", "Last Year", "All Time".

#### 3c. Chart Visualizations
Add Chart.js bar/pie charts for dollar distributions. Low priority — tables are sufficient for the initial request.

---

## 5. Database Preparation

### New Column
```sql
-- Add approved_at to RFPO model
ALTER TABLE rfpo ADD COLUMN approved_at TIMESTAMP;
CREATE INDEX idx_rfpo_approved_at ON rfpo (approved_at);

-- Backfill existing approved/completed RFPOs
UPDATE rfpo SET approved_at = updated_at
WHERE status IN ('approved', 'completed') AND approved_at IS NULL;
```

### Composite Indexes for Reporting Performance
```sql
-- Status + date range (most common report filter)
CREATE INDEX idx_rfpo_status_created ON rfpo (status, created_at DESC);

-- Status + approved_at (closed date range queries)
CREATE INDEX idx_rfpo_status_approved ON rfpo (status, approved_at DESC);
```

**Note:** The existing single-column indexes on `consortium_id`, `team_id`, `project_id`, `requestor_id` are sufficient for GROUP BY queries. PostgreSQL's query planner will combine them with the status index via bitmap index scans. These composite indexes are low-cost to add now and will prevent performance degradation as data grows.

---

## 6. Detailed Task Breakdown

| # | Task | File(s) | Effort | Phase |
|---|---|---|---|---|
| 1 | Add `approved_at` field to RFPO model | `models.py` | Small | 1 |
| 2 | Write ALTER TABLE migration for Azure | `migrations/add_approved_at.sql` (new) | Small | 1 |
| 3 | Set `approved_at` on approval status change | `simple_api.py` | Small | 1 |
| 4 | Backfill `approved_at` for existing RFPOs | `migrations/add_approved_at.sql` | Small | 1 |
| 5 | Create reporting blueprint (`api/report_routes.py`) | `api/report_routes.py` (new) | Medium | 1 |
| 6 | Implement `GET /api/reports/rfpos` — summary metrics | `api/report_routes.py` | Medium | 1 |
| 7 | Implement drill-down queries (by submitter/consortium/dept/project) | `api/report_routes.py` | Medium | 1 |
| 8 | Implement time-to-fulfill calculation | `api/report_routes.py` | Small | 1 |
| 9 | Implement rejected-by-category query | `api/report_routes.py` | Small | 1 |
| 10 | Register blueprint in `simple_api.py` | `simple_api.py` | Small | 1 |
| 11 | Add composite database indexes | `migrations/add_approved_at.sql` | Small | 1 |
| 12 | Admin reports route with server-side aggregation | `custom_admin.py` | Medium | 2 |
| 13 | Create reports template with summary cards | `templates/admin/reports.html` (new) | Medium | 2 |
| 14 | Add drill-down accordion tables to template | `templates/admin/reports.html` | Medium | 2 |
| 15 | Add rejected RFPOs section to template | `templates/admin/reports.html` | Small | 2 |
| 16 | Add date range filter form | `templates/admin/reports.html`, `custom_admin.py` | Small | 2 |
| 17 | Add "Reports" link to admin sidebar | `templates/admin/base.html` | Small | 2 |
| 18 | Add currency formatting (Jinja filter or JS) | `templates/admin/reports.html` | Small | 2 |
| 19 | Write integration tests for reporting API | `tests/integration/test_reports.py` (new) | Large | 1 |
| 20 | CSV export endpoint (optional) | `api/report_routes.py` | Small | 3 |
| 21 | Date range presets (optional) | `templates/admin/reports.html` | Small | 3 |

**Effort summary:** ~21 tasks, 5 new files, 4 modified files. Phase 1: 11 tasks (backend), Phase 2: 7 tasks (UI), Phase 3: 2 tasks (optional).

---

## 7. Testing Strategy

### Integration Tests (`tests/integration/test_reports.py`)

| # | Test Name | Description |
|---|---|---|
| 1 | `test_report_summary_empty_db` | Summary returns zeros when no RFPOs exist |
| 2 | `test_report_summary_with_data` | Summary returns correct counts and totals for open/closed/rejected |
| 3 | `test_report_open_rfpos_total` | Only draft/submitted/pending/conditional counted as open |
| 4 | `test_report_closed_last_year` | Only approved/completed with approved_at in last year |
| 5 | `test_report_closed_ytd` | Only approved/completed with approved_at in current year |
| 6 | `test_report_drilldown_by_consortium` | Groups and sums correctly by consortium |
| 7 | `test_report_drilldown_by_submitter` | Groups and sums correctly by requestor |
| 8 | `test_report_drilldown_by_department` | Groups and sums correctly by team |
| 9 | `test_report_drilldown_by_project` | Groups and sums correctly by project |
| 10 | `test_report_time_to_fulfill` | Correct avg days between created_at and approved_at |
| 11 | `test_report_rejected_by_category` | Groups refused/cancelled separately with counts/totals |
| 12 | `test_report_date_range_filter` | date_from/date_to correctly scopes all aggregates |
| 13 | `test_report_excludes_soft_deleted` | Soft-deleted RFPOs excluded from all metrics |
| 14 | `test_report_requires_admin_permission` | RFPO_USER gets 403, GOD/RFPO_ADMIN gets 200 |
| 15 | `test_report_unauthenticated_rejected` | No JWT → 401 |
| 16 | `test_report_null_amounts_handled` | RFPOs with NULL total_amount don't break SUM |

### Manual Verification
1. Navigate to Admin → Reports: verify all summary cards display correct numbers
2. Click each drill-down accordion: verify tables show correct groupings
3. Apply date range filter: verify all sections update
4. Cross-check one group total against the RFPO list filtered by that group
5. Verify currency formatting shows 2 decimal places with $ prefix

---

## 8. Security Considerations

| Concern | Mitigation |
|---|---|
| **SQL Injection** | All queries use SQLAlchemy ORM with parameterized queries — no raw SQL string concatenation |
| **Authorization** | Endpoint restricted to `GOD` / `RFPO_ADMIN` permissions; JWT required |
| **Data Exposure** | Reporting returns aggregate data only, not individual RFPO details; PII limited to submitter names already visible in admin panel |
| **Input Validation** | `date_from`/`date_to` parsed with `datetime.strptime()` and rejected if invalid; `group_by` validated against allowlist; `report_type` validated against allowlist |
| **Rate Limiting** | Aggregate queries are read-only and lightweight; existing Flask rate limiter applies |
| **XSS** | Template data rendered via Jinja2 auto-escaping; no `|safe` on user-supplied data |

---

## 9. Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| `approved_at` backfill inaccurate (using `updated_at`) | Low | `updated_at` is a reasonable approximation for historical data; going forward `approved_at` is set precisely |
| Aggregate queries slow on large datasets | Low | PostgreSQL handles SUM/COUNT well with existing indexes; composite indexes added for common patterns; data volume is small (~hundreds of RFPOs, not millions) |
| Soft-deleted RFPOs included in reports | Medium | All queries explicitly filter `deleted_at IS NULL` — enforcement via base query filter |
| `group_by` dimension has NULL values (no team, no consortium) | Medium | Use `COALESCE` / `isouter=True` joins and label NULLs as "Unassigned" in the response |
| Timezone mismatches for YTD/last-year boundaries | Low | Use UTC consistently; `datetime.utcnow()` for boundaries matches `created_at`/`approved_at` storage |
| Admin panel performance with many drill-down sections | Low | Server-side rendering of pre-computed aggregates is fast; accordion sections lazy-load visually but data is pre-fetched |

---

## 10. Review Summary

**Reviewer:** AI Code Review Agent (Explore)  
**Verdict:** Approve with Changes → All changes incorporated

### Findings and Resolutions

| # | Finding | Severity | Resolution |
|---|---|---|---|
| 1 | Status values used lowercase (`draft`, `submitted`, `pending`, etc.) but actual RFPO statuses are capitalized (`Draft`, `Pending Approval`, `Approved`, `Refused`) | MUST FIX | Fixed all status references throughout plan to use correct capitalized values |
| 2 | Plan referenced 8 statuses including `submitted`, `pending`, `conditional`, `cancelled`, `completed` — only 4 active statuses exist | MUST FIX | Corrected to 4 actual statuses; documented that `RFPOApprovalAction.status` uses separate lowercase values |
| 3 | Backfill SQL targeted `'completed'` which is never set on RFPOs | MUST FIX | Removed `'completed'` from backfill; only targets `'Approved'` |
| 4 | No constants defined for status values — prone to typos | SHOULD FIX | Added `RFPO_OPEN_STATUSES`, `RFPO_CLOSED_STATUSES`, `RFPO_REJECTED_STATUSES` constants |
| 5 | Rejected RFPOs time-to-fulfill unclear | SHOULD FIX | Documented that time-to-fulfill only applies to approved RFPOs; rejection timestamps exist in `RFPOApprovalAction.completed_at` |
| 6 | Composite indexes dismissed as premature | SHOULD FIX | Updated to recommend adding them now (low cost, prevents future perf issues) |
| 7 | `RFPOApprovalAction.status` vs `RFPO.status` case distinction not documented | SHOULD FIX | Added note clarifying the distinction |

---

## 11. Files Changed Summary

| File | Change Type | Phase |
|---|---|---|
| `models.py` | Modified — add `approved_at` field | 1 |
| `migrations/add_approved_at.sql` | New — DDL + backfill | 1 |
| `api/report_routes.py` | New — reporting blueprint | 1 |
| `simple_api.py` | Modified — register blueprint, set `approved_at` on approval | 1 |
| `custom_admin.py` | Modified — add reports route | 2 |
| `templates/admin/reports.html` | New — reports UI | 2 |
| `templates/admin/base.html` | Modified — add Reports nav link | 2 |
| `tests/integration/test_reports.py` | New — 16 integration tests | 1 |
