
#$DDB_ENDPOINT = "http://localhost:8000"
$AWS_REGION = "ap-south-1"
# Session table with basic fields and we will add more fileds for production code
aws dynamodb create-table --table-name dr_sessions `
  --attribute-definitions AttributeName=session_id,AttributeType=S `
  --key-schema AttributeName=session_id,KeyType=HASH `
  --billing-mode PAY_PER_REQUEST `
  --region $AWS_REGION

#Enable Time to Live to automatically expire Session
aws dynamodb update-time-to-live --table-name dr_sessions `
  --time-to-live-specification "Enabled=true,AttributeName=expires_at" `
  --region $AWS_REGION

# Basic User table created with sample data and this will be moved to RDBMS for production code
aws dynamodb create-table --table-name dr_users `
  --attribute-definitions AttributeName=user_id,AttributeType=S `
  --key-schema AttributeName=user_id,KeyType=HASH `
  --billing-mode PAY_PER_REQUEST `
  --region $AWS_REGION

aws dynamodb batch-write-item `
  --request-items file://setup/users.json `
  --region $AWS_REGION

$tables = @("dr_sessions", "dr_users")
foreach ($table in $tables) {
    Write-Host "==== TABLE: $table ====" -ForegroundColor Cyan
aws dynamodb scan `
    --table-name $table `
    --region $AWS_REGION `
    --output json |
    ConvertFrom-Json |
    Select-Object -ExpandProperty Items |
    ForEach-Object {
        $obj = @{}
        $_.psobject.Properties | ForEach-Object {
            $name = $_.Name
            $valueObject = $_.Value
            $stringValue = $valueObject.S  # all fields are S-type
            $obj[$name] = $stringValue
        }
        [PSCustomObject]$obj
    } | Format-Table -AutoSize

""  # spacing
}