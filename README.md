# CloudOptima — Multi-Cloud Spot Cost Intelligence

CloudOptima is a demo-first application for comparing AWS, Google Cloud, and Azure spot/preemptible compute costs. It provides normalized sample price records, deterministic cost calculations, a transparent provider recommendation, and a safe migration state-machine simulation.

> **Important:** The included prices are illustrative sample inputs, not live provider quotes. This build has no live spot-price or cloud provisioning adapters. Migration actions are simulations and do not create, modify, or terminate cloud resources.

## What works

- Responsive React dashboard with pricing, calculator, decision engine, migration center, analytics, and integration settings.
- FastAPI endpoints for sample pricing, deterministic cost analysis, provider recommendation, migration simulation, analytics, settings, and mock DNS validation.
- Pydantic validation and deterministic cost/eligibility logic.
- Explicit demo-only US East region grouping; no general region equivalence is inferred.
- Migration state machine with health-check failure, cancellation, source-workload safety, transition history, and unique IDs.
- Optional asynchronous MongoDB persistence. If MongoDB is unavailable, the backend logs a warning and reports that it is using in-memory demo storage; this data is not durable.
- Focused pytest suite for calculations, pricing validation/freshness, recommendations, migration transitions, and the mock DNS adapter.

## Architecture

```text
React + Vite frontend  ── REST/JSON ──>  FastAPI backend
                                             ├── Pydantic request/data contracts
                                             ├── deterministic pricing, cost, decision services
                                             ├── simulation migration state machine
                                             ├── mock DNS adapter
                                             └── MongoDB (optional) / explicit memory demo store
```

MongoDB collections are prepared with indexes for `pricing_snapshots`, `workload_configs`, `cost_analyses`, `migrations`, and `audit_logs`. Cost analyses, price refreshes, migration state, and decision audit events use the store. Workload configuration and audit records are not yet exposed as CRUD APIs. MongoDB is shared application metadata in this demo; it does not replicate application-specific mutable state or provide cross-region disaster recovery.

## Technology

- Frontend: React 19 and Vite. The existing JavaScript starter is reused, with responsive CSS and native chart/table rendering.
- Backend: Python, FastAPI, Pydantic, asynchronous PyMongo, and pytest.
- Optional database: MongoDB Atlas or local MongoDB.
- Live cloud SDKs, provider pricing APIs, DNS integrations, React Router, TypeScript, Tailwind, shadcn/ui, Recharts, Axios, and TanStack Query are **not wired in this demo build**. The UI does not imply otherwise.

## Folder structure

```text
CloudOptima/
├── backend/
│   ├── app/
│   │   ├── adapters/       # mock DNS adapter
│   │   ├── routers/        # health, pricing, costs, decisions, analytics, migrations
│   │   ├── services/       # pricing, cost, decisions, migration state machine
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── main.py         # API composition and OpenAPI docs
│   │   └── schemas.py
│   ├── tests/
│   ├── .env.example
│   └── requirements.txt
├── src/                    # existing React app, completed in place
├── .env.example
└── README.md
```

## Prerequisites

- Node.js 20.19+ or 22.12+ and npm.
- Python 3.11 or later. Python 3.14 is supported by the installed dependencies used here.
- MongoDB is optional for the demo. Without it, API persistence is in-memory for the lifetime of the backend process.

## Windows PowerShell setup

Run commands from the project folder (`C:\CloudOptima`).

### 1. Configure environment

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
```

The checked-in `backend\.env` contains only safe local demo defaults and empty secret placeholders. Keep real credentials out of source control.

### 2. Create the Python environment and install backend dependencies

```powershell
python --version
python -m venv backend\.venv
.\backend\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
```

Use Python 3.11 or later. This workspace was verified with Python 3.14.8.

If PowerShell blocks activation, use this for the current terminal only, or run the venv interpreter directly:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 3. Start the API (Terminal 1)

```powershell
Set-Location C:\CloudOptima
.\backend\.venv\Scripts\Activate.ps1
uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

The API is at `http://localhost:8000`; interactive OpenAPI documentation is at `http://localhost:8000/docs`.

### 4. Install frontend dependencies and start Vite (Terminal 2)

```powershell
Set-Location C:\CloudOptima
npm install
npm run dev
```

Open the URL Vite prints (normally `http://localhost:5173`). To use another API URL, set the public frontend variable `VITE_API_URL` in the root `.env` and restart Vite. Never put credentials in a `VITE_` variable.

### 5. Run checks

In the backend environment:

```powershell
Set-Location C:\CloudOptima\backend
.\.venv\Scripts\python.exe -m pytest tests
```

From the project root:

```powershell
npm run build
npm run lint
```

## MongoDB Atlas (optional)

1. Create an Atlas project and a free or appropriately sized cluster.
2. Create a database user with a strong unique password.
3. In Atlas Network Access, allow only the IP addresses that need access; avoid `0.0.0.0/0` except for a temporary, controlled test.
4. Copy the Python-driver connection string from Atlas and URL-encode special characters in the password.
5. Set `MONGODB_URI` in `backend\.env` and optionally change `DATABASE_NAME`.
6. Restart the backend and inspect `GET /api/health`. It reports `database.status=connected` and `persistence=mongodb` only after successful connection and index creation. Otherwise the API warns and identifies its memory-only fallback.

Database user credentials must stay in the backend environment. Do not put them into the frontend environment or browser storage.

## API reference

All routes are prefixed with `/api`. Requests and responses use JSON except the simple DNS simulation parameters. Validation errors use FastAPI's standard structured `detail`; unknown migration IDs return 404 and invalid state transitions return 409.

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/health` | API, MongoDB persistence mode, and integration status |
| GET | `/api/pricing` | Clearly labeled demo price records and warnings |
| POST | `/api/pricing/refresh` | Create new demo snapshots (does not call provider APIs) |
| POST | `/api/cost/calculate` | Validate and calculate one deterministic cost estimate |
| POST | `/api/decisions/recommend` | Rank eligible providers and explain rejected/no-savings outcomes |
| GET | `/api/analytics/savings` | Saved analyses and migration counts |
| POST | `/api/migrations` | Create an explicitly simulated migration |
| GET | `/api/migrations` | List migrations |
| GET | `/api/migrations/{migration_id}` | Get a migration and its timeline |
| POST | `/api/migrations/{migration_id}/advance` | Advance one simulated state; health-check gate at `HEALTH_CHECK` |
| POST | `/api/migrations/{migration_id}/cancel` | Cancel a non-terminal simulation |
| GET | `/api/settings/status` | Same integration and persistence status as health |
| POST | `/api/dns/simulate?endpoint=https%3A%2F%2Fexample.org&healthy=true` | Validate a target and simulate mock DNS behavior |

An example request collection is in [backend/requests.http](backend/requests.http).

## Demo and live integration status

The application starts in demo mode without cloud credentials. Demo records are generated locally and include their source, timestamp, freshness, and unavailable-capacity caveat. Refreshing pricing only makes a new demo snapshot.

Live provider pricing, real cloud provisioning, real DNS failover, scheduled refresh, WebSockets, and Groq explanations are not implemented or enabled. AWS, GCP, and Azure credentials are not needed to run the demo. `APP_ENV` and provider-related environment variables are placeholders for future adapters; setting credentials alone does not enable live operations. The health response reports unsupported integrations as unavailable. No billable cloud resource operation is performed by this application.

### Credentials to obtain only when implementing integrations

None of these credentials are required for the current demo, and entering them will not turn on live integration:

- **AWS:** use an IAM role or named AWS CLI profile rather than embedding access keys. A future read-only spot-price adapter would need the specific EC2 spot-price history read permission; provisioning would require a separately reviewed permission set and remains disabled.
- **GCP:** create/select a project in Google Cloud Console. For local development use Application Default Credentials (`gcloud auth application-default login`); for hosted services use a narrowly scoped service account. Do not grant project-wide Editor for pricing.
- **Azure:** obtain the subscription ID from Azure Portal and use a Microsoft Entra application or managed identity for future server-side access. Keep read-only pricing access separate from any future resource-write permissions.
- **MongoDB Atlas:** create a database user and copy the application connection string from the Atlas cluster's Connect flow.
- **Groq (optional, not wired):** create an API key in the Groq Console; it must remain backend-only.
- **DNS (mock only):** credentials would come from the selected DNS provider's API-token management page, scoped to the intended zone. No real DNS adapter is included.

## Security and billing

- Do not commit `.env` files, service-account files, cloud keys, database passwords, or DNS tokens.
- Keep backend secrets server-side; only `VITE_API_URL` is suitable for frontend configuration.
- CORS allows only `FRONTEND_ORIGIN` (default `http://localhost:5173`).
- No authentication/authorization is implemented; do not expose this demo API to untrusted networks.
- Do not use demo output as a purchasing decision or a cloud-provider quote.
- Real migration/provisioning and DNS changes are disabled. Adding them would require explicit authorization, confirmation, safe resource scoping, and billing safeguards.
- DNS changes, if added later, can take time to propagate and must be independently verified.

## Demo walkthrough

1. Start backend and frontend in separate PowerShell terminals.
2. Open **Cloud pricing** and note that all three provider prices are labeled as sample estimates.
3. Open **Cost calculator**, adjust duration and one-time egress/migration assumptions, and calculate the itemized result.
4. Open **Decision engine**, set capacity and savings constraints, then run the analysis. The engine may recommend staying on the current provider if no candidate clears the configured threshold.
5. Start a migration simulation. Advance through each state; at **Health check**, uncheck the success box and advance to observe the safe failure path, or leave it selected to progress through traffic switching and verification.
6. Review **Analytics** and **Settings** to see migration counts and database/integration health.

## Limitations and next steps

- The UI is React/JavaScript rather than TypeScript and uses native CSS and chart rendering rather than the full requested frontend library list.
- No provider price retrieval, availability/capacity APIs, cloud SDK adapters, authentication, DNS provider, background scheduler, or WebSocket progress transport is connected.
- Demo region groups are intentionally limited; location equivalence and availability need provider-specific verified data before real comparison.
- Browser-only fallback interactions are visibly described as local simulations; they are not persisted to the backend.
- For production use, implement and test each cloud adapter independently, require explicit operation confirmation, add authentication/authorization, and establish persistence/backup and disaster-recovery policies.
#   C l o u d O p t i m a  
 