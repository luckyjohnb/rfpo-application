# RFPO Application - Azure Container Apps Deployment

This guide walks you through deploying the RFPO (Request for Purchase Order) application to Azure Container Apps using Infrastructure as Code (Bicep) and automated CI/CD pipelines.

## 🏗️ Architecture Overview

The RFPO application is deployed as a 3-tier containerized application:

- **RFPO API** (Port 5002): REST API backend service
- **RFPO Admin Panel** (Port 5111): Administrative interface
- **RFPO User App** (Port 5001): End-user interface

### Azure Resources

- **Azure Container Apps**: Serverless container hosting
- **Azure Container Registry**: Private Docker registry
- **Azure File Share**: Persistent storage for SQLite database
- **Log Analytics**: Centralized logging and monitoring
- **Storage Account**: File storage backend

## 🚀 Quick Deployment

### Prerequisites

1. **Azure CLI** installed and logged in
2. **Docker** installed and running
3. **Subscription ID**: `e108977f-44ed-4400-9580-f7a0bc1d3630`
4. **Contributor** access to the subscription

### Step 1: Initial Setup and Container Registry

```bash
cd azure
./setup-acr.sh
```

This script will:
- Create resource group
- Set up Azure Container Registry
- Build and push Docker images
- Save configuration for deployment

### Step 2: Deploy Application

```bash
./deploy-to-azure.sh
```

This script will:
- Deploy infrastructure using Bicep
- Initialize the database
- Configure persistent storage
- Provide application URLs

## 📋 Manual Deployment Steps

If you prefer manual deployment or need to customize the process:

### 1. Login to Azure

```bash
az login
az account set --subscription "e108977f-44ed-4400-9580-f7a0bc1d3630"
```

### 2. Create Resource Group

```bash
az group create \
  --name "rg-rfpo-e108977f" \
  --location "East US"
```

### 3. Deploy with Bicep

```bash
az deployment group create \
  --resource-group "rg-rfpo-e108977f" \
  --template-file "main.bicep" \
  --parameters environmentType="prod"
```

### 4. Build and Push Images

```bash
# Login to ACR
az acr login --name "acrrfpoe108977f"

# Build and push images
docker build -f ../Dockerfile.api -t acrrfpoe108977f.azurecr.io/rfpo-api:latest ..
docker push acrrfpoe108977f.azurecr.io/rfpo-api:latest

docker build -f ../Dockerfile.admin -t acrrfpoe108977f.azurecr.io/rfpo-admin:latest ..
docker push acrrfpoe108977f.azurecr.io/rfpo-admin:latest

docker build -f ../Dockerfile.user-app -t acrrfpoe108977f.azurecr.io/rfpo-user:latest ..
docker push acrrfpoe108977f.azurecr.io/rfpo-user:latest
```

## 🔄 CI/CD with GitHub Actions

The application includes a complete GitHub Actions workflow for automated deployment.

### Setup GitHub Secrets

1. Create an Azure Service Principal:

```bash
az ad sp create-for-rbac \
  --name "rfpo-github-actions" \
  --role contributor \
  --scopes /subscriptions/e108977f-44ed-4400-9580-f7a0bc1d3630 \
  --sdk-auth
```

2. Add the output as a secret named `AZURE_CREDENTIALS` in your GitHub repository.

### Workflow Features

- **Automatic builds** on push to main
- **Multi-environment support** (dev, staging, prod)
- **Docker image versioning** with git SHA
- **Health checks** after deployment
- **Deployment summaries** in GitHub

### Manual Workflow Trigger

You can manually trigger deployments with specific environments:

1. Go to GitHub Actions
2. Select "Deploy RFPO to Azure Container Apps"
3. Click "Run workflow"
4. Choose environment (dev/staging/prod)

## 🔐 Security Configuration

### Environment Variables

The application uses the following secure environment variables:

- `JWT_SECRET_KEY`: JWT token signing key
- `API_SECRET_KEY`: API authentication key
- `ADMIN_SECRET_KEY`: Admin panel secret key
- `USER_APP_SECRET_KEY`: User app session key

All secrets are auto-generated using Azure resource IDs for uniqueness.

### Database Security

- SQLite database stored in Azure File Share
- Encrypted at rest
- Access controlled through Azure RBAC
- Backup included in storage account

## 📊 Monitoring and Logging

### Log Analytics

All container logs are centralized in Log Analytics workspace:

```bash
# View container logs
az containerapp logs show \
  --name rfpo-api \
  --resource-group rg-rfpo-e108977f \
  --follow
```

### Application Insights

Integration with Application Insights for:
- Performance monitoring
- Error tracking
- Usage analytics
- Custom metrics

### Health Checks

Each container app includes health endpoints:
- API: `/api/health`
- Admin: `/health`
- User App: `/health`

## 🔧 Management Commands

### Scaling Applications

```bash
# Scale API service
az containerapp update \
  --name rfpo-api \
  --resource-group rg-rfpo-e108977f \
  --min-replicas 2 \
  --max-replicas 10
```

### Updating Images

```bash
# Update with new image
az containerapp update \
  --name rfpo-api \
  --resource-group rg-rfpo-e108977f \
  --image acrrfpoe108977f.azurecr.io/rfpo-api:new-tag
```

### Environment Variables

```bash
# Update environment variables
az containerapp update \
  --name rfpo-api \
  --resource-group rg-rfpo-e108977f \
  --set-env-vars "NEW_VAR=value"
```

## 🗄️ Database Management

### Backup Database

```bash
# Connect to storage account
az storage file download \
  --account-name "strfpoe108977f" \
  --share-name "rfpo-data" \
  --path "rfpo_admin.db" \
  --dest "./backup-$(date +%Y%m%d).db"
```

### Restore Database

```bash
# Upload database backup
az storage file upload \
  --account-name "strfpoe108977f" \
  --share-name "rfpo-data" \
  --source "./backup.db" \
  --path "rfpo_admin.db"
```

### Database Migrations

Run database migrations using a temporary container:

```bash
az container create \
  --resource-group rg-rfpo-e108977f \
  --name rfpo-migrate \
  --image acrrfpoe108977f.azurecr.io/rfpo-admin:latest \
  --azure-file-volume-account-name "strfpoe108977f" \
  --azure-file-volume-share-name "rfpo-data" \
  --azure-file-volume-mount-path "/app/data" \
  --command-line "python migrate_script.py" \
  --restart-policy Never
```

## 🌐 Custom Domains and SSL

### Add Custom Domain

```bash
# Add custom domain to container app
az containerapp hostname add \
  --hostname "rfpo.yourdomain.com" \
  --name rfpo-user \
  --resource-group rg-rfpo-e108977f
```

### SSL Certificates

Container Apps automatically provision and manage SSL certificates for custom domains.

## 💰 Cost Optimization

### Resource Recommendations

- **Development**: 0.25 vCPU, 0.5 GB memory per service
- **Production**: 0.5 vCPU, 1 GB memory per service
- **Storage**: Standard LRS for cost efficiency
- **Container Registry**: Basic tier sufficient for most workloads

### Scaling Configuration

```bicep
scale: {
  minReplicas: 0  // Scale to zero for dev environments
  maxReplicas: 10
  rules: [
    {
      name: 'http-scaling'
      http: {
        metadata: {
          concurrentRequests: '30'
        }
      }
    }
  ]
}
```

## 🚨 Troubleshooting

### Common Issues

1. **Container startup failures**
   - Check container logs: `az containerapp logs show`
   - Verify image exists in ACR
   - Check environment variables

2. **Database connection issues**
   - Verify file share is mounted
   - Check storage account access keys
   - Ensure database file exists

3. **Application not accessible**
   - Check ingress configuration
   - Verify security groups
   - Test health endpoints

### Support Commands

```bash
# Get application status
az containerapp list --resource-group rg-rfpo-e108977f --output table

# View deployment logs
az deployment group list --resource-group rg-rfpo-e108977f --output table

# Check resource health
az resource list --resource-group rg-rfpo-e108977f --output table
```

## 📞 Support

For deployment issues or questions:

1. Check the GitHub Actions logs
2. Review Azure deployment logs
3. Check container application logs
4. Verify all prerequisites are met

## 🔄 Updates and Maintenance

### Regular Updates

1. **Security patches**: Monitor base image updates
2. **Application updates**: Use CI/CD pipeline
3. **Azure updates**: Monitor Azure service updates
4. **Certificate renewal**: Automatic for managed certificates

### Backup Strategy

- **Database**: Daily automated backups
- **File uploads**: Included in storage account backup
- **Configuration**: Stored in Git repository
- **Infrastructure**: Defined in Bicep templates

---

## ✅ **LIVE Production Application Access**

**Status**: 🟢 **DEPLOYED & OPERATIONAL**

Access your RFPO application (production):

- **Admin Panel**: <https://rfpo-admin.livelyforest-d06a98a0.eastus.azurecontainerapps.io>
- **User App**: <https://rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io>  
- **API**: <https://rfpo-api.livelyforest-d06a98a0.eastus.azurecontainerapps.io/api/health>

**Production Login:**
- Email: `admin@rfpo.com`
- Password: `admin123`

**Resource Details:**
- Resource Group: `rg-rfpo-e108977f`
- Environment: `rfpo-env-5kn5bsg47vvac`
- Registry: `acrrfpoe108977f.azurecr.io`
- Storage: `strfpo{unique}` with file share `rfpo-data`

> **Note**: Change the default password immediately after first login!