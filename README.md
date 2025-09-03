# RFPO Application

A modern, containerized Request for Purchase Order (RFPO) management system with separated user and admin interfaces.

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
   git clone <repository-url>
   cd rfpo-application
   ```

2. **Configure environment:**
   ```bash
   cp env.example .env
   # Edit .env file with your email/SMTP settings
   ```

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

### Environment Variables (.env file)

```bash
# JWT Secret Key
JWT_SECRET_KEY=your-jwt-secret-key

# Email Configuration (Gmail example)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# Application URLs
APP_URL=http://localhost:5000
SUPPORT_EMAIL=support@yourcompany.com

# Database (default SQLite)
DATABASE_URL=sqlite:///instance/rfpo_admin.db
```

### Email Setup

For email functionality to work, configure SMTP settings in your `.env` file:

1. **Gmail**: Use App Passwords (not your regular password)
2. **Outlook/Office365**: Use your account credentials
3. **Custom SMTP**: Configure your mail server details

## 🛠️ Development

### Project Structure

```
rfpo-application/
├── app.py                  # User-facing application (Port 5000)
├── custom_admin.py         # Admin panel (Port 5111)
├── simple_api.py          # API server (Port 5002)
├── models.py              # Database models
├── email_service.py       # Email functionality
├── api/                   # API routes (future expansion)
├── templates/
│   ├── admin/            # Admin panel templates
│   └── app/              # User app templates
├── static/               # CSS, JS, images
├── instance/             # Database files
├── uploads/              # File uploads
├── Dockerfile.api        # API service container
├── Dockerfile.admin      # Admin panel container  
├── Dockerfile.user-app   # User app container
└── docker-compose.yml    # Container orchestration
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