# Feature Plan: "Add from AI" — AI-Powered Line Item Extraction

> **Plan Status:** Reviewed & Approved (with changes incorporated)  
> **Created:** April 12, 2026  
> **Author:** AI Planning Agent  
> **Reviewed By:** AI Code Review Agent  

## 1. Feature Summary

Add an **"Add from AI"** button to the RFPO Create Stage 3 (Line Items) page. When clicked, a modal prompts the user to upload a document (invoice, quote, PO, etc.). The file is uploaded via the existing DOCUPLOAD pipeline into an `AIScanned` subfolder. Azure OpenAI GPT-4o then reads the document and extracts potential line items. The user reviews, edits, and prunes the extracted items before importing them into the RFPO.

### User Flow
```
1. User clicks "✨ Add from AI" button (next to existing "+ Add Line Item")
2. Modal opens with file upload area (drag & drop + browse)
3. User selects a file (PDF, image, Excel, CSV, Word doc)
4. File uploads to API → saved locally + pushed to DOCUPLOAD under AIScanned/
5. API sends document to Azure OpenAI GPT-4o for extraction
6. Modal shows extracted line items in an editable table:
   - Checkbox (select/deselect for import)
   - Description (editable text)
   - Quantity (editable number, default 1)
   - Unit Price (editable currency)
   - Calculated Total (auto)
7. User edits descriptions, adjusts prices, unchecks unwanted items
8. User clicks "Import Selected" → line items created via existing POST endpoint
9. Modal closes, line items table refreshes with new items
```

## 2. Architecture

### Separation of Concerns (per project rules)
- **User App (frontend)**: Modal UI, file selection, display extracted items, send import requests
- **API Layer**: Receives file upload, stores locally + DOCUPLOAD, calls Azure OpenAI, returns extracted items, creates line items
- **User App NEVER accesses the database directly** — all operations through API calls

### New API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/rfpos/<rfpo_id>/ai-scan/upload` | Upload file + extract line items via AI |

### Data Flow
```
Browser                    API (simple_api.py)              Azure OpenAI
  │                              │                              │
  ├── POST file ────────────────>│                              │
  │                              ├── Save locally               │
  │                              ├── Upload to DOCUPLOAD        │
  │                              │   (folder: AIScanned)        │
  │                              ├── Read file content ────────>│
  │                              │   (PDF→text, image→vision,   │
  │                              │    Excel→parsed rows)        │
  │                              │<── Extracted line items ─────│
  │<── JSON: extracted items ────│                              │
  │                              │                              │
  │  [User edits/prunes items]   │                              │
  │                              │                              │
  ├── POST each selected item ──>│                              │
  │   (existing line-items API)  ├── Create RFPOLineItem        │
  │<── Success ──────────────────│                              │
```

## 3. Detailed Task Breakdown

### Phase 1: API — AI Scan Endpoint

| # | Task | File(s) | Effort |
|---|------|---------|--------|
| 1.1 | Add Azure OpenAI config vars to `env_config.py` | `env_config.py` | Small |
| 1.2 | Create `ai_extractor.py` module — document parsing + OpenAI call | `ai_extractor.py` (new) | Large |
| 1.3 | Add `POST /api/rfpos/<rfpo_id>/ai-scan/upload` endpoint | `simple_api.py` | Medium |
| 1.4 | Add `.env` variables for Azure OpenAI | `.env`, `env.example` | Small |
| 1.5 | Add `AIUsageLog` model + budget enforcement | `models.py`, `ai_extractor.py` | Medium |

#### 1.1 — Environment Config (`env_config.py`)

Add Azure OpenAI settings using the project's `get_env()` helper (not raw `os.environ.get`):
```python
# Azure OpenAI
AZURE_OPENAI_ENDPOINT = get_env('AZURE_OPENAI_ENDPOINT', required=False)
AZURE_OPENAI_KEY = get_env('AZURE_OPENAI_KEY', required=False)
AZURE_OPENAI_DEPLOYMENT = get_env('AZURE_OPENAI_DEPLOYMENT', required=False) or 'gpt-4o'
AZURE_OPENAI_BUDGET_LIMIT = float(get_env('AZURE_OPENAI_BUDGET_LIMIT', required=False) or '100.00')
```

#### 1.2 — AI Extractor Module (`ai_extractor.py`)

New module responsible for:

**A. Document Content Extraction** — Convert uploaded file to text/images for GPT-4o:
- **PDF**: Use `PyPDF2` (already in project) to extract text. If text is minimal (scanned PDF), render pages as images and send via vision.
- **Images** (PNG, JPG, TIFF): Send directly to GPT-4o vision endpoint — it handles OCR natively.
- **Excel/CSV**: Use `openpyxl` or built-in `csv` to parse rows into structured text.
- **Word (.docx)**: Use `python-docx` (add to requirements) to extract text.

**B. GPT-4o Structured Extraction** — Call Azure OpenAI with:
```python
def extract_line_items(file_path: str, mime_type: str) -> list[dict]:
    """Extract line items from a document using Azure OpenAI GPT-4o.
    
    Returns list of:
        {"description": str, "quantity": int, "unit_price": float}
    """
```

**System prompt** for extraction:
```
You are a document analysis assistant. Extract all purchasable line items 
from the provided document. For each item, return:
- description: Brief item description
- quantity: Number of units (default 1 if not specified)
- unit_price: Price per unit in USD (numeric, no currency symbols)

Return ONLY a JSON array. If no items found, return [].
Do not invent items — only extract what is explicitly in the document.
```

**GPT-4o API call** using `openai` Python SDK with Azure configuration:
```python
from openai import AzureOpenAI

client = AzureOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_KEY,
    api_version="2024-12-01-preview"
)

# For text documents:
response = client.chat.completions.create(
    model=AZURE_OPENAI_DEPLOYMENT,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Extract line items from:\n\n{document_text}"}
    ],
    response_format={"type": "json_object"},
    temperature=0.1
)

# For images (scanned docs, photos):
response = client.chat.completions.create(
    model=AZURE_OPENAI_DEPLOYMENT,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "text", "text": "Extract all line items from this document image."},
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_image}"}}
        ]}
    ],
    response_format={"type": "json_object"},
    temperature=0.1
)
```

**Response parsing** with validation:
- Parse JSON array from response
- Validate each item has description (non-empty string), quantity (positive int), unit_price (non-negative float)
- Cap at 100 items max (safety limit)
- Return empty list on any parsing failure (don't crash)
- **Log token usage** from `response.usage` for cost tracking (prompt_tokens, completion_tokens)

**Timeout handling:**
- Set `timeout=60` on the OpenAI API call
- Catch `openai.APITimeoutError` and return empty list with a user-friendly warning message
- Catch `openai.RateLimitError` and return 429 to the caller

#### 1.5 — Budget Enforcement (`models.py` + `ai_extractor.py`)

**$100.00 spending cap** to prevent runaway costs during pre-production.

**A. New `AIUsageLog` model** in `models.py`:
```python
class AIUsageLog(db.Model):
    __tablename__ = "ai_usage_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    rfpo_id = db.Column(db.Integer, db.ForeignKey("rfpos.id"), nullable=True)
    operation = db.Column(db.String(50), nullable=False)  # e.g. "line_item_extraction"
    model_name = db.Column(db.String(50), nullable=False)  # e.g. "gpt-4o"
    prompt_tokens = db.Column(db.Integer, default=0)
    completion_tokens = db.Column(db.Integer, default=0)
    total_tokens = db.Column(db.Integer, default=0)
    estimated_cost_usd = db.Column(db.Numeric(10, 6), default=0)  # 6 decimal places for precision
    file_name = db.Column(db.String(256))
    items_extracted = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "rfpo_id": self.rfpo_id,
            "operation": self.operation,
            "model_name": self.model_name,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": float(self.estimated_cost_usd or 0),
            "file_name": self.file_name,
            "items_extracted": self.items_extracted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

**B. Cost calculation** in `ai_extractor.py`:
```python
# GPT-4o pricing (as of 2026)
COST_PER_1M_INPUT_TOKENS = 2.50   # $2.50 per 1M input tokens
COST_PER_1M_OUTPUT_TOKENS = 10.00  # $10.00 per 1M output tokens

def calculate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate estimated cost in USD from token counts."""
    input_cost = (prompt_tokens / 1_000_000) * COST_PER_1M_INPUT_TOKENS
    output_cost = (completion_tokens / 1_000_000) * COST_PER_1M_OUTPUT_TOKENS
    return round(input_cost + output_cost, 6)
```

**C. Budget check** — called BEFORE every AI scan:
```python
def check_budget() -> tuple[bool, float, float]:
    """Check if AI spending is within budget.
    Returns (within_budget, total_spent, budget_limit).
    """
    from models import AIUsageLog, db
    total_spent = db.session.query(
        db.func.coalesce(db.func.sum(AIUsageLog.estimated_cost_usd), 0)
    ).scalar()
    budget_limit = float(os.environ.get('AZURE_OPENAI_BUDGET_LIMIT', '100.00'))
    return (float(total_spent) < budget_limit, float(total_spent), budget_limit)
```

**D. Integration** in the API endpoint (step added to Phase 1.3 flow):
```python
# Step 0: Check budget BEFORE processing file
within_budget, spent, limit = check_budget()
if not within_budget:
    return jsonify({
        "success": False,
        "message": f"AI scanning budget exhausted. ${spent:.2f} of ${limit:.2f} used. Contact your administrator.",
        "budget_exceeded": True,
        "total_spent": float(spent),
        "budget_limit": float(limit)
    }), 429
```

**E. Log usage** after every successful extraction:
```python
# After GPT-4o call returns
usage_log = AIUsageLog(
    user_id=current_user.id,
    rfpo_id=rfpo_id,
    operation="line_item_extraction",
    model_name=AZURE_OPENAI_DEPLOYMENT,
    prompt_tokens=response.usage.prompt_tokens,
    completion_tokens=response.usage.completion_tokens,
    total_tokens=response.usage.total_tokens,
    estimated_cost_usd=calculate_cost(
        response.usage.prompt_tokens,
        response.usage.completion_tokens
    ),
    file_name=original_filename,
    items_extracted=len(extracted_items)
)
db.session.add(usage_log)
db.session.commit()
```

**F. Admin visibility** — Add `GET /api/ai-usage/summary` endpoint (admin-only):
```json
{
    "success": true,
    "total_spent_usd": 12.34,
    "budget_limit_usd": 100.00,
    "budget_remaining_usd": 87.66,
    "total_requests": 45,
    "total_tokens": 234567,
    "usage_by_user": [
        {"user_id": 1, "name": "John", "requests": 20, "cost": 5.67},
        {"user_id": 2, "name": "Jane", "requests": 25, "cost": 6.67}
    ]
}
```

#### 1.3 — API Endpoint (`simple_api.py`)

```python
@app.route("/api/rfpos/<int:rfpo_id>/ai-scan/upload", methods=["POST"])
@require_auth
def ai_scan_upload(rfpo_id):
    """Upload a document and extract line items using AI."""
```

**Flow:**
1. **Check AI budget** — call `check_budget()`. If exceeded, return 429 with spending details.
2. Validate RFPO exists (`RFPO.query.get(rfpo_id)` → 404 if not found)
3. **Validate user access** — user must be the RFPO requestor (`rfpo.requestor_id == current_user.id`) OR have admin role (`GOD` / `RFPO_ADMIN`). Return 403 otherwise.
4. **Validate RFPO status** — reject if status is in `('Pending Approval', 'Approved', 'Completed')` (same locked-status check as existing line item endpoints). Return 403.
5. Accept multipart file upload (same validations as existing upload: size, extension, magic bytes)
4. Generate UUID, save locally to `uploads/rfpos/{rfpo_id}/documents/AIScanned/{uuid}_{filename}`
5. Upload to DOCUPLOAD with `folder_path=f"rfpo/{rfpo_id}/AIScanned"`
6. Create `UploadedFile` record with `document_type="AIScanned"`
7. Call `ai_extractor.extract_line_items(file_path, mime_type)`
8. Return extracted items + file metadata

**Response:**
```json
{
    "success": true,
    "file": { "file_id": "...", "original_filename": "invoice.pdf" },
    "extracted_items": [
        {"description": "Widget A - Blue", "quantity": 10, "unit_price": 25.50},
        {"description": "Widget B - Red", "quantity": 5, "unit_price": 42.00}
    ],
    "item_count": 2,
    "cloud_upload": { "success": true, "folder_path": "rfpo/123/AIScanned" }
}
```

**Error cases:**
- No file provided → 400
- Invalid file type → 400
- RFPO locked → 403
- AI extraction fails → Return success with empty `extracted_items` + warning message
- Cloud upload fails → Log warning, continue (non-blocking, same as existing pattern)
- **Budget exceeded** → Return 429 with `budget_exceeded: true`, spent amount, and limit

**Timeout handling:**
- Azure OpenAI timeout: 60 seconds
- The API endpoint itself may take 10-30 seconds depending on document size
- The User App's `make_api_request` has a 10-second timeout — **this must be increased for this specific call** or the frontend should use `fetch()` directly with a longer timeout

### Phase 2: Frontend — Modal UI

| # | Task | File(s) | Effort |
|---|------|---------|--------|
| 2.1 | Add "Add from AI" button next to "+ Add Line Item" | `rfpo_create_stage3.html` | Small |
| 2.2 | Create AI scan modal HTML (upload + results table) | `rfpo_create_stage3.html` | Medium |
| 2.3 | JavaScript: file upload with progress indicator | `rfpo_create_stage3.html` | Medium |
| 2.4 | JavaScript: display extracted items in editable table | `rfpo_create_stage3.html` | Medium |
| 2.5 | JavaScript: import selected items via existing API | `rfpo_create_stage3.html` | Medium |

#### 2.1 — Button Placement

In the card header, add second button:
```html
<div class="card-header d-flex justify-content-between align-items-center">
    <h5 class="mb-0"><i class="fas fa-receipt"></i> Line Items <span class="badge bg-secondary" id="lineItemCount">0</span></h5>
    <div class="d-flex gap-2">
        <button class="btn btn-outline-info btn-sm" onclick="showAiScanModal()">
            <i class="fas fa-magic"></i> Add from AI
        </button>
        <button class="btn btn-primary btn-sm" onclick="showAddForm()">
            <i class="fas fa-plus"></i> Add Line Item
        </button>
    </div>
</div>
```

#### 2.2 — Modal Structure

Bootstrap 5 modal with two states:

**State 1: Upload**
```
┌──────────────────────────────────────────────┐
│  ✨ Add Line Items from AI                  ✕│
├──────────────────────────────────────────────┤
│                                              │
│  Upload a document (invoice, quote, PO)      │
│  and AI will extract line items for you.     │
│                                              │
│  ┌─────────────────────────────────────────┐ │
│  │     📄 Drag & drop file here            │ │
│  │        or click to browse               │ │
│  │                                         │ │
│  │  Supported: PDF, PNG, JPG, Excel, Word  │ │
│  └─────────────────────────────────────────┘ │
│                                              │
│  [Selected: invoice.pdf (2.1 MB)]            │
│                                              │
├──────────────────────────────────────────────┤
│                    [Cancel]  [Upload & Scan]  │
└──────────────────────────────────────────────┘
```

**State 2: Review & Edit** (after extraction)
```
┌──────────────────────────────────────────────────────┐
│  ✨ Review Extracted Line Items (5 found)            ✕│
├──────────────────────────────────────────────────────┤
│                                                      │
│  ☑ │ Description              │ Qty │ Unit Price     │
│  ──┼──────────────────────────┼─────┼───────────     │
│  ☑ │ [Widget A - Blue       ] │ [10]│ [$25.50  ]     │
│  ☑ │ [Widget B - Red        ] │ [ 5]│ [$42.00  ]     │
│  ☐ │ [Shipping & Handling   ] │ [ 1]│ [$15.00  ]     │
│  ☑ │ [Installation Service  ] │ [ 1]│ [$200.00 ]     │
│  ☑ │ [Extended Warranty     ] │ [ 1]│ [$75.00  ]     │
│                                                      │
│  ─────────────────────────────────────────────       │
│  Selected: 4 items │ Est. Total: $757.50             │
│                                                      │
│  ℹ️ Edit descriptions and prices as needed.          │
│     Uncheck items you don't want to import.          │
│                                                      │
├──────────────────────────────────────────────────────┤
│         [Cancel]  [Select All]  [Import Selected]    │
└──────────────────────────────────────────────────────┘
```

#### 2.3 — File Upload JavaScript

```javascript
async function uploadForAiScan() {
    const fileInput = document.getElementById('aiScanFile');
    const file = fileInput.files[0];
    if (!file) { showAlert('Please select a file', 'warning'); return; }

    const formData = new FormData();
    formData.append('file', file);

    // Show progress state
    showAiScanProgress(true);

    try {
        const response = await fetch(`/api/rfpos/${rfpoId}/ai-scan/upload`, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCsrfToken() },
            body: formData
        });
        const data = await response.json();

        if (data.success && data.extracted_items.length > 0) {
            displayExtractedItems(data.extracted_items);
        } else if (data.success && data.extracted_items.length === 0) {
            showAlert('No line items could be extracted from this document.', 'warning');
        } else {
            showAlert(data.message || 'AI scan failed', 'danger');
        }
    } catch (error) {
        showAlert(`Upload failed: ${error.message}`, 'danger');
    } finally {
        showAiScanProgress(false);
    }
}
```

**Note:** Uses raw `fetch()` instead of `makeApiCall()` because:
- `makeApiCall()` sets `Content-Type: application/json` which breaks `FormData`
- AI scan may take 15-30 seconds, exceeding normal timeout expectations
- We need custom progress indication

**Must include AbortController for timeout enforcement:**
```javascript
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 90000); // 90s

try {
    const response = await fetch(`/api/rfpos/${rfpoId}/ai-scan/upload`, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrfToken() },
        body: formData,
        signal: controller.signal
    });
    // ... handle response
} catch (e) {
    if (e.name === 'AbortError') {
        showAlert('AI scan timed out. Try a smaller document.', 'warning');
    } else {
        showAlert(`Upload failed: ${e.message}`, 'danger');
    }
} finally {
    clearTimeout(timeoutId);
}
```

#### 2.4 — Extracted Items Display

Build editable table from `extracted_items` array. Each row has:
- Checkbox (checked by default)
- Text input for description
- Number input for quantity
- Number input for unit price
- Auto-calculated total (qty × price)

JavaScript tracks items in `window.aiExtractedItems` array. On checkbox/edit changes, recalculate footer totals.

#### 2.5 — Import Selected Items

```javascript
async function importSelectedItems() {
    const selected = getCheckedItems(); // Returns array of {description, quantity, unit_price}
    if (selected.length === 0) { showAlert('No items selected', 'warning'); return; }

    let imported = 0;
    for (const item of selected) {
        try {
            const response = await makeApiCall(`/api/rfpos/${rfpoId}/line-items`, {
                method: 'POST',
                body: JSON.stringify({
                    description: item.description,
                    quantity: item.quantity,
                    unit_price: item.unit_price
                })
            });
            if (response.success) imported++;
        } catch (e) {
            console.error('Failed to import item:', item.description, e);
        }
    }

    // Close modal and refresh
    closeAiScanModal();
    await loadRfpoData();
    showAlert(`Successfully imported ${imported} of ${selected.length} line items`, 'success');
}
```

**Note:** Uses the existing `POST /api/rfpos/{rfpo_id}/line-items` endpoint sequentially. The API auto-increments `line_number` so ordering is preserved.

### Phase 3: Infrastructure & Dependencies

| # | Task | File(s) | Effort |
|---|------|---------|--------|
| 3.1 | Add `openai` package to requirements.txt | `requirements.txt` | Small |
| 3.2 | Add `python-docx` package (for .docx parsing) | `requirements.txt` | Small |
| 3.3 | Add Azure OpenAI env vars to `.env` and `env.example` | `.env`, `env.example` | Small |
| 3.4 | Add env vars to Azure Container App config | `azure/main.bicep` or deploy script | Small |
| 3.5 | Update Dockerfile.api if new system deps needed | `Dockerfile.api` | Small |

### Phase 4: User App Proxy Route

| # | Task | File(s) | Effort |
|---|------|---------|--------|
| 4.1 | Add proxy route for AI scan upload in User App | `user_app/blueprints/file_proxy.py` | Medium |

The User App proxies all file-related API calls through `file_proxy.py`. The new route **must** follow the existing pattern in that file:

```python
# In user_app/blueprints/file_proxy.py

@file_proxy_bp.route("/api/rfpos/<int:rfpo_id>/ai-scan/upload", methods=["POST"])
@require_auth_json
def api_rfpo_ai_scan(rfpo_id):
    """Proxy AI scan upload to API layer."""
    client = get_api_client()
    files = {}
    if "file" in request.files:
        f = request.files["file"]
        files["file"] = (f.filename, f.stream, f.content_type)

    resp = client.raw_post(
        f"/rfpos/{rfpo_id}/ai-scan/upload",
        files=files,
        timeout=90,  # Extended timeout for AI processing
    )
    return jsonify(resp.json()), resp.status_code
```

**Critical patterns (from reviewer):**
- Use `@file_proxy_bp.route()` — NOT `@pages_bp` (pages_bp is for template-rendering routes)
- Use `@require_auth_json` decorator — NOT `@login_required` (proxy routes use JWT auth)
- Use `f.stream` — NOT `f.read()` (avoids loading entire file into memory)
- Use `get_api_client()` — NOT direct `api_client` reference
- Extended timeout (90s) vs the default 30s, since AI processing takes 15-30 seconds

## 4. File Changes Summary

| File | Change Type | Phase |
|------|-------------|-------|
| `env_config.py` | Modify — add Azure OpenAI config + budget limit | Phase 1 |
| `ai_extractor.py` | **New** — AI extraction module + cost calculation + budget check | Phase 1 |
| `models.py` | Modify — add `AIUsageLog` model | Phase 1 |
| `simple_api.py` | Modify — add AI scan endpoint + budget enforcement + usage summary | Phase 1 |
| `sqlalchemy_db_init.py` | Modify — add `AIUsageLog` import (required for `db.create_all()`) | Phase 1 |
| `.env` | Modify — add Azure OpenAI vars + `AZURE_OPENAI_BUDGET_LIMIT=100.00` | Phase 3 |
| `env.example` | Modify — add Azure OpenAI vars + budget limit (no secrets) | Phase 3 |
| `requirements.txt` | Modify — add `openai`, `python-docx` | Phase 3 |
| `templates/app/rfpo_create_stage3.html` | Modify — button, modal, JS | Phase 2 |
| `user_app/blueprints/file_proxy.py` | Modify — proxy route | Phase 4 |
| `Dockerfile.api` | Possibly modify (if new sys deps) | Phase 3 |
| `azure/main.bicep` or deploy script | Modify — env vars for Container App | Phase 3 |

## 5. Security Considerations

- **File validation**: Reuse existing magic-byte + extension validation (no new attack surface)
- **API key**: Azure OpenAI key stored in env vars, never sent to browser
- **Input sanitization**: GPT-4o output is validated (JSON schema) before returning to client
- **Rate limiting**: 10K TPM on Azure OpenAI deployment limits abuse
- **Budget cap**: $100.00 hard limit enforced server-side via `AIUsageLog` table. Checked before every AI call. Configurable via `AZURE_OPENAI_BUDGET_LIMIT` env var.
- **RFPO access control**: Same auth checks as existing upload endpoint (requestor or admin)
- **No prompt injection risk from documents**: System prompt is fixed; document content is user-role only

## 6. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| AI extraction inaccurate | Medium | User reviews/edits every item before import. Items are clearly editable. |
| Large documents slow (30s+) | Medium | Progress spinner, extended timeout on proxy. Cap file size at 10MB (existing limit). |
| User App proxy timeout | High | Use 90-second timeout for AI scan proxy vs standard 10s. Frontend uses custom fetch, not makeApiCall(). |
| Azure OpenAI quotas | Low | 10K TPM is sufficient for document scanning (most docs < 5K tokens). Monitor usage. |
| Cost overrun | High | **$100.00 hard budget cap** enforced server-side. `AIUsageLog` tracks every call. Budget checked before processing. Admin can view usage via `/api/ai-usage/summary`. Configurable via `AZURE_OPENAI_BUDGET_LIMIT` env var. |
| Scanned PDFs with no text | Low | GPT-4o vision handles images natively. Fallback: render PDF pages as images. |
| Excel with complex formatting | Low | Parse to text/CSV first, send as structured text. Headers + rows pattern. |

## 7. Dependencies

**New Python packages:**
- `openai>=1.3.0` — Azure OpenAI SDK (minimum 1.3.0 for structured JSON output support)

**Existing packages already in requirements.txt:**
- `PyPDF2==3.0.1` — PDF text extraction
- `openpyxl==3.1.2` — Excel parsing
- `python-docx==1.1.0` — Word document parsing (already installed!)
- `Pillow` — Image handling

## 8. Testing Strategy

| Test | Type | Description |
|------|------|-------------|
| Extract from text PDF | Integration | Upload a PDF with clear line items, verify extraction |
| Extract from image | Integration | Upload a photo of an invoice, verify OCR + extraction |
| Extract from Excel | Integration | Upload spreadsheet with item rows, verify parsing |
| Empty document | Unit | Verify graceful handling of docs with no line items |
| Large document | Integration | Test 10MB file, verify timeout handling |
| Import flow | E2E | Extract → edit → import → verify line items in RFPO |
| Permission check | Unit | Non-requestor can't use AI scan on someone else's RFPO |
| Locked RFPO | Unit | Can't AI scan on approved/completed RFPOs |
| Budget exceeded | Unit | Returns 429 with budget details when $100 cap is reached |
| Budget tracking | Unit | Each scan logs tokens + cost accurately in AIUsageLog |
| Budget admin view | Integration | `/api/ai-usage/summary` returns spend totals per user |

## 9. Estimated Effort Summary

| Phase | Tasks | Complexity |
|-------|-------|------------|
| Phase 1: API + AI Module + Budget | 5 tasks | Large — core logic |
| Phase 2: Frontend Modal | 5 tasks | Medium — UI + JS |
| Phase 3: Infrastructure | 5 tasks | Small — config only |
| Phase 4: Proxy Route | 1 task | Small — plumbing |
| **Total** | **16 tasks** | |

## 9. Review Summary

**Reviewer:** AI Code Review Agent  
**Verdict:** Approved with Critical Changes (all incorporated below)

| # | Finding | Severity | Resolution |
|---|---------|----------|------------|
| 1 | Proxy route used wrong blueprint (`pages_bp`) and decorator (`@login_required`) | Critical | **Fixed** — Phase 4 now uses `file_proxy_bp` + `@require_auth_json` matching existing `file_proxy.py` pattern |
| 2 | No RFPO ownership/access validation in API endpoint | Critical | **Fixed** — Phase 1.3 now includes explicit requestor/admin check with 403 response |
| 3 | `env_config.py` used `os.environ.get()` instead of project's `get_env()` helper | Significant | **Fixed** — Phase 1.1 updated to use `get_env()` pattern |
| 4 | JavaScript `fetch()` had no AbortController for timeout enforcement | Significant | **Fixed** — Phase 2.3 now includes AbortController with 90s timeout and abort handling |
| 5 | `python-docx` listed as new dependency but already in requirements.txt | Minor | **Fixed** — Dependencies section corrected; only `openai>=1.3.0` is truly new |
| 6 | No token usage logging for cost tracking | Significant | **Fixed** — Phase 1.2 now logs `prompt_tokens` and `completion_tokens` from API response |
| 7 | No rate limiting for concurrent AI scans | Moderate | **Acknowledged** — Deferred to post-MVP. Azure OpenAI 10K TPM provides natural throttling. |
| 8 | Missing RFPO status validation code | Significant | **Fixed** — Phase 1.3 now explicitly checks locked statuses |
| 9 | No error handling for OpenAI timeouts/rate limits | Moderate | **Fixed** — Phase 1.2 now catches `APITimeoutError` and `RateLimitError` |
