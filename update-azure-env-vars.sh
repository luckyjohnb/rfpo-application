#!/bin/bash

# Update Azure Container Apps with Phase 1 environment variables

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SUBSCRIPTION_ID="e108977f-44ed-4400-9580-f7a0bc1d3630"
RESOURCE_GROUP="rg-rfpo-e108977f"

echo -e "${BLUE}🔧 Updating Azure Container Apps Environment Variables${NC}"
echo "=============================================="

# Set subscription
az account set --subscription "$SUBSCRIPTION_ID"

# Get database connection string
DB_URL="postgresql://rfpoadmin:RfpoSecure123!@rfpo-db-5kn5bsg47vvac.postgres.database.azure.com:5432/rfpodb?sslmode=require"

# Generate secure secret keys (32+ chars required)
FLASK_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
API_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
USER_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
ADMIN_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")

echo -e "${YELLOW}Generated secure secret keys${NC}"

# Update rfpo-api environment variables
echo -e "${YELLOW}Updating rfpo-api environment variables...${NC}"
az containerapp update \
    --name rfpo-api \
    --resource-group "$RESOURCE_GROUP" \
    --set-env-vars \
        "DATABASE_URL=$DB_URL" \
        "FLASK_SECRET_KEY=$FLASK_SECRET" \
        "JWT_SECRET_KEY=$JWT_SECRET" \
        "API_SECRET_KEY=$API_SECRET" \
        "LOG_LEVEL=INFO" \
    --output none

echo -e "${GREEN}✅ rfpo-api environment variables updated${NC}"

# Update rfpo-admin environment variables
echo -e "${YELLOW}Updating rfpo-admin environment variables...${NC}"
az containerapp update \
    --name rfpo-admin \
    --resource-group "$RESOURCE_GROUP" \
    --set-env-vars \
        "DATABASE_URL=$DB_URL" \
        "FLASK_SECRET_KEY=$FLASK_SECRET" \
        "ADMIN_SECRET_KEY=$ADMIN_SECRET" \
        "API_BASE_URL=https://rfpo-api-5kn5bsg47vvac.proudbush-cac5d6af.eastus.azurecontainerapps.io/api" \
        "LOG_LEVEL=INFO" \
    --output none

echo -e "${GREEN}✅ rfpo-admin environment variables updated${NC}"

# Update rfpo-user environment variables
echo -e "${YELLOW}Updating rfpo-user environment variables...${NC}"
az containerapp update \
    --name rfpo-user \
    --resource-group "$RESOURCE_GROUP" \
    --set-env-vars \
        "FLASK_SECRET_KEY=$FLASK_SECRET" \
        "USER_APP_SECRET_KEY=$USER_SECRET" \
        "API_BASE_URL=https://rfpo-api-5kn5bsg47vvac.proudbush-cac5d6af.eastus.azurecontainerapps.io/api" \
        "LOG_LEVEL=INFO" \
    --output none

echo -e "${GREEN}✅ rfpo-user environment variables updated${NC}"

echo ""
echo -e "${GREEN}🎉 All environment variables updated!${NC}"
echo "=============================================="
echo ""
echo -e "${YELLOW}Note: The secret keys have been randomly generated.${NC}"
echo -e "${YELLOW}Apps will restart automatically with new configuration.${NC}"
