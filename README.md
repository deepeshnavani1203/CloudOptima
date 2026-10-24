# CloudOptima — Multi-Cloud Spot Cost Intelligence

CloudOptima is a React + FastAPI cost-optimization workspace focused on Google Cloud Platform and Microsoft Azure. It retrieves public provider catalog data, normalizes supported hourly prices, saves observations when persistence is available, calculates cost estimates, and runs conservative decision analyses. Migration workflows remain simulations only.

> **Pricing caveat:** Public retail catalog data is not a negotiated contract rate, actual bill, capacity guarantee, or deployed-resource cost. Unsupported pricing units, currency, model, or machine specifications remain explicit and are excluded from recommendations. AWS pricing is out of scope.

## Features

- Responsive React dashboard: overview, pricing, calculator, decision engine, migration center, analytics, and settings.
- FastAPI endpoints with Pydantic validation and REST/JSON contracts.
- Backend-only Google Cloud Billing Catalog and Azure Retail Prices API adapters with bounded pagination, request timeouts, cache, and partial-provider failure handling.
- Normalized pricing snapshots with source SKU/meter identifiers, price-model evidence, currency, native units, fetch time, and freshness.
- Deterministic cost calculation, one-time migration/transfer costs, break-even, and savings threshold checks.
- Conservative decision response: incomplete specs, stale data, unsupported rates, incompatible regions/models, or non-USD pricing are excluded.
- Simulated migration states with health-check gate, cancellation, transition history, and source-workload safety.
- Optional MongoDB persistence; when unavailable, the API explicitly reports memory-only storage.
- Mock-only DNS adapter. No real DNS updates or cloud provisioning are enabled.

## Architecture and folder structure

```text
CloudOptima/
├── backend/
│   ├── app/
│   │   ├── adapters/       # GCP/Azure pricing and mock DNS adapters
│   │   ├── routers/        # health, pricing, costs, decisions, analytics, migrations
│   │   ├── services/       # normalization, costs, decisions, migration state machine
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── main.py
│   │   └── schemas.py
│   ├── tests/
│   ├── .env                # local config; ignored by Git
│   ├── .env.example
│   ├── pyproject.toml
│   ├── uv.lock
│   └── .venv/              # created locally by uv; ignored by Git
├── src/                    # existing React/Vite frontend
├── .env.example            # public Vite API URL only
├── PROFESSOR_DEMO_GUIDE.md
└── README.md
```

MongoDB stores historical `pricing_snapshots`, `cost_analyses`, `decision_analyses`, migration simulations in the existing `migrations` collection, and audit events in the existing `audit_logs` collection. Pricing snapshots retain provider identifiers and observation timestamps rather than replacing older observations. These records power the explorer, workspace history, and deterministic recommendations. MongoDB is optional; memory mode is reported and is not durable across API restarts.

## Technology and limitations

- Frontend: React and Vite using the existing JavaScript starter, responsive CSS, and native chart/table rendering.
- Backend: Python 3.11+, FastAPI, Pydantic, asynchronous PyMongo, `uv`, and pytest.
- Optional database: MongoDB Atlas or a local MongoDB instance.
- Not connected: cloud SDK provisioning, real DNS failover, authentication, scheduled refresh, WebSockets, or Groq explanations. TypeScript, Tailwind, React Router, Recharts, Axios, TanStack Query, and shadcn/ui are not used in this version.
- AWS pricing is deliberately not integrated. Existing provider enums remain for backward compatibility in non-pricing APIs.

## Prerequisites

- Node.js 20.19+ or 22.12+ and npm.
- Python 3.11+.
- `uv` installed and available in PowerShell.
- MongoDB is optional. Without it, backend persistence is in-memory and records disappear when the API process stops.

## Windows PowerShell setup

Run from `C:\CloudOptima`.

### Environment files

Configure real local values in `backend\.env`; do not replace that file with the template. `backend\.env.example` is a reference template with placeholders and non-secret defaults. The root `.env.example` contains only `VITE_API_URL=http://localhost:8000/api`; frontend variables must never contain secrets. If you need to create a local file that does not yet exist:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
```

`GCP_BILLING_API_KEY` is used only by the backend catalog adapter. The public Azure Retail Prices API does not require `AZURE_SUBSCRIPTION_ID`; Azure pricing must be explicitly enabled with `AZURE_PRICING_ENABLED=true`. `GOOGLE_APPLICATION_CREDENTIALS` is not required for public catalog requests. Keep all secrets in `backend\.env`.

The backend supports `APP_ENV`, `DEMO_MODE`, `FRONTEND_ORIGIN`, `MONGODB_URI`, `DATABASE_NAME`, `GROQ_API_KEY`, `GROQ_MODEL`, `GCP_PROJECT_ID`, `GCP_BILLING_API_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`, `AZURE_SUBSCRIPTION_ID`, `AZURE_PRICING_ENABLED`, `DNS_ADAPTER`, and `DNS_API_TOKEN`. Only the GCP billing key is needed for the public GCP catalog; Azure's public retail catalog is anonymous. `GROQ_API_KEY` and the DNS token are not used by the current pricing path.

### Create/sync the backend virtual environment with uv

```powershell
Set-Location C:\CloudOptima\backend
uv --version
uv sync
```

`uv sync` uses `pyproject.toml` and `uv.lock`, creates `backend\.venv`, and installs the locked dependencies. To choose a specific installed interpreter (3.11 or later), use `uv sync --python 3.11`.

### Start the backend (Terminal 1)

```powershell
Set-Location C:\CloudOptima\backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API base: `http://localhost:8000/api`  
Interactive API docs: `http://localhost:8000/docs`

### Start the frontend (Terminal 2)

```powershell
Set-Location C:\CloudOptima
npm install
npm run dev
```

Open the Vite URL, normally `http://localhost:5173`.

### Run tests and frontend checks

```powershell
Set-Location C:\CloudOptima\backend
uv run pytest

Set-Location C:\CloudOptima
npm run build
npm run lint
```

## MongoDB Atlas (optional)

1. Create an Atlas project and cluster, then a database user.
2. Restrict Network Access to the application host's IP.
3. Copy the Python-driver connection URI from the Atlas cluster page.
4. Set `MONGODB_URI` in `backend\.env`, URL-encoding special characters in credentials.
5. Restart FastAPI and check `GET /api/health` for `database.status=connected` and `persistence=mongodb`.

MongoDB credentials stay in the backend environment. The frontend must never receive them.

## API endpoints

All endpoints use the `/api` prefix.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | API mode, persistence, and integration status |
| GET | `/pricing` | Stored normalized observations; supports provider, region, model, search, freshness, and pagination filters |
| POST | `/pricing/refresh` | Refresh configured GCP and Azure catalogs; accepts optional `?region=eastus` for Azure |
| GET | `/pricing/status` | Per-provider configuration, last attempt/success, cache, and safe error status |
| POST | `/cost/calculate` | Deterministic cost breakdown using caller-provided inputs |
| POST | `/decisions/recommend` | Filter and rank only valid, compatible, like-for-like price records |
| GET | `/analytics/savings` | Saved cost and decision analyses, price snapshots, and migration counts |
| POST | `/migrations` | Create a simulation only |
| GET | `/migrations` | List migration operations |
| GET | `/migrations/{migration_id}` | Fetch a migration and its timeline |
| POST | `/migrations/{migration_id}/advance` | Advance simulation and enforce health check |
| POST | `/migrations/{migration_id}/cancel` | Cancel a non-terminal simulation |
| GET | `/settings/status` | Integration and persistence status |
| POST | `/dns/simulate?endpoint=https%3A%2F%2Fexample.org&healthy=true` | Validate endpoint and run mock DNS response |

See [backend/requests.http](backend/requests.http) for API examples. Any calculator numbers there are labeled classroom examples, not provider prices.

## Demo versus live mode

The app starts without provider credentials. GCP needs a backend API key; Azure's public catalog is enabled separately by configuration. Missing or failed integrations are reported without erasing the other provider's data. Cached results retain their original observation timestamps. The decision engine stays on the current provider if it cannot verify an eligible alternative. The migration workflow is simulation-only.

GCP and Azure catalog refreshes may make public HTTPS requests when you use **Refresh pricing**. Tests mock provider requests and do not require credentials. MongoDB is optional. No cloud resource or real DNS operation is performed.

## Security and billing notes

- `.env`, `.venv`, credentials, caches, build files, and logs are excluded by `.gitignore`.
- No secrets belong in the root/Vite environment.
- CORS is restricted to `FRONTEND_ORIGIN`.
- Authentication is not implemented; do not expose this demo API to an untrusted network.
- No live or billable cloud operations occur. Any future resource-writing integration must require separately reviewed least-privilege permissions, explicit confirmation, and billing safeguards.
- DNS propagation is not instantaneous and must be independently checked if a real integration is ever added.

The backend returns safe provider errors without response bodies, authorization headers, or API keys. GCP credentials are sent in a backend request header and are never returned to the browser.

Provider references: [Google Cloud Billing Catalog API](https://cloud.google.com/billing/v1/how-tos/catalog-api) and [Azure Retail Prices REST API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices). Refresh is bounded and cached; the API's catalog records may not expose comparable whole-instance prices or verified machine specifications, so such rows are shown as unsupported and excluded from recommendations.
