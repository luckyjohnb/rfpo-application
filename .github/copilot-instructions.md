# RFPO Application - AI Agent Instructions

## Architecture Overview

**3-tier containerized RFPO (Request for Purchase Order) management system:**
- **User App** (Port 5000/5001): Consumer-facing interface, calls API layer only
- **Admin Panel** (Port 5111): Full CRUD operations via Flask-Login with custom admin UI
- **API Layer** (Port 5002): RESTful API with JWT auth, shared database access

**Database:** Single SQLAlchemy database (SQLite local, PostgreSQL on Azure) shared across all services.

## Database Models (models.py)

**17 SQLAlchemy models** - always import ALL models for db.create_all() to work:
```python
from models import (
    db, User, Consortium, RFPO, RFPOLineItem, UploadedFile, DocumentChunk,
    Team, UserTeam, Project, Vendor, VendorSite, PDFPositioning, List,
    RFPOApprovalWorkflow, RFPOApprovalStage, RFPOApprovalStep,
    RFPOApprovalInstance, RFPOApprovalAction
)
```

**Key patterns:**
- JSON fields stored as `db.Text` with getter/setter methods (e.g., `User.get_permissions()`, `User.set_permissions()`)
- All models have `to_dict()` methods for API serialization
- Relationships use `lazy=True` and cascade deletes where appropriate
- User has complex permission system: `permissions` JSON field contains system-level roles (GOD, RFPO_ADMIN, etc.)
- Team membership tracked via `UserTeam` junction table + JSON viewer/admin arrays on Team/Consortium

## Database Initialization

**CRITICAL:** When initializing databases (especially Azure PostgreSQL), use `sqlalchemy_db_init.py`:
- Imports all 17 models (required for table creation)
- Creates admin user with werkzeug hashed password (NOT bcrypt!)
- Handles both SQLite and PostgreSQL via `DATABASE_URL` env var from `.env` file
- **NEVER hardcode connection strings** - use `env_config.py` centralized configuration
- Run with: `python sqlalchemy_db_init.py`

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

**Resources defined in azure/main.bicep:**
- Container Apps Environment with 3 apps (api, admin, user)
- Azure Container Registry (ACR)
- PostgreSQL Flexible Server
- Storage Account with File Share
- Log Analytics Workspace

**Deployment workflow:**
1. `cd azure && ./setup-acr.sh` - Create ACR, build & push images
2. `./deploy-to-azure.sh` - Deploy infrastructure via Bicep
3. Run `sqlalchemy_db_init.py` with Azure DATABASE_URL to initialize DB

**CI/CD:** `.github/workflows/deploy-azure.yml` automates build, push, and deployment on push to main.

**Azure specifics:**
- Subscription ID: `e108977f-44ed-4400-9580-f7a0bc1d3630`
- Resource Group: `rg-rfpo-e108977f`
- Location: `East US`
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
3. Rebuild containers: `docker-compose up --build -d`
4. For Azure: re-run `sqlalchemy_db_init.py` with PostgreSQL URL

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
- Verify all 17 models imported in init scripts
- For Azure: ensure `sslmode=require` in connection string
- Check `docker-compose logs` for SQLAlchemy errors
- **Schema mismatches**: `db.create_all()` won't add columns to existing tables - use ALTER TABLE or drop/recreate
- **Password hashing**: MUST use `werkzeug.security.generate_password_hash` (NOT bcrypt!) to match login verification

**API connection failures:**
- Verify `API_BASE_URL` env var in User App
- Check service health: `curl http://localhost:5002/api/health`
- Inspect JWT token in session storage
- Review CORS configuration for production

**PDF generation issues:**
- Verify template PDFs exist in `static/po_files/{consortium_abbrev}/`
- Check `PDFPositioning` record exists for consortium
- Ensure reportlab and PyPDF2 installed
- Review positioning coordinates in database

## Testing

**Admin login (localhost:5111):**
- Email: `admin@rfpo.com`
- Password: `admin123`

**Database inspection:**
```bash
# Local SQLite
sqlite3 instance/rfpo_admin.db ".tables"

# Azure PostgreSQL (from psql or script)
psql "postgresql://rfpoadmin:...@rfpo-db-*.postgres.database.azure.com:5432/rfpodb?sslmode=require"
```

**Health checks:**
- API: `http://localhost:5002/api/health`
- Admin: `http://localhost:5111/health`
- User: `http://localhost:5000/health`
