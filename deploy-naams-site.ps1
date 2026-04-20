# =============================================================================
# deploy-naams-site.ps1
# Deploy the redesigned NAAMS Standards site to Azure Storage Static Website
# =============================================================================
#
# Usage:   .\deploy-naams-site.ps1
# Prereqs: az login, storage account exists in rg-rfpo-e108977f
# =============================================================================

$ErrorActionPreference = "Stop"

$STORAGE_ACCOUNT = "strfpo5kn5bsg47vvac"
$RESOURCE_GROUP  = "rg-rfpo-e108977f"
$PDF_CONTAINER   = "naams-pdfs"
$SITE_DIR        = "naams_site_redesigned"
$DUMP_DIR        = "naams_site_dump"
$BLOB_BASE       = "https://$STORAGE_ACCOUNT.blob.core.windows.net/$PDF_CONTAINER"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  NAAMS Static Site Deployment to Azure"       -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Storage Account: $STORAGE_ACCOUNT"
Write-Host "Resource Group:  $RESOURCE_GROUP"
Write-Host ""
# ---------- Get account key ----------
Write-Host "Getting storage account key..." -ForegroundColor Yellow
$ACCT_KEY = (az storage account keys list --account-name $STORAGE_ACCOUNT --resource-group $RESOURCE_GROUP --query "[0].value" -o tsv)
if (-not $ACCT_KEY) { Write-Host "ERROR: Failed to get storage account key" -ForegroundColor Red; exit 1 }
Write-Host "  OK - Got account key" -ForegroundColor Green
# ---------- Step 1: Enable static website hosting ----------
Write-Host "[1/6] Enabling static website hosting..." -ForegroundColor Yellow
az storage blob service-properties update `
  --account-name $STORAGE_ACCOUNT `
  --account-key $ACCT_KEY `
  --static-website `
  --index-document "index.html" `
  --404-document "404.html" 2>$null
Write-Host "  OK - Static website hosting enabled" -ForegroundColor Green

# ---------- Step 2: Create blob container for PDFs ----------
Write-Host ""
Write-Host "[2/6] Creating '$PDF_CONTAINER' blob container..." -ForegroundColor Yellow
# Enable public blob access at account level
az storage account update --name $STORAGE_ACCOUNT --resource-group $RESOURCE_GROUP --allow-blob-public-access true 2>$null
# Create container (without public access first, then set it)
az storage container create --name $PDF_CONTAINER --account-name $STORAGE_ACCOUNT --account-key $ACCT_KEY 2>$null
# Set public read access
az storage container set-permission --name $PDF_CONTAINER --account-name $STORAGE_ACCOUNT --account-key $ACCT_KEY --public-access blob 2>$null
Write-Host "  OK - Container '$PDF_CONTAINER' ready (public read)" -ForegroundColor Green

# ---------- Step 3: Get static website URL ----------
Write-Host ""
Write-Host "[3/6] Getting static website endpoint..." -ForegroundColor Yellow
$SITE_URL = az storage account show `
  --name $STORAGE_ACCOUNT `
  --resource-group $RESOURCE_GROUP `
  --query "primaryEndpoints.web" -o tsv
Write-Host "  OK - Site URL: $SITE_URL" -ForegroundColor Green

# ---------- Step 4: Update PDF links in HTML files ----------
Write-Host ""
Write-Host "[4/6] Updating PDF links to point to blob storage..." -ForegroundColor Yellow

$DEPLOY_DIR = "${SITE_DIR}_deploy"
if (Test-Path $DEPLOY_DIR) { Remove-Item $DEPLOY_DIR -Recurse -Force }
Copy-Item $SITE_DIR $DEPLOY_DIR -Recurse

# Replace naamsstandards.org PDF/XLS URLs with blob storage URLs
$htmlFiles = Get-ChildItem "$DEPLOY_DIR" -Filter "*.html" -Recurse
foreach ($file in $htmlFiles) {
    $content = Get-Content $file.FullName -Raw
    # PDF links
    $content = $content -replace 'https://www\.naamsstandards\.org/([^"]*\.pdf)', "$BLOB_BASE/`$1"
    $content = $content -replace 'http://www\.naamsstandards\.org/([^"]*\.pdf)',  "$BLOB_BASE/`$1"
    $content = $content -replace 'http://naamsstandards\.org/([^"]*\.pdf)',       "$BLOB_BASE/`$1"
    $content = $content -replace 'https://naamsstandards\.org/([^"]*\.pdf)',      "$BLOB_BASE/`$1"
    # XLS links
    $content = $content -replace 'https://www\.naamsstandards\.org/([^"]*\.xls)', "$BLOB_BASE/`$1"
    $content = $content -replace 'http://www\.naamsstandards\.org/([^"]*\.xls)',  "$BLOB_BASE/`$1"
    # Archive links
    $content = $content -replace 'https://www\.naamsstandards\.org/(publications/archive/[^"]*)', "$BLOB_BASE/`$1"
    $content = $content -replace 'https://www\.naamsstandards\.org/(publications/assemblyCAD[^"]*)', "$BLOB_BASE/`$1"
    Set-Content $file.FullName $content -NoNewline
}

# Update PDF index JSON
$jsonFile = "$DEPLOY_DIR\data\pdf_index.json"
if (Test-Path $jsonFile) {
    $json = Get-Content $jsonFile -Raw
    $json = $json -replace 'http://naamsstandards\.org/',       "$BLOB_BASE/"
    $json = $json -replace 'https://naamsstandards\.org/',      "$BLOB_BASE/"
    $json = $json -replace 'https://www\.naamsstandards\.org/', "$BLOB_BASE/"
    Set-Content $jsonFile $json -NoNewline
}

Write-Host "  OK - PDF/XLS links updated to: $BLOB_BASE/..." -ForegroundColor Green

# ---------- Step 5: Upload site to $web ----------
Write-Host ""
Write-Host "[5/6] Uploading site files to `$web container..." -ForegroundColor Yellow
az storage blob upload-batch `
  --account-name $STORAGE_ACCOUNT `
  --account-key $ACCT_KEY `
  --source $DEPLOY_DIR `
  --destination '$web' `
  --overwrite 2>$null
Write-Host "  OK - Site uploaded to `$web" -ForegroundColor Green

# ---------- Step 6: Upload PDFs to blob storage ----------
Write-Host ""
Write-Host "[6/6] Uploading PDFs and documents to '$PDF_CONTAINER' container..." -ForegroundColor Yellow
Write-Host "  This will upload ~2.1 GB of files. This may take several minutes..."

# Upload Standards directory
$standardsDir = "$DUMP_DIR\Standards"
if (Test-Path $standardsDir) {
    Write-Host "  Uploading Standards/chapters/..."
    az storage blob upload-batch `
      --account-name $STORAGE_ACCOUNT `
      --account-key $ACCT_KEY `
      --source $standardsDir `
      --destination $PDF_CONTAINER `
      --destination-path "Standards" `
      --overwrite 2>$null
    Write-Host "  OK - Standards uploaded" -ForegroundColor Green
}

# Upload publications directory
$pubDir = "$DUMP_DIR\publications"
if (Test-Path $pubDir) {
    Write-Host "  Uploading publications/..."
    az storage blob upload-batch `
      --account-name $STORAGE_ACCOUNT `
      --account-key $ACCT_KEY `
      --source $pubDir `
      --destination $PDF_CONTAINER `
      --destination-path "publications" `
      --overwrite 2>$null
    Write-Host "  OK - Publications uploaded" -ForegroundColor Green
}

# Upload tables directory
$tablesDir = "$DUMP_DIR\tables"
if (Test-Path $tablesDir) {
    Write-Host "  Uploading tables/..."
    az storage blob upload-batch `
      --account-name $STORAGE_ACCOUNT `
      --account-key $ACCT_KEY `
      --source $tablesDir `
      --destination $PDF_CONTAINER `
      --destination-path "tables" `
      --overwrite 2>$null
    Write-Host "  OK - Tables uploaded" -ForegroundColor Green
}

# Cleanup
Remove-Item $DEPLOY_DIR -Recurse -Force

Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host "  DEPLOYMENT COMPLETE"                         -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Static Website: $SITE_URL"
Write-Host "  PDF Storage:    $BLOB_BASE/"
Write-Host ""
Write-Host "  Test links:"
Write-Host "    ${SITE_URL}index.html"
Write-Host "    ${SITE_URL}assembly.html"
Write-Host "    ${SITE_URL}pdf-index.html"
Write-Host "    $BLOB_BASE/Standards/chapters/assembly/A.pdf"
Write-Host ""
