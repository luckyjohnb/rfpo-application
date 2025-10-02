#!/usr/bin/env bash
set -euo pipefail

# ACR server-side build helper for RFPO images
# Usage examples:
#   ./azure/acr-build.sh local rfpo-api:latest Dockerfile.api
#   ./azure/acr-build.sh github rfpo-user:latest Dockerfile.user-app luckyjohnb/rfpo-application feature/phase1-security-improvements

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$ROOT_DIR"

if [[ ! -f azure/azure-config.env ]]; then
  echo "Missing azure/azure-config.env. Run azure/setup-acr.sh or create it with ACR_NAME, ACR_LOGIN_SERVER, RESOURCE_GROUP_NAME, SUBSCRIPTION_ID."
  exit 1
fi

source azure/azure-config.env

MODE=${1:-}
IMAGE=${2:-}
DOCKERFILE=${3:-}
REPO=${4:-}
BRANCH=${5:-}

if [[ -z "$MODE" || -z "$IMAGE" || -z "$DOCKERFILE" ]]; then
  echo "Usage: $0 <local|github> <image[:tag]> <dockerfile> [githubRepo] [branch]"
  exit 1
fi

az account set --subscription "$SUBSCRIPTION_ID" >/dev/null

if [[ "$MODE" == "local" ]]; then
  echo "Building in ACR from local context: $IMAGE ($DOCKERFILE)"
  az acr build \
    --registry "$ACR_NAME" \
    --image "$IMAGE" \
    --file "$DOCKERFILE" \
    --platform linux/amd64 \
    .
elif [[ "$MODE" == "github" ]]; then
  if [[ -z "$REPO" || -z "$BRANCH" ]]; then
    echo "For github mode, provide repo and branch: e.g., luckyjohnb/rfpo-application feature/phase1-security-improvements"
    exit 1
  fi
  echo "Building in ACR from GitHub repo: $REPO#$BRANCH — $IMAGE ($DOCKERFILE)"
  az acr build \
    --registry "$ACR_NAME" \
    --image "$IMAGE" \
    --file "$DOCKERFILE" \
    --platform linux/amd64 \
    "https://github.com/$REPO.git#$BRANCH:."
else
  echo "Unknown mode: $MODE (use local or github)"
  exit 1
fi

echo "✅ ACR build complete: $ACR_LOGIN_SERVER/$IMAGE"