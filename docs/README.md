# RFPO Application Documentation

This directory contains organized documentation for the RFPO (Request for Purchase Order) application.

## Directory Structure

- **`deployment/`** - Azure deployment guides, migration documentation, and production setup
- **`admin/`** - Administrative interface documentation and user guides  
- **`api/`** - API documentation, endpoints, and integration guides
- **`architecture/`** - System architecture, RBAC implementation, and design decisions

## Quick Links

### Getting Started

- [Main README](../README.md) - Project overview and setup
- [Admin Documentation](admin/README_ADMIN.md) - Administrative interface guide

### Deployment & Operations

- [Azure Deployment](deployment/AZURE_DEPLOYMENT_PHASE1.md) - Complete Azure setup guide
- [Deployment Summary](deployment/DEPLOYMENT_SUMMARY.md) - Current deployment status
- [Secrets Management](deployment/SECRETS.md) - Environment configuration and secrets

### Architecture & Design

- [RBAC Implementation](architecture/RBAC_IMPLEMENTATION_SUMMARY.md) - Role-based access control
- [Approver Tracking](architecture/APPROVER_TRACKING_README.md) - Approval workflow system

### Development

- See root level files: `requirements-dev.txt`, `.pre-commit-config.yaml`
- Development setup instructions in main [README](../README.md)

## Contributing

When adding new documentation:

1. Place files in the appropriate subdirectory
2. Update this README with links to new documents  
3. Keep documentation current with code changes
4. Use clear, descriptive filenames
