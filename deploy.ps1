# deploy.ps1 - Build the Lambda zip then run Terraform apply
# Usage: .\deploy.ps1
# Run from the repo root (C:\work\changi-dr-agent)
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$TerraformDir = Join-Path $ScriptDir "Terraform_scripts"
$EnvFile = Join-Path $ScriptDir ".env"

# --- Function to load .env variables ---
function Get-EnvVariables($filePath) {
    if (-not (Test-Path $filePath)) { return @{} }
    $vars = @{}
    Get-Content $filePath | ForEach-Object {
        if ($_ -match "^(?<name>[^#\s][^=]+)=(?<value>.*)$") {
            $name = $Matches['name'].Trim()
            $value = $Matches['value'].Trim()
            # Remove quotes if present
            $value = $value -replace '^["'']|["'']$', ''
            $vars[$name] = $value
        }
    }
    return $vars
}

Write-Host "==> Loading environment variables from .env..."
$envVars = Get-EnvVariables $EnvFile

$tfVars = @()
# Map .env to Terraform variables
if ($envVars.ContainsKey("OPENAI_API_KEY")) { $tfVars += "-var=`"openai_key=$($envVars['OPENAI_API_KEY'])`"" }
if ($envVars.ContainsKey("GEMINI_API_KEY")) { $tfVars += "-var=`"gemini_key=$($envVars['GEMINI_API_KEY'])`"" }
if ($envVars.ContainsKey("CHANGI_API_KEY")) { $tfVars += "-var=`"changi_api_key=$($envVars['CHANGI_API_KEY'])`"" }
if ($envVars.ContainsKey("MCP_API_URL")) { 
    $tfVars += "-var=`"mcp_api_url=$($envVars['MCP_API_URL'])`"" 
}
elseif ($envVars.ContainsKey("MCP_SERVER_URL")) {
    $tfVars += "-var=`"mcp_api_url=$($envVars['MCP_SERVER_URL'])`""
}
if ($envVars.ContainsKey("MCP_API_KEY")) { $tfVars += "-var=`"mcp_api_key=$($envVars['MCP_API_KEY'])`"" }

# Step 1: Build the Lambda zip
Write-Host ""
Write-Host "==> [1/3] Building Lambda deployment zip..."
& "$ScriptDir\build_lambda.ps1"

# Step 2: Terraform init
Write-Host ""
Write-Host "==> [2/3] Terraform init..."
Push-Location $TerraformDir
try {
    terraform init -upgrade

    # Step 3: Terraform apply
    Write-Host ""
    Write-Host "==> [3/3] Terraform apply..."
    
    # Combine auto-loaded vars with any manual @args
    $allArgs = $tfVars + $args
    if ($allArgs) {
        Write-Host "    Passing variables: $($tfVars -join ' ')"
        terraform apply -auto-approve $allArgs
    }
    else {
        terraform apply -auto-approve
    }
}
finally {
    Pop-Location
}
