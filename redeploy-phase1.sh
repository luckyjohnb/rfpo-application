#!/bin/bash

# Quick redeploy script for Phase 1 improvements
# Builds images on Azure Container Registry (server-side) from GitHub main
# and updates Azure Container Apps to the new images

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SUBSCRIPTION_ID="e108977f-44ed-4400-9580-f7a0bc1d3630"
RESOURCE_GROUP="rg-rfpo-e108977f"
ACR_NAME="acrrfpoe108977f"
LOCATION="eastus"
REPO_URL="https://github.com/luckyjohnb/rfpo-application.git"
GIT_REF="${GIT_REF:-main}"

# Resolve the current commit SHA for the ref (short and full) for traceability
echo -e "${YELLOW}🔎 Resolving commit SHA for ${GIT_REF}...${NC}"
GIT_SHORT_SHA=$(git rev-parse --short=7 "${GIT_REF}" 2>/dev/null || true)
if [ -z "$GIT_SHORT_SHA" ]; then
    # Fallback: query GitHub latest commit SHA via ACR build metadata later
    echo -e "${YELLOW}⚠️  Could not resolve local git SHA for ${GIT_REF}. Will extract from ACR build output.${NC}"
fi

echo -e "${BLUE}🚀 RFPO Phase 1 Improvements - Quick Redeploy${NC}"
echo "=============================================="
echo "This will rebuild and redeploy all containers with ACR builds from GitHub ($GIT_REF):"
echo "  ✅ Environment variable management"
echo "  ✅ Comprehensive error handling"
echo "  ✅ Structured logging"
echo "=============================================="
echo ""

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo -e "${RED}❌ Azure CLI is not installed${NC}"
    exit 1
fi

# Check login status
echo -e "${YELLOW}🔐 Checking Azure login...${NC}"
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}Logging in to Azure...${NC}"
    az login
fi

# Set subscription
echo -e "${YELLOW}📋 Setting subscription...${NC}"
az account set --subscription "$SUBSCRIPTION_ID"

# Validate ACR exists and is canonical
echo -e "${YELLOW}🔎 Validating ACR '${ACR_NAME}' in resource group '${RESOURCE_GROUP}'...${NC}"
if ! az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    echo -e "${RED}❌ ACR '$ACR_NAME' not found in resource group '$RESOURCE_GROUP'.${NC}"
    echo -e "${YELLOW}Hint:${NC} Run 'az acr list --resource-group $RESOURCE_GROUP -o table' to see available registries."
    exit 1
fi

# Enforce canonical tag if present
CANONICAL=$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query "tags.canonical" -o tsv 2>/dev/null || true)
CANONICAL_UPPER=$(printf '%s' "$CANONICAL" | tr '[:lower:]' '[:upper:]')
if [ -n "$CANONICAL" ] && [ "$CANONICAL_UPPER" != "TRUE" ]; then
    echo -e "${RED}❌ ACR '$ACR_NAME' is present but not tagged canonical=true (found: '$CANONICAL').${NC}"
    echo -e "${YELLOW}Resolve:${NC} Tag it with: az acr update --name $ACR_NAME --resource-group $RESOURCE_GROUP --set tags.canonical=true"
    exit 1
fi
echo -e "${GREEN}✅ ACR validation passed${NC}"

echo ""
echo -e "${BLUE}🏗️  Building images in ACR from GitHub ($GIT_REF)...${NC}"
echo "=============================================="

# Helper: ACR build function
acr_build() {
    local image="$1"; shift
    local dockerfile="$1"; shift
    echo -e "${YELLOW}Building ${image}...${NC}"
        az acr build \
        --registry "$ACR_NAME" \
        --image "${image}:latest" \
        --file "$dockerfile" \
        --platform linux/amd64 \
                "${REPO_URL}#${GIT_REF}:." | tee "/tmp/acr-build-${image}.log"

        # Capture digest and git-head-revision from the build output for pinning and metadata
        # Prefer the digest from the "- image:" dependency block (this is the built image),
        # NOT the base image digest printed earlier.
        IMAGE_BLOCK=$(sed -n '/- image:/,/- runtime-dependency:/p' "/tmp/acr-build-${image}.log" 2>/dev/null || true)
        DIGEST=$(printf "%s\n" "$IMAGE_BLOCK" | awk -v img="$image" '
            $1=="repository:" && $2==img { inrepo=1; next }
            inrepo && $1=="digest:" { print $2; exit }
        ')
        # Fallback: grab the digest from the "latest: digest:" push line if block parse failed
        if [ -z "$DIGEST" ]; then
            DIGEST=$(grep -Eo 'latest: digest: sha256:[a-f0-9]+' "/tmp/acr-build-${image}.log" | tail -n1 | awk '{print $3}')
        fi
        GIT_HEAD=$(grep -Eo 'git-head-revision: [a-f0-9]+' "/tmp/acr-build-${image}.log" | awk '{print $2}' | tail -n1)
        if [ -z "$DIGEST" ]; then
            echo -e "${RED}❌ Failed to extract image digest for ${image} from ACR build output${NC}"
            exit 1
        fi
        if [ -z "$GIT_HEAD" ]; then
            # Fallback to local short sha if available
            if [ -n "$GIT_SHORT_SHA" ]; then
                GIT_HEAD="$GIT_SHORT_SHA"
            else
                echo -e "${YELLOW}⚠️  Could not extract git-head-revision from build. Using 'unknown'.${NC}"
                GIT_HEAD="unknown"
            fi
        fi
        # Compute short SHA (first 8 chars) for use in revision suffixes
        GIT_SHORT="${GIT_HEAD:0:8}"
        # Export for callers
        eval "${image//-/_}_DIGEST='$DIGEST'"
        eval "${image//-/_}_GIT_HEAD='$GIT_HEAD'"
        eval "${image//-/_}_GIT_SHORT='$GIT_SHORT'"
    echo -e "${GREEN}✅ ${image} build complete${NC}"
}

# API, Admin, User builds
acr_build rfpo-api Dockerfile.api
acr_build rfpo-admin Dockerfile.admin
acr_build rfpo-user Dockerfile.user-app

# Restart Container Apps to pull new images (pin by digest) and inject APP_BUILD_SHA
echo ""
echo -e "${BLUE}🔄 Restarting Azure Container Apps...${NC}"
echo "=============================================="

# Get Container App Environment name
ENV_NAME=$(az containerapp env list --resource-group "$RESOURCE_GROUP" --query "[0].name" -o tsv)

if [ -z "$ENV_NAME" ]; then
    echo -e "${RED}❌ Could not find Container App Environment${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Environment: $ENV_NAME${NC}"

ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query loginServer --output tsv)

# Update API Container App
echo -e "${YELLOW}Updating rfpo-api container app...${NC}"
az containerapp update \
    --name rfpo-api \
    --resource-group "$RESOURCE_GROUP" \
    --image "$ACR_LOGIN_SERVER/rfpo-api@${rfpo_api_DIGEST}" \
    --set-env-vars APP_BUILD_SHA="${rfpo_api_GIT_HEAD}" \
    --revision-suffix "api-${rfpo_api_GIT_SHORT}" \
    --output none

echo -e "${GREEN}✅ rfpo-api updated${NC}"

# Update Admin Container App
echo -e "${YELLOW}Updating rfpo-admin container app...${NC}"
az containerapp update \
    --name rfpo-admin \
    --resource-group "$RESOURCE_GROUP" \
    --image "$ACR_LOGIN_SERVER/rfpo-admin@${rfpo_admin_DIGEST}" \
    --set-env-vars APP_BUILD_SHA="${rfpo_admin_GIT_HEAD}" \
    --revision-suffix "admin-${rfpo_admin_GIT_SHORT}" \
    --output none

echo -e "${GREEN}✅ rfpo-admin updated${NC}"

# Update User Container App
echo -e "${YELLOW}Updating rfpo-user container app...${NC}"
az containerapp update \
    --name rfpo-user \
    --resource-group "$RESOURCE_GROUP" \
        --image "$ACR_LOGIN_SERVER/rfpo-user@${rfpo_user_DIGEST}" \
        --set-env-vars APP_BUILD_SHA="${rfpo_user_GIT_HEAD}" \
        --revision-suffix "user-${rfpo_user_GIT_SHORT}" \
    --output none

# Quick health checks
echo ""
echo -e "${BLUE}🩺 Running health checks...${NC}"
for APP in rfpo-api rfpo-admin rfpo-user; do
    FQDN=$(az containerapp show --name "$APP" --resource-group "$RESOURCE_GROUP" --query properties.configuration.ingress.fqdn -o tsv)
    URL="https://${FQDN}"
    PATH="/api/health"
    [ "$APP" = "rfpo-admin" ] && PATH="/health"
    [ "$APP" = "rfpo-user" ] && PATH="/health"
    echo -e "${YELLOW}→ Checking ${APP} at ${URL}${PATH}${NC}"
    if curl -fsS "${URL}${PATH}" >/dev/null; then
        echo -e "${GREEN}   ${APP} healthy${NC}"
    else
        echo -e "${RED}   ${APP} health check failed${NC}"
    fi
done

echo -e "${GREEN}✅ rfpo-user updated${NC}"

# Get application URLs
echo ""
echo -e "${BLUE}📱 Getting application URLs...${NC}"
echo "=============================================="

API_FQDN=$(az containerapp show --name rfpo-api --resource-group "$RESOURCE_GROUP" --query properties.configuration.ingress.fqdn -o tsv)
ADMIN_FQDN=$(az containerapp show --name rfpo-admin --resource-group "$RESOURCE_GROUP" --query properties.configuration.ingress.fqdn -o tsv)
USER_FQDN=$(az containerapp show --name rfpo-user --resource-group "$RESOURCE_GROUP" --query properties.configuration.ingress.fqdn -o tsv)

echo ""
echo -e "${GREEN}🎉 Deployment Complete!${NC}"
echo "=============================================="
echo ""
echo -e "${BLUE}Application URLs:${NC}"
echo "  📊 Admin Panel:  https://$ADMIN_FQDN"
echo "  👥 User App:     https://$USER_FQDN"
echo "  🔌 API:          https://$API_FQDN"
echo ""
echo -e "${YELLOW}Test the improvements:${NC}"
echo "  1. Login to Admin Panel: admin@rfpo.com / admin123"
echo "  2. Check logs in Azure Portal (Container Apps → Logs)"
echo "  3. Test error handling: visit /nonexistent on any app"
echo "  4. Verify environment config loading from .env"
echo ""
echo -e "${BLUE}Monitor logs:${NC}"
echo "  az containerapp logs show --name rfpo-admin --resource-group $RESOURCE_GROUP --follow"
echo "  az containerapp logs show --name rfpo-api --resource-group $RESOURCE_GROUP --follow"
echo "  az containerapp logs show --name rfpo-user --resource-group $RESOURCE_GROUP --follow"
echo "=============================================="
