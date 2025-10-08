# RFPO Application - Admin Setup Guide

This guide will help you get the RFPO application running with proper database and admin user setup.

## 🚀 Quick Setup (3 Steps)

If you already have the application running but need to set up the database and admin user:

### Step 1: Initialize the Database
```bash
python init_db.py
```

### Step 2: Create Admin User
```bash
python create_admin_user.py
```

### Step 3: Start the Admin Panel
```bash
python custom_admin.py
```

Then visit: http://127.0.0.1:5111/

**Admin Login Credentials:**
- Email: `admin@rfpo.com`
- Password: `admin123`

---

## 📋 Complete Setup Guide

### Prerequisites
- Python 3.8+
- pip (Python package manager)
- The application files (already provided)

### 1. Environment Setup

Create a virtual environment (recommended):
```bash
# Create virtual environment
python -m venv venv

# Activate it (Windows)
venv\Scripts\activate

# Activate it (Mac/Linux)
source venv/bin/activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 2. Database Configuration

The application uses SQLite databases. There are three main database files:

- `instance/app.db` - Main application database (created by main app)
- `instance/rfpo_admin.db` - Admin panel database (created by custom_admin.py)  
- `instance/rfpo.db` - Additional RFPO data (created automatically)

Initialize the main database:
```bash
python init_db.py
```

This will create all necessary database tables including:
- Teams
- Users (SQLAlchemy models with Flask-Login)
- Consortiums
- Projects
- Vendors
- RFPOs
- Line Items
- Uploaded Files
- Document Chunks

### 3. Admin User Setup

Create the admin user for the custom admin panel:

```bash
python create_admin_user.py
```

This script will:
- Create the `rfpo_admin.db` database with all necessary tables
- Create an admin user with the credentials below
- Verify the user can authenticate properly

**Admin Credentials:**
- **Email**: admin@rfpo.com
- **Password**: admin123

The user data is stored in the SQLite database (`rfpo_admin.db`) using SQLAlchemy User models with proper password hashing.

### 4. Running the Applications

There are two main ways to access the admin interface:

#### Option A: Custom Admin Panel (Recommended)
```bash
python custom_admin.py
```
- Visit: http://127.0.0.1:5111/
- Full CRUD interface for all models
- Login with: admin@rfpo.com / admin123
- **Note**: Runs on port 5111 (not 5000)

#### Option B: Main Application
```bash
python app.py
```
- Visit: http://127.0.0.1:5000
- Full application with frontend
- API endpoints available
- **Note**: Runs on port 5000

### 5. Verification

After setup, verify everything works:

1. **Database Check**:
   ```bash
   python check_team_db.py
   ```

2. **Admin Login Test**:
   - Go to http://127.0.0.1:5111/
   - Login with admin@rfpo.com / admin123
   - You should see the admin dashboard with statistics

3. **API Test** (if running main app):
   - Go to http://127.0.0.1:5000/hello
   - Should return: `{"message": "Hello from Flask!", "status": "success"}`

---

## 🔧 Application Architecture

### Database Files
- **instance/app.db**: Main SQLAlchemy database with all models (used by app.py)
- **rfpo_admin.db**: Admin panel database (used by custom_admin.py - same schema as app.db, located in project root)
- **instance/rfpo.db**: Additional RFPO data storage

### User Management
The custom admin panel uses SQLAlchemy User models with Flask-Login for authentication. The admin user is created by running the `create_admin_user.py` script.

### Key Files
- `app.py` - Main Flask application
- `custom_admin.py` - Admin panel application  
- `models.py` - Database models
- `create_admin_user.py` - Create admin user for custom admin panel
- `init_db.py` - Database initialization for main app
- `user_management.py` - JSON-based user system (used by main app)

---

## 🐛 Troubleshooting

### Common Issues

#### 1. "Module not found" errors
```bash
# Make sure you're in the project directory
cd /path/to/rfpo-application

# Activate virtual environment
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt
```

#### 2. "Database doesn't exist" errors
```bash
# Initialize the main database
python init_db.py

# Create admin user and admin database
python create_admin_user.py
```

#### 3. "Admin user not found" errors
If you can't login to the admin panel:
- Make sure you've created the admin user: `python create_admin_user.py`
- Use the correct URL: http://127.0.0.1:5111/
- Use the correct credentials: admin@rfpo.com / admin123
- Check that the `rfpo_admin.db` file exists in the project root

#### 4. "Permission denied" errors
```bash
# Check if you're in the right directory
ls -la  # Should see app.py, models.py, etc.

# Make sure config directory exists
mkdir config
```

#### 5. Port already in use
If port 5000 is in use, the applications will show an error. Either:
- Stop other applications using port 5000
- Or modify the port in the application files

#### 6. Empty admin dashboard
If you see an empty admin dashboard:
1. Make sure `init_db.py` was run successfully
2. Check that database files exist in `instance/` directory
3. Try creating some test data through the admin interface
4. The dashboard shows counts of various entities - it's normal to see zeros initially

### Reset Everything
If you need to start fresh:
```bash
# Remove databases
rm instance/*.db
rm rfpo_admin.db

# Reinitialize
python init_db.py
python create_admin_user.py

# Restart admin panel
python custom_admin.py
```

---

## 📊 Default Data

After setup, you'll have:

### Admin User
- Email: admin@rfpo.com
- Password: admin123
- Access: Full administrative privileges

### Database Tables
- All models from `models.py` will be created
- Tables will be empty initially
- You can add data through the admin panel

---

## 🔐 Security Notes

### Default Passwords
The default admin password is `admin123`. For production:
1. Change this password immediately through the admin interface
2. The password is stored in the SQLite database with proper hashing
3. You can update user information through the Users section in the admin panel

### Database Security
- SQLite databases are stored in `instance/` directory
- This directory should be secured in production
- Consider backing up the databases regularly

### User Management
- User data is stored in the SQLite database (`rfpo_admin.db`)
- Passwords are properly hashed using Werkzeug security
- User management is available through the admin panel interface
- Admin user is created using the `create_admin_user.py` script

---

## 📞 Support

If you encounter issues:

1. Check this README first
2. Look at the application logs
3. Verify all files are present
4. Check that Python dependencies are installed
5. Try the "Reset Everything" steps above

The application includes comprehensive error messages and logging to help diagnose issues.

---

## 🚀 Next Steps

After successful setup:

1. **Explore the Admin Panel**: Add consortiums, teams, projects, vendors
2. **Test RFPO Creation**: Create sample RFPOs through the interface
3. **Upload Files**: Test file upload and processing
4. **API Testing**: Use the REST API endpoints
5. **Customize**: Modify the application for your specific needs

Remember to backup your databases regularly!

## 🎯 Key Features of the Admin Panel

The custom admin panel provides:

- **Dashboard**: Overview statistics and recent activity
- **Consortiums**: Manage research consortiums and their settings
- **Teams**: Manage research teams and their permissions
- **Projects**: Manage research projects and their associations
- **Vendors**: Manage vendor companies and their contact information
- **RFPOs**: Create and manage Request for Purchase Orders
- **Users**: Manage user accounts and permissions
   - Company Code ↔ Company Name auto-fill: Selecting a Company Code will auto-populate the Company Name from the option label (text to the right of the closing bracket). Typing a Company Name that matches a known option will auto-select the corresponding Company Code. Extra spaces and common separators (dashes, pipes, bullets, colons) are trimmed automatically. Live syncing uses a small debounce to avoid jitter while typing.
- **Lists**: Configuration management for dropdowns and settings
- **PDF Positioning**: Visual editor for PDF template positioning

The admin panel runs independently on port 5111 and provides a complete interface for managing all aspects of the RFPO system.
