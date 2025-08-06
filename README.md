# Flask User Management Application

A comprehensive Flask-based web application with advanced user management, role-based access control (RBAC), file processing, and secure authentication features.

## 🚀 Features

### Core Features
- **Advanced User Management**: Complete CRUD operations with role-based permissions
- **Secure Authentication**: JWT-based authentication with bcrypt password hashing
- **Role-Based Access Control**: Four user roles (Administrator, Manager, User, Inactive)
- **File Upload & Processing**: Support for CSV/Excel files with pandas integration
- **Account Security**: Password policies, account lockout, audit logging
- **Multi-Environment Support**: Development, production, and testing configurations

### Security Features
- Strong password requirements (uppercase, lowercase, numbers, special characters)
- Account lockout after multiple failed login attempts
- JWT token-based authentication with expiration
- Comprehensive audit logging
- Environment-based configuration management
- CSRF protection and secure headers

### Administrative Features
- User management dashboard
- Audit log viewing
- Account unlock capabilities
- Role assignment and management
- System health monitoring

## 📋 Requirements

- Python 3.8+
- Flask 2.3.3
- bcrypt for password hashing
- PyJWT for token authentication
- Optional: pandas for file processing
- Optional: ReportLab for PDF generation

## 🛠️ Installation & Setup

### 1. Clone and Navigate
```bash
cd "Example 1/simple-webpage"
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
```bash
# Copy environment template
copy .env.example .env

# Edit .env file with your configurations
# Update SECRET_KEY, database settings, etc.
```

### 4. Initialize Admin User
```bash
python init_admin.py
```

### 5. Run Application
```bash
# Development mode
python app.py

# Production mode (Windows)
setup_production.bat
```

## 🎯 Usage

### Access Points
- **Landing Page**: http://localhost:5000
- **Main Application**: http://localhost:5000/app
- **Admin Dashboard**: http://localhost:5000/admin (admin users only)

### Default Credentials
After running `init_admin.py`:
- **Username**: admin
- **Password**: Admin123!

### API Endpoints

#### Authentication
- `POST /api/auth/login` - User login
- `POST /api/auth/logout` - User logout
- `POST /api/auth/register` - User registration (if enabled)

#### User Management
- `GET /api/users` - List users (admin/manager only)
- `POST /api/users` - Create user (admin/manager only)
- `PUT /api/users/<id>` - Update user (admin/manager only)
- `DELETE /api/users/<id>` - Delete user (admin only)

#### File Processing
- `POST /upload` - Upload and process files
- `GET /files` - List uploaded files

## 🔧 Development Tools

### Development Utilities
```bash
# Create sample users for testing
python dev_utils.py create-samples

# List all users
python dev_utils.py list-users

# Reset user password
python dev_utils.py reset-password username newpassword

# Unlock user account
python dev_utils.py unlock-account username

# System health check
python dev_utils.py health-check

# Clean up old data
python dev_utils.py cleanup
```

### Testing
```bash
# Run comprehensive test suite
python test_suite.py

# Run specific test categories
python -m unittest test_suite.TestUserManagement
python -m unittest test_suite.TestSecurity
python -m unittest test_suite.TestFlaskApp
```

### Environment Check
```bash
# Check Python environment
check_env.bat

# Verify all dependencies
python -c "import flask, bcrypt, jwt; print('All dependencies OK')"
```

## 📁 Project Structure

```
simple-webpage/
├── app.py                    # Main Flask application
├── user_management.py        # User management system
├── config.py                # Configuration management
├── init_admin.py            # Admin user initialization
├── dev_utils.py             # Development utilities
├── test_suite.py            # Comprehensive test suite
├── requirements.txt          # Python dependencies
├── .env.example             # Environment template
├── .gitignore               # Git ignore rules
├── README.md                # Documentation
├── CHANGELOG.md             # Version history
├── CHAT_SYSTEM_DOCUMENTATION.md # Chat system docs
├── config/
│   └── users.json           # User data storage
├── static/
│   └── main.js              # Frontend JavaScript
├── templates/
│   ├── index.html           # Main application UI
│   └── landing.html         # Landing page
└── uploads/                 # File upload directory
```

## ⚙️ Configuration

### Environment Variables (.env)
```bash
# Application Settings
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
DEBUG=True

# Security Settings
JWT_EXPIRATION_HOURS=24
MAX_LOGIN_ATTEMPTS=5
ACCOUNT_LOCKOUT_MINUTES=30

# Upload Settings
MAX_FILE_SIZE_MB=10
ALLOWED_EXTENSIONS=txt,csv,xlsx,pdf

# Optional: Database Configuration
DATABASE_URL=sqlite:///app.db
```

### User Roles & Permissions

| Role | Permissions |
|------|------------|
| **Administrator** | Full system access, user management, system configuration |
| **Manager** | User management (except admins), data access, reporting |
| **User** | Basic application access, file upload, personal data |
| **Inactive** | No system access (disabled accounts) |

## 🛡️ Security Considerations

### Password Policy
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character

### Account Security
- Maximum 5 failed login attempts
- 30-minute account lockout
- JWT token expiration
- Comprehensive audit logging

### File Upload Security
- File type validation
- Size limitations
- Secure file storage
- Malware scanning (configurable)

## 🐛 Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Ensure you're in the correct directory
   cd "Example 1/simple-webpage"
   python -c "import app; print('OK')"
   ```

2. **Permission Errors**
   ```bash
   # Check file permissions
   python dev_utils.py health-check
   ```

3. **Database Issues**
   ```bash
   # Reset user data (CAUTION: This deletes all users)
   del config\users.json
   python init_admin.py
   ```

4. **Dependencies Missing**
   ```bash
   pip install -r requirements.txt --upgrade
   ```

### Log Files
- Application logs: Console output
- Audit logs: Stored in user data
- Error logs: Flask development server

## 📚 Documentation

- **API Documentation**: Available at `/api/docs` (when running)
- **Chat System**: See `CHAT_SYSTEM_DOCUMENTATION.md`
- **Change Log**: See `CHANGELOG.md`
- **Development Guide**: See inline code comments

## 🤝 Contributing

1. Run tests before submitting changes
2. Follow PEP 8 style guidelines
3. Update documentation for new features
4. Add tests for new functionality

## 📄 License

This project is for educational and development purposes. Please ensure compliance with your organization's security policies before production deployment.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Run `python dev_utils.py health-check`
3. Review application logs
4. Consult the comprehensive test suite for examples
