# RFPO File Upload Storage

This document explains where RFPO-uploaded documents live, how they’re named, and how to find and download them in both local and Azure environments.

## TL;DR

- Files are saved under `/app/uploads` inside the containers.
- In local dev, that path is backed by the repo folder `./uploads` (docker volume).
- In Azure, `/app/uploads` is mounted to an Azure File Share on a Storage Account.
- Each upload is recorded in the database (model: `UploadedFile`) and usually named `{uuid}_{secure_filename(original)}`.
- Files are saved under `/app/uploads` inside the containers.
- In local dev, that path is backed by the repo folder `./uploads` (docker volume).
- In Azure, `/app/uploads` is mounted to an Azure File Share on a Storage Account.
- Each upload is recorded in the database (model: `UploadedFile`) and usually named `{uuid}_{secure_filename(original)}`.

## Local development

- Host path: `./uploads` in this repo
- Container path: `/app/uploads`
- docker-compose mounts: `./uploads:/app/uploads`
- Files persist on your machine and across container restarts.
- Host path: `./uploads` in this repo
- Container path: `/app/uploads`
- docker-compose mounts: `./uploads:/app/uploads`
- Files persist on your machine and across container restarts.

## Azure (production)

- Container mount path: `/app/uploads` (and `/app/data` for some uses)
- Backing storage: Azure File Share, mounted via the Container Apps environment storage
  - Managed environment: `rfpo-env-5kn5bsg47vvac`
  - Environment storage name: `rfpo-storage`
  - Storage account: `strfpo5kn5bsg47vvac`
  - File share: `rfpo-data`
- Container Apps referencing this storage mount:
  - `rfpo-admin` (also mounts an `uploads-volume`)
  - `rfpo-api`
  - `rfpo-user`
- Container mount path: `/app/uploads` (and `/app/data` for some uses)
- Backing storage: Azure File Share, mounted via the Container Apps environment storage
  - Managed environment: `rfpo-env-5kn5bsg47vvac`
  - Environment storage name: `rfpo-storage`
  - Storage account: `strfpo5kn5bsg47vvac`
  - File share: `rfpo-data`
- Container Apps referencing this storage mount:
  - `rfpo-admin` (also mounts an `uploads-volume`)
  - `rfpo-api`
  - `rfpo-user`

### How to verify the storage mapping

- Azure Portal: Resource Group `rg-rfpo-e108977f` → Managed Environment `rfpo-env-5kn5bsg47vvac` → Storage → `rfpo-storage`
  - Shows: account `strfpo5kn5bsg47vvac`, share `rfpo-data`, AccessMode `ReadWrite`.
- CLI (optional):
  - List env storage:

    ```bash
    az containerapp env storage list \
      --name rfpo-env-5kn5bsg47vvac \
      --resource-group rg-rfpo-e108977f -o table
    ```
- Azure Portal: Resource Group `rg-rfpo-e108977f` → Managed Environment `rfpo-env-5kn5bsg47vvac` → Storage → `rfpo-storage`
  - Shows: account `strfpo5kn5bsg47vvac`, share `rfpo-data`, AccessMode `ReadWrite`.
- CLI (optional):
  - List env storage:
    ```bash
    az containerapp env storage list \
      --name rfpo-env-5kn5bsg47vvac \
      --resource-group rg-rfpo-e108977f -o table
    ```

## Browsing and downloading files

### Easiest: Azure Portal

1. Go to Resource Group `rg-rfpo-e108977f`.
2. Open Storage Account `strfpo5kn5bsg47vvac`.
3. File shares → `rfpo-data`.
4. Browse folders/files (e.g., files at the root or subfolders like `logos/` and `terms/`). You can download directly from here.
### Easiest: Azure Portal
1. Go to Resource Group `rg-rfpo-e108977f`.
2. Open Storage Account `strfpo5kn5bsg47vvac`.
3. File shares → `rfpo-data`.
4. Browse folders/files (e.g., files at the root or subfolders like `logos/` and `terms/`). You can download directly from here.

### CLI using Azure AD (RBAC)

You’ll need the correct data-plane role(s) on the storage account for Azure Files with Azure AD. Common roles:

- Storage File Data SMB Share Reader (read-only)
- Storage File Data SMB Share Contributor (read/write)

Then you can list/download with:

```bash
# List the root of the share (requires AD data-plane role)
az storage file list \
  --account-name strfpo5kn5bsg47vvac \
  --share-name rfpo-data \
  --auth-mode login \
  --enable-file-backup-request-intent \
  -o table --num-results 50

# Download a specific file
az storage file download \
  --account-name strfpo5kn5bsg47vvac \
  --share-name rfpo-data \
  --path <filename_or_subpath> \
  --dest . \
  --auth-mode login \
  --enable-file-backup-request-intent
```
You’ll need the correct data-plane role(s) on the storage account for Azure Files with Azure AD. Common roles:
- Storage File Data SMB Share Reader (read-only)
- Storage File Data SMB Share Contributor (read/write)

Then you can list/download with:
```bash
# List the root of the share (requires AD data-plane role)
az storage file list \
  --account-name strfpo5kn5bsg47vvac \
  --share-name rfpo-data \
  --auth-mode login \
  --enable-file-backup-request-intent \
  -o table --num-results 50

# Download a specific file
az storage file download \
  --account-name strfpo5kn5bsg47vvac \
  --share-name rfpo-data \
  --path <filename_or_subpath> \
  --dest . \
  --auth-mode login \
  --enable-file-backup-request-intent
```

If you do not have the data-plane role, either use the Portal or use an account key/SAS.

### CLI using account key (alternative)

If you have permission to read account keys (Owner/Contributor on the storage account):

```bash
# Get an account key
az storage account keys list \
  --resource-group rg-rfpo-e108977f \
  --account-name strfpo5kn5bsg47vvac \
  -o tsv --query [0].value

# Then pass --account-key to file commands
az storage file list \
  --account-name strfpo5kn5bsg47vvac \
  --share-name rfpo-data \
  --account-key <key> -o table --num-results 50
```
If you have permission to read account keys (Owner/Contributor on the storage account):
```bash
# Get an account key
az storage account keys list \
  --resource-group rg-rfpo-e108977f \
  --account-name strfpo5kn5bsg47vvac \
  -o tsv --query [0].value

# Then pass --account-key to file commands
az storage file list \
  --account-name strfpo5kn5bsg47vvac \
  --share-name rfpo-data \
  --account-key <key> -o table --num-results 50
```

### Quick in-container check (optional)

You can exec into a Container App to confirm mount contents (requires Container Apps exec permissions):

```bash
az containerapp exec \
  --name rfpo-admin \
  --resource-group rg-rfpo-e108977f \
  --command "sh -lc 'ls -la /app/uploads | head -n 50'"
```
You can exec into a Container App to confirm mount contents (requires Container Apps exec permissions):
```bash
az containerapp exec \
  --name rfpo-admin \
  --resource-group rg-rfpo-e108977f \
  --command "sh -lc 'ls -la /app/uploads | head -n 50'"
```

## How files are named and tracked

- Stored filename pattern: `{uuid}_{secure_filename(original)}` to avoid collisions.
- App-level folders: some admin assets use `uploads/logos/` and `uploads/terms/`.
- Database records:
  - `UploadedFile` model stores metadata (original name, stored name/path, rfpo_id, size, mime, timestamps).
  - If document processing is enabled, extracted text is stored as `DocumentChunk` rows (with embeddings) for RAG/search.
- Stored filename pattern: `{uuid}_{secure_filename(original)}` to avoid collisions.
- App-level folders: some admin assets use `uploads/logos/` and `uploads/terms/`.
- Database records:
  - `UploadedFile` model stores metadata (original name, stored name/path, rfpo_id, size, mime, timestamps).
  - If document processing is enabled, extracted text is stored as `DocumentChunk` rows (with embeddings) for RAG/search.

## Retrieval inside the app
- API/Admin routes resolve downloads/links using the `UploadedFile` DB record associated with an RFPO.
- The app serves files from the mounted share; files are not stored as blobs in the database.

## Backups and data retention (recommendation)
- Because uploads are on an Azure File Share, configure backups/snapshots at the Storage Account level (Azure Backup for File Shares).
- Retain snapshots before any schema or infrastructure changes.

## Troubleshooting
- “Permission denied” via CLI with `--auth-mode login`:
  - Ensure you have a Storage File Data SMB Share role on the storage account, or use an account key/SAS.
- “File not found”: Confirm the exact stored filename from the `UploadedFile` DB row, including the UUID prefix and subfolder (if any).
- Mount not visible inside container: Verify the Container App revision has the volume mount to `rfpo-storage` and the app is on the latest ready revision.

---
For a high-level overview of the app’s storage and deployment, see `AZURE_DEPLOYMENT_PHASE1.md` and `.github/copilot-instructions.md`.
