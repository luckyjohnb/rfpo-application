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
        "${REPO_URL}#${GIT_REF}:."
    echo -e "${GREEN}✅ ${image} build complete${NC}"
}

# API, Admin, User builds
acr_build rfpo-api Dockerfile.api
acr_build rfpo-admin Dockerfile.admin
acr_build rfpo-user Dockerfile.user-app

# Restart Container Apps to pull new images
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
    --image "$ACR_LOGIN_SERVER/rfpo-api:latest" \
    --revision-suffix "git-${GIT_REF}-$(date +%Y%m%d%H%M%S)" \
    --output none

echo -e "${GREEN}✅ rfpo-api updated${NC}"

# Update Admin Container App
echo -e "${YELLOW}Updating rfpo-admin container app...${NC}"
az containerapp update \
    --name rfpo-admin \
    --resource-group "$RESOURCE_GROUP" \
    --image "$ACR_LOGIN_SERVER/rfpo-admin:latest" \
    --revision-suffix "git-${GIT_REF}-$(date +%Y%m%d%H%M%S)" \
    --output none

echo -e "${GREEN}✅ rfpo-admin updated${NC}"

# Update User Container App
echo -e "${YELLOW}Updating rfpo-user container app...${NC}"
az containerapp update \
    --name rfpo-user \
    --resource-group "$RESOURCE_GROUP" \
    --image "$ACR_LOGIN_SERVER/rfpo-user:latest" \
    --revision-suffix "git-${GIT_REF}-$(date +%Y%m%d%H%M%S)" \
    --output none

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
