# CIM Backend Runbook

## 1. Project Requirements

Install:

 Git
 Docker Engine 24+ or Docker Desktop 4+

Windows and macOS developers should install Docker Desktop. Python is not required when using Docker.

## 2. Clone the Repository

Replace the placeholder with the repository URL:

```bash
git clone <REPOSITORY_URL>
cd <PROJECT_FOLDER>
```

## 3. Environment Setup

Linux/macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Required for incident search and ingestion:

- `GEMINI_API_KEY`

Required only for ServiceNow ingestion:

- `SERVICENOW_INSTANCE_URL`
- `SERVICENOW_USERNAME`
- `SERVICENOW_PASSWORD`
- `SERVICENOW_CLIENT_ID`
- `SERVICENOW_CLIENT_SECRET`

Required for authenticated API features:

- `JWT_SECRET_KEY`
- `STREAMLIT_COOKIE_SECRET`

Optional production search configuration:

- `AZURE_SEARCH_ENDPOINT`
- `AZURE_SEARCH_API_KEY`
- `AZURE_SEARCH_INDEX_NAME`

Do not commit `.env`. Replace the example secrets with long random values.

## 4. Azure AI Search vs ChromaDB

When all three Azure settings are populated, the backend uses Azure AI Search:

- `AZURE_SEARCH_ENDPOINT`
- `AZURE_SEARCH_API_KEY`
- `AZURE_SEARCH_INDEX_NAME`

Azure AI Search is the production vector database. When those values are missing, the incident search API uses persistent ChromaDB as the local development fallback. Chroma data is stored under `/app/data/chroma` in the container and is persisted to the host `data` directory.

If Azure is configured but unavailable, the API returns an error. It does not silently switch to ChromaDB.

## 5. Build Docker Image

```bash
docker build -t cim-backend .
```

## 6. Run Docker Container

Linux/macOS:

```bash
docker run --name cim-backend \
  --env-file .env \
  -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  cim-backend
```

Windows PowerShell:

```powershell
docker run --name cim-backend `
  --env-file .env `
  -p 8000:8000 `
  -v "${PWD}/data:/app/data" `
  cim-backend
```

The image contains the local `data/` directory and uses the copied ChromaDB by default. ServiceNow ingestion is disabled by default. Set `RUN_INGESTION_ON_STARTUP=true` only when you intentionally want to fetch and embed incidents at container startup.

The API listens on port `8000`.

To refresh the copied ChromaDB before building the image, run ingestion locally from the project root:

```bash
PYTHONPATH=. python backend/rag/servicenow_incident_ingestion.py
```

The command fetches ServiceNow incidents, generates embeddings, and writes ChromaDB files to `./data/chroma`. Rebuild the Docker image after refreshing the data.

To explicitly use the copied vectors without ingestion, set this in `.env`:

```env
RUN_INGESTION_ON_STARTUP=false
```

Then start the API container:

```bash
docker run -d --name cim-backend \
  --env-file .env \
  -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  --restart unless-stopped \
  cim-backend
```

## 7. Verify Backend

Open the health endpoint:

```text
http://localhost:8000/health
```

Expected response:

```json
{"status":"healthy"}
```

Open Swagger documentation at:

```text
http://localhost:8000/docs
```

Incident search endpoint:

```text
POST http://localhost:8000/api/v1/incidents/search
```

## 8. Running Without Docker

This repository also supports local Python execution:

```bash
python -m venv .venv
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies and start the backend:

If the host network uses corporate TLS inspection, obtain the approved organization root CA certificate from your IT team. Do not disable certificate verification. Mount the certificate and set `SSL_CERT_FILE`:

```bash
sudo docker run --rm \
  --env-file .env \
  -e SSL_CERT_FILE=/app/certs/company-root-ca.pem \
  -v "$(pwd)/certs/company-root-ca.pem:/app/certs/company-root-ca.pem:ro" \
  cim-backend:local \
  python backend/rag/servicenow_incident_ingestion.py
```
```bash
pip install -r requirements.txt
PYTHONPATH=. uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

To run the ServiceNow ingestion script separately:

```bash
PYTHONPATH=. python servicenow_incident_ingestion.py
```

## 9. Common Errors and Solutions

### Docker is not running

Start Docker Engine or Docker Desktop, then retry the build or run command.

### Port 8000 is already in use

Use another host port:

```bash
docker run --env-file .env -p 8001:8000 cim-backend
```

Then open `http://localhost:8001`.

### Gemini API key is missing

Set `GEMINI_API_KEY` in `.env` and restart the container. The key is required when calling incident search or ingestion, not for `/health`.

### TLS certificate verification failed

The image installs the standard CA certificates required for Gemini HTTPS connections. Rebuild the image after changing the Dockerfile:

```bash
sudo docker build --no-cache -t cim-backend:local .
```

If the host network uses corporate TLS inspection, obtain the approved organization root CA certificate from your IT team. Do not disable certificate verification. Mount the certificate and set `SSL_CERT_FILE`:

```bash
sudo docker run --rm \
  --env-file .env \
  -e SSL_CERT_FILE=/app/certs/company-root-ca.pem \
  -v "$(pwd)/certs/company-root-ca.pem:/app/certs/company-root-ca.pem:ro" \
  cim-backend:local \
  python backend/rag/servicenow_incident_ingestion.py
```

The certificate must be a trusted CA supplied by your organization. Never use `verify=False` or commit the certificate/private keys to Git.

Before mounting a corporate CA, verify that the source is a regular certificate file:

```bash
test -f certs/company-root-ca.crt && \
  openssl x509 -in certs/company-root-ca.crt -noout -subject -issuer
```

If Docker previously created `certs/company-root-ca.crt` as a directory because the source file did not exist, remove it and place the approved certificate at that exact path:

```bash
sudo rm -rf certs/company-root-ca.crt
mkdir -p certs
# Copy the approved company-root-ca.crt file into certs/ before running Docker.
```

If mounting the certificate with only `SSL_CERT_FILE` still fails, install it into the image trust store at container startup:

```bash
sudo docker run --rm \
  --env-file .env \
  -v "$(pwd)/certs/company-root-ca.crt:/usr/local/share/ca-certificates/company-root-ca.crt:ro" \
  cim-backend:local \
  sh -c "update-ca-certificates && python -c \"import urllib.request; print(urllib.request.urlopen('https://generativelanguage.googleapis.com').status)\""
```

If the command prints an HTTP status such as `404`, use the same mount and startup command for the application:

```bash
sudo docker rm -f cim-backend 2>/dev/null || true
sudo docker run -d --name cim-backend \
  --env-file .env \
  -v "$(pwd)/certs/company-root-ca.crt:/usr/local/share/ca-certificates/company-root-ca.crt:ro" \
  -v "$(pwd)/data:/app/data" \
  -p 8000:8000 \
  cim-backend:local \
  sh -c "set -e; update-ca-certificates; python backend/rag/servicenow_incident_ingestion.py; exec uvicorn backend.main:app --host 0.0.0.0 --port 8000"
```

If HTTPS works in WSL but fails only inside Docker, the WSL CA bundle may already contain the corporate CA. Test the image with the host bundle mounted read-only:

```bash
sudo docker run --rm \
  --env-file .env \
  -e SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
  -v /etc/ssl/certs/ca-certificates.crt:/etc/ssl/certs/ca-certificates.crt:ro \
  cim-backend:local \
  python -c "import urllib.request; print(urllib.request.urlopen('https://generativelanguage.googleapis.com').status)"
```

An HTTP status such as `404` is acceptable for this test: it proves that TLS verification succeeded and the request reached Google. If this test succeeds, use the same CA-bundle mount when running the API container:

```bash
sudo docker run -d --name cim-backend \
  --env-file .env \
  -e SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
  -v /etc/ssl/certs/ca-certificates.crt:/etc/ssl/certs/ca-certificates.crt:ro \
  -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  cim-backend:local
```

### Azure credentials are missing

This is valid for local development. The incident search API uses persistent ChromaDB when all Azure settings are not configured.

### Container exits immediately

Inspect the container state and logs:

```bash
docker ps -a
docker logs cim-backend
```

## 10. Stop the Application

```bash
docker ps
docker stop cim-backend
```

Remove the stopped container when needed:

```bash
docker rm cim-backend
```

With Compose:

```bash
docker compose down
```

## 11. Push the Docker Image

The image does not contain `.env` or application secrets. Pass `.env` only when running the container.

### Docker Hub

Replace `DOCKERHUB_USERNAME` with your Docker Hub username and choose an image name:

```bash
docker login
docker build -t DOCKERHUB_USERNAME/cim-backend:latest .
docker push DOCKERHUB_USERNAME/cim-backend:latest
```

Run the pushed image on another machine:

```bash
docker run --name cim-backend \
  --env-file .env \
  -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  DOCKERHUB_USERNAME/cim-backend:latest
```

### Azure Container Registry

Replace `REGISTRY_NAME` with the Azure Container Registry name. The registry login server is usually `REGISTRY_NAME.azurecr.io`:

```bash
az login
az acr login --name REGISTRY_NAME
docker build -t REGISTRY_NAME.azurecr.io/cim-backend:latest .
docker push REGISTRY_NAME.azurecr.io/cim-backend:latest
```

Run the Azure Container Registry image:

```bash
docker run --name cim-backend \
  --env-file .env \
  -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  REGISTRY_NAME.azurecr.io/cim-backend:latest
```

## 12. Run the Published Image in Another Environment

The published Docker Hub image is:

```text
narenabinbev/cim-backend:latest
```

On the new machine, install Docker Engine or Docker Desktop, then clone the repository. Do not copy the local `.env`, databases, virtual environment, or Chroma files.

Create the environment file:

```bash
cp .env.example .env
```

Edit `.env` and provide at least:

```text
GEMINI_API_KEY=your-gemini-api-key
JWT_SECRET_KEY=your-random-jwt-secret
STREAMLIT_COOKIE_SECRET=your-random-cookie-secret
```

To use Azure AI Search in production, also provide all three Azure values:

```text
AZURE_SEARCH_ENDPOINT=your-azure-search-endpoint
AZURE_SEARCH_API_KEY=your-azure-search-api-key
AZURE_SEARCH_INDEX_NAME=incidents
```

Pull and start the API image:

```bash
docker pull narenabinbev/cim-backend:latest
mkdir -p data
docker run -d --name cim-backend \
  --env-file .env \
  -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  --restart unless-stopped \
  narenabinbev/cim-backend:latest
```

Verify the container and API:

```bash
docker ps
curl http://localhost:8000/health
docker logs cim-backend
```

Expected health response:

```json
{"status":"healthy"}
```

Open the API documentation at `http://localhost:8000/docs`.

The container normally ingests before starting FastAPI. If automatic ingestion is disabled and the API container is already running, ingestion can be started manually inside it:

```bash
docker exec cim-backend python backend/rag/servicenow_incident_ingestion.py
```

Ingestion requires the ServiceNow variables in `.env`. Its Chroma data is written to the mounted host directory `./data/chroma`.

For a different host port, such as `8001`:

```bash
docker run -d --name cim-backend \
  --env-file .env \
  -p 8001:8000 \
  -v "$(pwd)/data:/app/data" \
  narenabinbev/cim-backend:latest
```

Then use `http://localhost:8001/health` and `http://localhost:8001/docs`.
