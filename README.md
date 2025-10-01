# RFPO Application

Containerized Request for Purchase Order (RFPO) management system with separated user and admin interfaces.

## 🏗️ Architecture

The RFPO application consists of three containerized services:

```
┌─────────────────────────────────────────────────────────┐
│                    RFPO Application                     │
├─────────────────┬─────────────────┬─────────────────────┤
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

- **Docker & Docker Compose**
- **Git** for cloning

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
   - **User Application**: http://localhost:5000
   - **Admin Panel**: http://localhost:5111
   - **API Documentation**: http://localhost:5002/api

## 🔐 Default Login

### Admin Panel (http://localhost:5111)
- **Email**: `admin@rfpo.com`
- **Password**: `admin123`

### User App (http://localhost:5000)
- **Create users** in the admin panel first
- **Users receive welcome emails** with login instructions
- **First-time login** requires password change

## 📋 Core Features

### Admin Panel (Port 5111)
- **User Management**: Create, edit, delete users with role-based permissions
- **Team Management**: Organize users into teams and consortiums
- **RFPO Management**: Full RFPO lifecycle management
- **Vendor Management**: Maintain vendor database
- **Project Management**: Track projects and assignments
- **Approval Workflows**: Configure multi-stage approval processes
- **Email Service**: Automated welcome emails and notifications

### User Application (Port 5000)
- **Modern Bootstrap UI**: Responsive, mobile-friendly interface
- **Dashboard**: Overview of RFPOs, teams, and quick actions
- **RFPO Views**: Create, view, and manage RFPOs
- **Team Views**: Browse and request team access
- **Profile Management**: Update personal information and password
- **First-Time Login Flow**: Guided password change and profile setup

### API Layer (Port 5002)
- **RESTful API**: JSON-based communication
- **JWT Authentication**: Secure token-based auth
- **CRUD Operations**: Full database operations
- **Health Monitoring**: Built-in health checks

## 🗄️ Database

The application uses a **single SQLite database** (`instance/rfpo_admin.db`) shared across all services:

- **Users**: User accounts with permissions and profile data
- **Teams**: Team organization and membership
- **RFPOs**: Request for Purchase Orders with line items
- **Vendors**: Vendor information and contacts
- **Projects**: Project definitions and assignments
- **Consortiums**: Consortium management
- **Approval Workflows**: Multi-stage approval configurations

## 🔧 Configuration

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
   DATABASE_URL=postgresql://username:password@server:5432/database?sslmode=require

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

```
rfpo-application/
├── app.py                  # User-facing application (Port 5000)
├── custom_admin.py         # Admin panel (Port 5111)
├── simple_api.py           # API server (Port 5002)
├── models.py               # Database models (17 SQLAlchemy models)
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
- `AuthenticationException` (401) - Invalid credentials, expired tokens
- `AuthorizationException` (403) - Insufficient permissions
- `ValidationException` (400) - Invalid input data
- `ResourceNotFoundException` (404) - Resources not found
- `DatabaseException` (500) - Database errors
- `ConfigurationException` (500) - Config/environment errors
- `FileProcessingException` (400) - File upload/processing errors
- `ExternalServiceException` (503) - External API failures
- `BusinessLogicException` (422) - Business rule violations

**Structured Logging** (`logging_config.py`):
- Rotating log files in `logs/` directory (10MB max, 5 backups)
- Configurable log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Standardized log formats with timestamps and context
- Helper functions for API requests, database operations, auth events

**Error Handlers** (`error_handlers.py`):
- Automatic registration in all Flask applications
- Returns JSON for API requests, HTML for web requests
- User-friendly error pages with Bootstrap styling
- Security-conscious (no sensitive data in error responses)

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

- **API**: http://localhost:5002/api/health
- **Admin**: http://localhost:5111/health
- **User App**: http://localhost:5000/health

### User Flow Testing

1. **Create user** in admin panel
2. **Check email** for welcome message
3. **Login to user app** with admin-set password
4. **Change password** (required on first login)
5. **Access dashboard** and features

## 🔒 Security Features

- **JWT Authentication**: Secure token-based authentication
- **Password Hashing**: Werkzeug security with salt
- **Role-Based Access**: Granular permission system
- **Input Validation**: Form validation and sanitization
- **CORS Protection**: Configurable cross-origin policies
- **Session Management**: Secure session handling

## 📧 User Permissions

- **GOD**: Super admin with full system access
- **RFPO_ADMIN**: Full RFPO management capabilities
- **RFPO_USER**: Basic RFPO access and creation
- **CAL_MEET_USER**: Meeting calendar access
- **VROOM_ADMIN**: Virtual room administration
- **VROOM_USER**: Virtual room access

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

## 🎯 Production Deployment

For production deployment:

1. **Update secrets**: Change all default passwords and keys
2. **Configure email**: Set up proper SMTP credentials
3. **Database backup**: Implement regular backups of `rfpo_admin.db`
4. **Reverse proxy**: Use nginx or similar for SSL termination
5. **Monitoring**: Set up log aggregation and monitoring

---

**RFPO Application - Modern, Scalable, Containerized Purchase Order Management** 🚀