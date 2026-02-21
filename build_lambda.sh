#!/usr/bin/env bash
# build_lambda.sh – Package the Lambda deployment zip (agent-dr.zip)
# Run from the repository root. Produces agent-dr.zip in the repo root.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/.build_lambda"
ZIP_OUT="${SCRIPT_DIR}/agent-dr.zip"

echo "==> Cleaning previous build..."
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

echo "==> Installing Python dependencies for linux/arm64..."
pip install \
  --platform manylinux2014_aarch64 \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all: \
  --upgrade \
  --target "${BUILD_DIR}" \
  -r "${SCRIPT_DIR}/requirements.txt"

echo "==> Copying application source code..."
# Copy all Python source directories/files (exclude venv, build artefacts, tests, Terraform, etc.)
rsync -a \
  --exclude='.venv' \
  --exclude='.build_lambda' \
  --exclude='agent-dr.zip' \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='*.pyo' \
  --exclude='.env' \
  --exclude='.env.json' \
  --exclude='tests/' \
  --exclude='Terraform_scripts/' \
  --exclude='samconfig.toml' \
  --exclude='template.yaml' \
  --exclude='build_lambda.sh' \
  --exclude='.idea/' \
  --exclude='.aws-sam/' \
  "${SCRIPT_DIR}/" "${BUILD_DIR}/"

echo "==> Creating zip archive: ${ZIP_OUT}"
rm -f "${ZIP_OUT}"
(cd "${BUILD_DIR}" && zip -r "${ZIP_OUT}" . -x "*.pyc" -x "__pycache__/*")

echo "==> Done. Artifact: ${ZIP_OUT}"
echo "    Size: $(du -sh "${ZIP_OUT}" | cut -f1)"
