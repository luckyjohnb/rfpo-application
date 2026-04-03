# DNS Configuration for uscar.org — RFPO Application

**Date:** 2026-04-02
**Audience:** USCAR DNS / IT Administrator
**Requested by:** RFPO Engineering

---

## Current Status (as of 2026-04-02)

### COMPLETED — No action needed:
- **Email sending from `rfpo@uscar.org`** — Domain verified, DKIM verified, SPF verified (updated to `-all`). Sender is live.

### ON HOLD — Do NOT add:
- **Email subdomain `rfpo.uscar.org`** — No longer needed since root domain SPF was fixed.

### ACTION REQUIRED — Please add these 6 DNS records:
- **Custom domain records** for `rfpo.uscar.org`, `rfpo-admin.uscar.org`, `rfpo-api.uscar.org`
- These give the RFPO web application clean branded URLs instead of the long Azure-generated ones
- **See the "Custom Domains" section below for the exact records**

---

## Custom Domains for RFPO Application (ACTION REQUIRED)

The RFPO application runs on Azure Container Apps, which assigns long auto-generated URLs like `rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io`. We need clean, branded `uscar.org` subdomains.

These custom domains also serve as the **SSO (SAML) Entity IDs and callback URLs** for the upcoming Microsoft Entra ID integration — so they need to be in place before SSO goes live.

### What the URLs Will Become

| Subdomain | Points To (Azure Container App) | Purpose |
|-----------|----------------------------------|--------|
| `rfpo.uscar.org` | `rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io` | Customer-facing user app |
| `rfpo-admin.uscar.org` | `rfpo-admin.livelyforest-d06a98a0.eastus.azurecontainerapps.io` | Admin panel |
| `rfpo-api.uscar.org` | `rfpo-api.livelyforest-d06a98a0.eastus.azurecontainerapps.io` | API layer |

### DNS Records Required (6 total)

Azure Container Apps requires **two records per subdomain**: a **TXT record** for domain ownership verification, and a **CNAME record** to route traffic.

#### Domain Verification TXT Records

All three apps share the same verification ID. Add these TXT records:

| # | Type | Host/Name | Value | TTL |
|---|------|-----------|-------|-----|
| 1 | TXT | `asuid.rfpo` | `92AD77A30DEAB51492DBE7D424BC6B8026AA51D21C1856F7498C4D009F697494` | 3600 |
| 2 | TXT | `asuid.rfpo-admin` | `92AD77A30DEAB51492DBE7D424BC6B8026AA51D21C1856F7498C4D009F697494` | 3600 |
| 3 | TXT | `asuid.rfpo-api` | `92AD77A30DEAB51492DBE7D424BC6B8026AA51D21C1856F7498C4D009F697494` | 3600 |

> **Note:** The `asuid.` prefix is required by Azure for domain verification. The value is the same for all three because they share the same Container Apps Environment.

#### CNAME Records

| # | Type | Host/Name | Target | TTL |
|---|------|-----------|--------|-----|
| 4 | CNAME | `rfpo` | `rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io` | 3600 |
| 5 | CNAME | `rfpo-admin` | `rfpo-admin.livelyforest-d06a98a0.eastus.azurecontainerapps.io` | 3600 |
| 6 | CNAME | `rfpo-api` | `rfpo-api.livelyforest-d06a98a0.eastus.azurecontainerapps.io` | 3600 |

### Summary Table (Copy-Paste Ready)

| # | Type  | Host/Name        | Value / Target                                                          | TTL  |
|---|-------|------------------|-------------------------------------------------------------------------|------|
| 1 | TXT   | `asuid.rfpo`      | `92AD77A30DEAB51492DBE7D424BC6B8026AA51D21C1856F7498C4D009F697494`     | 3600 |
| 2 | TXT   | `asuid.rfpo-admin` | `92AD77A30DEAB51492DBE7D424BC6B8026AA51D21C1856F7498C4D009F697494`    | 3600 |
| 3 | TXT   | `asuid.rfpo-api`  | `92AD77A30DEAB51492DBE7D424BC6B8026AA51D21C1856F7498C4D009F697494`     | 3600 |
| 4 | CNAME | `rfpo`            | `rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io`         | 3600 |
| 5 | CNAME | `rfpo-admin`      | `rfpo-admin.livelyforest-d06a98a0.eastus.azurecontainerapps.io`        | 3600 |
| 6 | CNAME | `rfpo-api`        | `rfpo-api.livelyforest-d06a98a0.eastus.azurecontainerapps.io`          | 3600 |

### Verification Checklist

After adding the records:

- [ ] `nslookup -type=txt asuid.rfpo.uscar.org` returns the verification ID
- [ ] `nslookup -type=txt asuid.rfpo-admin.uscar.org` returns the verification ID
- [ ] `nslookup -type=txt asuid.rfpo-api.uscar.org` returns the verification ID
- [ ] `nslookup -type=cname rfpo.uscar.org` → `rfpo-user.livelyforest-...`
- [ ] `nslookup -type=cname rfpo-admin.uscar.org` → `rfpo-admin.livelyforest-...`
- [ ] `nslookup -type=cname rfpo-api.uscar.org` → `rfpo-api.livelyforest-...`
- [ ] Notify RFPO engineering when records are live

### What Happens After DNS Is Configured

Once RFPO engineering confirms the DNS records are live:

1. Custom domains are added to each Container App in Azure
2. Azure automatically provisions **free managed TLS certificates** (HTTPS)
3. Application URLs become:
   - **User App:** `https://rfpo.uscar.org`
   - **Admin Panel:** `https://rfpo-admin.uscar.org`
   - **API:** `https://rfpo-api.uscar.org`
4. The old `*.livelyforest-*.azurecontainerapps.io` URLs will continue to work (they won't break)
5. SSO (SAML) configuration will be updated to use `rfpo.uscar.org` as the Entity ID

### Impact on Existing Services

- **No downtime** — custom domains are added alongside existing URLs
- **No email impact** — this is for web application URLs, not email sending
- **TLS is automatic** — Azure manages certificate provisioning and renewal
- **Old URLs keep working** — existing bookmarks and integrations won't break

---
---

# Reference: Previously Completed DNS Records

> **The sections below are for reference only. These records are already in place and verified. IT does not need to take any action on them.**

---

## Email Domain Records — COMPLETED (Reference Only)

These records were added and verified as of 2026-04-02. They enable the RFPO application to send emails as `rfpo@uscar.org`.

**Verification status:**
- Record 1 (Domain TXT) — VERIFIED
- Record 2 (DKIM1 CNAME) — VERIFIED
- Record 3 (DKIM2 CNAME) — VERIFIED
- Record 4 (DMARC TXT) — Added
- SPF — VERIFIED (IT updated from `~all` to `-all` on 2026-04-02)

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

## What Happened After DNS Was Configured (Completed)

The following steps were completed by RFPO engineering on 2026-04-02:

1. Domain verification triggered in Azure Communication Services — all checks passed
2. `uscar.org` linked to the ACS Communication Service resource (`rfpo-acs`)
3. Sender address `rfpo@uscar.org` ("USCAR RFPO System") created
4. Application configured with `ACS_SENDER_EMAIL=rfpo@uscar.org`
5. Email sending is live and operational

---

## Contact / Questions

If the DNS admin has questions about these records, they can reach out to the RFPO engineering team. Common questions:

**Q: Will this affect our existing email (Microsoft 365, Exchange)?**
A: No. The DKIM selectors are unique to Azure Communication Services (`selector1-azurecomm-prod-net`) and won't conflict with Microsoft 365 DKIM selectors (`selector1._domainkey`, `selector2._domainkey`). ACS uses the same SPF infrastructure as Microsoft 365 (`spf.protection.outlook.com`), so if uscar.org already uses M365, SPF is likely already configured correctly — no changes needed.

**Q: What does the `ms-domain-verification` TXT record do?**
A: It proves domain ownership to Azure. It has no effect on email delivery or any other service. It can be removed after initial verification, but we recommend keeping it in case re-verification is needed.

**Q: Can we use a subdomain instead (e.g., `notifications.uscar.org`)?**
A: We evaluated this but it's no longer needed — the root domain SPF fix (`-all`) resolved the verification issue.

**Q: What is the sender address?**
A: `rfpo@uscar.org` — this is the "From" address users will see. Only the RFPO application will send from this address via Azure Communication Services.

---

## ARCHIVED — rfpo.uscar.org Email Subdomain Records (ON HOLD — do NOT add)

**Date added:** 2026-04-02
**Status:** ON HOLD — Not needed since root domain SPF was fixed to `-all`

> **DO NOT ADD THESE RECORDS.** The root domain `uscar.org` is now fully verified for email sending. These records are documented here for reference only in case the strategy changes.

<details>
<summary>Click to expand archived email subdomain records (for reference only)</summary>

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

</details>

> **UPDATE 2026-04-02:** The root domain SPF was fixed to `-all` and is now fully verified. The `rfpo.uscar.org` email subdomain is **on hold**.


