$BucketName = "cjss-dr-artifacts"
$Region = "ap-south-1"
aws s3api create-bucket `
  --bucket $BucketName `
  --region $Region `
  --create-bucket-configuration LocationConstraint=$Region 

CD C:\work\ai\isc-tr
# ---------------------------------
# Static Assets Deployment Script
# ---------------------------------
$ErrorActionPreference = "Stop"

# -----------------------------
# Configuration
# -----------------------------
$BucketName = "cjss-dr-artifacts"
#$CliProfile = "lydia-sandbox"

$AdminStaticDir = "admin/static"
$ChatStaticDir  = "chat/static"
$StorageDir  = "core/storage"


$S3AdminPath = "s3://$BucketName/web_sc/admin/static"
$S3ChatPath  = "s3://$BucketName/web_sc/chat/static"
$S3StoragePath  = "s3://$BucketName/storage"

# -----------------------------
# Pre-flight checks
# -----------------------------
Write-Host " Checking AWS CLI..." -ForegroundColor Cyan
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    Write-Error "AWS CLI not found. Install it first: https://docs.aws.amazon.com/cli/"
    exit 1
}

Write-Host " Checking static directories..." -ForegroundColor Cyan
if (-not (Test-Path $AdminStaticDir)) {
    Write-Error "Missing directory: $AdminStaticDir"
    exit 1
}
if (-not (Test-Path $ChatStaticDir)) {
    Write-Error "Missing directory: $ChatStaticDir"
    exit 1
}

if (-not (Test-Path $StorageDir)) {
    Write-Error "Missing directory: $StorageDir"
    exit 1
}

Write-Host "Checking S3 bucket..." -ForegroundColor Cyan
try {
    aws s3api head-bucket --bucket $BucketName  | Out-Null
    Write-Host " Bucket $BucketName exists"
} catch {
    Write-Host "️ Bucket $BucketName not found. Creating..." -ForegroundColor Yellow
    aws s3api create-bucket `
        --bucket $BucketName `
        --region ap-south-1 `
        --create-bucket-configuration LocationConstraint=ap-south-1

    Write-Host " Bucket $BucketName created"
}

# -----------------------------
# Deploy
# -----------------------------
Write-Host "Deploying ADMIN static files..." -ForegroundColor Green
aws s3 sync `
    "$AdminStaticDir" `
    "$S3AdminPath" `
    --delete `
    --only-show-errors

Write-Host "Deploying CHAT static files..." -ForegroundColor Green
aws s3 sync `
    "$ChatStaticDir" `
    "$S3ChatPath" `
    --delete `
    --only-show-errors

Write-Host "Deploying Storage files..." -ForegroundColor Green
aws s3 sync `
    "$StorageDir" `
    "$S3StoragePath" `
    --delete `
    --only-show-errors

#Grant public access to static files
aws s3api put-public-access-block `
  --bucket cjss-dr-artifacts `
  --public-access-block-configuration `
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=false,RestrictPublicBuckets=false" `
  --region ap-south-1

aws s3api put-bucket-policy `
  --bucket cjss-dr-artifacts `
  --policy file://setup/bucket-policy.json `
  --region ap-south-1