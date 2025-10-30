# Secrets Management

🟢 **PRODUCTION STATUS: DEPLOYED & LIVE**

The RFPO application uses secure, environment-based secrets management with different approaches for local development and Azure production deployment. **No secrets are ever baked into Docker images or committed to the repository.**

## 🚀 Current Production Deployment

- **Status**: ✅ **LIVE ON AZURE CONTAINER APPS**
- **Resource Group**: `rg-rfpo-e108977f` (East US)
- **Environment**: `rfpo-env-5kn5bsg47vvac`
- **Domain**: `livelyforest-d06a98a0.eastus.azurecontainerapps.io`

**Live Applications:**
- 🟢 **Admin**: <https://rfpo-admin.livelyforest-d06a98a0.eastus.azurecontainerapps.io>
- 🟢 **User App**: <https://rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io>
- 🟢 **API**: <https://rfpo-api.livelyforest-d06a98a0.eastus.azurecontainerapps.io/api/health>

## 🏗️ Architecture Overview

```text
┌─────────────────────────────────────────────────────────┐
│                 Secret Management                       │
├─────────────────────┬───────────────────────────────────┤
│  Local Development  │      Azure Production             │
│                     │                                   │
│ • .env file         │ • Container App Secrets           │
│ • env_config.py     │ • Environment Variables           │
│ • Git ignored       │ • secretRef injection             │
│ • SQLite database   │ • PostgreSQL with SSL             │
└─────────────────────┴───────────────────────────────────┘
```

## Local development

- Source: `.env` file (create from `env.example`). Not committed to git.
- Access: Centralized via `env_config.py` (Config/get_database_url/get_secret_key) with validation.
- Typical keys:
  - `DATABASE_URL` (sqlite:///instance/rfpo_admin.db or PostgreSQL)
  - `ADMIN_SECRET_KEY` (admin app Flask secret)
  - `USER_APP_SECRET_KEY` (user app Flask secret)
  - `API_SECRET_KEY`, `JWT_SECRET_KEY` (API auth/signing)
  - `API_BASE_URL` for the user app (non-secret)

## Production (Azure Container Apps) ✅ **DEPLOYED**

**Environment:** `rg-rfpo-e108977f` (East US)  
**Container Apps:** `rfpo-admin`, `rfpo-api`, `rfpo-user` (all **RUNNING**)  
**Domain:** `livelyforest-d06a98a0.eastus.azurecontainerapps.io`

Secrets are stored as ACA secrets and injected into containers as environment variables using `secretRef`. These values never appear in the Dockerfiles or images.

### Secret names per app ✅ **CONFIGURED**

- **rfpo-admin** (🟢 LIVE: <https://rfpo-admin.livelyforest-d06a98a0.eastus.azurecontainerapps.io>)
  - `admin-secret` → `ADMIN_SECRET_KEY`
  - `database-url` → `DATABASE_URL`
- **rfpo-api** (🟢 LIVE: <https://rfpo-api.livelyforest-d06a98a0.eastus.azurecontainerapps.io>)
  - `jwt-secret` → `JWT_SECRET_KEY`
  - `api-secret` → `API_SECRET_KEY`
  - `database-url` → `DATABASE_URL`
- **rfpo-user** (🟢 LIVE: <https://rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io>)
  - `user-app-secret` → `USER_APP_SECRET_KEY`
  - `database-url` → `DATABASE_URL`

Each app also has non-secret envs:

- `APP_BUILD_SHA` (injected on deploy for traceability; shown in the UI footer)
- `FLASK_ENV` (set to `development` in current config)
- `API_BASE_URL` (rfpo-user only)

### Storage credentials ✅ **DEPLOYED**

- **Storage Account:** `strfpo{unique}` (Standard LRS, East US)
- **File Share:** `rfpo-data` (5GB quota, SMB enabled)
- **ACA Storage:** `rfpo-storage` (managed by Container Apps Environment)

**Volume Mounts:**
- **rfpo-admin**: `/app/data` and `/app/uploads` mounted from `data-volume` and `uploads-volume` (both AzureFile on `rfpo-storage`)
- **rfpo-api**: `/app/data` mounted from `data-volume` (AzureFile on `rfpo-storage`)
- **rfpo-user**: no mounts configured

**Security:** Storage account key/connection is held by ACA as a storage secret and not exposed in the codebase. Volume definitions reference `storageName: rfpo-storage`.

## How secrets are deployed

- Secrets are created/updated in ACA per app. Example (names only; values handled securely):

  ```bash
  az containerapp secret list --name <app> --resource-group rg-rfpo-e108977f
  ```

- Containers read secrets via env variables with `secretRef` in the container template.
- The deploy script builds images in ACR, pins by digest, updates ACA, and injects non-secret `APP_BUILD_SHA`. It does not overwrite secrets.

## Rotation and updates

- Rotate a secret:
  1. Update the secret in ACA (per app):

     ```bash
     az containerapp secret set --name <app> --resource-group rg-rfpo-e108977f --secrets <name>=<newValue>
     ```

  2. Restart or re-deploy the container app.
- Rotate database credentials: update `database-url` in each app using the same command; ensure connection string includes `sslmode=require` for PostgreSQL.
- Rotate storage credentials: update the storage on the container app env or the specific container app storage binding (ACA stores the key); restart apps that mount it.

## Rotation checklists (per app)

Use these minimal, repeatable steps to rotate secrets safely. Replace placeholders in angle brackets.

### rfpo-admin ✅ **LIVE PRODUCTION APP**

1. Plan the change
   - Identify which secret(s) to rotate: `admin-secret`, `database-url`
   - If rotating `database-url`, ensure the target DB is reachable and credentials are valid
2. Rotate in Azure (✅ **PRODUCTION COMMANDS**)

     ```bash
     az containerapp secret set --name rfpo-admin --resource-group rg-rfpo-e108977f --secrets admin-secret=<NEW_RANDOM_64_HEX>
     az containerapp secret set --name rfpo-admin --resource-group rg-rfpo-e108977f --secrets database-url='postgresql://rfpoadmin:<NEW_PASSWORD>@rfpo-db-{unique}.postgres.database.azure.com:5432/rfpodb?sslmode=require'
     ```

3. Restart

   ```bash
   az containerapp revision restart --name rfpo-admin --resource-group rg-rfpo-e108977f
   ```

4. Verify (✅ **LIVE ENDPOINTS**)
   - Health:

     ```bash
     curl -fsSL https://rfpo-admin.livelyforest-d06a98a0.eastus.azurecontainerapps.io/health
     ```

   - Logs:

     ```bash
     az containerapp logs show --name rfpo-admin --resource-group rg-rfpo-e108977f --tail 50
     ```

   - **Production login**: <https://rfpo-admin.livelyforest-d06a98a0.eastus.azurecontainerapps.io/login> (admin@rfpo.com / admin123)

### rfpo-api ✅ **LIVE PRODUCTION API**

1. Plan
   - Identify secret(s): `jwt-secret`, `api-secret`, `database-url`
   - ⚠️ Consider token invalidation impact when rotating `jwt-secret`
2. Rotate (✅ **PRODUCTION COMMANDS**)

   ```bash
   az containerapp secret set --name rfpo-api --resource-group rg-rfpo-e108977f --secrets jwt-secret=<NEW_RANDOM_64_HEX>
   az containerapp secret set --name rfpo-api --resource-group rg-rfpo-e108977f --secrets api-secret=<NEW_RANDOM_64_HEX>
   az containerapp secret set --name rfpo-api --resource-group rg-rfpo-e108977f --secrets database-url='postgresql://rfpoadmin:<NEW_PASSWORD>@rfpo-db-{unique}.postgres.database.azure.com:5432/rfpodb?sslmode=require'
   ```

3. Restart

   ```bash
   az containerapp revision restart --name rfpo-api --resource-group rg-rfpo-e108977f
   ```

4. Verify (✅ **LIVE ENDPOINTS**)
   - Health:

     ```bash
     curl -fsSL https://rfpo-api.livelyforest-d06a98a0.eastus.azurecontainerapps.io/api/health
     ```

   - API logs and DB connectivity check

### rfpo-user ✅ **LIVE PRODUCTION USER APP**

1. Plan
   - Identify secret(s): `user-app-secret`, optionally `database-url` if used
2. Rotate (✅ **PRODUCTION COMMANDS**)

   ```bash
   az containerapp secret set --name rfpo-user --resource-group rg-rfpo-e108977f --secrets user-app-secret=<NEW_RANDOM_64_HEX>
   # If present
   az containerapp secret set --name rfpo-user --resource-group rg-rfpo-e108977f --secrets database-url='postgresql://rfpoadmin:<NEW_PASSWORD>@rfpo-db-{unique}.postgres.database.azure.com:5432/rfpodb?sslmode=require'
   ```

3. Restart

   ```bash
   az containerapp revision restart --name rfpo-user --resource-group rg-rfpo-e108977f
   ```

4. Verify (✅ **LIVE ENDPOINT**)
   - **Production app**: <https://rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io> - ensure sessions and API calls work

### Storage (Azure Files)

1. Plan
   - Rotating storage keys or regenerating SAS for `rfpo-storage`.
2. Rotate
   - Update the Container App storage binding or env’s storage reference so that `storageName: rfpo-storage` uses the new credentials.
   - Update all apps that mount it (rfpo-admin, rfpo-api).
3. Restart apps that mount storage
4. Verify read/write to `/app/uploads` (admin) and `/app/data`

## Verification (safe)

- Show env wiring (no values revealed; `secretRef` only):

  ```bash
  az containerapp show --name <app> --resource-group rg-rfpo-e108977f --query "properties.template.containers[0].env" -o table
  ```

- List secret names:

  ```bash
  az containerapp secret list --name <app> --resource-group rg-rfpo-e108977f -o table
  ```

- Check volumes/mounts:

  ```bash
  az containerapp show --name <app> --resource-group rg-rfpo-e108977f --query "{volumes:properties.template.volumes, mounts:properties.template.containers[0].volumeMounts}" -o json
  ```

## CI/CD: Avoid leaking secrets in logs (GitHub Actions)

- Never echo secrets directly. Use GitHub’s masking and env scoping:
  - Ensure org/repo secrets are configured; reference as `${{ secrets.MY_SECRET }}`.
  - Avoid `set -x` which prints commands and arguments.
  - Redact values in script output (use placeholders when printing).
- Prefer Azure login via OIDC (federated credentials) so you don’t store cloud keys in Actions:
  - Use `azure/login@v2` with `permissions: id-token: write`.
- Pass secrets to steps as env variables, not as command-line args (CLI history/logging risk).
- Validate that Action logs do not contain sensitive substrings (simple `grep -i` checks).

## Notes

- Always keep `.env` out of version control.
- For PostgreSQL in Azure, include `sslmode=require` in `DATABASE_URL`.
- APP_BUILD_SHA is not a secret; it’s used for deployment traceability and UI badges.
