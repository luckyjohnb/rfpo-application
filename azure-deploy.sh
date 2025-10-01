#!/bin/bash

# RFPO Azure Quick Start
# One-command deployment to Azure Container Apps

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 RFPO Azure Quick Start${NC}"
echo "=============================="
echo "This script will deploy the RFPO application to Azure Container Apps"
echo "Subscription: e108977f-44ed-4400-9580-f7a0bc1d3630"
echo ""

# Check if we're in the right directory
if [ ! -f "azure/main.bicep" ]; then
    echo -e "${YELLOW}Please run this script from the rfpo-application root directory${NC}"
    exit 1
fi

# Check prerequisites
echo -e "${YELLOW}🔍 Checking prerequisites...${NC}"

if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI not found. Please install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker Desktop"
    exit 1
fi

echo "✅ Prerequisites check passed"
echo ""

# Confirm deployment
echo -e "${YELLOW}⚠️  This will create Azure resources in subscription e108977f-44ed-4400-9580-f7a0bc1d3630${NC}"
echo "Estimated cost: ~$50-100/month for development environment"
echo ""
read -p "Do you want to continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled"
    exit 0
fi

echo ""
echo -e "${BLUE}Starting deployment...${NC}"

# Change to azure directory
cd azure

# Step 1: Setup ACR and build images
echo -e "${YELLOW}📦 Step 1: Setting up Container Registry and building images...${NC}"
if [ ! -f "azure-config.env" ]; then
    ./setup-acr.sh
else
    echo "Configuration exists, skipping ACR setup"
fi

# Step 2: Deploy to Azure
echo -e "${YELLOW}🚀 Step 2: Deploying to Azure Container Apps...${NC}"
./deploy-to-azure.sh

echo ""
echo -e "${GREEN}🎉 Deployment completed!${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "1. Check deployment-info.txt for application URLs"
echo "2. Login to the admin panel with admin@rfpo.com / admin123"
echo "3. Configure users and teams as needed"
echo ""
echo -e "${YELLOW}Useful commands:${NC}"
echo "- View logs: az containerapp logs show --name [app-name] --resource-group [rg-name] --follow"
echo "- Scale app: az containerapp update --name [app-name] --resource-group [rg-name] --min-replicas X"
echo "- Update app: Commit changes and push to GitHub (if CI/CD is configured)"
echo ""
echo "Happy RFPOing! 🎯"