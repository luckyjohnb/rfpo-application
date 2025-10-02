#!/bin/bash

# Quick redeploy script for Phase 1 improvements
# This rebuilds containers and updates Azure Container Apps

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

echo -e "${BLUE}🚀 RFPO Phase 1 Improvements - Quick Redeploy${NC}"
echo "=============================================="
echo "This will rebuild and redeploy all containers with:"
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

# Get ACR login server
echo -e "${YELLOW}🔍 Getting ACR details...${NC}"
ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query loginServer --output tsv)
echo -e "${GREEN}✅ ACR Server: $ACR_LOGIN_SERVER${NC}"

# Login to ACR
echo -e "${YELLOW}🔑 Logging into ACR...${NC}"
az acr login --name "$ACR_NAME"

# Build and push images with linux/amd64 platform
echo ""
echo -e "${BLUE}🏗️  Building Docker images for Linux (Azure)...${NC}"
echo "=============================================="

# Build API image
echo -e "${YELLOW}Building RFPO API...${NC}"
docker build --platform linux/amd64 -f Dockerfile.api -t "$ACR_LOGIN_SERVER/rfpo-api:phase1" -t "$ACR_LOGIN_SERVER/rfpo-api:latest" .
docker push "$ACR_LOGIN_SERVER/rfpo-api:phase1"
docker push "$ACR_LOGIN_SERVER/rfpo-api:latest"
echo -e "${GREEN}✅ API image pushed${NC}"

# Build Admin image
echo -e "${YELLOW}Building RFPO Admin...${NC}"
docker build --platform linux/amd64 -f Dockerfile.admin -t "$ACR_LOGIN_SERVER/rfpo-admin:phase1" -t "$ACR_LOGIN_SERVER/rfpo-admin:latest" .
docker push "$ACR_LOGIN_SERVER/rfpo-admin:phase1"
docker push "$ACR_LOGIN_SERVER/rfpo-admin:latest"
echo -e "${GREEN}✅ Admin image pushed${NC}"

# Build User App image
echo -e "${YELLOW}Building RFPO User App...${NC}"
docker build --platform linux/amd64 -f Dockerfile.user-app -t "$ACR_LOGIN_SERVER/rfpo-user:phase1" -t "$ACR_LOGIN_SERVER/rfpo-user:latest" .
docker push "$ACR_LOGIN_SERVER/rfpo-user:phase1"
docker push "$ACR_LOGIN_SERVER/rfpo-user:latest"
echo -e "${GREEN}✅ User App image pushed${NC}"

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

# Update API Container App
echo -e "${YELLOW}Updating rfpo-api container app...${NC}"
az containerapp update \
    --name rfpo-api \
    --resource-group "$RESOURCE_GROUP" \
    --image "$ACR_LOGIN_SERVER/rfpo-api:latest" \
    --output none

echo -e "${GREEN}✅ rfpo-api updated${NC}"

# Update Admin Container App
echo -e "${YELLOW}Updating rfpo-admin container app...${NC}"
az containerapp update \
    --name rfpo-admin \
    --resource-group "$RESOURCE_GROUP" \
    --image "$ACR_LOGIN_SERVER/rfpo-admin:latest" \
    --output none

echo -e "${GREEN}✅ rfpo-admin updated${NC}"

# Update User Container App
echo -e "${YELLOW}Updating rfpo-user container app...${NC}"
az containerapp update \
    --name rfpo-user \
    --resource-group "$RESOURCE_GROUP" \
    --image "$ACR_LOGIN_SERVER/rfpo-user:latest" \
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
