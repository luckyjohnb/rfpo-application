---
name: build-feature-plans
description: "Build implementation plans for open feature requests. Use when: build feature plans, plan feature requests, FR plan, feature request planning. Queries the RFPO production API for open feature_request tickets, interprets each request, builds a detailed implementation plan, has another agent review it, saves the plan to docs/feature-request/, and marks the ticket as planned."
argument-hint: "Optionally specify a ticket number like FR-0001, or leave blank for all open feature requests"
---

# Build Feature Plans

Automate the full feature-request planning workflow: query open tickets → analyze codebase → build plan → peer review → save → update ticket status.

## When to Use

- User says "build feature plans" or invokes `/build-feature-plans`
- User wants to plan one or all open feature requests
- User references a specific FR ticket for planning

## Prerequisites

- RFPO production API must be reachable at the Azure Container Apps URL
- Admin credentials for API authentication (see [copilot-instructions.md](../../.github/copilot-instructions.md))
- The `docs/feature-request/` directory in the workspace (create if missing)

## Procedure

### Step 1: Authenticate to the Production API

Use PowerShell to obtain a JWT token from the production API:

```
API base URL: https://rfpo-api.livelyforest-d06a98a0.eastus.azurecontainerapps.io
Login endpoint: POST /api/auth/login
Body: {"username": "admin@rfpo.com", "password": "admin123"}
Extract: token from response
```

### Step 2: Query Open Feature Requests

Call `GET /api/tickets?type=feature_request&status=open&per_page=50` with the Bearer token.

- If the user specified a ticket number (e.g., "FR-0003"), filter results to that ticket only.
- If no ticket specified, process ALL open feature_request tickets.
- For each ticket, also fetch full details via `GET /api/tickets/<id>` to get comments and attachments.

Record for each ticket:
- `id` (integer — needed for API calls)
- `ticket_number` (e.g., FR-0001)
- `title`
- `description`
- `priority`
- `page_url` (context about where the feature is wanted)
- `creator_name`
- `created_at`
- `comments` (any additional context from discussion)
- `attachments` (any mockups or references)

### Step 3: Analyze the Codebase for Each Ticket

For each feature request, investigate the relevant parts of the codebase:

1. **Identify affected areas** — Use the ticket's title, description, and page_url to determine which files/modules are involved.
2. **Read the current implementation** — Read the relevant route handlers, templates, models, and API endpoints.
3. **Check for existing patterns** — Search the codebase for similar features already implemented that should be used as reference patterns.
4. **Identify database impact** — Determine if schema changes, new indexes, or migrations are needed.
5. **Check test coverage** — Look for existing tests related to the affected area.

### Step 4: Build the Implementation Plan

Create a comprehensive markdown plan with these sections:

```markdown
# <TICKET_NUMBER>: <Title>

> **Plan Status:** Reviewed & Approved
> **Created:** <today's date>
> **Reviewed By:** AI Code Review Agent

## 1. Feature Request Details
Table with: Ticket, Title, Description, Submitted By, Priority, Status, Created, Page Context

## 2. Interpretation
Clear explanation of what the user is asking for, resolving any ambiguity or typos in the original request.

## 3. Current State Analysis
- What exists today in each affected layer (admin panel, API, user app, database)
- Existing patterns to reference
- Current database indexes relevant to the feature

## 4. Implementation Plan
Break into phases (Phase 1 = core/backend, Phase 2 = UI, Phase 3 = optional enhancements).
Include code snippets showing the implementation pattern.
Document key decisions with rationale.

## 5. Database Preparation
Any DDL statements needed (CREATE INDEX, ALTER TABLE, etc.)

## 6. Detailed Task Breakdown
Table with: #, Task, File(s), Effort (Small/Medium/Large), Phase

## 7. Testing Strategy
- List specific test cases by name and description
- Note if there are zero existing tests for the area (common)
- Include manual verification steps

## 8. Security Considerations
SQL injection, XSS, auth, input validation, etc.

## 9. Risk Assessment
Table with: Risk, Severity, Mitigation

## 10. Review Summary
Reviewer verdict and resolution of all findings

## 11. Files Changed Summary
Table with: File, Change Type, Phase
```

### Step 5: Have Another Agent Review the Plan

Invoke a subagent (use the "Explore" agent) to perform a thorough review. The review prompt MUST include:

1. **Read the draft plan** from the file location
2. **Validate every claim** against the actual codebase — read the files referenced in the plan
3. **Check for gaps**: missing edge cases, performance concerns, existing patterns not referenced, UX conflicts, missing indexes
4. **Check existing test coverage** for the affected area
5. **Return a structured review** with: Accuracy Assessment, Gaps Found, Suggestions, Risk Assessment, Verdict (Approve / Approve with Changes / Reject)

After the review, incorporate ALL reviewer feedback into the final plan:
- Address every "MUST FIX" item
- Document decisions on "SHOULD FIX" items
- Add a Review Summary section showing each finding and its resolution

### Step 6: Save the Final Plan

Save the reviewed plan to: `docs/feature-request/<TICKET_NUMBER>-<slug>.md`

- Use lowercase ticket number and a slug derived from the title
- Example: `docs/feature-request/FR-0001-search-capabilities-plan.md`
- Create the `docs/feature-request/` directory if it doesn't exist

### Step 7: Upload the Plan to the Ticket

**This step MUST complete successfully before proceeding to Step 8 or Step 9.**

Upload the full plan markdown file as an attachment to the ticket via the API. Use `curl.exe` for reliable multipart/form-data uploads (PowerShell 5.1's `Invoke-RestMethod` does not support `-Form`).

```powershell
$planPath = "docs/feature-request/<TICKET_NUMBER>-<slug>.md"
$result = curl.exe -s -X POST "$api/api/tickets/<ticket_id>/attachments" `
    -H "Authorization: Bearer $token" `
    -F "file=@$planPath" | ConvertFrom-Json
```

**Verify the upload succeeded** by checking `$result.success -eq $true`. If it fails:
- Log the error message
- Do NOT proceed to Steps 8 or 9
- Report the failure to the user with the error details

The attachment endpoint will:
- Save the `.md` file locally under `uploads/tickets/<TICKET_NUMBER>/feature/`
- Upload to DOCUPLOAD (Azure Blob Storage) under `tickets/<TICKET_NUMBER>/feature/`
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
📋 IMPLEMENTATION PLAN — <TICKET_NUMBER>

Interpretation: <2-3 sentence summary of what the feature means>

Phases:
• Phase 1: <one-line summary + files affected>
• Phase 2: <one-line summary + files affected>
• Phase 3 (optional): <one-line summary>

Key tasks: <count> tasks across <count> files
Testing: <count> new test cases planned
Database changes: <yes/no — summary if yes>
Risk level: <Low/Medium/High>

Full plan attached as: <filename>.md
Also saved in repo at: docs/feature-request/<filename>.md
```

If the plan summary would exceed 10,000 characters, truncate the phases/tasks section to fit. The full plan is always available as the attached file and in the repo.

### Step 9: Mark the Ticket as Planned

**Only execute this step if BOTH Step 7 (upload) and Step 8 (comment) succeeded.**

This is the final step — it signals that the ticket has a complete, reviewed, uploaded plan. Marking as planned before the attachment and comment are in place creates an inconsistent state.

```
PUT /api/tickets/<ticket_id>
Headers: Authorization: Bearer <token>, Content-Type: application/json
Body: {"status": "planned"}
```

**Verify** the response shows `status: "planned"`. If this fails, report the error but note that the plan file and comment were successfully attached.

### Step 10: Report Summary

After processing all tickets, provide a summary:

```
Processed X feature request(s):
- FR-XXXX: <title> → Plan saved ✓ | Uploaded ✓ | Comment posted ✓ | Status: planned ✓
- FR-YYYY: <title> → Plan saved ✓ | Uploaded ✗ (error: ...) | Skipped remaining steps
```

Include the outcome of each step so the user knows exactly what succeeded and what didn't.

## Execution Order (Critical)

The following order MUST be followed for each ticket. Later steps depend on earlier ones succeeding.

```
Step 1: Authenticate          ──→ required for all API calls
Step 2: Query open tickets    ──→ only process status=open tickets
Step 3: Analyze codebase      ──→ understand what to build
Step 4: Build plan             ──→ create the markdown document
Step 5: Peer review            ──→ another agent validates the plan
Step 6: Save to repo           ──→ write docs/feature-request/<file>.md
Step 7: Upload to ticket       ──→ attach .md file to the ticket (MUST succeed)
Step 8: Post summary comment   ──→ internal comment with plan overview (MUST succeed)
Step 9: Mark as planned        ──→ ONLY after Steps 7+8 succeed
Step 10: Report                ──→ show per-ticket outcome to user
```

**If Step 7 fails**, do NOT execute Steps 8 or 9. The plan is still saved locally (Step 6).
**If Step 8 fails**, do NOT execute Step 9. The plan is uploaded but the comment is missing.
**If Step 9 fails**, the plan and comment are in place — just report the status update failure.

## Important Notes

- **Only process tickets with status `open`** — skip any ticket that is already `planned`, `in_progress`, `completed`, `under_review`, or `declined` unless the user explicitly asks to re-plan a specific ticket
- **Never mark as planned until upload + comment succeed** — Steps 7 → 8 → 9 are a strict chain; if any step fails, halt and report
- **Never skip the review step** — every plan must be reviewed by a subagent before saving
- **Always use the production API** — tickets live in Azure PostgreSQL, not local SQLite
- **Use `curl.exe` for file uploads** — PowerShell 5.1 does not support `-Form`; use `curl.exe -F "file=@path"`
- **Preserve existing ticket data** — only update the `status` field, never modify title/description
- **One plan per ticket** — each feature request gets its own markdown file
- **Check for existing plans** — if `docs/feature-request/<TICKET_NUMBER>-*.md` already exists, ask the user whether to overwrite or skip
