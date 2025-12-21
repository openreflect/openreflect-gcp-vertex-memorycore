# PowerShell test script for local Docker container testing

Write-Host "Building Docker image locally..."
docker build -t openreflect-mcp:local .

Write-Host "Starting container..."
$containerId = docker run -d `
  -p 8080:8080 `
  -e GOOGLE_CLOUD_PROJECT=directed-asset-479716-f6 `
  -e GOOGLE_CLOUD_LOCATION=us-central1 `
  -e PORT=8080 `
  openreflect-mcp:local

Write-Host "Container started with ID: $containerId"
Write-Host "Waiting for container to be ready..."
Start-Sleep -Seconds 5

Write-Host "Testing health endpoint..."
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8080/health" -UseBasicParsing
    Write-Host "Health check: $($response.StatusCode) - $($response.Content)"
} catch {
    Write-Host "Health check failed: $_"
}

Write-Host "Testing root endpoint..."
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8080/" -UseBasicParsing
    Write-Host "Root endpoint: $($response.StatusCode) - $($response.Content)"
} catch {
    Write-Host "Root endpoint failed: $_"
}

Write-Host "Container logs:"
docker logs $containerId

Write-Host "Stopping container..."
docker stop $containerId
docker rm $containerId

Write-Host "Local testing complete!"
