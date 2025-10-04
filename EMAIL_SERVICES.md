# RFPO Application – Email Services

This document explains how outbound email works in the RFPO application, how to provision and configure Azure Communication Services (ACS) Email, how to use SMTP as a fallback, and how to test and troubleshoot.

- Preferred provider: Azure Communication Services (Email)
- Fallback provider: SMTP (MAIL_/SMTP_/GMAIL_ env variants)
- Admin UI: shows a small badge indicating the active provider mode and includes a Tools → Email Test page for quick validation.

Related files:

- `email_service.py` – provider selection, ACS/SMTP sending, diagnostics
- `custom_admin.py` – injects email mode/label into templates and provides an admin test route
- `templates/admin/base.html` – badge showing current email mode
- `templates/admin/tools/email_test.html` – email test page (subject/body tagging, “Send to me” quick action)
- `update-azure-env-vars.sh` – updates Azure Container Apps environment variables, including optional ACS/SMTP settings


## 1) Provider selection and behavior

The application automatically selects a provider based on environment variables:

Priority order:

1. ACS if both are set:
   - `ACS_CONNECTION_STRING`
   - `ACS_SENDER_EMAIL`
1. SMTP if a compatible set of variables is provided (any of MAIL_/SMTP_/GMAIL_ variants). See Appendix A for full list.

UI indicators and tagging:

- Admin sidebar shows a badge like: “Email: ACS” or “Email: SMTP” or “Email: disabled”.
- The email test page normalizes the subject with `[ACS]` or `[SMTP]` so it’s easy to confirm which provider sent it.
- The admin test route surfaces diagnostics from the last send attempt (provider, sender, error/status).


## 2) Provision ACS Email (recommended)

These steps create an ACS resource, an Email Service, an Azure-managed domain, and a sender identity.

Prerequisites:
- Azure CLI logged in to the correct subscription
- Resource Group: `rg-rfpo-e108977f`
- Location/Data Location: United States (to match SDK and service availability)

Steps:

1. Register the resource provider (one-time per subscription):

```sh
az provider register -n Microsoft.Communication --wait
```

2. Create the Communication Service (ACS):

```sh
az communication create \
  --name rfpo-acs \
  --resource-group rg-rfpo-e108977f \
  --location global \
  --data-location UnitedStates \
  --tags project=rfpo env=prod
```

3. Create the Email Service (for domains/senders):

```sh
az communication email create \
  --name rfpo-email \
  --resource-group rg-rfpo-e108977f \
  --location global \
  --data-location UnitedStates \
  --tags project=rfpo env=prod
```

4. Create an Azure-managed domain (no DNS setup required):

```sh
az communication email domain create \
  --email-service-name rfpo-email \
  --resource-group rg-rfpo-e108977f \
  --name AzureManagedDomain \
  --location global \
  --domain-management AzureManaged
```

Note: The managed domain will be something like `<guid>.azurecomm.net` and is fully verified automatically (SPF/DKIM/DMARC).

  1. Link the domain to the Communication Service (required):

  ```sh
  az communication update \
    --name rfpo-acs \
    --resource-group rg-rfpo-e108977f \
    --set linked_domains="[\"/subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630/resourceGroups/rg-rfpo-e108977f/providers/Microsoft.Communication/emailServices/rfpo-email/domains/AzureManagedDomain\"]"
  ```

  Without this link, sends fail with DomainNotLinked. Re-run if you recreate the Email Service or the domain.

5. Create a sender username on the managed domain:

```sh
az communication email domain sender-username create \
  --email-service-name rfpo-email \
  --resource-group rg-rfpo-e108977f \
  --domain-name AzureManagedDomain \
  --name <sender_user> \
  --username <sender_user>
```

6. Retrieve the domain to compose the From address:

```sh
MANAGED_DOMAIN=$(az communication email domain show \
  --email-service-name rfpo-email \
  --resource-group rg-rfpo-e108977f \
  --name AzureManagedDomain \
  --query fromSenderDomain -o tsv)

# Example sender email (replace <sender_user> appropriately)
export ACS_SENDER_EMAIL="<sender_user>@${MANAGED_DOMAIN}"
```

7. Get the ACS connection string (and keep it secret):

```sh
export ACS_CONNECTION_STRING=$(az communication list-key \
  --name rfpo-acs \
  --resource-group rg-rfpo-e108977f \
  --query primaryConnectionString -o tsv)
```

8. Apply to rfpo-admin (Container Apps) using the helper script:

```sh
./update-azure-env-vars.sh
```

This script safely updates `rfpo-admin` with `ACS_CONNECTION_STRING` and `ACS_SENDER_EMAIL` when they are defined in your shell environment. It also refreshes other app env vars.

Security tip: If you ever printed a connection string to the console, rotate it:

```sh
az communication regenerate-key \
  --name rfpo-acs \
  --resource-group rg-rfpo-e108977f \
  --key-type primary

# Then re-apply the new connection string to rfpo-admin as above
```


## 3) Using your own domain (optional)

If you want the From address to come from a domain you control (e.g., `notifications@yourdomain.com`), use a Customer Managed domain and complete DNS verification.

1. Create the domain as CustomerManaged:

```sh
az communication email domain create \
  --email-service-name rfpo-email \
  --resource-group rg-rfpo-e108977f \
  --name <YourDomainResourceName> \
  --location global \
  --domain-management CustomerManaged \
  --domain-name yourdomain.com
```

1. Initiate verification to see the DNS records:

```sh
az communication email domain initiate-verification \
  --email-service-name rfpo-email \
  --resource-group rg-rfpo-e108977f \
  --name <YourDomainResourceName>
```

1. Add the provided TXT/CNAME/MX records in your DNS. Re-run the show command until all records are Verified.

1. Create a sender username on your verified domain and set `ACS_SENDER_EMAIL` to the new From address. Re-run `./update-azure-env-vars.sh` to apply.


## 4) SMTP fallback (iCloud/Gmail/other)

If you need to send from a mailbox like `johnbouchard@icloud.com`, you can use SMTP instead of ACS. The app recognizes a variety of MAIL_/SMTP_/GMAIL_ environment variables (see Appendix A).

Example (iCloud with app-specific password):

```sh
export MAIL_SERVER=smtp.mail.me.com
export MAIL_PORT=587
export MAIL_USE_TLS=true
export MAIL_USERNAME="johnbouchard@icloud.com"
export MAIL_PASSWORD="<icloud_app_password>"
export MAIL_DEFAULT_SENDER="johnbouchard@icloud.com"

./update-azure-env-vars.sh
```

Notes:

- iCloud and Gmail require app-specific passwords when 2FA is enabled.
- When SMTP is configured (and ACS is not), the admin badge will show “Email: SMTP” and the test page will tag subjects with [SMTP].
- If both ACS and SMTP are configured, ACS takes precedence by default.


## 5) Testing in the Admin UI

- Go to the Admin app and login (see repo docs for credentials)
- Navigate to: Tools → Email Test
- Use “Send to me” to quickly send a test email
- The page flashes provider/sender and error/status details from the last send

Visual cues:

- Sidebar badge: shows current mode (ACS/SMTP/disabled)
- Subject tag: automatically normalized to [ACS] or [SMTP]


## 6) Troubleshooting

- “Email: disabled” badge
  - No ACS or SMTP environment variables were detected. Set either ACS variables or SMTP variables and re-deploy/update envs.
- `Microsoft.Communication` not registered
  - Run `az provider register -n Microsoft.Communication --wait` and retry ACS provisioning.
- “Resource name should be AzureManagedDomain”
  - The Azure-managed domain resource must be named `AzureManagedDomain`.
- Cannot send “From” third-party domains
  - ACS requires domain ownership/verification. You cannot send as `@icloud.com` or other domains you don’t own. Use SMTP for those.
- SMTP auth errors
  - Verify server, port, TLS, and app-specific password. For Gmail, ensure “App Passwords” are set up and use `smtp.gmail.com`.
- No emails received
  - Check spam/filters; ensure the recipient domain accepts the managed domain; try SMTP alternative to isolate issues.
- Rotate compromised keys
  - Use `az communication regenerate-key` and re-apply to rfpo-admin.


## 7) Dependencies

- Python SDK: `azure-communication-email` (see `requirements.txt`)
- Flask app uses Jinja templates and `email_service.py` to orchestrate provider selection and sending.


## Appendix A – Recognized environment variables

ACS (preferred):

- `ACS_CONNECTION_STRING` (required for ACS)
- `ACS_SENDER_EMAIL` (required for ACS)

SMTP (any compatible set – the app will combine variants):

- `MAIL_SERVER` or `SMTP_SERVER`
- `MAIL_PORT` or `SMTP_PORT` (e.g., 587)
- `MAIL_USE_TLS` or `SMTP_USE_TLS` (true/false)
- `MAIL_USERNAME` or `SMTP_USERNAME` or `GMAIL_USER`
- `MAIL_PASSWORD` or `SMTP_PASSWORD` or `GMAIL_APP_PASSWORD`
- `MAIL_DEFAULT_SENDER` or `SMTP_DEFAULT_SENDER` or `GMAIL_USER`

Tip: Use the helper script `./update-azure-env-vars.sh` to apply these to the `rfpo-admin` Container App. It will only set ACS/SMTP envs if they are present in your shell environment.

---

If you want help switching to a Customer Managed domain or wiring SMTP for a specific mailbox, open an issue or ping in chat—we can apply the exact DNS records or SMTP provider settings for your environment.
