# Phase 1 Azure Deployment Guide

✅ **STATUS: SUCCESSFULLY DEPLOYED TO PRODUCTION**

This guide explains how to deploy the Phase 1 security and error handling improvements to your Azure Container Apps environment.

**Current Production Status:**
- 🟢 **LIVE**: All applications deployed and operational
- 🟢 **URLs**: <https://rfpo-admin.livelyforest-d06a98a0.eastus.azurecontainerapps.io>
- 🟢 **Database**: PostgreSQL running with proper schema
- 🟢 **Storage**: Azure Files mounted and operational

## Secrets

For how secrets are managed locally and in Azure (per-app secret names, storage mounts, rotation, and verification), see SECRETS.md.

## What's Being Deployed

### Phase 1 Activity 1: Environment Configuration

- ✅ Centralized `env_config.py` for all configuration
- ✅ Eliminated hardcoded database credentials from 10 scripts
- ✅ Environment variable validation on startup
- ✅ Secure secret key management

### Phase 1 Activity 3: Error Handling & Logging

- ✅ Custom exception hierarchy (9 exception types)
- ✅ Structured logging with rotation (10MB, 5 backups)
- ✅ Flask error handlers for all applications
- ✅ Beautiful error pages for end users
- ✅ JSON error responses for API requests

## Prerequisites

1. Azure CLI installed and logged in

    ```bash
    az --version
    az login
    ```

2. On correct branch (if building from local context)

    ```bash
    git status  # Should show: feature/phase1-security-improvements
    ```

Note: Docker is not required if you use ACR server-side builds (recommended). If you choose local docker builds, ensure Docker is running and build for linux/amd64.

## Deployment Steps

### Option 1: Quick Deployment (Local docker) — use only if Docker is available

This rebuilds containers locally and updates Azure in one step:

```bash
# Run the deployment script
./redeploy-phase1.sh
```

This script will:

1. ✅ Build Docker images for Linux/AMD64 (Azure platform)
2. ✅ Push images to Azure Container Registry
3. ✅ Update all 3 Container Apps with new images
4. ✅ Display application URLs when complete

If your local Docker daemon isn’t available or you hit network timeouts uploading layers, use Option 2A (ACR server-side builds), which is faster and more reliable.

### Option 2A: Step-by-Step with ACR server-side builds (Recommended)

Build images in Azure Container Registry (no local Docker required) and update Container Apps.

#### Step 1: Build and push images in ACR

From project root:

```bash
# Ensure config loaded
source azure/azure-config.env

# Build API from local context (uses .dockerignore)
./azure/acr-build.sh local rfpo-api:latest Dockerfile.api

# Build Admin from local context
./azure/acr-build.sh local rfpo-admin:latest Dockerfile.admin

# Build User from GitHub (avoids large local uploads)
./azure/acr-build.sh github rfpo-user:latest Dockerfile.user-app luckyjohnb/rfpo-application feature/phase1-security-improvements
```

Alternatively, to build all three from GitHub (best for slow networks):

```bash
./azure/acr-build.sh github rfpo-api:latest Dockerfile.api luckyjohnb/rfpo-application feature/phase1-security-improvements
./azure/acr-build.sh github rfpo-admin:latest Dockerfile.admin luckyjohnb/rfpo-application feature/phase1-security-improvements
./azure/acr-build.sh github rfpo-user:latest Dockerfile.user-app luckyjohnb/rfpo-application feature/phase1-security-improvements
```

#### Step 2: Update Container Apps to latest images

```bash
az containerapp update --name rfpo-api   --resource-group rg-rfpo-e108977f --image acrrfpoe108977f.azurecr.io/rfpo-api:latest
az containerapp update --name rfpo-admin --resource-group rg-rfpo-e108977f --image acrrfpoe108977f.azurecr.io/rfpo-admin:latest
az containerapp update --name rfpo-user  --resource-group rg-rfpo-e108977f --image acrrfpoe108977f.azurecr.io/rfpo-user:latest
```

### Option 2B: Step-by-Step with local Docker (legacy)

If you prefer more control:

#### Step 1: Update Environment Variables

```bash
# Update all Container Apps with proper environment variables
./update-azure-env-vars.sh
```

This sets:

- `DATABASE_URL` - PostgreSQL connection string
- `FLASK_SECRET_KEY`, `JWT_SECRET_KEY`, etc. - Secure random secrets (64 chars)
- `LOG_LEVEL=INFO` - Logging configuration
- `API_BASE_URL` - Internal API communication

#### Step 2: Build and Push Images (local docker)

```bash
# Navigate to project root
cd /Users/johnbouchard/projects/rfpo-application

# Login to Azure Container Registry
az acr login --name acrrfpoe108977f

# Get ACR login server
ACR_SERVER=$(az acr show --name acrrfpoe108977f --resource-group rg-rfpo-e108977f --query loginServer --output tsv)

# Build and push API image (local docker)
docker build --platform linux/amd64 -f Dockerfile.api -t $ACR_SERVER/rfpo-api:phase1 -t $ACR_SERVER/rfpo-api:latest .
docker push $ACR_SERVER/rfpo-api:phase1
docker push $ACR_SERVER/rfpo-api:latest

# Build and push Admin image (local docker)
docker build --platform linux/amd64 -f Dockerfile.admin -t $ACR_SERVER/rfpo-admin:phase1 -t $ACR_SERVER/rfpo-admin:latest .
docker push $ACR_SERVER/rfpo-admin:phase1
docker push $ACR_SERVER/rfpo-admin:latest

# Build and push User App image (local docker)
docker build --platform linux/amd64 -f Dockerfile.user-app -t $ACR_SERVER/rfpo-user:phase1 -t $ACR_SERVER/rfpo-user:latest .
docker push $ACR_SERVER/rfpo-user:phase1
docker push $ACR_SERVER/rfpo-user:latest
```

#### Step 3: Update Container Apps

```bash
# Update API
az containerapp update \
    --name rfpo-api \
    --resource-group rg-rfpo-e108977f \
    --image $ACR_SERVER/rfpo-api:latest

# Update Admin
az containerapp update \
    --name rfpo-admin \
    --resource-group rg-rfpo-e108977f \
    --image $ACR_SERVER/rfpo-admin:latest

# Update User App
az containerapp update \
    --name rfpo-user \
    --resource-group rg-rfpo-e108977f \
    --image $ACR_SERVER/rfpo-user:latest
```

## Verification & Testing

### 1. Check Application URLs

```bash
# Get all URLs
az containerapp show --name rfpo-admin --resource-group rg-rfpo-e108977f --query properties.configuration.ingress.fqdn -o tsv
az containerapp show --name rfpo-user --resource-group rg-rfpo-e108977f --query properties.configuration.ingress.fqdn -o tsv
az containerapp show --name rfpo-api --resource-group rg-rfpo-e108977f --query properties.configuration.ingress.fqdn -o tsv
```

### 2. Test Admin Panel

Visit: `https://rfpo-admin-5kn5bsg47vvac.proudbush-cac5d6af.eastus.azurecontainerapps.io`

- Login: `admin@rfpo.com` / `admin123`
- Should load without errors
- Check browser console for any JavaScript errors

### 3. Test Error Handling

Visit a non-existent page to test error handling:

- `https://rfpo-admin-<...>.azurecontainerapps.io/nonexistent`
- Should see beautiful error page (not generic Azure error)

### 4. View Logs

Check that structured logging is working:

```bash
# Admin logs
az containerapp logs show \
    --name rfpo-admin \
    --resource-group rg-rfpo-e108977f \
    --follow

# API logs
az containerapp logs show \
    --name rfpo-api \
    --resource-group rg-rfpo-e108977f \
    --follow

# User App logs
az containerapp logs show \
    --name rfpo-user \
    --resource-group rg-rfpo-e108977f \
    --follow
```

Look for:

- ✅ "Logging initialized for [app_name] at level INFO"
- ✅ "Error handlers registered for [app_name]"
- ✅ Structured log format with timestamps
- ✅ No errors about missing environment variables

### 5. Test Environment Configuration

Check that environment variables are loading correctly:

```bash
# Check admin app logs for startup messages
az containerapp logs show --name rfpo-admin --resource-group rg-rfpo-e108977f --tail 50

# Look for:
# - "Logging initialized..."
# - "Error handlers registered..."
# - No "ConfigurationException" errors
```

## Troubleshooting

### Issue: net::ERR_CONNECTION_RESET or ACR upload errors

If you see network errors while building/pushing (e.g., ERR_CONNECTION_RESET, or SAS timing messages like "Signed expiry time must be after signed start time"):

- Prefer ACR server-side builds: use `./azure/acr-build.sh` with `local` or `github` mode.
- Build from GitHub for large contexts to avoid uploading big tarballs from your machine.
- Ensure your clock is in sync (NTP), as SAS token timing can be skewed if system time is off.
- Keep the build context small. We include a `.dockerignore` to exclude venvs, logs, local DB, and uploads.

### Issue: "Module not found: dotenv"

**Solution:** The container needs python-dotenv installed. Check Dockerfile:

```dockerfile
RUN pip install -r requirements.txt
```

Make sure `requirements.txt` includes `python-dotenv==1.0.0`

### Issue: "Configuration validation failed"

**Solution:** Environment variables not set in Azure. Run:

```bash
./update-azure-env-vars.sh
```

### Issue: "Database connection failed"

**Solution:** Check DATABASE_URL environment variable:

```bash
az containerapp show \
    --name rfpo-admin \
    --resource-group rg-rfpo-e108977f \
    --query properties.template.containers[0].env
```

### Issue: Images not updating

**Solution:** Container Apps may cache images. Force restart:

```bash
az containerapp revision restart \
    --name rfpo-admin \
    --resource-group rg-rfpo-e108977f
```

### Issue: Local Docker daemon not running

Use ACR builds instead of local docker:

```bash
./azure/acr-build.sh local rfpo-api:latest Dockerfile.api
./azure/acr-build.sh local rfpo-admin:latest Dockerfile.admin
./azure/acr-build.sh github rfpo-user:latest Dockerfile.user-app luckyjohnb/rfpo-application feature/phase1-security-improvements
```

## Rollback Plan

If something goes wrong:

### Option 1: Quick Rollback to Previous Image

```bash
# List revisions
az containerapp revision list \
    --name rfpo-admin \
    --resource-group rg-rfpo-e108977f \
    --query "[].name"

# Activate previous revision
az containerapp revision activate \
    --name rfpo-admin \
    --resource-group rg-rfpo-e108977f \
    --revision <previous-revision-name>
```

### Option 2: Rollback Git Branch

```bash
# Switch back to main branch
git checkout main

# Redeploy from main
./redeploy-phase1.sh
```

## Monitoring Post-Deployment

### 1. Azure Portal

1. Go to Azure Portal → Container Apps
2. Select each app (rfpo-api, rfpo-admin, rfpo-user)
3. View:
   - **Metrics**: CPU, Memory, Request count
   - **Logs**: Application logs with filtering
   - **Revisions**: Active revision and history

### 2. Application Health

Check health endpoints:

- API: `https://rfpo-api-<...>.azurecontainerapps.io/api/health`
- Admin: `https://rfpo-admin-<...>.azurecontainerapps.io/health`
- User: `https://rfpo-user-<...>.azurecontainerapps.io/health`

All should return JSON with `"status": "healthy"`

## Performance Impact

Expected changes:

- **Startup time**: +2-3 seconds (environment validation, logger setup)
- **Memory usage**: +5-10 MB (logging buffers)
- **Error response time**: Slightly faster (optimized error handlers)
- **Log file size**: Auto-rotated at 10MB (5 backups = 50MB max per app)

## Next Steps After Deployment

1. **Monitor for 24 hours**: Check logs for any unexpected errors
2. **Test all major workflows**: Login, RFPO creation, approval workflows
3. **Review error logs**: Look for any ValidationException or AuthenticationException patterns
4. **Merge to main**: Once stable, merge `feature/phase1-security-improvements` to `main`
5. **Enable automated deployments**: GitHub Actions will auto-deploy on push to main

## Questions?

Check:

- Azure Portal Logs for real-time errors
- `DEPLOYMENT_SUMMARY.md` for infrastructure details
- `.github/copilot-instructions.md` for architecture patterns
- `FILE_UPLOAD_STORAGE.md` for where uploads live and how to access them (local and Azure)

---

**Deployed by:** Phase 1 Security & Error Handling Improvements  
**Branch:** main (production)  
**Date:** October 30, 2025  
**Status:** ✅ **LIVE & OPERATIONAL IN PRODUCTION**

---

## Canonical ACR and cleanup

- Canonical registry: `acrrfpoe108977f` (eastus, Basic)
- The redeploy script validates that the configured ACR exists and, if a `canonical` tag is present, it must be `true`.
- Useful commands:

    - List registries in RG:

        ```bash
        az acr list --resource-group rg-rfpo-e108977f -o table
        ```

    - Delete an unused registry:

        ```bash
        az acr delete --name <registryName> --resource-group rg-rfpo-e108977f --yes
        ```

    - Tag the canonical registry:

        ```bash
        az acr update --name acrrfpoe108977f --resource-group rg-rfpo-e108977f --set tags.canonical=true
        ```
