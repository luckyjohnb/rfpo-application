# Azure Blob Storage Migration Guide

## Overview
This guide outlines the steps to migrate from local file storage to Azure Blob Storage for assets like logos, terms PDFs, and RFPO attachments. This will enable both the admin panel and user application to access the same assets via URLs.

## Current Architecture
```
┌─────────────────┐    ┌─────────────────┐
│   Admin Panel   │    │   User App      │
│   (Port 5111)   │    │   (Port 5000)   │
│                 │    │                 │
│ uploads/        │    │ static/         │
│ ├─ logos/       │    │ └─ po_files/    │
│ ├─ terms/       │    │   └─ logo.jpg   │
│ └─ rfpo_files/  │    │   └─ terms.pdf  │
└─────────────────┘    └─────────────────┘
```

## Target Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Admin Panel   │    │   User App      │    │  Azure Blob     │
│   (Port 5111)   │    │   (Port 5000)   │    │   Storage       │
│                 │    │                 │    │                 │
│ Upload Handler  │───▶│ Asset URLs      │───▶│ rfpo-assets/    │
│ File Manager    │    │ Template Refs   │    │ ├─ logos/       │
│ URL Generator   │    │ Preview Render  │    │ ├─ terms/       │
└─────────────────┘    └─────────────────┘    │ └─ rfpo_files/  │
                                              └─────────────────┘
```

## Migration Steps

### Phase 1: Azure Setup & Configuration

#### 1.1 Azure Storage Account Setup
```bash
# Create resource group
az group create --name rfpo-resources --location eastus

# Create storage account
az storage account create \
  --name rfpoassetstorage \
  --resource-group rfpo-resources \
  --location eastus \
  --sku Standard_LRS \
  --kind StorageV2

# Create containers
az storage container create --name logos --account-name rfpoassetstorage
az storage container create --name terms --account-name rfpoassetstorage  
az storage container create --name rfpo-files --account-name rfpoassetstorage
```

#### 1.2 Environment Variables
Add to `.env`:
```bash
# Azure Blob Storage
AZURE_STORAGE_ACCOUNT_NAME=rfpoassetstorage
AZURE_STORAGE_ACCOUNT_KEY=your_account_key_here
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=rfpoassetstorage;AccountKey=your_key;EndpointSuffix=core.windows.net

# Asset Base URLs
AZURE_BLOB_BASE_URL=https://rfpoassetstorage.blob.core.windows.net
LOGOS_CONTAINER_URL=${AZURE_BLOB_BASE_URL}/logos
TERMS_CONTAINER_URL=${AZURE_BLOB_BASE_URL}/terms
RFPO_FILES_CONTAINER_URL=${AZURE_BLOB_BASE_URL}/rfpo-files
```

### Phase 2: Code Changes

#### 2.1 Install Azure Dependencies
Add to `requirements.txt`:
```txt
azure-storage-blob==12.19.0
azure-identity==1.15.0
```

#### 2.2 Create Azure Blob Service
Create `services/azure_blob_service.py`:
```python
from azure.storage.blob import BlobServiceClient, BlobClient
from azure.core.exceptions import ResourceNotFoundError
import os
from datetime import datetime, timedelta
import mimetypes

class AzureBlobService:
    def __init__(self):
        self.connection_string = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
        self.account_name = os.environ.get('AZURE_STORAGE_ACCOUNT_NAME')
        self.base_url = os.environ.get('AZURE_BLOB_BASE_URL')
        self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
    
    def upload_file(self, file_data, container_name, blob_name, content_type=None):
        """Upload file to Azure Blob Storage"""
        try:
            if not content_type:
                content_type = mimetypes.guess_type(blob_name)[0] or 'application/octet-stream'
            
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name, 
                blob=blob_name
            )
            
            blob_client.upload_blob(
                file_data, 
                overwrite=True,
                content_settings={'content_type': content_type}
            )
            
            return f"{self.base_url}/{container_name}/{blob_name}"
        except Exception as e:
            print(f"Error uploading to Azure Blob: {e}")
            return None
    
    def delete_file(self, container_name, blob_name):
        """Delete file from Azure Blob Storage"""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name, 
                blob=blob_name
            )
            blob_client.delete_blob()
            return True
        except ResourceNotFoundError:
            return True  # Already deleted
        except Exception as e:
            print(f"Error deleting from Azure Blob: {e}")
            return False
    
    def get_file_url(self, container_name, blob_name):
        """Get public URL for file"""
        return f"{self.base_url}/{container_name}/{blob_name}"
    
    def generate_sas_url(self, container_name, blob_name, expiry_hours=24):
        """Generate SAS URL for temporary access"""
        try:
            from azure.storage.blob import generate_blob_sas, BlobSasPermissions
            
            sas_token = generate_blob_sas(
                account_name=self.account_name,
                container_name=container_name,
                blob_name=blob_name,
                account_key=os.environ.get('AZURE_STORAGE_ACCOUNT_KEY'),
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=expiry_hours)
            )
            
            return f"{self.base_url}/{container_name}/{blob_name}?{sas_token}"
        except Exception as e:
            print(f"Error generating SAS URL: {e}")
            return self.get_file_url(container_name, blob_name)
```

#### 2.3 Update Models
Modify `models.py` to include Azure URLs:

```python
class Consortium(db.Model):
    # ... existing fields ...
    logo = db.Column(db.String(255))  # Now stores Azure blob name
    logo_url = db.Column(db.String(500))  # Full Azure URL
    terms_pdf = db.Column(db.String(255))  # Azure blob name
    terms_pdf_url = db.Column(db.String(500))  # Full Azure URL
    
    def get_logo_url(self):
        """Get logo URL (Azure or fallback)"""
        if self.logo_url:
            return self.logo_url
        elif self.logo:
            # Fallback for migration period
            return f"/uploads/logos/{self.logo}"
        return None
    
    def get_terms_url(self):
        """Get terms PDF URL (Azure or fallback)"""
        if self.terms_pdf_url:
            return self.terms_pdf_url
        elif self.terms_pdf:
            return f"/uploads/terms/{self.terms_pdf}"
        return None

class RFPOFile(db.Model):
    # ... existing fields ...
    file_url = db.Column(db.String(500))  # Azure URL
    
    def get_file_url(self):
        """Get file URL (Azure or local fallback)"""
        if self.file_url:
            return self.file_url
        # Fallback to local file system during migration
        return f"/uploads/rfpo_files/rfpo_{self.rfpo_id}/{self.file_id}_{self.original_filename}"
```

### Phase 3: Admin Panel Changes

#### 3.1 Update File Upload Handlers
Modify `custom_admin.py`:

```python
from services.azure_blob_service import AzureBlobService

# Initialize Azure service
azure_blob = AzureBlobService()

@app.route('/consortium/<int:id>/edit', methods=['POST'])
def consortium_edit_post(id):
    # ... existing code ...
    
    # Handle logo upload
    if 'logo_file' in request.files:
        file = request.files['logo_file']
        if file and file.filename:
            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{secure_filename(file.filename)}"
            
            # Upload to Azure
            logo_url = azure_blob.upload_file(
                file.read(), 
                'logos', 
                filename,
                file.content_type
            )
            
            if logo_url:
                # Delete old logo if exists
                if consortium.logo:
                    azure_blob.delete_file('logos', consortium.logo)
                
                consortium.logo = filename
                consortium.logo_url = logo_url
            else:
                flash('Failed to upload logo', 'error')
    
    # Handle terms PDF upload
    if 'terms_file' in request.files:
        file = request.files['terms_file']
        if file and file.filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{secure_filename(file.filename)}"
            
            terms_url = azure_blob.upload_file(
                file.read(),
                'terms',
                filename,
                'application/pdf'
            )
            
            if terms_url:
                if consortium.terms_pdf:
                    azure_blob.delete_file('terms', consortium.terms_pdf)
                
                consortium.terms_pdf = filename
                consortium.terms_pdf_url = terms_url
```

#### 3.2 Update RFPO File Handling
```python
@app.route('/rfpo/<int:rfpo_id>/upload-file', methods=['POST'])
def rfpo_upload_file(rfpo_id):
    # ... existing validation ...
    
    for file in request.files.getlist('files'):
        if file and file.filename:
            # Generate unique filename
            file_id = str(uuid.uuid4())
            safe_filename = secure_filename(file.filename)
            blob_name = f"rfpo_{rfpo_id}/{file_id}_{safe_filename}"
            
            # Upload to Azure
            file_url = azure_blob.upload_file(
                file.read(),
                'rfpo-files',
                blob_name,
                file.content_type
            )
            
            if file_url:
                # Save to database
                rfpo_file = RFPOFile(
                    file_id=file_id,
                    rfpo_id=rfpo_id,
                    original_filename=file.filename,
                    file_size=len(file.read()),
                    file_url=file_url,
                    document_type=request.form.get('document_type', 'Other'),
                    uploaded_by=current_user.get_display_name(),
                    uploaded_at=datetime.utcnow()
                )
                db.session.add(rfpo_file)
```

### Phase 4: User App Changes

#### 4.1 Update Templates
Modify `templates/app/rfpo_preview.html`:

```html
<div class="logo1">
    {% if consortium and consortium.get_logo_url() %}
    <img width="300" src="{{ consortium.get_logo_url() }}" alt="{{ consortium.name }}" border="0">
    {% else %}
    <img width="300" src="{{ url_for('static', filename='po_files/uscar_logo.jpg') }}" alt="Default Logo" border="0">
    {% endif %}
</div>

<!-- Terms section -->
{% if consortium and consortium.get_terms_url() %}
<A href="{{ consortium.get_terms_url() }}" target="_blank">PDF template files</A>
{% else %}
<A href="{{ url_for('static', filename='po_files/uscar_terms.pdf') }}" target="_blank">PDF template files</A>
{% endif %}
```

#### 4.2 Update API Responses
Modify `simple_api.py` to include Azure URLs:

```python
@app.route('/api/consortiums')
@require_auth
def list_consortiums():
    consortiums = Consortium.query.filter_by(active=True).all()
    return jsonify({
        'success': True,
        'consortiums': [{
            'id': c.id,
            'consort_id': c.consort_id,
            'name': c.name,
            'abbrev': c.abbrev,
            'logo_url': c.get_logo_url(),
            'terms_url': c.get_terms_url(),
            'active': c.active
        } for c in consortiums]
    })
```

### Phase 5: Migration Script

Create `migrate_to_azure_blob.py`:

```python
#!/usr/bin/env python3
"""
Migration script to move existing files to Azure Blob Storage
"""
import os
import shutil
from services.azure_blob_service import AzureBlobService
from models import db, Consortium, RFPOFile
from app import create_app

def migrate_files():
    app = create_app()
    azure_blob = AzureBlobService()
    
    with app.app_context():
        print("Starting Azure Blob Storage migration...")
        
        # Migrate consortium logos
        print("Migrating consortium logos...")
        consortiums = Consortium.query.all()
        for consortium in consortiums:
            if consortium.logo and not consortium.logo_url:
                local_path = f"uploads/logos/{consortium.logo}"
                if os.path.exists(local_path):
                    with open(local_path, 'rb') as f:
                        logo_url = azure_blob.upload_file(
                            f.read(),
                            'logos',
                            consortium.logo
                        )
                        if logo_url:
                            consortium.logo_url = logo_url
                            print(f"✅ Migrated logo: {consortium.logo}")
                        else:
                            print(f"❌ Failed to migrate logo: {consortium.logo}")
        
        # Migrate terms PDFs
        print("Migrating terms PDFs...")
        for consortium in consortiums:
            if consortium.terms_pdf and not consortium.terms_pdf_url:
                local_path = f"uploads/terms/{consortium.terms_pdf}"
                if os.path.exists(local_path):
                    with open(local_path, 'rb') as f:
                        terms_url = azure_blob.upload_file(
                            f.read(),
                            'terms',
                            consortium.terms_pdf,
                            'application/pdf'
                        )
                        if terms_url:
                            consortium.terms_pdf_url = terms_url
                            print(f"✅ Migrated terms: {consortium.terms_pdf}")
        
        # Migrate RFPO files
        print("Migrating RFPO files...")
        rfpo_files = RFPOFile.query.filter(RFPOFile.file_url.is_(None)).all()
        for rfpo_file in rfpo_files:
            local_path = f"uploads/rfpo_files/rfpo_{rfpo_file.rfpo_id}/{rfpo_file.file_id}_{rfpo_file.original_filename}"
            if os.path.exists(local_path):
                blob_name = f"rfpo_{rfpo_file.rfpo_id}/{rfpo_file.file_id}_{rfpo_file.original_filename}"
                with open(local_path, 'rb') as f:
                    file_url = azure_blob.upload_file(
                        f.read(),
                        'rfpo-files',
                        blob_name
                    )
                    if file_url:
                        rfpo_file.file_url = file_url
                        print(f"✅ Migrated RFPO file: {rfpo_file.original_filename}")
        
        db.session.commit()
        print("Migration completed!")

if __name__ == '__main__':
    migrate_files()
```

### Phase 6: Deployment Considerations

#### 6.1 Docker Configuration
Update `docker-compose.yml`:

```yaml
services:
  rfpo-admin:
    environment:
      - AZURE_STORAGE_CONNECTION_STRING=${AZURE_STORAGE_CONNECTION_STRING}
      - AZURE_STORAGE_ACCOUNT_NAME=${AZURE_STORAGE_ACCOUNT_NAME}
      - AZURE_BLOB_BASE_URL=${AZURE_BLOB_BASE_URL}
    # Remove volumes for uploads since they'll be in Azure
    # volumes:
    #   - ./uploads:/app/uploads
  
  rfpo-user-app:
    environment:
      - AZURE_BLOB_BASE_URL=${AZURE_BLOB_BASE_URL}
```

#### 6.2 Backup Strategy
```bash
# Before migration, backup existing files
tar -czf uploads_backup_$(date +%Y%m%d).tar.gz uploads/

# After successful migration and testing
# rm -rf uploads/  # Remove local files
```

## Migration Impact Assessment

### **Low Impact** ✅
- **User App Templates**: Minor URL changes
- **API Responses**: Add URL fields to existing responses
- **Database Schema**: Add new URL columns (non-breaking)

### **Medium Impact** ⚠️
- **Admin Panel Upload Logic**: Replace local file handling
- **File Management**: New Azure service integration
- **Environment Configuration**: New Azure settings

### **High Impact** ❗
- **Migration Script**: One-time data migration required
- **Deployment Process**: New Azure dependencies
- **Error Handling**: Network-dependent file operations

## Testing Strategy

1. **Development Environment**: Test with Azure Storage Emulator
2. **Staging Environment**: Full Azure integration testing
3. **Migration Testing**: Run migration script on copy of production data
4. **Rollback Plan**: Keep local files until Azure is fully validated

## Timeline Estimate

- **Setup & Configuration**: 1-2 days
- **Code Implementation**: 3-4 days  
- **Testing & Validation**: 2-3 days
- **Migration & Deployment**: 1 day
- **Total**: ~1-2 weeks

## Benefits

1. **Shared Assets**: Both apps access same files
2. **Scalability**: Azure handles storage scaling
3. **Reliability**: Built-in redundancy and backup
4. **Performance**: CDN-like distribution
5. **Security**: Granular access control with SAS tokens
6. **Cost**: Pay-per-use storage model

This migration will significantly improve the architecture by centralizing asset storage and eliminating the need to manually sync files between applications.
