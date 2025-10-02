#!/bin/bash

# Azure Container Registry Setup and Build Script
# This script builds and pushes Docker images to Azure Container Registry

set -e

# Configuration
SUBSCRIPTION_ID="e108977f-44ed-4400-9580-f7a0bc1d3630"
RESOURCE_GROUP_NAME="rg-rfpo-$(echo $SUBSCRIPTION_ID | cut -c1-8)"
LOCATION="East US"
ACR_NAME="acrrfpo$(echo $SUBSCRIPTION_ID | cut -c1-8 | tr '[:upper:]' '[:lower:]')"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 RFPO Azure Container Registry Setup${NC}"
echo "=============================================="
echo "Subscription ID: $SUBSCRIPTION_ID"
echo "Resource Group: $RESOURCE_GROUP_NAME"
echo "ACR Name: $ACR_NAME"
echo "Location: $LOCATION"
echo "=============================================="

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo -e "${RED}❌ Azure CLI is not installed. Please install it first.${NC}"
    echo "Install from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Login to Azure (if not already logged in)
echo -e "${YELLOW}🔐 Checking Azure login status...${NC}"
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}Please log in to Azure...${NC}"
    az login
fi

# Set subscription
echo -e "${YELLOW}📋 Setting Azure subscription...${NC}"
az account set --subscription "$SUBSCRIPTION_ID"

# Create resource group if it doesn't exist
echo -e "${YELLOW}🏗️  Creating resource group...${NC}"
az group create \
    --name "$RESOURCE_GROUP_NAME" \
    --location "$LOCATION" \
    --tags project=rfpo-application environment=production

# Create Azure Container Registry
echo -e "${YELLOW}🐳 Creating Azure Container Registry...${NC}"
az acr create \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$ACR_NAME" \
    --sku Basic \
    --admin-enabled true \
    --location "$LOCATION" \
    --tags project=rfpo-application environment=production

# Get ACR login server
ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP_NAME" --query loginServer --output tsv)
echo -e "${GREEN}✅ ACR Login Server: $ACR_LOGIN_SERVER${NC}"

# Login to ACR
echo -e "${YELLOW}🔑 Logging into Azure Container Registry...${NC}"
az acr login --name "$ACR_NAME"

# Build and push Docker images
echo -e "${YELLOW}🏗️  Building and pushing Docker images...${NC}"

# Build API image
echo -e "${BLUE}Building RFPO API image...${NC}"
docker build --platform linux/amd64 -f ../Dockerfile.api -t "$ACR_LOGIN_SERVER/rfpo-api:latest" ..
docker push "$ACR_LOGIN_SERVER/rfpo-api:latest"
echo -e "${GREEN}✅ RFPO API image pushed${NC}"

# Build Admin image
echo -e "${BLUE}Building RFPO Admin image...${NC}"
docker build --platform linux/amd64 -f ../Dockerfile.admin -t "$ACR_LOGIN_SERVER/rfpo-admin:latest" ..
docker push "$ACR_LOGIN_SERVER/rfpo-admin:latest"
echo -e "${GREEN}✅ RFPO Admin image pushed${NC}"

# Build User App image
echo -e "${BLUE}Building RFPO User App image...${NC}"
docker build --platform linux/amd64 -f ../Dockerfile.user-app -t "$ACR_LOGIN_SERVER/rfpo-user:latest" ..
docker push "$ACR_LOGIN_SERVER/rfpo-user:latest"
echo -e "${GREEN}✅ RFPO User App image pushed${NC}"

# Show summary
echo ""
echo -e "${GREEN}🎉 Container Registry Setup Complete!${NC}"
echo "=============================================="
echo "Registry URL: $ACR_LOGIN_SERVER"
echo "Images pushed:"
echo "  - $ACR_LOGIN_SERVER/rfpo-api:latest"
echo "  - $ACR_LOGIN_SERVER/rfpo-admin:latest"
echo "  - $ACR_LOGIN_SERVER/rfpo-user:latest"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Run the deployment script: ./deploy-to-azure.sh"
echo "2. Or deploy using Azure CLI with the Bicep template"
echo "=============================================="

# Save configuration for deployment script
cat > azure-config.env << EOF
SUBSCRIPTION_ID=$SUBSCRIPTION_ID
RESOURCE_GROUP_NAME=$RESOURCE_GROUP_NAME
ACR_NAME=$ACR_NAME
ACR_LOGIN_SERVER=$ACR_LOGIN_SERVER
LOCATION="$LOCATION"
EOF

echo -e "${GREEN}✅ Configuration saved to azure-config.env${NC}"