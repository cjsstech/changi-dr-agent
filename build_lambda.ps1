# build_lambda.ps1 - Package the Lambda deployment zip (agent-dr.zip)
# Run from the repository root. Produces agent-dr.zip in the repo root.
# Target: python3.12 / x86_64 / Amazon Linux 2023
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BuildDir = Join-Path $ScriptDir ".build_lambda"
$ZipOut = Join-Path $ScriptDir "agent-dr.zip"
$ReqFile = Join-Path $ScriptDir "requirements.txt"

Write-Host "==> Cleaning previous build..."
if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir }
New-Item -ItemType Directory -Path $BuildDir | Out-Null

# ── Install dependencies ───────────────────────────────────────────────────────
# Lambda Python 3.12 on x86_64 / Amazon Linux 2023.
# manylinux2014_x86_64 wheels are universally available on PyPI.
Write-Host "==> Installing Python dependencies (linux/x86_64, python3.12)..."
& python -m pip install `
    --platform manylinux2014_x86_64 `
    --implementation cp `
    --python-version 3.12 `
    --only-binary :all: `
    --prefer-binary `
    --ignore-installed `
    --upgrade `
    --target $BuildDir `
    -r $ReqFile

if ($LASTEXITCODE -ne 0) {
    throw "pip install failed with exit code $LASTEXITCODE"
}

# ── Diagnostics: verify pydantic_core C extension ─────────────────────────────
Write-Host ""
Write-Host "==> Checking pydantic_core installation..."
$pydanticDir = Join-Path $BuildDir "pydantic_core"
if (Test-Path $pydanticDir) {
    $soFiles = Get-ChildItem -Path $pydanticDir -Filter "_pydantic_core*.so" -ErrorAction SilentlyContinue
    $pydFiles = Get-ChildItem -Path $pydanticDir -Filter "_pydantic_core*" -ErrorAction SilentlyContinue
    if ($soFiles) {
        Write-Host "    OK: $($soFiles[0].Name)"
    }
    else {
        Write-Warning "MISSING: _pydantic_core*.so not found!"
        Write-Host "    Files found:"
        $pydFiles | ForEach-Object { Write-Host "      $($_.Name)" }
    }
}
else {
    Write-Warning "pydantic_core directory NOT FOUND in build dir!"
}
Write-Host ""

# ── Copy application source ────────────────────────────────────────────────────
Write-Host "==> Copying application source code..."
$Excludes = @(
    '.venv', '.build_lambda', 'agent-dr.zip', '.git', '__pycache__',
    '*.pyc', '*.pyo', '.env', '.env.json', 'tests', 'Terraform_scripts',
    'samconfig.toml', 'template.yaml', 'build_lambda.sh', 'build_lambda.ps1',
    'deploy.ps1', '.idea', '.aws-sam', '.terraform', 'packaged.yaml'
)

Get-ChildItem -Path $ScriptDir -Force | Where-Object {
    $name = $_.Name
    -not ($Excludes | Where-Object { $name -like $_ })
} | ForEach-Object {
    $dest = Join-Path $BuildDir $_.Name
    if ($_.PSIsContainer) {
        Copy-Item -Recurse -Path $_.FullName -Destination $dest
    }
    else {
        Copy-Item -Path $_.FullName -Destination $dest
    }
}

Get-ChildItem -Path $BuildDir -Recurse -Filter "__pycache__" -Directory -ErrorAction SilentlyContinue |
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# ── Create zip ─────────────────────────────────────────────────────────────────
Write-Host "==> Creating zip archive: $ZipOut"
if (Test-Path $ZipOut) { Remove-Item $ZipOut }

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($BuildDir, $ZipOut)

$sizeMB = [math]::Round((Get-Item $ZipOut).Length / 1MB, 2)
Write-Host "==> Done. Artifact: $ZipOut  ($sizeMB MB)"
