# DNS Configuration for uscar.org Email Sending

**Date:** 2026-04-01 (refreshed)
**Audience:** USCAR DNS / IT Administrator
**Requested by:** RFPO Engineering
**Purpose:** Enable the RFPO application to send emails from `rfpo@uscar.org`

---

## Background

The RFPO application sends transactional emails (account invitations, approval notifications, PO documents). These emails currently come from an Azure-managed domain (`*.azurecomm.net`) which is flagged as spam by corporate mail filters — especially Microsoft 365 tenants like USCAR's.

To fix this, we need to verify `uscar.org` as a **custom sender domain** in Azure Communication Services (ACS). This requires **four DNS records** to be added to the `uscar.org` DNS zone.

Once these records are in place and verified, the application will send all emails as `rfpo@uscar.org`, which will pass SPF, DKIM, and DMARC checks and be delivered to users' primary inboxes.

---

## What the DNS Admin Needs to Do

Add the following records to the **uscar.org** DNS zone. All four records are needed for full verification and deliverability.

### Record 1 — Domain Ownership Verification (TXT)

This proves to Azure that USCAR authorizes the RFPO application to send on behalf of `uscar.org`.

| Field       | Value                                                       |
|-------------|-------------------------------------------------------------|
| **Type**    | TXT                                                         |
| **Host**    | `@` (root domain)                                           |
| **Value**   | `ms-domain-verification=a5695984-4dc7-4841-abd3-25c71f092ee7` |
| **TTL**     | 3600                                                        |

### Record 2 — DKIM Signing Key Selector 1 (CNAME)

DKIM allows receiving mail servers to verify that the email was actually sent by an authorized system and was not tampered with in transit.

| Field       | Value                                                              |
|-------------|--------------------------------------------------------------------|
| **Type**    | CNAME                                                              |
| **Host**    | `selector1-azurecomm-prod-net._domainkey`                         |
| **Target**  | `selector1-azurecomm-prod-net._domainkey.azurecomm.net`           |
| **TTL**     | 3600                                                               |

### Record 3 — DKIM Signing Key Selector 2 (CNAME)

Second DKIM selector for key rotation (Azure rotates signing keys automatically).

| Field       | Value                                                              |
|-------------|--------------------------------------------------------------------|
| **Type**    | CNAME                                                              |
| **Host**    | `selector2-azurecomm-prod-net._domainkey`                         |
| **Target**  | `selector2-azurecomm-prod-net._domainkey.azurecomm.net`           |
| **TTL**     | 3600                                                               |

### Record 4 — DMARC Policy (TXT) — Strongly Recommended

DMARC tells receiving mail servers what to do when SPF or DKIM checks fail. Without it, some corporate mail systems (including Microsoft 365) may still reject or quarantine messages.

| Field       | Value                                                              |
|-------------|--------------------------------------------------------------------|
| **Type**    | TXT                                                                |
| **Host**    | `_dmarc`                                                           |
| **Value**   | `v=DMARC1; p=none; rua=mailto:dmarc-reports@uscar.org; fo=1`     |
| **TTL**     | 3600                                                               |

> **Note on DMARC `p=none`:** This starts in monitor-only mode so you can review aggregate reports without blocking any mail. Once you confirm everything looks good, you can tighten it to `p=quarantine` or `p=reject`.
>
> **Note on `rua` address:** Replace `dmarc-reports@uscar.org` with whatever mailbox should receive DMARC aggregate reports. This can be a shared mailbox or an external DMARC reporting service.

---

## Important: SPF Record Handling

**Do NOT add a new SPF (TXT) record if one already exists for `uscar.org`.** The DNS standard allows only **one** SPF record per domain. Having two will cause SPF validation to fail for *all* mail from `uscar.org`.

Azure Communication Services uses its own IP infrastructure for sending. If `uscar.org` already has an SPF record (e.g., for Microsoft 365), you need to **append** the ACS include to the existing record:

**If no SPF record exists yet**, add:
```
v=spf1 include:spf.protection.outlook.com -all
```

**If an SPF record already exists**, ensure it includes `spf.protection.outlook.com`. For example, if the current record is:
```
v=spf1 include:_spf.google.com ~all
```
Update it to:
```
v=spf1 include:_spf.google.com include:spf.protection.outlook.com -all
```

**If the SPF record already contains `include:spf.protection.outlook.com`** (common for Microsoft 365 domains), **no SPF change is needed** — ACS sends through the same Microsoft infrastructure.

> **Important correction:** Azure Communication Services uses `include:spf.protection.outlook.com` for SPF — the same as Microsoft 365. There is no `spf.azurecomm.net` record. If uscar.org already uses Microsoft 365 for email, the existing SPF record likely already authorizes ACS sends.

### How to Check the Current SPF Record

```bash
# From any command line:
nslookup -type=txt uscar.org

# Or on Linux/Mac:
dig TXT uscar.org +short
```

Look for a TXT record starting with `v=spf1`. If one exists, modify it. If none exists, create one.

---

## Summary Table (Copy-Paste Ready)

| # | Type  | Host/Name                                      | Value / Target                                               | TTL  |
|---|-------|-------------------------------------------------|--------------------------------------------------------------|------|
| 1 | TXT   | `@`                                             | `ms-domain-verification=a5695984-4dc7-4841-abd3-25c71f092ee7` | 3600 |
| 2 | CNAME | `selector1-azurecomm-prod-net._domainkey`       | `selector1-azurecomm-prod-net._domainkey.azurecomm.net`      | 3600 |
| 3 | CNAME | `selector2-azurecomm-prod-net._domainkey`       | `selector2-azurecomm-prod-net._domainkey.azurecomm.net`      | 3600 |
| 4 | TXT   | `_dmarc`                                        | `v=DMARC1; p=none; rua=mailto:dmarc-reports@uscar.org; fo=1` | 3600 |
| 5 | TXT   | `@` (**update existing SPF, do NOT add second**) | Ensure `include:spf.protection.outlook.com` is present (see SPF section above) | 3600 |

---

## Verification Checklist (For DNS Admin)

After adding the records:

- [ ] TXT record for `@` contains `ms-domain-verification=a5695984-...` (visible via `nslookup -type=txt uscar.org`)
- [ ] CNAME for `selector1-azurecomm-prod-net._domainkey.uscar.org` resolves to `...azurecomm.net`
- [ ] CNAME for `selector2-azurecomm-prod-net._domainkey.uscar.org` resolves to `...azurecomm.net`
- [ ] `_dmarc.uscar.org` TXT record is present with `v=DMARC1` policy
- [ ] SPF record for `uscar.org` includes `include:spf.protection.outlook.com` (single SPF record only — if uscar.org uses M365, this is likely already present)
- [ ] Notify the RFPO engineering team when records are live so we can trigger verification on the Azure side

> **DNS propagation:** Changes typically take 15-60 minutes, but can take up to 48 hours depending on TTL of previously cached records and registrar.

---

## What Happens After DNS Is Configured

Once the DNS admin confirms the records are live, the RFPO engineering team will:

1. **Trigger domain verification** in Azure Communication Services (automated check of TXT + DKIM records)
2. **Link `uscar.org`** to the ACS Communication Service resource
3. **Create the sender address** `rfpo@uscar.org` within ACS
4. **Update the application configuration** to use `rfpo@uscar.org` as the sender (`ACS_SENDER_EMAIL`)
5. **Send test emails** to USCAR mailboxes and confirm:
   - Delivery to primary inbox (not spam)
   - Sender shows `rfpo@uscar.org`
   - Email headers pass SPF, DKIM, and DMARC checks
6. **Confirm with the customer** that emails are being received

---

## Timeline Expectations

| Step | Owner | Estimated Time |
|------|-------|----------------|
| Add DNS records | USCAR DNS Admin | Same day (once approved) |
| DNS propagation | Automatic | 15 min – 48 hours |
| Azure domain verification | RFPO Engineering | Minutes (after propagation) |
| Sender configuration + testing | RFPO Engineering | Same day |
| Customer confirmation | USCAR / RFPO | 1-2 business days |

---

## Contact / Questions

If the DNS admin has questions about these records, they can reach out to the RFPO engineering team. Common questions:

**Q: Will this affect our existing email (Microsoft 365, Exchange)?**
A: No. The DKIM selectors are unique to Azure Communication Services (`selector1-azurecomm-prod-net`) and won't conflict with Microsoft 365 DKIM selectors (`selector1._domainkey`, `selector2._domainkey`). ACS uses the same SPF infrastructure as Microsoft 365 (`spf.protection.outlook.com`), so if uscar.org already uses M365, SPF is likely already configured correctly — no changes needed.

**Q: What does the `ms-domain-verification` TXT record do?**
A: It proves domain ownership to Azure. It has no effect on email delivery or any other service. It can be removed after initial verification, but we recommend keeping it in case re-verification is needed.

**Q: Can we use a subdomain instead (e.g., `notifications.uscar.org`)?**
A: Yes — we are now using `rfpo.uscar.org` as the email subdomain to avoid SPF conflicts with the root domain. See the subdomain section below.

**Q: What is the sender address?**
A: `rfpo@rfpo.uscar.org` — this is the "From" address users will see. Only the RFPO application will send from this address via Azure Communication Services.

---

## NEW: rfpo.uscar.org Subdomain Records (Priority)

**Date added:** 2026-04-02
**Status:** DNS records needed from IT — Azure domain already created and waiting for verification

To avoid SPF conflicts with the root `uscar.org` domain (which uses `~all` soft-fail and includes other mechanisms that ACS verification rejects), we are using the subdomain `rfpo.uscar.org` for RFPO email sending. This subdomain gets its own clean SPF record with exactly what Azure requires.

**The sender address will be:** `rfpo@rfpo.uscar.org`

### Subdomain Record 1 — Domain Ownership Verification (TXT)

| Field       | Value                                                       |
|-------------|-------------------------------------------------------------|
| **Type**    | TXT                                                         |
| **Host**    | `rfpo` (or `rfpo.uscar.org` if your DNS requires FQDN)     |
| **Value**   | `ms-domain-verification=108186d9-e50b-415f-8418-7aa9ceb1b6b2` |
| **TTL**     | 3600                                                        |

### Subdomain Record 2 — SPF (TXT)

This is a **new record** on the subdomain — it will NOT conflict with the root domain's SPF.

| Field       | Value                                                       |
|-------------|-------------------------------------------------------------|
| **Type**    | TXT                                                         |
| **Host**    | `rfpo` (or `rfpo.uscar.org` if your DNS requires FQDN)     |
| **Value**   | `v=spf1 include:spf.protection.outlook.com -all`            |
| **TTL**     | 3600                                                        |

> **Note:** This is a completely separate SPF record from the root `uscar.org` SPF. It only applies to `rfpo.uscar.org` and does not affect any existing email infrastructure.

### Subdomain Record 3 — DKIM Signing Key Selector 1 (CNAME)

| Field       | Value                                                              |
|-------------|--------------------------------------------------------------------|
| **Type**    | CNAME                                                              |
| **Host**    | `selector1-azurecomm-prod-net._domainkey.rfpo`                    |
| **Target**  | `selector1-azurecomm-prod-net._domainkey.azurecomm.net`           |
| **TTL**     | 3600                                                               |

### Subdomain Record 4 — DKIM Signing Key Selector 2 (CNAME)

| Field       | Value                                                              |
|-------------|--------------------------------------------------------------------|
| **Type**    | CNAME                                                              |
| **Host**    | `selector2-azurecomm-prod-net._domainkey.rfpo`                    |
| **Target**  | `selector2-azurecomm-prod-net._domainkey.azurecomm.net`           |
| **TTL**     | 3600                                                               |

### Subdomain Record 5 — DMARC (TXT) — Recommended

| Field       | Value                                                              |
|-------------|--------------------------------------------------------------------|
| **Type**    | TXT                                                                |
| **Host**    | `_dmarc.rfpo`                                                      |
| **Value**   | `v=DMARC1; p=reject; rua=mailto:dmarc-reports@uscar.org; fo=1`   |
| **TTL**     | 3600                                                               |

> **Note:** Since `rfpo.uscar.org` is exclusively used by the RFPO application through Azure, we can use `p=reject` (strict mode) instead of `p=none`. This tells mail servers to reject any email from `rfpo.uscar.org` that fails SPF/DKIM — providing maximum anti-spoofing protection.

### Subdomain Summary Table (Copy-Paste Ready)

| # | Type  | Host/Name                                      | Value / Target                                               | TTL  |
|---|-------|-------------------------------------------------|--------------------------------------------------------------|------|
| 1 | TXT   | `rfpo`                                          | `ms-domain-verification=108186d9-e50b-415f-8418-7aa9ceb1b6b2` | 3600 |
| 2 | TXT   | `rfpo`                                          | `v=spf1 include:spf.protection.outlook.com -all`             | 3600 |
| 3 | CNAME | `selector1-azurecomm-prod-net._domainkey.rfpo`  | `selector1-azurecomm-prod-net._domainkey.azurecomm.net`      | 3600 |
| 4 | CNAME | `selector2-azurecomm-prod-net._domainkey.rfpo`  | `selector2-azurecomm-prod-net._domainkey.azurecomm.net`      | 3600 |
| 5 | TXT   | `_dmarc.rfpo`                                   | `v=DMARC1; p=reject; rua=mailto:dmarc-reports@uscar.org; fo=1` | 3600 |

### Verification Checklist (Subdomain)

After adding the subdomain records:

- [ ] TXT record for `rfpo.uscar.org` contains `ms-domain-verification=108186d9-...` (check: `nslookup -type=txt rfpo.uscar.org`)
- [ ] TXT record for `rfpo.uscar.org` contains `v=spf1 include:spf.protection.outlook.com -all` (check: `nslookup -type=txt rfpo.uscar.org`)
- [ ] CNAME `selector1-azurecomm-prod-net._domainkey.rfpo.uscar.org` resolves to `...azurecomm.net`
- [ ] CNAME `selector2-azurecomm-prod-net._domainkey.rfpo.uscar.org` resolves to `...azurecomm.net`
- [ ] TXT record for `_dmarc.rfpo.uscar.org` contains DMARC policy
- [ ] Notify RFPO engineering when records are live

> **Why a subdomain?** The root `uscar.org` SPF record contains additional mechanisms and uses `~all` (soft-fail) which Azure's SPF verification does not accept. The subdomain gets a clean, dedicated SPF record that passes Azure's strict verification. This also means zero risk to existing `uscar.org` email infrastructure.
