#!/usr/bin/env bash
# =============================================================================
# deploy-naams-site.sh
# Deploy the redesigned NAAMS Standards site to Azure Storage Static Website
# =============================================================================
#
# Usage:   ./deploy-naams-site.sh
# Prereqs: az login, storage account exists in rg-rfpo-e108977f
#
# This script:
# 1. Enables static website hosting on the storage account
# 2. Creates a 'naams-pdfs' blob container for the 2.1GB PDF library
# 3. Updates HTML files to point PDF links to blob storage URLs
# 4. Uploads the redesigned site to the $web container
# 5. Uploads all PDFs from naams_site_dump to the naams-pdfs container
# =============================================================================

set -euo pipefail

STORAGE_ACCOUNT="strfpo5kn5bsg47vvac"
RESOURCE_GROUP="rg-rfpo-e108977f"
PDF_CONTAINER="naams-pdfs"
SITE_DIR="naams_site_redesigned"
DUMP_DIR="naams_site_dump"
BLOB_BASE="https://${STORAGE_ACCOUNT}.blob.core.windows.net/${PDF_CONTAINER}"

echo "============================================="
echo "  NAAMS Static Site Deployment to Azure"
echo "============================================="
echo ""
echo "Storage Account: ${STORAGE_ACCOUNT}"
echo "Resource Group:  ${RESOURCE_GROUP}"
echo ""

# ---------- Step 1: Enable static website hosting ----------
echo "[1/6] Enabling static website hosting..."
az storage blob service-properties update \
  --account-name "$STORAGE_ACCOUNT" \
  --static-website \
  --index-document "index.html" \
  --404-document "index.html" \
  --auth-mode login \
  2>/dev/null || {
    echo "  Falling back to account key auth..."
    az storage blob service-properties update \
      --account-name "$STORAGE_ACCOUNT" \
      --static-website \
      --index-document "index.html" \
      --404-document "index.html"
  }
echo "  ✓ Static website hosting enabled"

# ---------- Step 2: Create blob container for PDFs ----------
echo ""
echo "[2/6] Creating '${PDF_CONTAINER}' blob container..."
az storage container create \
  --name "$PDF_CONTAINER" \
  --account-name "$STORAGE_ACCOUNT" \
  --public-access blob \
  --auth-mode login \
  2>/dev/null || {
    echo "  Falling back to account key auth..."
    az storage container create \
      --name "$PDF_CONTAINER" \
      --account-name "$STORAGE_ACCOUNT" \
      --public-access blob
  }
echo "  ✓ Container '${PDF_CONTAINER}' ready (public read)"

# ---------- Step 3: Get the static website URL ----------
echo ""
echo "[3/6] Getting static website endpoint..."
SITE_URL=$(az storage account show \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query "primaryEndpoints.web" -o tsv)
echo "  ✓ Site URL: ${SITE_URL}"

# ---------- Step 4: Update PDF links in HTML files ----------
echo ""
echo "[4/6] Updating PDF links to point to blob storage..."

# Create a working copy to avoid modifying originals
DEPLOY_DIR="${SITE_DIR}_deploy"
rm -rf "$DEPLOY_DIR"
cp -r "$SITE_DIR" "$DEPLOY_DIR"

# Replace naamsstandards.org PDF URLs with blob storage URLs
# Pattern: https://www.naamsstandards.org/path/to/file.pdf -> blob_base/path/to/file.pdf
find "$DEPLOY_DIR" -name "*.html" -exec sed -i \
  "s|https://www.naamsstandards.org/\([^\"]*\.pdf\)|${BLOB_BASE}/\1|g" {} \;
find "$DEPLOY_DIR" -name "*.html" -exec sed -i \
  "s|http://www.naamsstandards.org/\([^\"]*\.pdf\)|${BLOB_BASE}/\1|g" {} \;
find "$DEPLOY_DIR" -name "*.html" -exec sed -i \
  "s|http://naamsstandards.org/\([^\"]*\.pdf\)|${BLOB_BASE}/\1|g" {} \;
find "$DEPLOY_DIR" -name "*.html" -exec sed -i \
  "s|https://naamsstandards.org/\([^\"]*\.pdf\)|${BLOB_BASE}/\1|g" {} \;

# Also update XLS links
find "$DEPLOY_DIR" -name "*.html" -exec sed -i \
  "s|https://www.naamsstandards.org/\([^\"]*\.xls\)|${BLOB_BASE}/\1|g" {} \;
find "$DEPLOY_DIR" -name "*.html" -exec sed -i \
  "s|http://www.naamsstandards.org/\([^\"]*\.xls\)|${BLOB_BASE}/\1|g" {} \;

# Update the JSON data file too (for PDF Index page)
if [ -f "$DEPLOY_DIR/data/pdf_index.json" ]; then
  sed -i "s|http://naamsstandards.org/|${BLOB_BASE}/|g" "$DEPLOY_DIR/data/pdf_index.json"
  sed -i "s|https://naamsstandards.org/|${BLOB_BASE}/|g" "$DEPLOY_DIR/data/pdf_index.json"
  sed -i "s|https://www.naamsstandards.org/|${BLOB_BASE}/|g" "$DEPLOY_DIR/data/pdf_index.json"
fi

echo "  ✓ PDF/XLS links updated to: ${BLOB_BASE}/..."

# ---------- Step 5: Upload site to $web ----------
echo ""
echo "[5/6] Uploading site files to \$web container..."
az storage blob upload-batch \
  --account-name "$STORAGE_ACCOUNT" \
  --source "$DEPLOY_DIR" \
  --destination '$web' \
  --overwrite \
  --content-type "" \
  --auth-mode login \
  2>/dev/null || {
    echo "  Falling back to account key auth..."
    az storage blob upload-batch \
      --account-name "$STORAGE_ACCOUNT" \
      --source "$DEPLOY_DIR" \
      --destination '$web' \
      --overwrite
  }
echo "  ✓ Site uploaded to \$web"

# ---------- Step 6: Upload PDFs to blob storage ----------
echo ""
echo "[6/6] Uploading PDFs and documents to '${PDF_CONTAINER}' container..."
echo "  This will upload ~2.1 GB of files. This may take several minutes..."

# Upload Standards directory (contains chapter PDFs)
if [ -d "${DUMP_DIR}/Standards" ]; then
  echo "  Uploading Standards/chapters/..."
  az storage blob upload-batch \
    --account-name "$STORAGE_ACCOUNT" \
    --source "${DUMP_DIR}/Standards" \
    --destination "${PDF_CONTAINER}/Standards" \
    --overwrite \
    --auth-mode login \
    2>/dev/null || {
      az storage blob upload-batch \
        --account-name "$STORAGE_ACCOUNT" \
        --source "${DUMP_DIR}/Standards" \
        --destination "${PDF_CONTAINER}/Standards" \
        --overwrite
    }
  echo "  ✓ Standards uploaded"
fi

# Upload publications directory (contains interactive 3D PDFs, code search XLS, archives)
if [ -d "${DUMP_DIR}/publications" ]; then
  echo "  Uploading publications/..."
  az storage blob upload-batch \
    --account-name "$STORAGE_ACCOUNT" \
    --source "${DUMP_DIR}/publications" \
    --destination "${PDF_CONTAINER}/publications" \
    --overwrite \
    --auth-mode login \
    2>/dev/null || {
      az storage blob upload-batch \
        --account-name "$STORAGE_ACCOUNT" \
        --source "${DUMP_DIR}/publications" \
        --destination "${PDF_CONTAINER}/publications" \
        --overwrite
    }
  echo "  ✓ Publications uploaded"
fi

# Upload tables directory (cross-reference XLS files)
if [ -d "${DUMP_DIR}/tables" ]; then
  echo "  Uploading tables/..."
  az storage blob upload-batch \
    --account-name "$STORAGE_ACCOUNT" \
    --source "${DUMP_DIR}/tables" \
    --destination "${PDF_CONTAINER}/tables" \
    --overwrite \
    --auth-mode login \
    2>/dev/null || {
      az storage blob upload-batch \
        --account-name "$STORAGE_ACCOUNT" \
        --source "${DUMP_DIR}/tables" \
        --destination "${PDF_CONTAINER}/tables" \
        --overwrite
    }
  echo "  ✓ Tables uploaded"
fi

# Cleanup deploy dir
rm -rf "$DEPLOY_DIR"

echo ""
echo "============================================="
echo "  ✓ DEPLOYMENT COMPLETE"
echo "============================================="
echo ""
echo "  Static Website: ${SITE_URL}"
echo "  PDF Storage:    ${BLOB_BASE}/"
echo ""
echo "  Test links:"
echo "    ${SITE_URL}index.html"
echo "    ${SITE_URL}assembly.html"
echo "    ${SITE_URL}pdf-index.html"
echo "    ${BLOB_BASE}/Standards/chapters/assembly/A.pdf"
echo ""
