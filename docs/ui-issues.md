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

- [ ] Form input trimming (leading/trailing spaces) across common text fields
- [ ] Consistent placeholder/help text for required fields
- [ ] Button label consistency (e.g., Save vs. Update)
- [ ] Table column alignment and responsive truncation of long values
- [ ] Flash/alert placement and auto-dismiss timing review
- [ ] Accessibility quick pass (labels/aria, contrast, focus states)
- [ ] Mobile layout review for key pages (Users, Vendors, RFPOs)

## Notes

- Keep changes small and reviewable; group them into logical commits.
- Avoid risky JS refactors; prefer targeted improvements.
- Link each commit to this PR and tick the checklist where applicable.
