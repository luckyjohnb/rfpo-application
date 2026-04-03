# UI Issues and Enhancements (Tracking)

This tracking document accompanies the "UI issues" Pull Request and will be updated as we iterate.

## Scope

- Minor UX polish, layout fixes, and small quality-of-life improvements across Admin and User apps.
- Low-risk behavioral tweaks (e.g., input trimming, auto-fill, labels/helptext).

## Recently Addressed

- Admin > Users > Create/Edit: Company Code ↔ Company Name auto-fill/sync
  - Selecting a Company Code auto-populates the Company Name (text to the right of "]").
  - Typing a Company Name that matches a known option auto-selects the Company Code.
  - Trims extra whitespace and common separators (dashes, pipes, bullets, colons) and debounces live input.

## Candidate Items (Checklist)

- [x] Form input trimming (leading/trailing spaces) across common text fields
  - Global `submit` event handler in both `admin/base.html` and `app/base.html` trims all text/email/search/url/tel inputs and textareas on form submit.
- [x] Consistent placeholder/help text for required fields
  - Audited all form templates; all required fields already have descriptive `placeholder` attributes.
- [x] Button label consistency (e.g., Save vs. Update)
  - Standardized 8 form templates: edit mode shows "Save X", create mode shows "Create X" (was previously showing "Edit X").
- [x] Table column alignment and responsive truncation of long values
  - Added `.text-truncate-cell` (max-width 200px) and `.text-truncate-cell-sm` (max-width 120px) CSS classes in `admin/base.html`. Applied to Users, Vendors, and RFPOs list tables.
- [x] Flash/alert placement and auto-dismiss timing review
  - Admin flash alerts auto-dismiss after 5 seconds via `bootstrap.Alert` in `admin/base.html`.
- [x] Accessibility quick pass (labels/aria, contrast, focus states)
  - Added `:focus-visible` outline styles in both base templates. Added `aria-label` on User App nav, `role="navigation"` on sidebar, `role="main"` on content area. Added `scope="col"` to User App table headers.
- [x] Mobile layout review for key pages (Users, Vendors, RFPOs)
  - Added `@media (max-width: 767.98px)` rules in both base templates: sidebar collapses to full-width, tables get smaller font/padding, cards and headings resize, button groups wrap.

## Notes

- Keep changes small and reviewable; group them into logical commits.
- Avoid risky JS refactors; prefer targeted improvements.
- Link each commit to this PR and tick the checklist where applicable.
