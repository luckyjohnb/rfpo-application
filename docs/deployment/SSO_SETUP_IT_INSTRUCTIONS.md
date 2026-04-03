# SAML SSO Setup Instructions for USCAR IT

**Date:** 2026-04-02
**Audience:** USCAR IT / Entra ID Administrator
**Requested by:** RFPO Engineering
**Purpose:** Create a SAML Enterprise Application in Entra ID so RFPO users from Ford, GM, Stellantis, and other partner companies can sign in with their corporate credentials.

---

## Overview

The RFPO application at `https://rfpo.uscar.org` needs SAML SSO so that external users (B2B guests from @ford.com, @gm.com, @stellantis.com, etc.) can sign in with their corporate credentials via Microsoft Entra ID.

The application handles its own user management — IT's role is to:
1. Create the Enterprise Application
2. Configure SAML endpoints and claims
3. Invite guest users and assign roles

---

## Step 1: Create Enterprise Application

1. Go to **Microsoft Entra admin center** → **Enterprise applications** → **New application**
2. Click **Create your own application**
3. Name: `RFPO Application` (or similar)
4. Select: **Integrate any other application you don't find in the gallery (Non-gallery)**
5. Click **Create**

---

## Step 2: Configure SAML Single Sign-On

1. In the Enterprise Application → **Single sign-on** → Select **SAML**
2. Under **Basic SAML Configuration**, click **Edit** and enter these values:

> **Shortcut (optional):** Instead of entering values manually, you can import our SP metadata XML from `https://rfpo.uscar.org/saml/metadata`. This auto-fills the fields below. If you prefer manual entry, use the table:

| Setting | Value |
|---------|-------|
| **Identifier (Entity ID)** | `https://rfpo.uscar.org` |
| **Reply URL (Assertion Consumer Service URL)** | `https://rfpo.uscar.org/saml/acs` |
| **Sign on URL** | `https://rfpo.uscar.org/` |
| **Relay State** | *(leave empty)* |
| **Logout URL** | `https://rfpo.uscar.org/saml/sls` |

3. Click **Save**

---

## Step 3: Configure Attributes & Claims

1. In the **Single sign-on** page → **Attributes & Claims** → click **Edit**

### 3a. Required Claim (Name ID)

The default Name ID should be set to:

| Setting | Value |
|---------|-------|
| **Name identifier format** | Email address |
| **Source** | Attribute |
| **Source attribute** | `user.userprincipalname` |

> **Important:** The Name ID must be the user's email address. The RFPO application matches users by email.

### 3b. Custom Role Claim (Add New Claim)

Click **Add new claim** and configure:

| Setting | Value |
|---------|-------|
| **Name** | `role` |
| **Namespace** | `https://rfpo.uscar.org/saml/attributes` |
| **Source** | Attribute |
| **Source attribute** | `user.assignedroles` |

This produces the full claim URI: `https://rfpo.uscar.org/saml/attributes/role`

> **Why this matters:** The RFPO application reads this claim to determine the user's permission level (RFPO_USER vs RFPO_ADMIN).

### 3c. Standard Additional Claims

These should already be present by default. Verify they exist:

| Claim Name | Source Attribute |
|------------|------------------|
| `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress` | `user.mail` |
| `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname` | `user.givenname` |
| `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname` | `user.surname` |
| `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name` | `user.userprincipalname` |

---

## Step 4: Define App Roles

App Roles must be defined on the **App Registration** (not the Enterprise Application). To find the App Registration:

1. Go to **Microsoft Entra admin center** → **App registrations** → search for `RFPO Application`
2. Click **App roles** → **Create app role** for each:

| Display Name | Value | Description | Allowed member types |
|-------------|-------|-------------|---------------------|
| RFPO User | `RFPO_USER` | Standard RFPO user — can view and create RFPOs | Users/Groups |
| RFPO Admin | `RFPO_ADMIN` | RFPO administrator — full CRUD operations | Users/Groups |

> **Note:** These are case-sensitive values. Use `RFPO_USER` and `RFPO_ADMIN` exactly as shown.

---

## Step 5: Create Security Groups & Assign to App

1. Go to **Microsoft Entra admin center** → **Groups** → **New group**
2. Create groups such as:
   - `RFPO Users` → will be assigned the `RFPO_USER` role
   - `RFPO Admins` → will be assigned the `RFPO_ADMIN` role
3. Go back to the **Enterprise Application** → **Users and groups** → **Add user/group**
4. Select the group → Select the appropriate role → **Assign**

---

## Step 6: Configure B2B Collaboration Settings

To allow external users from partner companies:

1. Go to **Microsoft Entra admin center** → **External Identities** → **Cross-tenant access settings**
2. Ensure the following domains are allowed for B2B collaboration:
   - `ford.com`
   - `gm.com`
   - `stellantis.com`
   - *(add other partner domains as needed)*

---

## Step 7: Invite Test Guest User

1. Go to **Microsoft Entra admin center** → **Users** → **Invite external user**
2. Invite a test user (e.g., a @ford.com email)
3. Add the guest user to one of the security groups created in Step 5
4. The user should receive an invitation email — they accept it to complete B2B enrollment

---

## Step 8: Provide These 4 Values to RFPO Engineering

After completing the Enterprise Application setup, RFPO engineering needs these values from the **Single sign-on** page of the Enterprise Application:

| What We Need | Where to Find It in Azure Portal |
|-------------|----------------------------------|
| **IdP Entity ID** (Azure AD Identifier) | Single sign-on → Section 4 "Set up RFPO Application" → **Azure AD Identifier** |
| **IdP SSO URL** (Login URL) | Single sign-on → Section 4 "Set up RFPO Application" → **Login URL** |
| **IdP SLS URL** (Logout URL) | Single sign-on → Section 4 "Set up RFPO Application" → **Logout URL** |
| **X.509 Signing Certificate** (Base64) | Single sign-on → Section 3 "SAML Certificates" → **Certificate (Base64)** → click **Download** |

### Expected format of values

The IdP values will look like:
- **Azure AD Identifier:** `https://sts.windows.net/3f59ba70-530a-4800-be1b-f5b04e0e15f7/`
- **Login URL:** `https://login.microsoftonline.com/3f59ba70-530a-4800-be1b-f5b04e0e15f7/saml2`
- **Logout URL:** `https://login.microsoftonline.com/3f59ba70-530a-4800-be1b-f5b04e0e15f7/saml2`
- **Certificate:** A downloaded `.cer` file — send the file or the Base64 text content

> **Note on the tenant ID:** The USCAR tenant is `3f59ba70-530a-4800-be1b-f5b04e0e15f7`. The URLs above are examples — the actual values will appear in the Azure Portal after the Enterprise Application is created.

---

## Verification Checklist

Before notifying RFPO engineering that the setup is complete:

- [ ] Enterprise Application created with SAML single sign-on
- [ ] Basic SAML Configuration has all 4 URLs entered correctly
- [ ] Name ID is set to `user.userprincipalname` with email format
- [ ] Custom role claim `https://rfpo.uscar.org/saml/attributes/role` is configured with source `user.assignedroles`
- [ ] Standard claims (email, givenname, surname, name) are present
- [ ] App Roles `RFPO_USER` and `RFPO_ADMIN` are defined on the App Registration
- [ ] At least one security group is created and assigned to the Enterprise Application with a role
- [ ] At least one test guest user is invited and added to a group
- [ ] B2B collaboration allows @ford.com, @gm.com, @stellantis.com domains
- [ ] The 4 IdP values (Entity ID, Login URL, Logout URL, Certificate) are collected and ready to send to engineering

---

## What Happens After You Send Us the 4 Values

RFPO engineering will:

1. Set the IdP environment variables on the RFPO Container App
2. Enable SAML SSO (`SAML_ENABLED=true`)
3. The login page at `https://rfpo.uscar.org/login` will show a **"Sign in with Microsoft"** button
4. Users click the button → redirected to Microsoft login → authenticate with their corporate credentials → returned to RFPO
5. Existing password login will **continue to work** alongside SSO (both methods available)

---

## Impact on Existing Users

- **No disruption** — existing password-based logins remain functional
- **No user migration needed** — SSO users are matched by email to existing RFPO accounts
- **No downtime** — SSO is enabled via environment variables without redeployment
- **Gradual rollout** — can start with one test user before opening to all partner domains

---

## FAQ

**Q: Will this affect the Admin Panel at `rfpo-admin.uscar.org`?**
A: Not in Phase 1. The admin panel will remain password-only. SSO will be added to the admin panel in a future phase if needed.

**Q: Do we need to create RFPO user accounts separately?**
A: Yes. The RFPO application requires a user account to exist before SSO login works. An RFPO admin creates the user (with their corporate email) in the RFPO admin panel, then the user can sign in via SSO. This is by design — it prevents unauthorized access.

**Q: What if a user's email in Entra ID doesn't match their RFPO account?**
A: The application matches on email (case-insensitive). The user's `userprincipalname` in Entra ID must match the email address in their RFPO account. For B2B guests, this is typically their home email (e.g., `user@ford.com`).

**Q: Can we test SSO before inviting all partner users?**
A: Yes. Invite one test guest user, add them to the RFPO Users group, and create a matching RFPO account. Engineering will test the full flow with this single user before opening up.

**Q: What certificate format do you need?**
A: The Base64-encoded X.509 signing certificate. Download the "Certificate (Base64)" from the SAML Certificates section. Send the `.cer` file or paste the Base64 content (the text between `-----BEGIN CERTIFICATE-----` and `-----END CERTIFICATE-----`, without headers).
