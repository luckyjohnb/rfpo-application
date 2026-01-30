# Developer Setup Guide - RFPO Application

## 🚀 Quick Start (5 minutes)

### Prerequisites
- **Docker Desktop** installed and running
- **Git** installed
- **Code editor** (VS Code recommended)

### Step 1: Clone Repository

```bash
git clone https://github.com/luckyjohnb/rfpo-application.git
cd rfpo-application
```

### Step 2: Choose Your Branch

```bash
# For latest features (recommended for development):
git checkout JanuaryFixes

# OR for stable base:
git checkout main
```

### Step 3: Configure Environment

```bash
# Copy the example environment file
cp .env.example .env
```

**Edit `.env` file** - Use these values for local development:

```bash
# Database (SQLite for local dev - no setup needed!)
DATABASE_URL=sqlite:///instance/rfpo_admin.db

# Secret Keys (generate your own or use these for dev)
FLASK_SECRET_KEY=dev-secret-key-change-in-production-32chars-minimum
JWT_SECRET_KEY=dev-jwt-secret-change-in-production-32chars-minimum

# API Configuration
API_BASE_URL=http://localhost:5002

# Email (optional for local dev - can be left empty)
GMAIL_USER=
GMAIL_APP_PASSWORD=

# Azure Communication Email (optional)
AZURE_COMMUNICATION_CONNECTION_STRING=
```

### Step 4: Start Everything

```bash
# Start all services (builds automatically on first run)
docker-compose up -d

# Wait 30 seconds for containers to start, then check status
docker-compose ps
```

You should see 3 services running:
- ✅ `rfpo-admin` (healthy)
- ✅ `rfpo-api` (healthy)  
- ✅ `rfpo-user` (healthy)

### Step 5: Access the Applications

Open in your browser:

- **Admin Panel**: http://localhost:5111
- **User App**: http://localhost:5000
- **API Health**: http://localhost:5002/api/health

**Default Login:**
- Email: `admin@rfpo.com`
- Password: `2026$Covid`

---

## 📂 Project Structure

```
rfpo-application/
├── app.py                    # User-facing application
├── custom_admin.py           # Admin panel application
├── models.py                 # SQLAlchemy database models (18 models)
├── api/                      # API layer
│   ├── api_server.py         # Main API server
│   ├── auth_routes.py        # Authentication endpoints
│   ├── team_routes.py        # Team management
│   ├── rfpo_routes.py        # RFPO operations
│   └── user_routes.py        # User management
├── templates/                # Jinja2 templates
│   ├── admin/                # Admin panel templates
│   └── app/                  # User app templates
├── static/                   # CSS, JS, images
├── docker-compose.yml        # Local dev orchestration
├── Dockerfile.admin          # Admin panel container
├── Dockerfile.api            # API container
├── Dockerfile.user-app       # User app container
├── requirements.txt          # Python dependencies
└── .env                      # Environment configuration (you create this)
```

---

## 🛠️ Common Development Tasks

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f rfpo-admin
docker-compose logs -f rfpo-api
docker-compose logs -f rfpo-user
```

### Restart After Code Changes

```bash
# Rebuild and restart all services
docker-compose up -d --build

# Or restart specific service
docker-compose restart rfpo-admin
```

### Stop Everything

```bash
docker-compose down
```

### Access Database

```bash
# SQLite database is at:
./instance/rfpo_admin.db

# Access with sqlite3 CLI:
sqlite3 instance/rfpo_admin.db

# Or use a GUI tool like DB Browser for SQLite
```

### Run Tests

```bash
# If tests are available
docker-compose exec rfpo-api pytest

# Or run locally
python -m pytest tests/
```

---

## 🗄️ Database Models (Important!)

The application uses **18 SQLAlchemy models**. Key ones:

- **User** - User accounts with permissions (GOD, RFPO_ADMIN, etc.)
- **Consortium** - Organizations 
- **Team** - Teams within consortiums
- **RFPO** - Request for Purchase Order (main entity)
- **RFPOLineItem** - Line items within RFPOs
- **RFPOApprovalWorkflow** - Approval process definitions
- **RFPOApprovalInstance** - Active approval processes
- **Vendor**, **VendorSite** - Vendor information
- **UploadedFile**, **DocumentChunk** - File storage and RAG

**All models imported in `models.py`** - when making DB changes, always import ALL models.

---

## 🔐 Authentication & Authorization

### System Permissions (in User model)
- `GOD` - Full system access
- `RFPO_ADMIN` - RFPO administration
- `RFPO_USER` - Basic RFPO access
- `VROOM_ADMIN` - Vehicle room management
- `CAL_MEET_USER` - Calendar access

### API Authentication
- Uses JWT tokens
- Admin panel uses Flask-Login sessions
- User app calls API via `make_api_request()` helper

---

## 🎨 Frontend Stack

- **Flask** - Python web framework
- **Jinja2** - Template engine
- **Bootstrap 5** - CSS framework
- **jQuery** - JavaScript (some components)
- **Custom filters** - `|currency` for formatting prices

---

## 📋 Environment Variables Reference

| Variable | Required | Local Dev Value | Description |
|----------|----------|-----------------|-------------|
| `DATABASE_URL` | ✅ | `sqlite:///instance/rfpo_admin.db` | Database connection |
| `FLASK_SECRET_KEY` | ✅ | `dev-secret-key...` | Flask session encryption |
| `JWT_SECRET_KEY` | ✅ | `dev-jwt-secret...` | JWT token signing |
| `API_BASE_URL` | ✅ | `http://localhost:5002` | API endpoint for user app |
| `GMAIL_USER` | ❌ | (empty for local) | Email notifications |
| `GMAIL_APP_PASSWORD` | ❌ | (empty for local) | Gmail app password |
| `AZURE_COMMUNICATION_CONNECTION_STRING` | ❌ | (empty) | Azure email service |

---

## 🐳 Docker Configuration

### Services & Ports

| Service | Port | Health Check | Description |
|---------|------|--------------|-------------|
| `rfpo-admin` | 5111 | `/health` | Admin panel |
| `rfpo-api` | 5002 | `/api/health` | REST API |
| `rfpo-user` | 5000 | `/health` | User application |

### Shared Volumes
- `./instance` - SQLite database (persisted)
- `./uploads` - File uploads (persisted)
- `./static` - Static files

---

## 🚨 Troubleshooting

### Port Already in Use

```bash
# Find process using port
lsof -i :5111

# Kill the process
kill -9 <PID>

# Or change ports in docker-compose.yml
```

### Container Won't Start

```bash
# Check logs
docker-compose logs rfpo-admin

# Remove containers and rebuild
docker-compose down
docker-compose up -d --build
```

### Database Issues

```bash
# Reset database (WARNING: Deletes all data!)
rm instance/rfpo_admin.db

# Restart containers to recreate
docker-compose restart
```

### Permission Errors

```bash
# Fix file permissions
chmod -R 755 instance/ uploads/ static/

# Or run with sudo (not recommended)
sudo docker-compose up -d
```

---

## 📚 Additional Resources

- **Main README**: [README.md](./README.md) - Complete documentation
- **Changelog**: [CHANGELOG_2026.md](./CHANGELOG_2026.md) - Release notes
- **Deployment**: [DEPLOYMENT_SUMMARY.md](./DEPLOYMENT_SUMMARY.md) - Azure deployment
- **Azure Guide**: [azure/README.md](./azure/README.md) - Cloud deployment
- **AI Instructions**: [.github/copilot-instructions.md](./.github/copilot-instructions.md) - Architecture details

---

## 🎯 What's New in JanuaryFixes Branch

If you checked out the `JanuaryFixes` branch, you get these improvements:

- 💰 **Currency Formatting** - All prices display with commas ($1,234,567.89)
- 🐛 **Form Validation Fix** - Fixed field selector bug in modal forms
- 🙈 **Hidden Generate PO** - Button now hidden until approval criteria met
- 🔐 **Security Update** - Enhanced admin password

---

## ✅ Verification Checklist

After setup, verify:

- [ ] All 3 Docker containers running and healthy
- [ ] Admin panel accessible at http://localhost:5111
- [ ] Can login with `admin@rfpo.com` / `2026$Covid`
- [ ] User app accessible at http://localhost:5000
- [ ] API health check returns 200 at http://localhost:5002/api/health
- [ ] Database file created at `instance/rfpo_admin.db`
- [ ] No errors in `docker-compose logs`

---

## 💡 Pro Tips

1. **Use VS Code** with Docker extension for easy container management
2. **Enable file watching** if you modify templates (Flask auto-reloads)
3. **Don't commit `.env`** - it's in `.gitignore` for security
4. **Check logs frequently** when debugging with `docker-compose logs -f`
5. **Use DB Browser for SQLite** to inspect database during development

---

## 🤝 Getting Help

- **GitHub Issues**: https://github.com/luckyjohnb/rfpo-application/issues
- **Check Logs**: `docker-compose logs -f`
- **Review Docs**: See README.md for detailed architecture
- **Database Schema**: Inspect `models.py` for all tables

---

## 🎉 You're Ready!

With everything running, you can:
- Login to admin panel and explore features
- Create teams, users, and RFPOs
- Test the approval workflow
- Explore the API at `/api` endpoints
- Modify code and see changes with `docker-compose up -d --build`

**Happy coding!** 🚀
