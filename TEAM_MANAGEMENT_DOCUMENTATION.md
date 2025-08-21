# Team Management System Documentation

## Overview
The Team Management System is a comprehensive feature within the RFPO (Request for Proposal Operations) application that allows users to create, manage, and organize teams within consortiums.

## Features Implemented

### 🗄️ Database Model
- **Team Model** (`models.py`):
  - Primary key: `id`
  - Team identification: `name`, `abbrev`, `consortium_id`
  - User management: `viewer_user_ids`, `limited_admin_user_ids`
  - Status: `active` (boolean)
  - Metadata: `description`, `created_at`, `updated_at`, `created_by`, `updated_by`
  - Unique constraints: team name and abbreviation per consortium

### 🔗 API Endpoints
All endpoints implemented in `app.py`:

#### GET /api/teams
- Returns list of all teams
- Response: JSON array of team objects

#### POST /api/teams
- Creates a new team
- Request body: team data (name, abbrev, consortium_id, etc.)
- Response: created team object

#### GET /api/teams/<id>
- Returns specific team by ID
- Response: team object

#### PUT /api/teams/<id>
- Updates existing team
- Request body: updated team data
- Response: updated team object

#### DELETE /api/teams/<id>
- Deletes team by ID
- Response: success confirmation

#### POST /api/teams/<id>/activate
- Activates a team (sets active=true)
- Response: success confirmation

#### POST /api/teams/<id>/deactivate
- Deactivates a team (sets active=false)
- Response: success confirmation

### 🖥️ User Interface
Comprehensive Bootstrap 5 interface integrated into `templates/index.html`:

#### Navigation
- Added "Teams" tab to RFPO section navigation
- Tabbed interface: Dashboard | Teams | Projects | Reports

#### Dashboard Tab
Statistics cards showing:
- Total Teams count
- Active Teams count
- Total Members across all teams
- Number of Consortiums

#### Teams Tab
- **Teams Table**: Displays all teams with columns for:
  - ID (badge)
  - Name
  - Abbreviation (badge)
  - Consortium ID
  - Status (Active/Inactive badge)
  - Member Count (badge)
  - Created Date
  - Action buttons (Edit, View, Activate/Deactivate, Delete)

- **Create/Edit Form**: Modal-style form with fields:
  - Team Name (required)
  - Abbreviation (required)
  - Consortium ID (required)
  - Status (Active/Inactive)
  - Description (optional)
  - Viewer User IDs (comma-separated)
  - Limited Admin User IDs (comma-separated)

### ⚙️ JavaScript Functionality
Complete client-side implementation in `templates/index.html`:

#### Core Functions
- `loadTeams()` - Fetches and displays all teams
- `displayTeams(teams)` - Renders teams table
- `updateTeamStats(teams)` - Updates dashboard statistics
- `createNewTeam()` - Shows create form
- `editTeam(id)` - Loads team data and shows edit form
- `deleteTeam(id)` - Deletes team with confirmation
- `activateTeam(id)` / `deactivateTeam(id)` - Toggle team status
- `refreshTeams()` - Refreshes team list

#### Form Handling
- Dynamic form submission for create/update operations
- Proper data validation and error handling
- Success/error notifications with auto-dismiss
- Form reset and cancellation

#### User Experience
- Auto-load teams when Teams tab is activated
- Real-time statistics updates after operations
- Loading indicators and error states
- Responsive design with Bootstrap components

## Database Setup

### Initialization
1. Run `python init_db.py` to create database tables
2. Database file created at: `instance/app.db` (SQLite)

### Verification
- Use `python check_team_db.py` to verify database structure
- Use `python verify_team_functionality.py` for comprehensive testing

## Usage Instructions

### Accessing Team Management
1. Start the Flask application: `python app.py`
2. Navigate to: `http://127.0.0.1:5000`
3. Log in with admin credentials
4. Click on "RFPO Application" in the navigation menu
5. Click on the "Teams" tab

### Creating a Team
1. In the Teams tab, click "Create New Team" button
2. Fill in required fields:
   - Team Name
   - Abbreviation  
   - Consortium ID
3. Optionally add description and user assignments
4. Click "Save Team"

### Managing Teams
- **Edit**: Click edit button in team row
- **View**: Click view button for team details
- **Activate/Deactivate**: Click play/pause button
- **Delete**: Click delete button (with confirmation)
- **Refresh**: Click refresh button to reload team list

## Technical Architecture

### Backend
- **Flask 3.0.0**: Web framework
- **SQLAlchemy**: ORM for database operations
- **Flask-Migrate**: Database migration support
- **SQLite**: Database engine (configurable)

### Frontend
- **Bootstrap 5.1.3**: UI framework
- **Font Awesome**: Icons
- **Vanilla JavaScript**: Client-side functionality
- **Fetch API**: AJAX requests

### Integration
- Fully integrated with existing RFPO application
- Uses existing authentication system
- Maintains consistent design and UX patterns
- Follows RESTful API conventions

## File Structure
```
├── models.py              # Team database model
├── app.py                 # Flask app with team API endpoints
├── templates/index.html   # UI with team management interface
├── init_db.py            # Database initialization script
├── check_team_db.py      # Database verification script
├── verify_team_functionality.py  # Comprehensive test suite
└── instance/app.db       # SQLite database file
```

## Testing
- **Manual Testing**: Use web interface to test all CRUD operations
- **API Testing**: Use `test_teams_api.py` for endpoint verification
- **Database Testing**: Use verification scripts for data integrity
- **Integration Testing**: Verify with existing application features

## Future Enhancements
- Team member role management interface
- Bulk operations (import/export teams)
- Team activity logging and audit trails
- Advanced filtering and search capabilities
- Team hierarchy and sub-team support
- Integration with project management features

---

✅ **Status**: Complete and fully functional
🚀 **Ready for**: Production deployment
📝 **Last Updated**: August 20, 2025
