# Setup and Deployment Guide

## 1. System Requirements
- **Operating System:** macOS (Apple Silicon / Intel), Linux (Ubuntu 22.04+), or Windows (WSL2)
- **Python:** 3.12 or 3.14+
- **Node.js:** 18.0.0+ and `npm` 9.0.0+
- **Docker:** (Optional) Docker 24.0+ and Docker Compose v2

---

## 2. Local Environment Setup

### 2.1 Backend Setup
```bash
# Navigate to workspace
cd /Users/tejashr/Downloads/enterprise-agentic-ops-workspace

# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install exact pinned dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
```

### 2.2 Frontend Setup
```bash
cd frontend
npm install
npm run build
```

---

## 3. Running the Applications Locally

### Terminal 1: Backend Server (FastAPI)
```bash
cd /Users/tejashr/Downloads/enterprise-agentic-ops-workspace
PYTHONPATH=.:backend .venv/bin/uvicorn backend.src.main:app --host 127.0.0.1 --port 8000 --reload
```
- API Base: `http://localhost:8000`
- Interactive OpenAPI Docs: `http://localhost:8000/docs`
- Live Health Probe: `http://localhost:8000/health/live`
- Ready Health Probe: `http://localhost:8000/health/ready`

### Terminal 2: Frontend Web UI (Vite + React)
```bash
cd /Users/tejashr/Downloads/enterprise-agentic-ops-workspace/frontend
npm run dev -- --port 5173
```
- Web Application: `http://localhost:5173`

---

## 4. Running the Verification Test Suite
Execute the comprehensive 30-test automated regression suite:
```bash
cd /Users/tejashr/Downloads/enterprise-agentic-ops-workspace
.venv/bin/pytest -v --junitxml=artifacts/test-results.xml
```
Test results will be exported to `artifacts/test-results.xml`.

---

## 5. Running the Empirical Benchmark Suite
To measure real latency percentiles on the local hardware:
```bash
cd /Users/tejashr/Downloads/enterprise-agentic-ops-workspace
PYTHONPATH=.:backend .venv/bin/python artifacts/benchmark_harness.py
```
Benchmark results will be persisted to `artifacts/benchmark-results.json`.

---

## 6. Docker Container Deployment
To run both backend and frontend in containerized production mode:
```bash
docker compose up --build -d
```
- Web Application: `http://localhost:3000`
- Backend API: `http://localhost:8000`
