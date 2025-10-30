# Local Development with Azure Backend Services

## Overview

This guide enables local development using Azure production database and storage services while avoiding interference with the live deployment. This hybrid approach allows rapid development iteration without affecting the production environment.

## Prerequisites

- Docker and Docker Compose installed
- Azure CLI authenticated (`az login`)
- GitHub CLI authenticated (`gh auth login`)
- Local `.env.local` file configured (created during setup)

## Setup

### 1. Azure Firewall Configuration
Your local IP address (97.156.82.96) is already whitelisted in the Azure PostgreSQL firewall rules:
```bash
# Verify firewall rules
az postgres flexible-server firewall-rule list \
  --name rfpo-db-5kn5bsg47vvac \
  --resource-group rg-rfpo-e108977f \
  --output table
```

### 2. Local Environment Configuration
The `.env.local` file contains:
- **Azure PostgreSQL connection**: Direct connection to production database
- **Local storage paths**: File uploads stored locally in `./uploads`
- **Development secrets**: Generated secure keys for local development
- **Debug settings**: Enhanced logging and error reporting

**IMPORTANT**: Never commit `.env.local` - it contains production credentials!

### 3. Docker Compose Development
Use `docker-compose.dev.yml` for local development:
```bash
# Start local development environment
docker-compose -f docker-compose.dev.yml up --build -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f

# Stop services
docker-compose -f docker-compose.dev.yml down
```

## Services

| Service | Local Port | Description |
|---------|------------|-------------|
| Admin Panel | 5111 | Direct Azure DB access, local file storage |
| User App | 5000/5001 | API calls only, no direct DB access |
| API Layer | 5002 | Azure DB + JWT auth, local files |

## Key Differences from Production

### Database
- **Production**: Azure PostgreSQL with Container Apps network
- **Local**: Direct connection to same Azure PostgreSQL from local machine
- **Data**: Same production data - BE CAREFUL with modifications!

### File Storage
- **Production**: Azure File Share mounted to containers
- **Local**: Local `./uploads` directory
- **Impact**: Uploaded files won't sync between local and production

### Environment Variables
- **Production**: Azure Container Apps environment variables
- **Local**: `.env.local` file with development-specific settings
- **Secrets**: Local development uses generated secure keys

## Development Workflow

### 1. Start Local Development
```bash
# Ensure Azure access
az account show

# Start development environment
docker-compose -f docker-compose.dev.yml up --build -d

# Check service health
curl http://localhost:5002/api/health
curl http://localhost:5111/health  # Admin panel
```

### 2. Access Local Services
- **Admin Panel**: http://localhost:5111/login
- **User App**: http://localhost:5000
- **API Documentation**: http://localhost:5002/api/health

### 3. Development Iteration
- Code changes are reflected immediately (volumes mounted)
- Database changes affect production data - use with caution
- File uploads stored locally for testing

### 4. Database Operations
```bash
# Connect to Azure PostgreSQL from local machine
psql "postgresql://rfpoadmin:RfpoSecure123!@rfpo-db-5kn5bsg47vvac.postgres.database.azure.com:5432/rfpodb?sslmode=require"

# Run database initialization (if needed - CAREFUL!)
python sqlalchemy_db_init.py  # Uses .env.local configuration
```

## Safety Guidelines

### Database Safety
- **READ OPERATIONS**: Safe - no impact on production
- **INSERT/UPDATE**: Caution - affects production data
- **DELETE/DROP**: Never do this - will destroy production data!
- **Schema Changes**: Test on local SQLite copy first

### File Operations
- **Local uploads**: Safe - isolated from production
- **Production file access**: Not available in local development
- **PDF generation**: Uses local templates and positioning

### Testing Approach
1. **Read-only testing**: Safe with production database
2. **Write operations**: Use test data or temporary records
3. **Destructive operations**: Never on production database
4. **Schema testing**: Use local SQLite database first

## Troubleshooting

### Database Connection Issues
```bash
# Test database connectivity
python3 -c "
import psycopg2
conn = psycopg2.connect('postgresql://rfpoadmin:RfpoSecure123!@rfpo-db-5kn5bsg47vvac.postgres.database.azure.com:5432/rfpodb?sslmode=require')
print('Database connection successful')
conn.close()
"
```

### Firewall Access
```bash
# Check if your IP is whitelisted
az postgres flexible-server firewall-rule list \
  --name rfpo-db-5kn5bsg47vvac \
  --resource-group rg-rfpo-e108977f

# Add current IP if needed (get IP from ipinfo.io)
curl -s ipinfo.io/ip
az postgres flexible-server firewall-rule create \
  --name "LocalDev-$(date +%Y%m%d)" \
  --resource-group rg-rfpo-e108977f \
  --rule-name rfpo-db-5kn5bsg47vvac \
  --start-ip-address YOUR_IP \
  --end-ip-address YOUR_IP
```

### Container Issues
```bash
# Rebuild with fresh images
docker-compose -f docker-compose.dev.yml down
docker-compose -f docker-compose.dev.yml up --build --force-recreate -d

# Check container logs
docker-compose -f docker-compose.dev.yml logs rfpo-admin
docker-compose -f docker-compose.dev.yml logs rfpo-api
docker-compose -f docker-compose.dev.yml logs rfpo-user
```

### Environment Configuration
```bash
# Validate environment variables
python3 -c "
from env_config import Config
config = Config('.env.local')
print('Database URL:', config.DATABASE_URL[:50] + '...')
print('Secret Key length:', len(config.FLASK_SECRET_KEY))
"
```

## Production vs Local Comparison

| Aspect | Production (Azure) | Local Development |
|--------|-------------------|-------------------|
| Database | Azure PostgreSQL | Same Azure PostgreSQL |
| File Storage | Azure File Share | Local ./uploads |
| Container Platform | Azure Container Apps | Docker Compose |
| Network Access | Container Apps network | Public internet + firewall |
| SSL/TLS | Azure-managed HTTPS | HTTP (local only) |
| Secrets Management | Azure Key Vault | .env.local file |
| Scaling | Auto-scale | Single containers |
| Monitoring | Azure Monitor | Docker logs |

## Notes

- **Data Consistency**: Both environments use the same database
- **File Isolation**: Local uploads don't affect production files
- **Development Speed**: Faster iteration without Azure deployment delays
- **Cost Optimization**: No additional Azure resources needed for development
- **Security**: Production credentials in local .env.local - keep secure!

## Next Steps

1. Test the local development setup
2. Document any additional configuration needed
3. Create development-specific database seeding if required
4. Set up IDE integration and debugging workflows
