---
name: build-bug-plans
description: "Build fix plans for open bug reports. Use when: build bug plans, plan bug fixes, BUG plan, bug planning, plan bug. Queries the RFPO production API for open bug tickets, analyzes root cause, builds a detailed fix plan, has another agent review it, saves the plan to docs/bugs/, and marks the ticket as in_progress."
argument-hint: "Optionally specify a ticket number like BUG-0001, or leave blank for all open bugs"
---

# Build Bug Plans

Automate the full bug-fix planning workflow: query open bug tickets → analyze codebase → build fix plan → peer review → save → update ticket status.

## When to Use

- User says "build bug plans", "plan bug", or "plan bug fix"
- User wants to plan one or all open bug reports
- User references a specific BUG ticket for planning (e.g., "plan BUG-0001")

## Prerequisites

- RFPO production API must be reachable at the Azure Container Apps URL
- Admin credentials for API authentication (see [copilot-instructions.md](../../.github/copilot-instructions.md))
- The `docs/bugs/` directory in the workspace (create if missing)

## Procedure

### Step 1: Authenticate to the Production API

Use PowerShell to obtain a JWT token from the production API:

```
API base URL: https://rfpo-api.livelyforest-d06a98a0.eastus.azurecontainerapps.io
Login endpoint: POST /api/auth/login
Body: {"username": "admin@rfpo.com", "password": "admin123"}
Extract: token from response
```

### Step 2: Query Open Bug Tickets

Call `GET /api/tickets?type=bug&status=open&per_page=50` with the Bearer token.

- If the user specified a ticket number (e.g., "BUG-0003"), filter results to that ticket only.
- If no ticket specified, process ALL open bug tickets.
- For each ticket, also fetch full details via `GET /api/tickets/<id>` to get comments and attachments.

Record for each ticket:
- `id` (integer — needed for API calls)
- `ticket_number` (e.g., BUG-0001)
- `title`
- `description`
- `priority` (low / medium / high / critical)
- `severity` (cosmetic / minor / major / blocker) — bug-specific
- `steps_to_reproduce` — bug-specific
- `page_url` (where the bug occurred)
- `creator_name`
- `created_at`
- `comments` (any additional context from discussion)
- `attachments` (screenshots, logs, etc.)

### Step 3: Analyze the Codebase for Each Bug

For each bug ticket, investigate the relevant parts of the codebase:

1. **Reproduce mentally** — Use the `steps_to_reproduce` and `page_url` to trace the code path that triggers the bug.
2. **Identify root cause** — Read the relevant route handlers, templates, models, and API endpoints to find the defect.
3. **Assess severity impact**:
   - **Blocker**: May need immediate hotfix; prioritize for urgent review
   - **Major**: Fix needed for next release
   - **Minor**: Can be planned for near-term resolution
   - **Cosmetic**: Low urgency, plan for longer-term fix
4. **Check for related bugs** — Search the codebase for similar patterns that might have the same underlying issue.
5. **Identify regression risk** — Determine what other features could break if this area is modified.
6. **Check test coverage** — Look for existing tests related to the affected area.

### Step 4: Build the Bug Fix Plan

Create a comprehensive markdown plan with these sections:

```markdown
# <TICKET_NUMBER>: <Title>

> **Plan Status:** Reviewed & Approved
> **Created:** <today's date>
> **Reviewed By:** AI Code Review Agent
> **Severity:** <cosmetic / minor / major / blocker>

## 1. Bug Details

| Field | Value |
|---|---|
| **Ticket** | BUG-XXXX |
| **Title** | <title> |
| **Description** | <description> |
| **Submitted By** | <creator_name> |
| **Priority** | <priority> |
| **Severity** | <severity> |
| **Status** | Open |
| **Created** | <date> |
| **Page Context** | <page_url or N/A> |
| **Steps to Reproduce** | <steps_to_reproduce or N/A> |

## 2. Root Cause Analysis
- What is broken and why
- The specific code path that leads to the bug
- Whether this is a logic error, data issue, race condition, missing validation, etc.

## 3. Impact Assessment
- Where in the code the bug manifests (list affected files/functions)
- User-facing impact (what the user sees/experiences)
- Data impact (is data corrupted, lost, or incorrectly stored?)
- Scope (how many users/workflows are affected)

## 4. Fix Strategy
Break into phases if the fix is complex:
- Phase 1: Core fix (the minimal change to resolve the bug)
- Phase 2: Hardening (add validation, error handling to prevent recurrence)
- Phase 3: Optional improvements discovered during analysis

Include code snippets showing the fix pattern.
Document key decisions with rationale.

## 5. Database Impact
- Any DDL statements needed (ALTER TABLE, CREATE INDEX, data fixes)
- If no database changes: state "No database changes required"

## 6. Detailed Task Breakdown
Table with: #, Task, File(s), Effort (Small/Medium/Large), Phase

## 7. Testing Strategy
- Regression tests: verify the bug is fixed
- Edge case tests: verify related scenarios still work
- Manual verification steps
- Note if there are zero existing tests for the area

## 8. Regression Prevention
- What tests to add to prevent this bug from recurring
- Related areas to verify haven't been broken by the fix
- Any monitoring or logging to add

## 9. Security Considerations
SQL injection, XSS, auth, input validation — only if relevant to the fix

## 10. Risk Assessment
Table with: Risk, Severity, Mitigation

## 11. Review Summary
Reviewer verdict and resolution of all findings

## 12. Files Changed Summary
Table with: File, Change Type, Phase
```

### Step 5: Have Another Agent Review the Plan

Invoke a subagent (use the "Explore" agent) to perform a thorough review. The review prompt MUST include:

1. **Read the draft plan** from the file location
2. **Validate the root cause analysis** against the actual codebase — read the files referenced in the plan and confirm the bug exists where claimed
3. **Verify the fix strategy** — confirm it addresses the root cause, not just a symptom
4. **Check for regression risks**: could the fix break other features? Are affected areas covered by tests?
5. **Check existing test coverage** for the affected area
6. **Return a structured review** with: Accuracy Assessment, Root Cause Verification, Gaps Found, Suggestions, Risk Assessment, Verdict (Approve / Approve with Changes / Reject)

After the review, incorporate ALL reviewer feedback into the final plan:
- Address every "MUST FIX" item
- Document decisions on "SHOULD FIX" items
- Add a Review Summary section showing each finding and its resolution

### Step 6: Save the Final Plan

Save the reviewed plan to: `docs/bugs/<BUG-NUMBER>.md`

- Use the ticket number directly (e.g., `docs/bugs/BUG-0001.md`)
- Create the `docs/bugs/` directory if it doesn't exist

### Step 7: Upload the Plan to the Ticket

**This step MUST complete successfully before proceeding to Step 8 or Step 9.**

Upload the full plan markdown file as an attachment to the ticket via the API. Use `curl.exe` for reliable multipart/form-data uploads (PowerShell 5.1's `Invoke-RestMethod` does not support `-Form`).

```powershell
$planPath = "docs/bugs/<BUG-NUMBER>.md"
$result = curl.exe -s -X POST "$api/api/tickets/<ticket_id>/attachments" `
    -H "Authorization: Bearer $token" `
    -F "file=@$planPath" | ConvertFrom-Json
```

**Verify the upload succeeded** by checking `$result.success -eq $true`. If it fails:
- Log the error message
- Do NOT proceed to Steps 8 or 9
- Report the failure to the user with the error details

The attachment endpoint will:
- Save the `.md` file locally under `uploads/tickets/<BUG-NUMBER>/bug/`
- Upload to DOCUPLOAD (Azure Blob Storage) under `tickets/<BUG-NUMBER>/bug/`
- Create a `TicketAttachment` record linked to the ticket

### Step 8: Post the Plan Summary as a Comment

**Only execute this step if Step 7 succeeded.**

Post a brief **internal admin comment** summarizing the plan so it's visible in the admin panel without downloading the attachment:

```
POST /api/tickets/<ticket_id>/comments
Headers: Authorization: Bearer <token>, Content-Type: application/json
Body: {
    "content": "<plan summary — see format below>",
    "is_internal": true
}
```

**Comment format** (must fit within 10,000 character limit):
```
🐛 BUG FIX PLAN — <BUG-NUMBER>

Root Cause: <2-3 sentence summary of what's broken and why>
Severity: <cosmetic / minor / major / blocker>

Fix Strategy:
• Phase 1: <one-line summary of core fix + files affected>
• Phase 2: <one-line summary of hardening + files affected>
• Phase 3 (optional): <one-line summary>

Key tasks: <count> tasks across <count> files
Testing: <count> new test cases planned
Database changes: <yes/no — summary if yes>
Regression risk: <Low/Medium/High — summary>

Full plan attached as: <BUG-NUMBER>.md
Also saved in repo at: docs/bugs/<BUG-NUMBER>.md
```

If the plan summary would exceed 10,000 characters, truncate the phases/tasks section to fit. The full plan is always available as the attached file and in the repo.

### Step 9: Mark the Ticket as In Progress

**Only execute this step if BOTH Step 7 (upload) and Step 8 (comment) succeeded.**

Bug tickets have no "planned" status. The equivalent is `in_progress`, which signals that the bug has been analyzed and a fix plan is in place.

```
PUT /api/tickets/<ticket_id>
Headers: Authorization: Bearer <token>, Content-Type: application/json
Body: {"status": "in_progress"}
```

**Verify** the response shows `status: "in_progress"`. If this fails, report the error but note that the plan file and comment were successfully attached.

### Step 10: Report Summary

After processing all tickets, provide a summary:

```
Processed X bug ticket(s):
- BUG-XXXX: <title> → Plan saved ✓ | Uploaded ✓ | Comment posted ✓ | Status: in_progress ✓
- BUG-YYYY: <title> → Plan saved ✓ | Uploaded ✗ (error: ...) | Skipped remaining steps
```

Include the outcome of each step so the user knows exactly what succeeded and what didn't.

## Execution Order (Critical)

The following order MUST be followed for each ticket. Later steps depend on earlier ones succeeding.

```
Step 1: Authenticate          ──→ required for all API calls
Step 2: Query open bugs       ──→ only process status=open tickets
Step 3: Analyze codebase      ──→ find root cause, assess severity
Step 4: Build fix plan         ──→ create the markdown document
Step 5: Peer review            ──→ another agent validates the plan
Step 6: Save to repo           ──→ write docs/bugs/<BUG-NUMBER>.md
Step 7: Upload to ticket       ──→ attach .md file to the ticket (MUST succeed)
Step 8: Post summary comment   ──→ internal comment with plan overview (MUST succeed)
Step 9: Mark as in_progress    ──→ ONLY after Steps 7+8 succeed
Step 10: Report                ──→ show per-ticket outcome to user
```

**If Step 7 fails**, do NOT execute Steps 8 or 9. The plan is still saved locally (Step 6).
**If Step 8 fails**, do NOT execute Step 9. The plan is uploaded but the comment is missing.
**If Step 9 fails**, the plan and comment are in place — just report the status update failure.

## Important Notes

- **Only process tickets with status `open`** — skip any ticket that is already `in_progress`, `resolved`, `closed`, or `wont_fix` unless the user explicitly asks to re-plan a specific ticket
- **Never mark as in_progress until upload + comment succeed** — Steps 7 → 8 → 9 are a strict chain; if any step fails, halt and report
- **Never skip the review step** — every plan must be reviewed by a subagent before saving
- **Always use the production API** — tickets live in Azure PostgreSQL, not local SQLite
- **Use `curl.exe` for file uploads** — PowerShell 5.1 does not support `-Form`; use `curl.exe -F "file=@path"`
- **Preserve existing ticket data** — only update the `status` field, never modify title/description
- **One plan per ticket** — each bug gets its own markdown file
- **Check for existing plans** — if `docs/bugs/<BUG-NUMBER>.md` already exists, ask the user whether to overwrite or skip
- **Bug statuses are different from feature statuses** — bugs use: `open`, `in_progress`, `resolved`, `closed`, `wont_fix` (there is NO `planned` status for bugs)
