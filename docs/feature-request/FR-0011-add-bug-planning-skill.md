# FR-0011: Add Bug Planning Skill

> **Plan Status:** Reviewed & Approved  
> **Created:** 2026-04-13  
> **Reviewed By:** AI Code Review Agent  

---

## 1. Feature Request Details

| Field | Value |
|---|---|
| **Ticket** | FR-0011 |
| **Title** | Add Bug Planning Skill |
| **Description** | Create a bug planning skill modeled after the feature request planning skill (FR-0001). Save plans to Azure folder called "bugs" and locally under `docs/bugs/<BUG-NUMBER>.md`. Create a reusable skill callable via simple invocation. |
| **Submitted By** | John Bouchard |
| **Priority** | Medium |
| **Status** | Open |
| **Created** | 2026-04-11 |
| **Page Context** | N/A |

---

## 2. Interpretation

The user wants a **new Copilot skill** (`.github/skills/build-bug-plans/SKILL.md`) that mirrors the existing `build-feature-plans` skill but targets **bug tickets** (`type=bug`) instead of feature requests. The workflow should:

1. Query the production API for open bug tickets
2. Analyze the codebase to understand the bug and affected areas
3. Build a detailed bug fix plan with root cause analysis, fix strategy, and testing
4. Have the plan peer-reviewed by another agent
5. Save the plan locally to `docs/bugs/<BUG-NUMBER>.md` (e.g., `docs/bugs/BUG-0001.md`)
6. Upload the plan to the ticket as an attachment (stored in Azure Blob under `tickets/<BUG-NUMBER>/bug/`)
7. Post an internal summary comment on the ticket
8. Update the ticket status to `in_progress` (the bug equivalent of "planned")

Key differences from the feature planning skill:
- **Ticket type filter**: `type=bug` instead of `type=feature_request`
- **Status transitions**: Bug tickets use `open → in_progress` (no "planned" status for bugs)
- **Save path**: `docs/bugs/<BUG-NUMBER>.md` instead of `docs/feature-request/<TICKET_NUMBER>-<slug>.md`
- **Plan content**: Focuses on root cause analysis, reproduction steps, and fix strategy rather than feature design
- **Azure folder**: `tickets/<BUG-NUMBER>/bug/` (already handled by the attachment endpoint's `ticket_type_folder` logic)

---

## 3. Current State Analysis

### Existing Feature Planning Skill (`.github/skills/build-feature-plans/SKILL.md`)
- 10-step procedure: Authenticate → Query → Analyze → Plan → Review → Save → Upload → Comment → Mark status → Report
- Uses production API at `https://rfpo-api.livelyforest-d06a98a0.eastus.azurecontainerapps.io`
- Admin credentials for JWT auth
- Strict execution ordering: Steps 7→8→9 are chained (upload must succeed before comment, comment must succeed before status update)
- Uses `curl.exe` for file uploads (PowerShell 5.1 lacks `-Form`)
- Plans saved to `docs/feature-request/<TICKET_NUMBER>-<slug>.md`

### Ticket Model (`models.py` line 2487)
- Unified `Ticket` model handles both bugs and features via `type` field
- **Bug statuses**: `open`, `in_progress`, `resolved`, `closed`, `wont_fix`
- **Bug-specific fields**: `severity` (cosmetic/minor/major/blocker), `steps_to_reproduce`
- No "planned" status for bugs — the closest equivalent is `in_progress`

### Ticket API Endpoints (`simple_api.py`)
- `GET /api/tickets?type=bug&status=open` — list open bugs
- `GET /api/tickets/<id>` — full details with comments/attachments
- `POST /api/tickets/<id>/attachments` — upload file (already routes to `tickets/<TICKET_NUMBER>/bug/` folder for bug tickets)
- `POST /api/tickets/<id>/comments` — add comment with `is_internal` flag
- `PUT /api/tickets/<id>` — update status

### File Upload Logic (`simple_api.py` line 4698)
- `ticket_type_folder` is already `"bug"` when `ticket.type == "bug"` — no API changes needed
- Local storage: `uploads/tickets/<TICKET_NUMBER>/bug/`
- DOCUPLOAD cloud path: `tickets/<TICKET_NUMBER>/bug/`
- `.md` files are already in `ALLOWED_UPLOAD_EXTENSIONS`

### Directory Structure
- `docs/feature-request/` exists with FR-0001 plan
- `docs/bugs/` does **NOT** exist yet — needs to be created

---

## 4. Implementation Plan

### Phase 1: Create the Bug Planning Skill

**File: `.github/skills/build-bug-plans/SKILL.md`**

Create a new skill file modeled after `build-feature-plans/SKILL.md` with these key modifications:

1. **YAML frontmatter**: 
   - `name: build-bug-plans`
   - `description`: References bug planning, bug fix plans, BUG tickets
   - `argument-hint`: Accepts optional BUG-XXXX ticket number

2. **Step 2 — Query**: Filter by `type=bug&status=open` instead of `type=feature_request&status=open`

3. **Step 3 — Analyze**: Bug-specific analysis:
   - Reproduce the bug from `steps_to_reproduce` field
   - Identify root cause in the codebase
   - Check `severity` field (cosmetic/minor/major/blocker) to gauge urgency:
     - **Blocker**: May need immediate hotfix; prioritize for urgent review
     - **Major**: Fix needed for next release
     - **Minor/Cosmetic**: Can be planned for longer-term resolution
   - Examine related error handling and edge cases

4. **Step 4 — Plan template**: Bug-specific sections:
   - **Bug Details table**: Include `severity`, `steps_to_reproduce`, `page_url`
   - **Root Cause Analysis**: Instead of "Interpretation"
   - **Reproduction**: Steps to reproduce and verify
   - **Fix Strategy**: Instead of "Implementation Plan"
   - **Regression Prevention**: What to test to ensure the fix doesn't break other things
   - **Testing Strategy**: Unit tests, integration tests, manual verification

5. **Step 6 — Save path**: `docs/bugs/<BUG-NUMBER>.md` (e.g., `docs/bugs/BUG-0001.md`)
   - Simpler naming than feature plans (just ticket number, no slug)
   - Create `docs/bugs/` directory if it doesn't exist

6. **Step 9 — Status**: Set to `in_progress` instead of `planned` (bug tickets have no "planned" status)

7. **Steps 7-8-9 chain**: Same strict ordering — upload must succeed → comment must succeed → then update status

### Phase 2: Create `docs/bugs/` Directory

- Create `docs/bugs/` directory with a `.gitkeep` or `README.md` placeholder
- This ensures the directory is tracked in git before any plans are saved

### Phase 3: Register Skill in Copilot Instructions (Optional)

- Add the new skill to the `<skills>` section if skill registration is manual
- The skill should auto-discover from `.github/skills/` directory structure

---

## 5. Database Preparation

**No database changes required.**

- The `Ticket` model already supports bug tickets with all necessary fields
- The attachment upload endpoint already handles bug-type folder routing
- No new tables, columns, or indexes are needed

---

## 6. Detailed Task Breakdown

| # | Task | File(s) | Effort | Phase |
|---|------|---------|--------|-------|
| 1 | Create `build-bug-plans` skill YAML frontmatter | `.github/skills/build-bug-plans/SKILL.md` | Small | 1 |
| 2 | Write "When to Use" section with bug-specific triggers | `.github/skills/build-bug-plans/SKILL.md` | Small | 1 |
| 3 | Write "Prerequisites" section | `.github/skills/build-bug-plans/SKILL.md` | Small | 1 |
| 4 | Write Step 1 (Authenticate) — same as feature skill | `.github/skills/build-bug-plans/SKILL.md` | Small | 1 |
| 5 | Write Step 2 (Query) — filter `type=bug&status=open` | `.github/skills/build-bug-plans/SKILL.md` | Small | 1 |
| 6 | Write Step 3 (Analyze) — bug-specific: root cause, severity, reproduction | `.github/skills/build-bug-plans/SKILL.md` | Medium | 1 |
| 7 | Write Step 4 (Build Plan) — bug fix plan template with all sections | `.github/skills/build-bug-plans/SKILL.md` | Large | 1 |
| 8 | Write Step 5 (Peer Review) — same structure, bug-specific review criteria | `.github/skills/build-bug-plans/SKILL.md` | Small | 1 |
| 9 | Write Step 6 (Save) — path `docs/bugs/<BUG-NUMBER>.md` | `.github/skills/build-bug-plans/SKILL.md` | Small | 1 |
| 10 | Write Step 7 (Upload) — same curl.exe pattern, bug folder | `.github/skills/build-bug-plans/SKILL.md` | Small | 1 |
| 11 | Write Step 8 (Comment) — bug-specific summary format | `.github/skills/build-bug-plans/SKILL.md` | Small | 1 |
| 12 | Write Step 9 (Mark Status) — `in_progress` instead of `planned` | `.github/skills/build-bug-plans/SKILL.md` | Small | 1 |
| 13 | Write Step 10 (Report) — per-ticket outcome summary | `.github/skills/build-bug-plans/SKILL.md` | Small | 1 |
| 14 | Write Execution Order and Important Notes sections | `.github/skills/build-bug-plans/SKILL.md` | Small | 1 |
| 15 | Create `docs/bugs/` directory with README.md placeholder | `docs/bugs/README.md` | Small | 2 |

---

## 7. Testing Strategy

Since this is a Copilot skill (not application code), testing is done via **manual invocation**:

| # | Test Case | Description | Expected Result |
|---|-----------|-------------|-----------------|
| 1 | Skill discovery | Say "plan bug" or "build bug plans" | Agent loads the skill and begins execution |
| 2 | No open bugs | All bugs are non-open status | Agent reports "No open bug tickets found" and exits |
| 3 | Single open bug | One bug with status=open | Agent processes the bug through all 10 steps |
| 4 | Specific bug number | "Plan BUG-0001" | Agent filters to that specific bug only |
| 5 | Existing plan check | Plan already exists at `docs/bugs/BUG-XXXX.md` | Agent asks whether to overwrite or skip |
| 6 | Upload failure | API returns error on attachment upload | Agent halts at Step 7, does not comment or update status |
| 7 | Comment failure | API returns error on comment post | Agent halts at Step 8, does not update status |
| 8 | Status update | Verify bug moved to `in_progress` | API returns `status: "in_progress"` |

**No automated tests needed** — this is a workflow skill, not application code. Testing is performed by invoking the skill and verifying each step's output.

---

## 8. Security Considerations

| Concern | Assessment |
|---------|------------|
| **Credential handling** | API credentials are used transiently in terminal commands; JWT tokens are not persisted to disk |
| **File path traversal** | Save paths are hardcoded to `docs/bugs/` — no user-controlled path components beyond the ticket number (which is validated server-side as `BUG-XXXX` format) |
| **API authorization** | Uses admin JWT — same security model as the feature planning skill |
| **Plan content** | Plans are `is_internal: true` comments — not visible to non-admin users |
| **Markdown injection** | Plan files are saved as `.md` and rendered by GitHub/VS Code markdown — no executable content |

---

## 9. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Skill not discovered by Copilot | Low | Follows same `.github/skills/` convention as the working feature skill |
| Bug status `in_progress` ambiguity | Low | `in_progress` is the correct status for "actively being worked on"; document this clearly in the skill |
| Large plan exceeds comment limit | Low | Same 10,000-char truncation logic as feature skill; full plan is in the attachment |
| Concurrent bug planning | Low | Each bug gets its own plan file; no shared state between invocations |

---

## 10. Review Summary

| # | Finding | Severity | Resolution |
|---|---------|----------|------------|
| 1 | Bug tickets have no "planned" status | Info | Use `in_progress` — documented in skill and plan |
| 2 | `docs/bugs/` directory doesn't exist | Must Fix | Created as part of Phase 2 |
| 3 | Bug-specific fields (severity, steps_to_reproduce) must be captured | Must Fix | Added to Step 2 data collection and Step 4 plan template |
| 4 | Attachment upload already handles bug folder routing | Info | No API changes needed — confirmed in `simple_api.py` line 4770 |
| 5 | Simpler file naming for bug plans (just `BUG-XXXX.md` vs slug) | Info | Per user request — matches `docs/bugs/<bug-number>.md` pattern |
| 6 | Missing severity-driven analysis priority in Step 3 | Should Fix | Added blocker/major/minor urgency guidance to Step 3 |
| 7 | `in_progress` status doesn't set `resolved_at` timestamp | Info | Expected — `resolved_at` only set for `resolved` status; no action needed |

---

## 11. Files Changed Summary

| File | Change Type | Phase |
|------|-------------|-------|
| `.github/skills/build-bug-plans/SKILL.md` | New file | 1 |
| `docs/bugs/README.md` | New file | 2 |

**No existing files are modified.** This feature is entirely additive — a new skill file and a new directory.
