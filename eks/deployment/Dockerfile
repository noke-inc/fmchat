# Build from the fm-chat root:
#   docker build -f deployment/Dockerfile -t noke-mcp-server .

FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server package, agent, and UI
COPY mcp_server/ ./mcp_server/
COPY agent/ ./agent/
COPY ui/ ./ui/

EXPOSE 8000

# All config comes from environment variables injected at runtime (K8s secret/configmap).
# Never bake .env into the image.
CMD ["python", "-m", "uvicorn", "mcp_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
