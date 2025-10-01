#!/bin/bash

# Deploy RFPO Application to Azure Container Apps
# This script deploys the entire RFPO application stack to Azure

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Load configuration
if [ -f "azure-config.env" ]; then
    source azure-config.env
    echo -e "${GREEN}✅ Loaded configuration from azure-config.env${NC}"
else
    echo -e "${RED}❌ azure-config.env not found. Please run setup-acr.sh first.${NC}"
    exit 1
fi

# Default values
ENVIRONMENT_TYPE=${ENVIRONMENT_TYPE:-"dev"}
DEPLOYMENT_NAME="rfpo-deployment-$(date +%Y%m%d-%H%M%S)"

echo -e "${BLUE}🚀 RFPO Azure Container Apps Deployment${NC}"
echo "=============================================="
echo "Subscription ID: $SUBSCRIPTION_ID"
echo "Resource Group: $RESOURCE_GROUP_NAME"
echo "Environment: $ENVIRONMENT_TYPE"
echo "Deployment Name: $DEPLOYMENT_NAME"
echo "=============================================="

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo -e "${RED}❌ Azure CLI is not installed. Please install it first.${NC}"
    exit 1
fi

# Check login status
echo -e "${YELLOW}🔐 Checking Azure login status...${NC}"
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}Please log in to Azure...${NC}"
    az login
fi

# Set subscription
az account set --subscription "$SUBSCRIPTION_ID"

# Check if Container Apps extension is installed
echo -e "${YELLOW}🔧 Checking Azure CLI extensions...${NC}"
if ! az extension list --query "[?name=='containerapp'].name" -o tsv | grep -q containerapp; then
    echo -e "${YELLOW}Installing Container Apps extension...${NC}"
    az extension add --name containerapp --upgrade
fi

# Register required providers
echo -e "${YELLOW}📋 Registering required Azure providers...${NC}"
az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.OperationalInsights --wait

# Deploy the Bicep template
echo -e "${YELLOW}🏗️  Deploying infrastructure using Bicep template...${NC}"
DEPLOYMENT_OUTPUT=$(az deployment group create \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --template-file "main.bicep" \
    --parameters environmentType="$ENVIRONMENT_TYPE" acrName="$ACR_NAME" \
    --name "$DEPLOYMENT_NAME" \
    --query 'properties.outputs' \
    -o json)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Infrastructure deployment completed successfully!${NC}"
else
    echo -e "${RED}❌ Infrastructure deployment failed!${NC}"
    exit 1
fi

# Extract outputs
API_URL=$(echo "$DEPLOYMENT_OUTPUT" | jq -r '.apiUrl.value')
ADMIN_URL=$(echo "$DEPLOYMENT_OUTPUT" | jq -r '.adminUrl.value')
USER_URL=$(echo "$DEPLOYMENT_OUTPUT" | jq -r '.userUrl.value')
STORAGE_ACCOUNT=$(echo "$DEPLOYMENT_OUTPUT" | jq -r '.storageAccountName.value')
FILE_SHARE=$(echo "$DEPLOYMENT_OUTPUT" | jq -r '.fileShareName.value')
CONTAINER_ENV=$(echo "$DEPLOYMENT_OUTPUT" | jq -r '.containerAppsEnvironmentName.value')

# Initialize database in Azure File Share
echo -e "${YELLOW}📁 Setting up database in Azure File Share...${NC}"

# Get storage account key
STORAGE_KEY=$(az storage account keys list \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --account-name "$STORAGE_ACCOUNT" \
    --query "[0].value" -o tsv)

# Create a temporary container to initialize the database
echo -e "${YELLOW}🗄️  Initializing database...${NC}"
TEMP_CONTAINER="rfpo-db-init-$(date +%s)"

# Run database initialization
az container create \
    --resource-group "$RESOURCE_GROUP_NAME" \
    --name "$TEMP_CONTAINER" \
    --image "$ACR_LOGIN_SERVER/rfpo-admin:latest" \
    --registry-login-server "$ACR_LOGIN_SERVER" \
    --registry-username "$(az acr credential show --name $ACR_NAME --query username -o tsv)" \
    --registry-password "$(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)" \
    --azure-file-volume-account-name "$STORAGE_ACCOUNT" \
    --azure-file-volume-account-key "$STORAGE_KEY" \
    --azure-file-volume-share-name "$FILE_SHARE" \
    --azure-file-volume-mount-path "/app/data" \
    --environment-variables \
        DATABASE_URL="sqlite:///app/data/rfpo_admin.db" \
        FLASK_ENV="production" \
    --command-line "python create_admin_user.py" \
    --restart-policy Never \
    --location "$LOCATION"

# Wait for container to complete
echo -e "${YELLOW}⏳ Waiting for database initialization to complete...${NC}"
while [ "$(az container show --resource-group $RESOURCE_GROUP_NAME --name $TEMP_CONTAINER --query instanceView.state -o tsv)" = "Running" ]; do
    echo "Still initializing database..."
    sleep 10
done

# Get logs and check if successful
INIT_LOGS=$(az container logs --resource-group "$RESOURCE_GROUP_NAME" --name "$TEMP_CONTAINER")
if echo "$INIT_LOGS" | grep -q "Setup completed successfully"; then
    echo -e "${GREEN}✅ Database initialized successfully!${NC}"
else
    echo -e "${YELLOW}⚠️  Database initialization logs:${NC}"
    echo "$INIT_LOGS"
fi

# Clean up temporary container
az container delete --resource-group "$RESOURCE_GROUP_NAME" --name "$TEMP_CONTAINER" --yes

# Display deployment summary
echo ""
echo -e "${GREEN}🎉 RFPO Application Deployment Complete!${NC}"
echo "=============================================="
echo -e "${BLUE}Application URLs:${NC}"
echo "📊 Admin Panel:     $ADMIN_URL"
echo "👥 User App:        $USER_URL"
echo "🔗 API Endpoint:    $API_URL"
echo ""
echo -e "${BLUE}Default Login Credentials:${NC}"
echo "📧 Email:           admin@rfpo.com"
echo "🔑 Password:        admin123"
echo ""
echo -e "${BLUE}Azure Resources:${NC}"
echo "📂 Resource Group:  $RESOURCE_GROUP_NAME"
echo "🐳 Container Registry: $ACR_LOGIN_SERVER"
echo "💾 Storage Account: $STORAGE_ACCOUNT"
echo "🗂️  File Share:      $FILE_SHARE"
echo "🌐 Container Environment: $CONTAINER_ENV"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Visit the Admin Panel: $ADMIN_URL"
echo "2. Login with admin@rfpo.com / admin123"
echo "3. Create additional users and configure teams"
echo "4. Test the User App: $USER_URL"
echo ""
echo -e "${BLUE}To update the application:${NC}"
echo "1. Build new images: ./setup-acr.sh"
echo "2. Redeploy: ./deploy-to-azure.sh"
echo "=============================================="

# Save deployment info
cat > deployment-info.txt << EOF
RFPO Application - Azure Deployment Information
Generated: $(date)

Application URLs:
- Admin Panel: $ADMIN_URL
- User App: $USER_URL
- API Endpoint: $API_URL

Default Login:
- Email: admin@rfpo.com
- Password: admin123

Azure Resources:
- Subscription: $SUBSCRIPTION_ID
- Resource Group: $RESOURCE_GROUP_NAME
- Container Registry: $ACR_LOGIN_SERVER
- Storage Account: $STORAGE_ACCOUNT
- File Share: $FILE_SHARE
- Container Environment: $CONTAINER_ENV

Management Commands:
- View logs: az containerapp logs show --name [app-name] --resource-group $RESOURCE_GROUP_NAME
- Scale app: az containerapp update --name [app-name] --resource-group $RESOURCE_GROUP_NAME --min-replicas X --max-replicas Y
- Update image: az containerapp update --name [app-name] --resource-group $RESOURCE_GROUP_NAME --image $ACR_LOGIN_SERVER/[image]:latest
EOF

echo -e "${GREEN}✅ Deployment info saved to deployment-info.txt${NC}"