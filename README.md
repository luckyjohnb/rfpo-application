# RFPO Application
Carlos
Containerized Request for Purchase Order (RFPO) management system with separated user and admin interfaces.

## 📢 Latest Release: JanuaryFixes (January 28, 2026)

✅ **Deployed to Production**

**New Features:**
- 💰 Currency formatting with thousand separators ($1,234,567.89)
- 🐛 Fixed form validation field selector bug
- 🙈 Generate PO button now hidden until approval criteria met
- 🔐 Enhanced admin security

**See [CHANGELOG_2026.md](./CHANGELOG_2026.md) for detailed release notes.**

## 🏗️ Architecture

The RFPO application consists of three containerized services:

```text
┌─────────────────────────────────────────────────────────┐
│                    RFPO Application                     │
├─────────────────┬─────────────────┬───────**Azure specifics:**
- **Status**: ✅ **DEPLOYED TO PRODUCTION**
- Subscription ID: `e108977f-44ed-4400-9580-f7a0bc1d3630`
- Resource Group: `rg-rfpo-e108977f`
- Location: `East US`
- ACR: `acrrfpoe108977f.azurecr.io`
- Container Apps Environment: `rfpo-env-5kn5bsg47vvac`
- **Container platform: linux/amd64** (NOT arm64/Mac)
- Always use `sslmode=require` for PostgreSQL connections─────────┤
│   User App      │   Admin Panel   │      API Layer      │
│   Port: 5000    │   Port: 5111    │     Port: 5002      │
│                 │                 │                     │
│ • Modern UI     │ • User Mgmt     │ • Auth Routes       │
│ • Dashboard     │ • Team Mgmt     │ • Team Routes       │
│ • RFPO Views    │ • RFPO Admin    │ • RFPO Routes       │
│ • API Consumer  │ • Reports       │ • Database Access   │
└─────────────────┴─────────────────┴─────────────────────┤
│                  Database: instance/rfpo_admin.db       │
│                     (SQLite Database)                   │
└─────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites


### Deployment

1. **Clone the repository:**

   ```bash
   git clone https://github.com/luckyjohnb/rfpo-application.git
   cd rfpo-application
   ```

2. **Configure environment:**

   ```bash
   cp .env.example .env
   # Edit .env file with your configuration:
   # - DATABASE_URL (PostgreSQL for production, SQLite for local dev)
   # - FLASK_SECRET_KEY, JWT_SECRET_KEY (generate with: python -c "import secrets; print(secrets.token_hex(32))")
   # - GMAIL_USER, GMAIL_APP_PASSWORD (for email functionality)
   # - API_BASE_URL (adjust for your deployment)
   ```
   
   **Important:** Never commit the `.env` file to version control! It contains sensitive credentials.

3. **Start all services:**

   ```bash
   docker-compose up -d
   ```

4. **Check status:**

   ```bash
   docker-compose ps
   ```

5. **Access applications:**

   - **User Application**: <http://localhost:5000>
   - **Admin Panel**: <http://localhost:5111>
   - **API Documentation**: <http://localhost:5002/api>

## 🔐 Default Login

### Admin Panel

URL: <http://localhost:5111>


### User App

URL: <http://localhost:5000>


## 📋 Core Features

### Admin Panel (Port 5111)


### User Application (Port 5000)


### API Layer (Port 5002)


## 🗄️ Database

The application uses a **single SQLite database** (`instance/rfpo_admin.db`) shared across all services:


## � File Upload Storage

Looking for where uploaded documents live locally and in Azure (and how to access them)? See FILE_UPLOAD_STORAGE.md for a concise guide to paths, Azure Files mounting, RBAC, and retrieval options.

## �🔧 Configuration

### Secrets

For a complete overview of how secrets are managed locally and in Azure (per-app secret names, storage mounts, rotation, and verification), see SECRETS.md.

### Environment Variables Setup

All configuration is managed via a `.env` file. **Never commit this file to version control!**

1. **Create .env file from template:**

   ```bash
   cp .env.example .env
   ```

2. **Edit .env with your configuration:**

   ```bash
   # Database Configuration
   # For local development (SQLite):
   DATABASE_URL=sqlite:///instance/rfpo_admin.db
   # For production (PostgreSQL on Azure):
   **Azure PostgreSQL connection string format (in .env file):**
```
DATABASE_URL=postgresql://rfpoadmin:PASSWORD@rfpo-db-{unique}.postgres.database.azure.com:5432/rfpodb?sslmode=require
```

**Current Production Database:** `rfpo-db-{unique}.postgres.database.azure.com` (SSL enabled, 32GB storage)

   # Application Secrets (MUST CHANGE FOR PRODUCTION!)
   # Generate secure keys with: python -c "import secrets; print(secrets.token_hex(32))"
   FLASK_SECRET_KEY=your-64-char-hex-string-here-change-in-production
   JWT_SECRET_KEY=your-64-char-hex-string-here-change-in-production
   API_SECRET_KEY=your-64-char-hex-string-here-change-in-production
   USER_APP_SECRET_KEY=your-64-char-hex-string-here-change-in-production
   ADMIN_SECRET_KEY=your-64-char-hex-string-here-change-in-production

   # API Configuration
   API_BASE_URL=http://localhost:5002

   # Email Configuration (Gmail example)
   GMAIL_USER=your-email@gmail.com
   GMAIL_APP_PASSWORD=your-gmail-app-password

   # Security Settings
   SESSION_COOKIE_SECURE=false  # Set to true for HTTPS
   SESSION_COOKIE_HTTPONLY=true
   SESSION_COOKIE_SAMESITE=Lax

   # Logging
   LOG_LEVEL=INFO
   LOG_FILE=logs/rfpo.log
   ```

3. **Validate configuration:**

   ```bash
   python -c "from env_config import validate_configuration; validate_configuration(); print('✅ Configuration valid')"
   ```

### Email Setup (Gmail)

For email functionality to work:

1. **Enable 2-Factor Authentication** on your Gmail account
2. **Generate App Password**:
   - Go to Google Account Settings → Security → 2-Step Verification → App passwords
   - Select "Mail" and your device
   - Copy the 16-character password
3. **Update .env file** with `GMAIL_USER` and `GMAIL_APP_PASSWORD`

**Security Note:** Never use your regular Gmail password. Always use App Passwords.

## 🛠️ Development

### Project Structure

```text
rfpo-application/
├── app.py                  # User-facing application (Port 5000)
├── custom_admin.py         # Admin panel (Port 5111)
├── simple_api.py           # API server (Port 5002)
├── models.py               # Database models (18 SQLAlchemy models)
├── env_config.py           # Centralized configuration management
├── exceptions.py           # Custom exception hierarchy
├── error_handlers.py       # Flask error handlers
├── logging_config.py       # Structured logging setup
├── email_service.py        # Email functionality
├── pdf_generator.py        # RFPO PDF generation
├── api/                    # API routes (auth, teams, rfpo, users)
├── templates/
│   ├── admin/              # Admin panel templates
│   ├── app/                # User app templates
│   └── error.html          # Error page template
├── static/                 # CSS, JS, images
├── instance/               # Database files
├── uploads/                # File uploads
├── logs/                   # Application logs (auto-created)
├── .env                    # Environment variables (DO NOT COMMIT)
├── .env.example            # Environment variable template
├── Dockerfile.api          # API service container
├── Dockerfile.admin        # Admin panel container  
├── Dockerfile.user-app     # User app container
└── docker-compose.yml      # Container orchestration
```

### Development Workflow

1. **Make code changes** to Python files or templates
2. **Rebuild and restart** affected services:
   
   ```bash
   docker-compose up --build -d
   ```
3. **View logs** to debug:
   
   ```bash
   docker-compose logs -f rfpo-admin  # Follow admin logs
   ```
4. **Test changes** via web interfaces

### Adding New Features

1. **User App Features**: Edit `app.py` and add templates in `templates/app/`
2. **Admin Features**: Edit `custom_admin.py` and add templates in `templates/admin/`
3. **API Endpoints**: Add to `simple_api.py` or create new files in `api/`
4. **Database Changes**: Edit `models.py` and rebuild containers

### Error Handling & Logging

The application includes comprehensive error handling and structured logging:

**Custom Exceptions** (`exceptions.py`):

**Structured Logging** (`logging_config.py`):

**Error Handlers** (`error_handlers.py`):

**Viewing Logs:**

```bash
# View application logs
tail -f logs/admin.log      # Admin panel logs
tail -f logs/user_app.log   # User application logs
tail -f logs/api.log        # API server logs

# Or use Docker logs
docker-compose logs -f rfpo-admin
docker-compose logs -f rfpo-user
docker-compose logs -f rfpo-api
```

### Docker Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs
docker-compose logs rfpo-admin  # Specific service

# Rebuild after changes
docker-compose up --build -d

# Stop services
docker-compose down

# Check status
docker-compose ps

# Access container shell for debugging
docker exec -it rfpo-admin /bin/bash
```

## 🧪 Testing

### Health Checks

All services provide health endpoints:


### User Flow Testing

1. **Create user** in admin panel
2. **Check email** for welcome message
3. **Login to user app** with admin-set password
4. **Change password** (required on first login)
5. **Access dashboard** and features

## 🔒 Security Features


## 📧 User Permissions


## 🐛 Troubleshooting

### Common Issues

1. **Services not starting**: Check `docker-compose logs`
2. **Database errors**: Verify `instance/rfpo_admin.db` exists and has proper permissions
3. **Email not working**: Check SMTP configuration in `.env`
4. **Port conflicts**: Ensure ports 5000, 5002, 5111 are available

### Logs

```bash
# View all logs
docker-compose logs

# View specific service logs
docker-compose logs rfpo-admin
docker-compose logs rfpo-api
docker-compose logs rfpo-user

# Follow logs in real-time
docker-compose logs -f
```

## 📞 Support

For issues or questions:

1. Check the logs first: `docker-compose logs`
2. Verify configuration: `.env` file settings
3. Test individual services: Use health check endpoints
4. Database issues: Check `instance/rfpo_admin.db` permissions

## ☁️ Azure Deployment

The RFPO application is **production-ready on Azure Container Apps** with automatic CI/CD, PostgreSQL database, and secure secret management.

### Azure Architecture

```text
┌─────────────────────────────────────────────────────────────────────┐
│                        Azure Container Apps                         │
├──────────────────┬──────────────────┬─────────────────────────────────┤
│   RFPO User      │   RFPO Admin     │        RFPO API                 │
│   (Port 5000)    │   (Port 5111)    │      (Port 5002)               │
│                  │                  │                                 │
│ • Public Access  │ • Admin Access   │ • Authentication                │
│ • Dashboard      │ • User Mgmt      │ • RESTful API                   │
│ • RFPO Views     │ • Team Mgmt      │ • Database Access               │
│ • API Calls      │ • Reports        │ • JWT Tokens                    │
└──────────────────┴──────────────────┴─────────────────────────────────┤
│          Azure PostgreSQL Flexible Server (Production DB)            │
├─────────────────────────────────────────────────────────────────────┤
│  Azure Container Registry (ACR) • Azure Files • Key Vault • ACS     │
└─────────────────────────────────────────────────────────────────────┘
```

### 🚀 Quick Deploy to Azure

**Prerequisites:**
- Azure subscription
- Azure CLI installed and logged in
- Docker (for local builds)

**One-Command Deployment:**

```bash
# Deploy everything to Azure Container Apps
./redeploy-phase1.sh
```

This script:
- Builds Docker images for linux/amd64 platform (required for Azure)
- Pushes to Azure Container Registry (ACR)
- Updates Container Apps with new images
- Runs health checks

### Azure Resources ✅ **DEPLOYED**

The application uses these Azure services:

| Resource | Purpose | Configuration | Status |
|----------|---------|---------------|--------|
| **Container Apps Environment** | Hosts all 3 microservices | `rfpo-env-5kn5bsg47vvac` | 🟢 **Active** |
| **Container Apps** | Application hosting | `rfpo-api`, `rfpo-admin`, `rfpo-user` | 🟢 **Running** |
| **Container Registry** | Docker image storage | `acrrfpoe108977f.azurecr.io` | 🟢 **Active** |
| **PostgreSQL Flexible Server** | Production database | `rfpo-db-{unique}` - SSL required | 🟢 **Running** |
| **Azure Files** | File upload storage | Mounted to `/app/uploads`, `/app/data` | 🟢 **Mounted** |
| **Log Analytics** | Monitoring & logs | Application insights and health | 🟢 **Collecting** |

### 🔧 Azure Configuration ✅ **PRODUCTION READY**

- **Resource Group:** `rg-rfpo-e108977f`  
- **Location:** `East US`  
- **Subscription:** `e108977f-44ed-4400-9580-f7a0bc1d3630`
- **Environment:** `rfpo-env-5kn5bsg47vvac.eastus.azurecontainerapps.io`
- **Domain:** `livelyforest-d06a98a0.eastus.azurecontainerapps.io`

### Production URLs ✅ **LIVE & DEPLOYED**

| Service | URL | Purpose | Status |
|---------|-----|---------|--------|
| **Admin Panel** | <https://rfpo-admin.livelyforest-d06a98a0.eastus.azurecontainerapps.io> | User/Team/RFPO management | 🟢 **LIVE** |
| **User App** | <https://rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io> | End-user dashboard | 🟢 **LIVE** |
| **API Health** | <https://rfpo-api.livelyforest-d06a98a0.eastus.azurecontainerapps.io/api/health> | Health check endpoint | 🟢 **LIVE** |

**Login Credentials (Production):**
- Admin Email: `admin@rfpo.com`
- Admin Password: `admin123`

### 🔐 Production Security

**Container Apps Security:**
- HTTPS enforced (automatic certificates)
- Environment variables for secrets
- Private networking between services
- Azure-managed identity for ACR access

**Database Security:**
- PostgreSQL with SSL required
- Connection string in environment variables
- Private endpoints (optional)
- Automated backups

**Secret Management:**
```bash
# Secrets are stored as Container App environment variables:
DATABASE_URL=postgresql://rfpoadmin:PASSWORD@rfpo-db-{unique}.postgres.database.azure.com:5432/rfpodb?sslmode=require
FLASK_SECRET_KEY=<64-char-secure-key>
JWT_SECRET_KEY=<64-char-secure-key>
ACS_CONNECTION_STRING=<azure-communication-services-connection>
```

### 📊 Monitoring & Health

**Health Endpoints:**
- API: `/api/health` (JSON status)
- Admin: `/health` (basic check)  
- User: `/health` (basic check)

**Azure Monitor Integration:**
```bash
# Check app status
az containerapp list --resource-group rg-rfpo-e108977f --output table

# View logs
az containerapp logs show --name rfpo-admin --resource-group rg-rfpo-e108977f --follow
az containerapp logs show --name rfpo-api --resource-group rg-rfpo-e108977f --follow
az containerapp logs show --name rfpo-user --resource-group rg-rfpo-e108977f --follow
```

### 🛠️ Development to Production Workflow

**Local Development:**
1. Code changes in VS Code
2. Test with `docker-compose up -d` (SQLite database)
3. Commit to main branch

**Azure Deployment:**
1. **Automatic CI/CD**: GitHub Actions trigger on push to main
2. **Manual Deploy**: Run `./redeploy-phase1.sh` for immediate deployment
3. **Health Check**: Verify all services via production URLs

**Database Migration:**
```bash
# Initialize Azure PostgreSQL database
python sqlalchemy_db_init.py  # Uses DATABASE_URL from .env
```

### 🔄 CI/CD Pipeline

**GitHub Actions** (`.github/workflows/deploy-azure.yml`):
- Triggers on push to `main` branch
- Builds Docker images with `--platform linux/amd64`
- Pushes to Azure Container Registry
- Updates Container Apps with new images
- Runs health checks

**Manual Deployment Script** (`redeploy-phase1.sh`):
- One-command deployment for immediate updates
- Builds all 3 services simultaneously
- Updates Container Apps with digest-pinned images
- Provides deployment status and URLs

### 📦 Container Images

All images are built for **linux/amd64** platform and stored in ACR:

```bash
# Latest images in production:
acrrfpoe108977f.azurecr.io/rfpo-api:latest
acrrfpoe108977f.azurecr.io/rfpo-admin:latest  
acrrfpoe108977f.azurecr.io/rfpo-user:latest
```

**Build Process:**
- Source: GitHub main branch
- Platform: linux/amd64 (Azure Container Apps requirement)
- Registry: Azure Container Registry with managed identity
- Deployment: Digest-pinned for consistent deployments

### 🗃️ Database Differences: Local vs Azure

| Aspect | Local (SQLite) | Azure (PostgreSQL) |
|--------|---------------|-------------------|
| **File** | `instance/rfpo_admin.db` | Azure PostgreSQL Flexible Server |
| **Connection** | `sqlite:///instance/rfpo_admin.db` | `postgresql://user:pass@server:5432/db?sslmode=require` |
| **Initialization** | `python sqlalchemy_db_init.py` | Same command with Azure `DATABASE_URL` |
| **Backup** | Copy SQLite file | Azure automated backups + manual exports |
| **Performance** | Limited by filesystem | Scalable, managed service |
| **SSL** | Not applicable | Required (`sslmode=require`) |

### 🚨 Troubleshooting Azure Deployment

**Common Issues:**

1. **Build Failures**: Ensure `--platform linux/amd64` in Docker builds
2. **Database Connections**: Verify PostgreSQL connection string and SSL
3. **Secret Errors**: Check Container App environment variables
4. **Image Pull Issues**: Verify ACR permissions and image digests

**Debug Commands:**
```bash
# Check Container App status
az containerapp show --name rfpo-admin --resource-group rg-rfpo-e108977f

# View recent logs  
az containerapp logs show --name rfpo-admin --resource-group rg-rfpo-e108977f --tail 50

# Test health endpoints
curl https://rfpo-api.livelyforest-d06a98a0.eastus.azurecontainerapps.io/api/health
```

**Deployment Verification:**
1. All Container Apps show "Running" status
2. Health endpoints return 200 OK
3. Admin login works with test credentials
4. Database connections successful

### 💰 Azure Costs & Scaling

**Container Apps Pricing:**
- Pay-per-use model (CPU/memory/requests)
- Auto-scale from 0 to N instances
- Free tier available for development

**Cost Optimization:**
- Set minimum replicas to 0 for non-production
- Use appropriate resource limits
- Monitor usage via Azure Cost Management

## 🎯 Production Deployment

**Azure Container Apps** (Recommended - Production Ready):
- Automatic CI/CD via GitHub Actions
- Managed PostgreSQL database
- HTTPS with automatic certificates  
- Built-in monitoring and scaling
- One-command deployment: `./redeploy-phase1.sh`

**Self-Hosted** (Alternative):
1. **Update secrets**: Change all default passwords and keys
2. **Configure email**: Set up proper SMTP credentials  
3. **Database backup**: Implement regular backups of database
4. **Reverse proxy**: Use nginx or similar for SSL termination
5. **Monitoring**: Set up log aggregation and monitoring

**RFPO Application - Modern, Scalable, Containerized Purchase Order Management** 🚀

## ✉️ Azure Communication Services (Email)

You can send transactional emails via Azure Communication Services (ACS) with automatic SMTP fallback for local/dev.

1. Provision ACS Email in Azure and connect a verified sender domain or use a sandbox sender.
2. Add these environment variables (see `.env.example` for names):

   ```bash
   ACS_CONNECTION_STRING="endpoint=https://<your-acs>.communication.azure.com/;accesskey=<key>"
   ACS_SENDER_EMAIL="no-reply@yourdomain.com"  # Must be a verified sender in ACS
   ```

3. Deploy updated secrets to Container Apps or set them in your local `.env`.
4. Test delivery from the Admin Panel:
   - Navigate to Tools → Email Test (route: `/tools/email-test`)
   - Enter a recipient and subject/body; submit to send via ACS (or SMTP fallback if ACS is unavailable)

Notes:

- The email service automatically prefers ACS when `ACS_CONNECTION_STRING` is set; otherwise it falls back to SMTP using `GMAIL_USER` and `GMAIL_APP_PASSWORD`.
- For production, keep `SESSION_COOKIE_SECURE=true`, use HTTPS, and rotate keys regularly (see `SECRETS.md`).
