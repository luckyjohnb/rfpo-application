# RFPO Application - AI Agent Instructions

## Architecture Overview

**3-tier containerized RFPO (Request for Purchase Order) management system:**
- **User App** (Local: Port 5000/5001 | Azure: HTTPS): Consumer-facing interface, calls API layer only via `make_api_request()`
- **Admin Panel** (Local: Port 5111 | Azure: HTTPS): Full CRUD operations via Flask-Login with custom admin UI, direct database access
- **API Layer** (Local: Port 5002 | Azure: HTTPS): RESTful API with JWT auth, shared database access

**Database:** Single SQLAlchemy database (SQLite local, PostgreSQL on Azure) shared across all services.

**Deployment:** Production runs on Azure Container Apps (HTTPS), local development uses docker-compose (HTTP with ports).

**Critical separation of concerns:**
- User App NEVER accesses database directly - only API calls
- Admin Panel has direct SQLAlchemy access for CRUD operations
- API Layer is the single source of truth for authentication/authorization

## Database Models (models.py)

**18 SQLAlchemy models** - always import ALL models for db.create_all() to work:
```python
from models import (
    db, User, Consortium, RFPO, RFPOLineItem, UploadedFile, DocumentChunk,
    Team, UserTeam, Project, Vendor, VendorSite, PDFPositioning, List,
    RFPOApprovalWorkflow, RFPOApprovalStage, RFPOApprovalStep,
    RFPOApprovalInstance, RFPOApprovalAction
)
```

**Key model patterns:**
- **JSON fields** stored as `db.Text` with getter/setter methods:
  ```python
  # Example: User permissions
  user.get_permissions()  # Returns list from JSON
  user.set_permissions(['GOD', 'RFPO_ADMIN'])  # Stores as JSON
  ```
- **All models have `to_dict()`** for API serialization (returns dict with snake_case keys)
- **Relationships** use `lazy=True` and cascade deletes where appropriate
- **Audit fields** standard: `created_at`, `updated_at`, `created_by`, `updated_by`
- **User model** has complex permission system: `permissions` JSON field contains system-level roles (GOD, RFPO_ADMIN, RFPO_USER, VROOM_ADMIN, CAL_MEET_USER)
- **Team membership** tracked via `UserTeam` junction table PLUS JSON arrays on Team/Consortium models (`viewer_user_ids`, `admin_user_ids`)

## Database Initialization

**CRITICAL:** When initializing databases (especially Azure PostgreSQL), use `sqlalchemy_db_init.py`:
- Imports all 18 models (required for table creation - missing even ONE will break db.create_all())
- Creates admin user with werkzeug hashed password (NOT bcrypt! - admin panel uses werkzeug.security for verification)
- Handles both SQLite and PostgreSQL via `DATABASE_URL` env var from `.env` file
- **NEVER hardcode connection strings** - use `env_config.py` centralized configuration
- Run with: `python sqlalchemy_db_init.py`
- **Schema updates**: `db.create_all()` won't add columns to existing tables - use ALTER TABLE or drop/recreate for schema changes

**⚠️ DATA PRESERVATION - CRITICAL:**
- **NEVER use `db.drop_all()` without explicit user permission** - this destroys ALL data
- **NEVER drop tables in production** unless explicitly instructed
- For schema changes: Use `ALTER TABLE ADD COLUMN` to add fields (preserves existing data)
- For complex migrations: Use Alembic or write manual migration scripts
- **Always backup database before schema changes**: `pg_dump` (PostgreSQL) or copy SQLite file
- Test schema changes on local SQLite copy first, never directly on Azure production database

**Environment Configuration:**
All configuration now managed via `.env` file and `env_config.py`:
```python
from env_config import get_database_url, get_secret_key, Config

# Get database URL (validates PostgreSQL/SQLite format)
db_url = get_database_url()

# Get validated secret key (ensures 32+ chars, not default value)
secret = get_secret_key('FLASK_SECRET_KEY')

# Or use Config singleton for all settings
config = Config()
db_url = config.DATABASE_URL
api_url = config.API_BASE_URL
```

**Azure PostgreSQL connection string format (in .env file):**
```
DATABASE_URL=postgresql://rfpoadmin:PASSWORD@rfpo-db-{unique}.postgres.database.azure.com:5432/rfpodb?sslmode=require
```

## Application Structure

### User App (app.py)
- **NO direct database access** - all operations via API requests to `API_BASE_URL`
- Uses `make_api_request()` helper for authenticated API calls
- Session stores `auth_token` for JWT authentication
- First-time login detection: checks if `last_visit == created_at`

### Admin Panel (custom_admin.py)
- **Direct database access** via SQLAlchemy models
- Custom UI without Flask-Admin (avoid WTForms compatibility issues)
- Flask-Login for session management
- All routes require `@login_required` decorator
- File uploads stored in `uploads/logos/` and `uploads/terms/`
- PDF generation via `RFPOPDFGenerator` (pdf_generator.py)

### API Layer (api/api_server.py)
- Blueprints: `auth_routes`, `team_routes`, `rfpo_routes`, `user_routes`
- Database path: `instance/rfpo_admin.db` (configurable via `DATABASE_URL`)
- CORS enabled for all origins (configure for production)
- Health check at `/api/health`

## Docker & Deployment

### Local Development (docker-compose.yml)
```bash
docker-compose up -d              # Start all services
docker-compose up --build -d      # Rebuild after changes
docker-compose logs -f rfpo-admin # Follow specific service logs
```

**Shared volumes:**
- `./instance:/app/instance` - SQLite database
- `./uploads:/app/uploads` - User-uploaded files
- `./static:/app/static` - Static assets

### Azure Deployment

**CRITICAL: This app runs in Azure, not locally!**
- **Production deployment** is ALWAYS to Azure Container Apps
- **Docker images MUST be built for linux/amd64** (Azure platform), NOT arm64 (Mac)
- **Use `./redeploy-phase1.sh`** for one-command deployment - automatically builds with correct platform
- **Never push Mac-built images** to Azure - they won't work!

**Correct build command for Azure:**
```bash
# Always specify --platform linux/amd64 when building for Azure
docker build --platform linux/amd64 -f Dockerfile.api -t acrrfpoe108977f.azurecr.io/rfpo-api:latest .
```

**Resources defined in azure/main.bicep:**
- Container Apps Environment with 3 apps (api, admin, user)
- Azure Container Registry (ACR)
- PostgreSQL Flexible Server
- Storage Account with File Share
- Log Analytics Workspace

**Quick deployment to Azure:**
```bash
./redeploy-phase1.sh  # Builds for linux/amd64, pushes to ACR, updates Container Apps
```

**Deployment workflow:**
1. `./redeploy-phase1.sh` - One-command deployment (builds for linux/amd64, pushes, updates)
2. Alternative: `cd azure && ./setup-acr.sh` then `./deploy-to-azure.sh`
3. Run `sqlalchemy_db_init.py` with Azure DATABASE_URL to initialize DB

**CI/CD:** `.github/workflows/deploy-azure.yml` automates build, push, and deployment on push to main.

**Azure specifics:**
- Subscription ID: `e108977f-44ed-4400-9580-f7a0bc1d3630`
- Resource Group: `rg-rfpo-e108977f`
- Location: `East US`
- ACR: `acrrfpoe108977f.azurecr.io`
- **Container platform: linux/amd64** (NOT arm64/Mac)
- Always use `sslmode=require` for PostgreSQL connections

## Critical Patterns

### Permission System
Users have multi-layer permissions:
- **System permissions** (JSON array): `GOD`, `RFPO_ADMIN`, `RFPO_USER`, `VROOM_ADMIN`, `CAL_MEET_USER`
- **Team-level access**: via `UserTeam` + Team's `viewer_user_ids`/`admin_user_ids` JSON arrays
- **Consortium-level access**: via Consortium's `rfpo_viewer_user_ids`/`rfpo_admin_user_ids` JSON arrays
- Use `user.has_permission('GOD')` to check system permissions
- Use `user.get_teams()` to get accessible teams

### RFPO Workflow
1. Created via Admin Panel with line items
2. Calculates totals: `rfpo.update_totals()` (includes cost sharing)
3. Approval workflow: `RFPOApprovalWorkflow` → `RFPOApprovalStage` → `RFPOApprovalStep` → `RFPOApprovalInstance`
4. PDF generation: `RFPOPDFGenerator` overlays data on template PDFs from `static/po_files/`
5. Uses `PDFPositioning` model for field coordinates

### File Uploads
- Generate UUID: `file_id = str(uuid.uuid4())`
- Store as: `{uuid}_{secure_filename(original)}`
- Track in `UploadedFile` model with RFPO association
- RAG processing: extract text → create `DocumentChunk` records with embeddings

## Common Tasks

### Add new database model:
1. Define in `models.py` with `db.Model`, `to_dict()`, relationships
2. Add import to `sqlalchemy_db_init.py` (critical!)
3. **Test locally first**: Use local SQLite to verify model works
4. Rebuild containers: `docker-compose up --build -d`
5. For Azure: **NEVER drop tables** - use `db.create_all()` which only creates missing tables (safe)
6. **Alternative for Azure**: Write ALTER TABLE statements to add new tables manually

### Add column to existing model:
**⚠️ NEVER drop and recreate tables - this loses all data!**
1. Add field to model in `models.py`
2. **Local SQLite**: Use ALTER TABLE or recreate (local data is disposable)
3. **Azure PostgreSQL**: Write migration script:
   ```sql
   ALTER TABLE table_name ADD COLUMN new_column_name column_type;
   ```
4. Connect to Azure PostgreSQL and run ALTER TABLE manually
5. Document the change in a migration file for tracking

### Add API endpoint:
1. Create route in appropriate blueprint (`api/*_routes.py`)
2. Use `@jwt_required()` decorator for protected routes
3. Return `jsonify({'success': bool, 'data': ...})`
4. Update User App's `make_api_request()` calls as needed

### Add admin feature:
1. Create route in `custom_admin.py` with `@login_required`
2. Add template in `templates/admin/`
3. Update navigation in admin base template
4. Direct database operations via SQLAlchemy models

## Troubleshooting

**Environment configuration:**
- Create `.env` file from `.env.example` template
- All scripts now use `env_config.py` - no hardcoded credentials
- Use `validate_configuration()` to check all required values are set
- Secret keys must be 32+ characters and not default values
- Database URL must start with `postgresql://` or `sqlite://`

**Database issues:**
- Always use `get_database_url()` from `env_config` instead of hardcoding
- Verify all 18 models imported in init scripts
- For Azure: ensure `sslmode=require` in connection string
- Check `docker-compose logs` for SQLAlchemy errors
- **Schema mismatches**: `db.create_all()` won't add columns to existing tables - use ALTER TABLE (NEVER drop tables!)
- **Password hashing**: MUST use `werkzeug.security.generate_password_hash` (NOT bcrypt!) to match login verification
- **Data preservation**: Backup before any schema changes, test on local copy first

**API connection failures:**
- Verify `API_BASE_URL` env var in User App
- Check service health: 
  - Local: `curl http://localhost:5002/api/health`
  - Azure: `curl https://rfpo-api.livelyforest-d06a98a0.eastus.azurecontainerapps.io/api/health`
- Inspect JWT token in session storage
- Review CORS configuration for production

**PDF generation issues:**
- Verify template PDFs exist in `static/po_files/{consortium_abbrev}/`
- Check `PDFPositioning` record exists for consortium
- Ensure reportlab and PyPDF2 installed
- Review positioning coordinates in database

## Error Handling

**Custom exception hierarchy** (exceptions.py):
All applications use structured exceptions with proper HTTP status codes:
```python
from exceptions import (
    AuthenticationException,  # 401 - Invalid credentials, expired tokens
    AuthorizationException,   # 403 - Insufficient permissions
    ValidationException,      # 400 - Invalid input data
    ResourceNotFoundException, # 404 - RFPO, user, team not found
    DatabaseException,        # 500 - DB connection, query errors
    ConfigurationException,   # 500 - Missing/invalid env vars
    FileProcessingException,  # 400 - Upload failures, invalid format
    ExternalServiceException, # 503 - Email, external API failures
    BusinessLogicException    # 422 - Budget exceeded, workflow violations
)

# Raise with context
raise ValidationException(
    "Invalid email format",
    payload={'field': 'email', 'value': email}
)
```

**Structured logging** (logging_config.py):
```python
from logging_config import get_logger, log_exception, log_api_request

logger = get_logger('app_name')

# Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
logger.info("User logged in successfully")
logger.warning("Failed login attempt")
logger.error("Database connection failed")

# Log exceptions with context
try:
    process_rfpo(rfpo_id)
except Exception as e:
    log_exception(logger, e, {'rfpo_id': rfpo_id, 'user_id': user.id})

# Log API requests
log_api_request(logger, 'POST', '/api/rfpo', user_id=user.id, status_code=201)
```

**Flask error handlers** (error_handlers.py):
All Flask apps auto-register error handlers:
```python
from error_handlers import register_error_handlers

app = Flask(__name__)
register_error_handlers(app, 'app_name')  # Done! All errors now handled
```

## Testing

**Admin login credentials:**
- Email: `admin@rfpo.com`
- Password: `admin123`

**Local environment (docker-compose):**
- Admin: `http://localhost:5111/login`
- User App: `http://localhost:5000`
- API: `http://localhost:5002/api/health`

**Azure environment (production):**
- Admin: `https://rfpo-admin.livelyforest-d06a98a0.eastus.azurecontainerapps.io/login`
- User App: `https://rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io`
- API: `https://rfpo-api.livelyforest-d06a98a0.eastus.azurecontainerapps.io/api/health`

**Database inspection:**
```bash
# Local SQLite
sqlite3 instance/rfpo_admin.db ".tables"

# Azure PostgreSQL (from psql or script)
psql "postgresql://rfpoadmin:...@rfpo-db-*.postgres.database.azure.com:5432/rfpodb?sslmode=require"
```
