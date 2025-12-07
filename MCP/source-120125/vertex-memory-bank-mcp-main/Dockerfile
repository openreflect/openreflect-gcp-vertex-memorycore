FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install additional dependencies for HTTP server
RUN pip install --no-cache-dir fastapi uvicorn

# Copy application source code
COPY src/ ./src/
COPY memory_bank_server.py .

# Expose port 8080 (Cloud Run default)
EXPOSE 8080

# Set environment variable for port
ENV PORT=8080

# Run the HTTP server
# Use PORT environment variable from Cloud Run
CMD python -c "import os; import sys; sys.path.insert(0, '/app'); from src.server_http import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', '8080')), log_level='info')"

