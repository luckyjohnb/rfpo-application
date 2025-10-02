#!/bin/bash

# Authentication Status Checker
# Run this script to verify GitHub and Azure authentication before starting work

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔐 Checking Authentication Status...${NC}"
echo "========================================"
echo ""

# Check GitHub Authentication
echo -e "${YELLOW}Checking GitHub...${NC}"
if gh auth status &>/dev/null; then
    echo -e "${GREEN}✅ GitHub: Authenticated${NC}"
    gh auth status 2>&1 | head -n 3
else
    echo -e "${RED}❌ GitHub: NOT authenticated${NC}"
    echo -e "${YELLOW}   Run: gh auth login${NC}"
    GITHUB_AUTH=false
fi
echo ""

# Check Azure Authentication
echo -e "${YELLOW}Checking Azure...${NC}"
if az account show &>/dev/null; then
    echo -e "${GREEN}✅ Azure: Authenticated${NC}"
    SUBSCRIPTION=$(az account show --query name -o tsv)
    ACCOUNT=$(az account show --query user.name -o tsv)
    echo "   Account: $ACCOUNT"
    echo "   Subscription: $SUBSCRIPTION"
else
    echo -e "${RED}❌ Azure: NOT authenticated${NC}"
    echo -e "${YELLOW}   Run: az login${NC}"
    AZURE_AUTH=false
fi
echo ""

# Check Docker
echo -e "${YELLOW}Checking Docker...${NC}"
if docker info &>/dev/null; then
    echo -e "${GREEN}✅ Docker: Running${NC}"
else
    echo -e "${RED}❌ Docker: NOT running${NC}"
    echo -e "${YELLOW}   Open Docker Desktop${NC}"
    DOCKER_RUNNING=false
fi
echo ""

# Check Git Remote
echo -e "${YELLOW}Checking Git Remote...${NC}"
if git remote -v | grep -q "origin"; then
    REMOTE=$(git remote get-url origin)
    echo -e "${GREEN}✅ Git Remote: Connected${NC}"
    echo "   Remote: $REMOTE"
else
    echo -e "${RED}❌ Git Remote: NOT configured${NC}"
    GIT_REMOTE=false
fi
echo ""

# Summary
echo "========================================"
if [ "$GITHUB_AUTH" = false ] || [ "$AZURE_AUTH" = false ] || [ "$DOCKER_RUNNING" = false ]; then
    echo -e "${YELLOW}⚠️  Some services need authentication${NC}"
    echo ""
    echo "Quick fix commands:"
    if [ "$GITHUB_AUTH" = false ]; then
        echo -e "  ${YELLOW}gh auth login${NC}             # Login to GitHub"
    fi
    if [ "$AZURE_AUTH" = false ]; then
        echo -e "  ${YELLOW}az login${NC}                  # Login to Azure"
    fi
    if [ "$DOCKER_RUNNING" = false ]; then
        echo -e "  ${YELLOW}open -a Docker${NC}            # Start Docker Desktop"
    fi
    echo ""
    exit 1
else
    echo -e "${GREEN}✅ All services authenticated!${NC}"
    echo ""
    echo "You're ready to:"
    echo "  • Push code to GitHub"
    echo "  • Deploy to Azure Container Apps"
    echo "  • Run Docker containers"
    echo ""
    exit 0
fi
