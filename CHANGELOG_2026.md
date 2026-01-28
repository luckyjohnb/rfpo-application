# RFPO Application Changelog - 2026

## [January 28, 2026] - JanuaryFixes Release 🎉

### 🚀 Deployed to Azure Production
- **Status**: ✅ Successfully deployed to Azure Container Apps
- **Branch**: `JanuaryFixes` (commit `0e7680c`)
- **Images Deployed**:
  - `rfpo-api:latest` (sha256:2cac53fe76b54ba087df892c35c2f79be23a43ec6e40e08156b09c4ea94e4a21)
  - `rfpo-admin:latest` (sha256:1986aef7ae2d61f04495079ca22f5377d948cca4c565011fc7f1b8d8b57f08b7)
  - `rfpo-user:latest` (sha256:d69f73cd5fad891247625480bcd81a2d9397e9620896f0d3ffc5d07e0c0ddd41)

### ✨ Features & Improvements

#### 1. **Currency Formatting** 💰
- Added custom Jinja2 template filter `|currency` for consistent price display
- Formats all monetary values with thousand separators: `$1,234,567.89`
- Applied to:
  - Admin RFPO editing page (unit prices, totals, subtotals, cost shares)
  - Admin RFPO preview page (all price displays)
  - User-facing RFPO preview page
  - Approval workflow instance displays
- **Implementation**: Custom filter in both `custom_admin.py` (Admin Panel) and `app.py` (User App)
- Database stores clean numeric values; only UI formatting changes

#### 2. **Form Validation Bug Fix** 🐛
- Fixed field selector bug in RFPO editing form validation
- **Issue**: Validation was incorrectly selecting fields with matching IDs from outside the modal form
- **Solution**: Changed from `document.getElementById()` to `form.querySelector()` to scope field selection to the specific form
- This prevents validation of unintended form fields when multiple forms exist on the page
- **Files Modified**: `templates/admin/rfpo_edit.html`

#### 3. **Generate PO Button Hidden** 🙈
- Hid the "Generate PO" button until approval workflow criteria are met
- **Implementation**: Added Bootstrap `d-none` class to button with id `generatePoBtn`
- Button can be shown/hidden via JavaScript based on approval status
- Prevents premature PO generation before proper approval
- **Files Modified**: `templates/admin/rfpo_edit.html`

#### 4. **Security Update** 🔐
- Reset admin account password to `2026$Covid` (both local SQLite and Azure PostgreSQL)
- Enhanced password security for authentication

### 📁 Modified Files

```
custom_admin.py
├── Added @app.template_filter('currency') for admin panel price formatting

app.py
├── Added @app.template_filter('currency') for user app price formatting

templates/admin/rfpo_edit.html
├── Line 21-24: Generate PO button hidden with d-none class, added id="generatePoBtn"
├── Added |currency filter to unit_price and total_price displays
├── Added |currency filter to subtotal, cost_share, and total displays
├── Fixed form validation to use form.querySelector() instead of getElementById()

templates/admin/rfpo_preview.html
├── Updated all price displays to use |currency filter

templates/admin/approval_instances.html
├── Updated approval instance amount displays with |currency filter

templates/admin/approval_instance_view.html
├── Updated RFPO total amount to use |currency filter

templates/app/rfpo_preview.html
├── Updated all user-facing price displays with |currency filter
```

### 🧪 Testing Completed

- ✅ Local Docker containers built and verified healthy
  - rfpo-admin: UP and healthy
  - rfpo-api: UP and healthy
  - rfpo-user: UP and healthy
- ✅ Currency formatting verified across all templates
- ✅ Form validation tested and working correctly
- ✅ Generate PO button hidden as expected
- ✅ Azure Container Registry images built successfully from JanuaryFixes branch
- ✅ Azure Container Apps deployed and updated with new images

### 🌐 Production URLs

- **Admin Panel**: https://rfpo-admin.livelyforest-d06a98a0.eastus.azurecontainerapps.io/login
- **User App**: https://rfpo-user.livelyforest-d06a98a0.eastus.azurecontainerapps.io
- **API**: https://rfpo-api.livelyforest-d06a98a0.eastus.azurecontainerapps.io/api/health

### 📝 Deployment Notes

- Deployment used `GIT_REF=JanuaryFixes ./redeploy-phase1.sh` to ensure correct branch was used
- All 3 container images rebuilt from JanuaryFixes branch in Azure Container Registry
- Previous deployment used main branch by default; this deployment explicitly targeted JanuaryFixes
- All changes are backward compatible (formatting-only changes to UI, no database migrations)

### 🔄 Branch Management

- Branch: `JanuaryFixes`
- Base: `main`
- Status: ✅ All changes merged to origin and deployed
- Previous releases available on `main` branch

### 🎯 Next Steps

- Monitor Azure production for any issues
- Users can now see properly formatted currency values in all RFPO views
- Admin panel shows cleaner, more readable price displays
- Form validation is more robust and prevents field selector conflicts

---

**Deployed by**: Automated deployment script
**Deployment Date**: January 28, 2026, 07:08 UTC
**All tests passed**: ✅
