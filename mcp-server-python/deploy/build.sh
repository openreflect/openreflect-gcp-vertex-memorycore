#!/bin/bash
set -e

# Configuration
PROJECT_ID="directed-asset-479716-f6"
IMAGE_NAME="openreflect-mcp"
TAG="latest"

echo "========================================================"
echo "Building Golden Image for OpenReflect MCP"
echo "Project: ${PROJECT_ID}"
echo "Image:   gcr.io/${PROJECT_ID}/${IMAGE_NAME}:${TAG}"
echo "========================================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "Error: Docker is not running."
  exit 1
fi

# Build
echo "Building Docker image..."
docker build -t gcr.io/${PROJECT_ID}/${IMAGE_NAME}:${TAG} ..

# Push
echo "Pushing to Google Container Registry..."
# Ensure gcloud auth is configured for docker
# gcloud auth configure-docker
docker push gcr.io/${PROJECT_ID}/${IMAGE_NAME}:${TAG}

echo "========================================================"
echo "Build Complete!"
echo "Image URI: gcr.io/${PROJECT_ID}/${IMAGE_NAME}:${TAG}"
echo "========================================================"
