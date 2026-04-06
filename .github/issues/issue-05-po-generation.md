## Summary
PDF purchase order generation outputs misaligned fields, missing data, and uses the internal RFPO ID instead of a proper sequential PO number.

## Customer Report
> "the system does not correctly generate a PO - there is no PO number created and the PO form is all garbled, not all sections are properly filled out or correct"

## Problem Statement
1. **No PO number field exists** — `pdf_generator.py` line 311 draws `rfpo.rfpo_id` (e.g., `RFPO-PROJ-2025-08-24-N01`) as the PO number
2. **PDF positioning uses hardcoded offsets** (e.g., line 156 applies a `-15px` preview offset) that don't match actual templates
3. **Some data fields are not populated** or correctly mapped to template positions
4. **No `po_number` column** exists in the RFPO model (confirmed by grep)

## Priority
**Critical** — Core business deliverable non-functional (Sprint 1-2)

> **Engineering review note:** Recommend splitting into two deliverables:
> - (a) PO number generation logic (Sprint 2)
> - (b) PDF positioning/field mapping fix (Sprint 2-3, requires customer screenshots)

## Expected Behavior
Generated PO PDF has a sequential PO number, all fields correctly positioned and filled, matching the organization's PO template format.

## Actual Behavior
PO shows internal RFPO ID, fields are garbled/misaligned, some sections empty.

## Validation Tasks
- [ ] Generate test PO PDF and compare against expected template
- [ ] Verify `PDFPositioning` records exist for target consortium
- [ ] Verify template PDFs exist in `static/po_files/`
- [ ] Request customer screenshots of specific garbled sections
- [ ] Audit all field coordinate mappings in `pdf_generator.py`

## Implementation Approach

### Part A: PO Number Generation
1. Add `po_number` column to RFPO model
2. Implement auto-generation logic: `PO-{consortium_abbrev}-{YYYYMMDD}-{seq:04d}`
3. Generate PO number upon first successful approval completion (not on creation)
4. Display PO number in RFPO detail views and PDF

### Part B: PDF Positioning & Field Mapping
1. Audit all field coordinates against actual template PDFs per consortium
2. Fix or remove hardcoded offset adjustments (line 156 `-15px` offset)
3. Verify all required template sections have corresponding data mappings
4. Test PDF output for each consortium template
5. Consider building a visual positioning preview tool

## Acceptance Criteria
- [ ] PO PDF contains a sequential, formatted PO number
- [ ] PO number is generated only after approval completion
- [ ] All template fields correctly positioned and filled
- [ ] Output matches customer-provided PO format template
- [ ] Each consortium's template renders correctly

## Open Questions
- What is the required PO number format?
- Which template PDF / consortium is affected?
- Can customer provide screenshots of current garbled output?
- Should PO number be generated on approval or explicit "finalize" action?

## Triage Reference
Customer Triage 2026-04-01 — Issue #5
Epic: PO Generation Fix
