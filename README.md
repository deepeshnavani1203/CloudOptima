# CloudOptima — Multi-Cloud Spot Cost Intelligence

CloudOptima is a demo-first application for comparing AWS, Google Cloud, and Azure spot/preemptible compute costs. It provides a React dashboard, deterministic cost calculations, a conservative decision engine, and a safe migration state-machine simulation.

> **Pricing status:** No provider pricing adapters or credentials are configured. The application intentionally displays no provider prices rather than inventing them. Calculator figures must be entered by the user. Migration actions are simulations only and never create or modify real cloud resources.

## Features

- Responsive React dashboard: overview, pricing, calculator, decision engine, migration center, analytics, and settings.
- FastAPI endpoints with Pydantic validation and REST/JSON contracts.
- Deterministic cost calculation, one-time migration/transfer costs, break-even, and savings threshold checks.
- Conservative decision response: without provider price records, it stays on the current cloud and reports that a recommendation cannot be verified.
- Simulated migration states with health-check gate, cancellation, transition history, and source-workload safety.
- Optional MongoDB persistence; when unavailable, the API explicitly reports memory-only storage.
- Mock-only DNS adapter. No real DNS updates or cloud provisioning are enabled.

## Architecture and folder structure

```text
CloudOptima/
├── backend/
│   ├── app/
│   │   ├── adapters/       # mock DNS adapter
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

MongoDB collection indexes are prepared for pricing snapshots, workload configurations, cost analyses, migrations, and audit logs. Current APIs persist cost analyses, migration records, and decision audit data. Pricing snapshots remain empty because no pricing adapter is available; workload configuration has no CRUD API yet. The database stores shared application metadata; this project does not implement cross-cloud or cross-region disaster recovery.

## Technology and limitations

- Frontend: React and Vite using the existing JavaScript starter, responsive CSS, and native chart/table rendering.
- Backend: Python 3.11+, FastAPI, Pydantic, asynchronous PyMongo, `uv`, and pytest.
- Optional database: MongoDB Atlas or a local MongoDB instance.
- Not connected: live AWS/GCP/Azure pricing, cloud SDK provisioning, real DNS failover, auth, scheduled refresh, WebSockets, or Groq. TypeScript, Tailwind, React Router, Recharts, Axios, TanStack Query, and shadcn/ui are not used in this version.

## Prerequisites

- Node.js 20.19+ or 22.12+ and npm.
- Python 3.11+.
- `uv` installed and available in PowerShell.
- MongoDB is optional. Without it, backend persistence is in-memory and records disappear when the API process stops.

## Windows PowerShell setup

Run from `C:\CloudOptima`.

### Environment files

`backend\.env` is already created with local demo settings, including:

- `FRONTEND_ORIGIN=http://localhost:5173`
- `MONGODB_URI=mongodb://localhost:27017`
- `DATABASE_NAME=cloudoptima`
- Demo mode enabled and optional provider credentials left blank

`backend\.env.example` documents backend variables. The root `.env.example` contains only `VITE_API_URL=http://localhost:8000/api`; frontend variables must never contain secrets. If you need to recreate either file:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
```

No cloud API links or credentials were supplied, and those integrations are not implemented. Do not invent values for them. Add only real URLs/credentials obtained from provider consoles, and keep secrets in `backend\.env`.

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
| GET | `/pricing` | Configured normalized prices; currently an empty list with an availability warning |
| POST | `/pricing/refresh` | Check configured adapters; currently reports none available |
| POST | `/cost/calculate` | Deterministic cost breakdown using caller-provided inputs |
| POST | `/decisions/recommend` | Rank known candidates or safely stay put if pricing is unavailable |
| GET | `/analytics/savings` | Saved analyses and migration counts |
| POST | `/migrations` | Create a simulation only |
| GET | `/migrations` | List migration operations |
| GET | `/migrations/{migration_id}` | Fetch a migration and its timeline |
| POST | `/migrations/{migration_id}/advance` | Advance simulation and enforce health check |
| POST | `/migrations/{migration_id}/cancel` | Cancel a non-terminal simulation |
| GET | `/settings/status` | Integration and persistence status |
| POST | `/dns/simulate?endpoint=https%3A%2F%2Fexample.org&healthy=true` | Validate endpoint and run mock DNS response |

See [backend/requests.http](backend/requests.http) for API examples. Any calculator numbers there are labeled classroom examples, not provider prices.

## Demo versus live mode

The app works without cloud credentials. The pricing list remains empty because live provider adapters are not implemented. Cost calculations work with user-entered inputs. Without actual price records, the decision engine refuses to recommend moving clouds. The migration workflow can be exercised in simulation mode and is clearly distinguished from a real deployment.

No AWS, GCP, Azure, DNS, or Groq account is required to run this build. Setting credentials in `.env` does not enable unsupported integrations.

## Security and billing notes

- `.env`, `.venv`, credentials, caches, build files, and logs are excluded by `.gitignore`.
- No secrets belong in the root/Vite environment.
- CORS is restricted to `FRONTEND_ORIGIN`.
- Authentication is not implemented; do not expose this demo API to an untrusted network.
- No live or billable cloud operations occur. Any future resource-writing integration must require separately reviewed least-privilege permissions, explicit confirmation, and billing safeguards.
- DNS propagation is not instantaneous and must be independently checked if a real integration is ever added.

For the professor-ready presentation sequence and classroom-only calculator example, see [PROFESSOR_DEMO_GUIDE.md](./PROFESSOR_DEMO_GUIDE.md).
