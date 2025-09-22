#!/bin/bash

# Docker Migration Script for Approver Tracking
# This script runs the approver tracking migration in the Docker environment

echo "🐳 Starting Docker migration for approver tracking..."
echo "=" * 60

# Check if containers are running
if ! docker ps | grep -q rfpo-admin; then
    echo "❌ RFPO Admin container is not running!"
    echo "Please start the containers first with: docker-compose up -d"
    exit 1
fi

echo "✅ RFPO Admin container is running"

# Run the migration script inside the container
echo "🔄 Running migration inside Docker container..."
docker exec -it rfpo-admin python migrate_add_approver_tracking.py

# Check the exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Migration completed successfully!"
    echo ""
    echo "📋 What was done:"
    echo "  ✓ Added is_approver column to users table"
    echo "  ✓ Added approver_updated_at column to users table"
    echo "  ✓ Synced approver status for all existing users"
    echo "  ✓ Verified migration integrity"
    echo ""
    echo "🚀 The approver tracking feature is now available:"
    echo "  • Admin Panel: Users will show approver status in user forms"
    echo "  • API: /api/users/approver-status endpoint available"
    echo "  • API: User login/verify responses include approver info"
    echo ""
    echo "💡 Next steps:"
    echo "  1. Restart your containers to ensure all changes are loaded"
    echo "  2. Test the admin panel user management section"
    echo "  3. Test the API endpoints in your other applications"
else
    echo ""
    echo "💥 Migration failed!"
    echo "Please check the error messages above and try again."
    exit 1
fi

echo "=" * 60
