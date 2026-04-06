## Summary
System emails are sent from an unrecognized/spam-flagged domain, preventing users from receiving account invitations and notifications.

## Customer Report
> "emails from rfpo@spammylookingemail is causing problems with even USCAR users getting the new account email... change the system email to a uscar.org email, so that when users get an email from the system, they actually get it"

## Problem Statement
The email sender address is not from a trusted domain. Email clients (especially corporate Microsoft 365 tenants) reject or spam-filter these messages. The `email_service.py` sender falls back to env vars or empty string if unconfigured.

## Priority
**Critical** — Blocking user onboarding (Sprint 1)

## Expected Behavior
Emails arrive in users' primary inbox from a recognized `@uscar.org` address.

## Actual Behavior
Emails are blocked or sent to spam. Users never see welcome/notification emails.

## Validation Tasks
- [ ] Identify current production `MAIL_DEFAULT_SENDER` / `ACS_SENDER_EMAIL` value
- [ ] Send test email to USCAR mailbox and confirm delivery/spam status
- [ ] Verify DNS records (SPF, DKIM, DMARC) for chosen sender domain

## Implementation Approach
1. Register and verify a custom `uscar.org` domain in Azure Communication Services
2. Update production `ACS_SENDER_EMAIL` to `rfpo@uscar.org` (or appropriate address agreed with customer)
3. Coordinate with USCAR IT for DNS record provisioning (SPF, DKIM, DMARC)
4. Test delivery to multiple USCAR recipients
5. Update `.env.example` to document required sender configuration

## Acceptance Criteria
- [ ] Welcome emails arrive in primary inbox for USCAR Microsoft 365 users
- [ ] Sender shows as `rfpo@uscar.org` (or agreed-upon address)
- [ ] No SPF/DKIM/DMARC failures in email headers
- [ ] Test email tool in admin panel confirms successful delivery

## Open Questions
- Exact sender address desired (e.g., `rfpo@uscar.org`, `noreply@uscar.org`)?
- USCAR IT contact for DNS provisioning?

## Triage Reference
Customer Triage 2026-04-01 — Issue #1
Epic: Email & Notifications
