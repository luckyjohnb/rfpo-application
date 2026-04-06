# RFPO Application — Feature Roadmap

## Planned Features

### RFPO Templates
**Priority:** Medium  
**Status:** Planned  

Allow admins to create and manage reusable RFPO templates that pre-fill common fields (team, vendor, line item structure, cost share settings, etc.).

**Scope:**
- **Admin Panel:** CRUD interface for RFPO templates (`/admin/rfpo-templates`)
- **API:** New `RFPOTemplate` model and REST endpoints (`/api/rfpo-templates`)
- **User App:** Template picker on the RFPO creation flow (Stage 1 or 2)
- **Database:** New `rfpo_templates` table with JSON fields for default values

**Acceptance Criteria:**
1. Admin can create a template with: name, consortium, project defaults, default line items, cost share presets, and description
2. Admin can edit/delete templates
3. When creating a new RFPO, user can optionally select a template to pre-fill the form
4. Template selection does not lock any fields — user can override all pre-filled values
5. Templates are scoped per consortium (only templates matching the selected consortium are shown)

**Implementation Notes:**
- Model should store defaults as a JSON blob for flexibility
- Template picker should appear after consortium/project selection (Stage 2) as an optional step
- Consider versioning templates so existing RFPOs are not affected by template edits
