#!/bin/bash
set -e

# Configuration
PROJECT_ID="directed-asset-479716-f6"
REGION="us-central1"
SERVICE_NAME="vertex-memory-bank-mcp"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

echo "Building Docker image..."
docker build -t ${IMAGE_NAME} .

echo "Pushing image to Google Container Registry..."
docker push ${IMAGE_NAME}

echo "Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME} \
  --platform managed \
  --region ${REGION} \
  --project ${PROJECT_ID} \
  --allow-unauthenticated \
  --service-account vertex-memory-bank-mcp-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --set-env-vars GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION} \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300s \
  --max-instances 10 \
  --port 8080

echo "Deployment complete!"
echo "Service URL: $(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --project ${PROJECT_ID} --format 'value(status.url)')"

