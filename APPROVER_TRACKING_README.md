# Approver Tracking Feature

This document describes the new approver tracking functionality that automatically tracks when users are assigned to approval workflows.

## Overview

The approver tracking feature adds a boolean `is_approver` field to users that automatically updates when users are added to or removed from approval workflow steps. This allows both the admin panel and API to quickly identify users who have approver responsibilities.

## Database Changes

### New Columns in `users` table:
- `is_approver` (BOOLEAN, default FALSE): Indicates if the user is currently assigned to any approval workflow
- `approver_updated_at` (DATETIME, nullable): Timestamp of when the approver status was last updated

## Features

### 1. Admin Panel Integration

When viewing or editing a user in the admin panel (`/user/<id>/edit`), there is now a new "Approval Workflow Status" section that shows:

- **For Non-Approvers**: Clear indication that the user is not assigned to any approval workflows
- **For Approvers**: 
  - Summary of their approver roles (primary/backup)
  - Count of active vs inactive workflows they're assigned to
  - Expandable details showing all workflow assignments with:
    - Workflow name and type (consortium/team/project)
    - Entity name
    - Step name and approval type
    - Role (primary/backup)
    - Workflow status (active/inactive)

### 2. API Integration

#### Enhanced User Data
All user-related API endpoints now include approver information:

```json
{
  "user": {
    "id": 123,
    "email": "user@example.com",
    "is_approver": true,
    "approver_updated_at": "2025-01-15T10:30:00Z",
    "approver_summary": {
      "is_approver": true,
      "summary": "Approver in 2 workflows (1 active, 1 inactive)",
      "assignments_summary": "2 primary, 1 backup approver roles",
      "last_updated": "2025-01-15T10:30:00Z",
      "details": {
        "is_approver": true,
        "total_assignments": 3,
        "primary_assignments": 2,
        "backup_assignments": 1,
        "active_workflows_count": 1,
        "inactive_workflows_count": 1,
        "workflow_assignments": [...]
      }
    }
  }
}
```

#### New API Endpoints

**GET /api/users/approver-status**
- Returns detailed approver status for the current user
- Requires authentication

**POST /api/users/sync-approver-status**
- Force refresh of approver status for current user
- Requires authentication
- Useful if workflows were modified externally

### 3. Automatic Status Synchronization

The approver status is automatically updated when:
- New approval workflows are created
- Approval steps are added to workflows
- Approval steps are deleted from workflows
- Users are assigned as primary or backup approvers

## Installation (Docker Environment)

### Step 1: Run the Migration

```bash
# Make sure your containers are running
docker-compose up -d

# Run the migration script
./docker_migrate_approver_tracking.sh
```

### Step 2: Restart Containers (Optional)

```bash
docker-compose restart
```

## Manual Migration (Alternative)

If you prefer to run the migration manually:

```bash
# Execute migration inside the admin container
docker exec -it rfpo-admin python migrate_add_approver_tracking.py
```

## User Model Methods

### New Methods Added to User Class:

#### `check_approver_status()`
Returns detailed information about the user's approver assignments:
```python
{
    'is_approver': bool,
    'total_assignments': int,
    'primary_assignments': int,
    'backup_assignments': int,
    'active_workflows_count': int,
    'inactive_workflows_count': int,
    'workflow_assignments': [...]
}
```

#### `update_approver_status(updated_by=None)`
Updates the `is_approver` field based on current workflow assignments.
Returns `True` if status changed, `False` if no change.

#### `get_approver_summary()`
Returns a formatted summary suitable for display in UI:
```python
{
    'is_approver': bool,
    'summary': str,
    'assignments_summary': str,
    'last_updated': str,
    'details': {...}
}
```

## Utility Functions

### `sync_all_users_approver_status(updated_by=None)`
Syncs approver status for all users in the system. Useful after bulk workflow changes.

### `sync_user_approver_status_for_workflow(workflow_id, updated_by=None)`
Syncs approver status for users affected by a specific workflow.

## Usage Examples

### Check if a user is an approver
```python
user = User.query.get(user_id)
if user.is_approver:
    print(f"{user.get_display_name()} is an approver")
```

### Get detailed approver information
```python
user = User.query.get(user_id)
approver_info = user.check_approver_status()
if approver_info['is_approver']:
    print(f"User has {approver_info['total_assignments']} workflow assignments")
```

### Force refresh approver status
```python
user = User.query.get(user_id)
status_changed = user.update_approver_status(updated_by="admin")
if status_changed:
    db.session.commit()
    print("Approver status updated")
```

## API Usage Examples

### Check current user's approver status
```javascript
fetch('/api/users/approver-status', {
  headers: {
    'Authorization': 'Bearer ' + token
  }
})
.then(response => response.json())
.then(data => {
  if (data.success && data.is_approver) {
    console.log('User is an approver:', data.approver_summary.summary);
  }
});
```

### Sync approver status
```javascript
fetch('/api/users/sync-approver-status', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ' + token
  }
})
.then(response => response.json())
.then(data => {
  console.log(data.message);
});
```

## Troubleshooting

### Migration Issues
- Ensure containers are running before migration
- Check container logs for any database errors
- Verify database permissions

### Status Not Updating
- Use the sync endpoints to force refresh
- Check that workflows are properly configured
- Verify user record_ids match in workflow steps

### API Issues
- Ensure authentication tokens are valid
- Check that user has proper permissions
- Verify API endpoints are accessible

## Performance Considerations

- Approver status is cached in the database for quick lookups
- Status updates are triggered only when workflows change
- API responses include cached approver summaries
- Large workflow changes may take a few seconds to sync all users

## Security Notes

- Only authenticated users can access their own approver status via API
- Admin users can view all users' approver status in the admin panel
- Approver status is automatically maintained - no manual intervention required
