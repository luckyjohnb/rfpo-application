# uscar.org DNS Records for ACS Email

These records are required to verify the Customer Managed Azure Communication Services (ACS) Email domain for uscar.org and enable DKIM. Share this file with the DNS administrators.

Important

- Add the TXT and both CNAME records exactly as shown below.
- Do NOT add a second SPF record if one already exists for uscar.org.
- DMARC is optional but recommended for deliverability.

Required records

1. TXT (domain verification)

   - Name/Host: @ (root)
   - Type: TXT
   - TTL: 3600
   - Value: `ms-domain-verification=a5695984-4dc7-4841-abd3-25c71f092ee7`

2. CNAME (DKIM selector 1)

   - Name/Host: `selector1-azurecomm-prod-net._domainkey`
   - Type: CNAME
   - TTL: 3600
   - Target: `selector1-azurecomm-prod-net._domainkey.azurecomm.net`

3. CNAME (DKIM selector 2)

   - Name/Host: `selector2-azurecomm-prod-net._domainkey`
   - Type: CNAME
   - TTL: 3600
   - Target: `selector2-azurecomm-prod-net._domainkey.azurecomm.net`

Optional (recommended)

4. DMARC TXT

   - Name/Host: `_dmarc`
   - Type: TXT
   - TTL: 3600
   - Value: `v=DMARC1; p=none; rua=mailto:dmarc@uscar.org; fo=1`

Cutover steps after DNS verifies

1. Link uscar.org to the Communication Service (rfpo-acs linkedDomains)
2. Create sender username: rfpo (address `rfpo@uscar.org`)
3. Update rfpo-admin env: `ACS_SENDER_EMAIL=rfpo@uscar.org`
4. Use Admin → Tools → Email Test to validate E2E sending
