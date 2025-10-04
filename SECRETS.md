# Secrets Management

This app uses environment-based secrets locally and Azure Container Apps (ACA) secrets in production. No secrets are baked into images or committed to the repo.

## Local development

- Source: `.env` file (create from `env.example`). Not committed to git.
- Access: Centralized via `env_config.py` (Config/get_database_url/get_secret_key) with validation.
- Typical keys:
  - `DATABASE_URL` (sqlite:///instance/rfpo_admin.db or PostgreSQL)
  - `ADMIN_SECRET_KEY` (admin app Flask secret)
  - `USER_APP_SECRET_KEY` (user app Flask secret)
  - `API_SECRET_KEY`, `JWT_SECRET_KEY` (API auth/signing)
  - `API_BASE_URL` for the user app (non-secret)

## Production (Azure Container Apps)

Secrets are stored as ACA secrets and injected into containers as environment variables using `secretRef`. These values never appear in the Dockerfiles or images.

### Secret names per app

- rfpo-admin
  - `admin-secret` → `ADMIN_SECRET_KEY`
  - `database-url` → `DATABASE_URL`
- rfpo-api
  - `jwt-secret` → `JWT_SECRET_KEY`
  - `api-secret` → `API_SECRET_KEY`
  - `database-url` → `DATABASE_URL`
- rfpo-user
  - `user-app-secret` → `USER_APP_SECRET_KEY`
  - `database-url` → `DATABASE_URL`

Each app also has non-secret envs:

- `APP_BUILD_SHA` (injected on deploy for traceability; shown in the UI footer)
- `FLASK_ENV` (set to `development` in current config)
- `API_BASE_URL` (rfpo-user only)

### Storage credentials

- File storage uses an Azure Files share exposed via an ACA managed storage: `rfpo-storage`.
- Mounts:
  - rfpo-admin: `/app/data` and `/app/uploads` mounted from volumes `data-volume` and `uploads-volume` (both `AzureFile` on `rfpo-storage`).
  - rfpo-api: `/app/data` mounted from `data-volume` (AzureFile on `rfpo-storage`).
  - rfpo-user: no mounts configured.
- Under the hood, the storage account key/connection is held by ACA as a storage secret and not exposed in the codebase. Volume definitions reference `storageName: rfpo-storage`.

## How secrets are deployed

- Secrets are created/updated in ACA per app. Example (names only; values handled securely):
  - `az containerapp secret list --name <app> --resource-group rg-rfpo-e108977f`
- Containers read secrets via env variables with `secretRef` in the container template.
- The deploy script builds images in ACR, pins by digest, updates ACA, and injects non-secret `APP_BUILD_SHA`. It does not overwrite secrets.

## Rotation and updates

- Rotate a secret:
  1. Update the secret in ACA (per app): `az containerapp secret set --name <app> --resource-group rg-rfpo-e108977f --secrets <name>=<newValue>`
  2. Restart or re-deploy the container app.
- Rotate database credentials: update `database-url` in each app using the same command; ensure connection string includes `sslmode=require` for PostgreSQL.
- Rotate storage credentials: update the storage on the container app env or the specific container app storage binding (ACA stores the key); restart apps that mount it.

## Verification (safe)

- Show env wiring (no values revealed; `secretRef` only):
  - `az containerapp show --name <app> --resource-group rg-rfpo-e108977f --query "properties.template.containers[0].env" -o table`
- List secret names:
  - `az containerapp secret list --name <app> --resource-group rg-rfpo-e108977f -o table`
- Check volumes/mounts:
  - `az containerapp show --name <app> --resource-group rg-rfpo-e108977f --query "{volumes:properties.template.volumes, mounts:properties.template.containers[0].volumeMounts}" -o json`

## Notes

- Always keep `.env` out of version control.
- For PostgreSQL in Azure, include `sslmode=require` in `DATABASE_URL`.
- APP_BUILD_SHA is not a secret; it’s used for deployment traceability and UI badges.
