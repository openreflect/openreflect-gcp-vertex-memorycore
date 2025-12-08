#!/bin/bash
# Test script for local Docker container testing

set -e

echo "Building Docker image locally..."
docker build -t vertex-memory-bank-mcp:local .

echo "Starting container..."
CONTAINER_ID=$(docker run -d \
  -p 8080:8080 \
  -e GOOGLE_CLOUD_PROJECT=directed-asset-479716-f6 \
  -e GOOGLE_CLOUD_LOCATION=us-central1 \
  -e PORT=8080 \
  vertex-memory-bank-mcp:local)

echo "Container started with ID: $CONTAINER_ID"
echo "Waiting for container to be ready..."
sleep 5

echo "Testing health endpoint..."
curl -f http://localhost:8080/health || echo "Health check failed"

echo "Testing root endpoint..."
curl -f http://localhost:8080/ || echo "Root endpoint failed"

echo "Testing SSE endpoint with initialize message..."
curl -X POST http://localhost:8080/sse \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' \
  --max-time 10 || echo "SSE endpoint test failed"

echo "Container logs:"
docker logs $CONTAINER_ID

echo "Stopping container..."
docker stop $CONTAINER_ID
docker rm $CONTAINER_ID

echo "Local testing complete!"

