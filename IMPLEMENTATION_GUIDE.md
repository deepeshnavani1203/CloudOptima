# CloudOptima Implementation Guide

Practical setup, runbook, configuration, testing, troubleshooting, and extension notes for the **current repository**.

> **Status first:** This repository has a working React/Vite UI and FastAPI demo API. It does **not** have live AWS/GCP/Azure price adapters or cloud provisioning. The pricing endpoints deliberately return no price records. Do not enter classroom/example values as provider prices or put secrets in the frontend.

## 1. Prerequisites

- Windows 10/11 and PowerShell.
- Node.js 20.19+ or 22.12+ with npm (Vite 8 requirement).
- Python 3.11+ and [`uv`](https://docs.astral.sh/uv/getting-started/installation/).
- Optional MongoDB: local server or MongoDB Atlas. The app can start without it, using explicitly reported in-memory storage.
- AWS, GCP, Azure, Groq, and DNS credentials are **not required** for the current demo.

## 2. Repository map
    
```text
C:\CloudOptima\
├── backend\
│   ├── app\
│   │   ├── adapters\dns.py       # mock DNS behavior only
│   │   ├── routers\              # FastAPI route groups
│   │   ├── services\             # cost, decision, migration, price validation
│   │   ├── config.py             # loads backend\.env
│   │   ├── db.py                 # async MongoDB / memory store
│   │   ├── main.py               # FastAPI app and CORS
│   │   └── schemas.py            # Pydantic contracts
│   ├── tests\                    # pytest tests
│   ├── .env                      # local-only configuration; ignored by Git
│   ├── .env.example
│   ├── pyproject.toml
│   ├── uv.lock
│   └── .venv\                    # local uv environment; ignored by Git
├── src\                          # React/Vite JavaScript frontend
├── .env.example                  # public VITE_API_URL only
├── package.json
└── vite.config.js
```

The project name in `package.json` and backend metadata is CloudOptima. The requested product concept is a multi-cloud Spot Instance Arbitrage Engine.

## 3. Configure environment safely

The repository has a root `.env.example` with:

```dotenv
VITE_API_URL=http://localhost:8000/api
```

Backend settings live in `backend\.env`; `backend\app\config.py` loads that file. The template lists:

| Variable | Current purpose/status |
|---|---|
| `APP_ENV` | Environment label; defaults to `demo` |
| `DEMO_MODE` | Defaults to `true`; backend migration route blocks non-simulation operations |
| `FRONTEND_ORIGIN` | CORS origin; default `http://localhost:5173` |
| `MONGODB_URI` | MongoDB URI; default local URI `mongodb://localhost:27017` |
| `DATABASE_NAME` | Database name; default `cloudoptima` |
| `GROQ_API_KEY`, `GROQ_MODEL` | Optional placeholders; Groq is not implemented |
| `AWS_PROFILE`, `AWS_REGION` | Placeholders; no AWS adapter reads these |
| `GCP_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS` | Placeholders; no GCP adapter reads these |
| `AZURE_SUBSCRIPTION_ID` | Placeholder; no Azure adapter reads this |
| `DNS_ADAPTER`, `DNS_API_TOKEN` | Placeholders; only the mock DNS adapter exists |

If either environment file needs to be recreated, run from `C:\CloudOptima`:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
```

The frontend currently defaults to `http://localhost:8000/api` in `src\App.jsx`; setting the root `VITE_API_URL` overrides it. A Vite `VITE_` variable is public and gets included in browser code: never put API keys, passwords, or cloud credentials there.

Do not paste secrets into chat, commit them, or share screenshots that reveal them. The backend `.env` is ignored by Git; templates should contain placeholders only.

## 4. Create/sync the backend environment with uv

Open a PowerShell terminal:

```powershell
Set-Location C:\CloudOptima\backend
uv --version
uv sync
```

`uv sync` uses `pyproject.toml` and the committed `uv.lock`, creates `.venv` in the backend folder if needed, and installs locked runtime and development dependencies. No manual venv activation is needed when using `uv run`.

Optional: select a Python 3.11 interpreter if installed/available:

```powershell
uv sync --python 3.11
```

## 5. Start the application

Keep both terminals open.

### Terminal 1 — FastAPI

```powershell
Set-Location C:\CloudOptima\backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Verify:

- Health: [http://localhost:8000/api/health](http://localhost:8000/api/health)
- Interactive OpenAPI docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Pricing: [http://localhost:8000/api/pricing](http://localhost:8000/api/pricing)

Expected pricing response has `items: []` and warnings that no pricing source/adapters are configured. This is intentional; it is not a failed price refresh pretending to succeed.

### Terminal 2 — React/Vite

```powershell
Set-Location C:\CloudOptima
npm install
npm run dev
```

Open the local URL Vite prints, usually [http://localhost:5173](http://localhost:5173). Stop either server with `Ctrl+C` in that server's terminal.

## 6. MongoDB (optional)

The API starts when MongoDB is absent. At startup, the backend tries to ping MongoDB and create indexes. On failure it logs a warning and reports `persistence: memory` / `status: unavailable`; memory records disappear when the backend stops. This is not durable persistence.

### Local MongoDB

1. Install MongoDB Community Server using the official [MongoDB installation documentation](https://www.mongodb.com/docs/manual/installation/).
2. Start the MongoDB service.
3. Keep `MONGODB_URI=mongodb://localhost:27017` in `backend\.env`.
4. Restart FastAPI and check `/api/health` for `database.status=connected` and `database.persistence=mongodb`.

### MongoDB Atlas

1. Create a cluster and database user in [MongoDB Atlas](https://www.mongodb.com/cloud/atlas).
2. Restrict Network Access to your development IP; do not open access globally for convenience.
3. Use **Connect → Drivers** to obtain the URI.
4. Put it in `MONGODB_URI` in `backend\.env`, encoding special characters in the password.
5. Restart FastAPI and verify `/api/health`.

MongoDB collections/indexes are initialized in `backend\app\db.py`: `pricing_snapshots`, `workload_configs`, `cost_analyses`, `migrations`, and `audit_logs`. Presently the app persists cost analyses, migrations, and decision/migration audit entries. No workload-config CRUD endpoints exist, and pricing snapshots are not populated because adapters are absent.

## 7. What is implemented and how to demonstrate it

| Capability | Current status | What to show |
|---|---|---|
| Dashboard/navigation | Implemented in the React UI | Workspace status, empty-price warning, recent migrations |
| Cloud pricing view | UI and API routes exist; **no provider adapter/data** | Empty table and source-unavailable message |
| Cost calculator | Implemented; accepts user-entered assumptions | Enter clearly labeled classroom values; see breakdown |
| Decision API | Deterministic service exists; API supplies an empty candidate list | It keeps the current provider and reports no data |
| Browser decision fallback | Present, but no candidate data is loaded in the UI | It also declines to recommend without prices |
| Migration workflow | **Simulation only** | Create a simulation; advance steps; fail health check and show source remains active |
| Analytics | Basic saved analysis/migration counts | Explain that it depends on records saved in current memory/DB mode |
| Settings/health | Implemented status view and `/api/health` | Show integration unavailable and database mode |
| DNS | Mock adapter only | It validates URL/health and returns simulated DNS result |
| Live cloud prices/resources | **Not implemented** | Do not claim a live integration |
| Authentication, schedule, WebSocket, Groq | **Not implemented** | Future enhancements only |

For the presentation arithmetic, enter values manually rather than treating them as cloud quotes:

| Input | Example only |
|---|---:|
| Current provider/hourly rate | AWS / `$0.10` |
| Target provider/hourly rate | GCP / `$0.07` |
| Duration | 720 hours |
| Transfer cost | `$12` |
| Migration overhead | `$5` |
| Other costs | `$3` |
| Minimum savings | 1% |

Expected: current compute `$72.00`; target compute `$50.40`; target total `$70.40`; savings `$1.60` (about `2.22%`); break-even `(12+5+3)/(0.10-0.07) = 666.7` hours. These are hand-entered math examples, **not provider prices**. Excluded costs include tax, discounts, licensing, and services not manually included.

## 8. Current API reference

All endpoints use `/api`; request and response schemas are in `backend\app\schemas.py`. Detailed interactive docs are at `/docs`.

| Method | Route | Current behavior |
|---|---|---|
| GET | `/api/health` | Returns demo mode, MongoDB/memory status, and unavailable integration statuses |
| GET | `/api/pricing` | Returns an empty `items` list and pricing-unavailable warnings |
| POST | `/api/pricing/refresh` | Returns no items and states that no adapter was queried |
| POST | `/api/cost/calculate` | Validates costs/duration and returns breakdown, savings, break-even, assumptions; saves analysis |
| POST | `/api/decisions/recommend` | Calls deterministic decision service with `[]`; stays on current provider |
| GET | `/api/analytics/savings` | Returns saved analyses and migration success/failure counts |
| POST | `/api/migrations` | Creates an explicit simulation; rejects same-provider and non-simulation requests |
| GET | `/api/migrations` | Lists saved/in-memory simulations |
| GET | `/api/migrations/{migration_id}` | Gets one simulation or 404 |
| POST | `/api/migrations/{migration_id}/advance` | Advances one state; checks health at `HEALTH_CHECK`; rejects `confirm_live=true` |
| POST | `/api/migrations/{migration_id}/cancel` | Cancels a non-terminal simulation |
| GET | `/api/settings/status` | Returns health/integration status |
| POST | `/api/dns/simulate?endpoint=https%3A%2F%2Fexample.org&healthy=true` | Mock URL/health validation; no real DNS operation |

Example HTTP requests are in `backend\requests.http`. Its cost figures are labeled classroom examples.

## 9. Live pricing: what is required before it can work

**Putting a key in `.env` will not enable prices in this repository.** `backend\app\routers\pricing.py` always returns `items: []`; `/pricing/refresh` does not call a provider. `backend\app\routers\decisions.py` calls the decision engine with an empty list. Provider credential variables are placeholders and are not consumed by adapters.

### AWS

- The official EC2 [DescribeSpotPriceHistory API](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeSpotPriceHistory.html) returns Spot price history by parameters such as instance type, product description, and zone/region.
- Obtain AWS access through IAM/role/short-lived credentials. For local use, prefer an AWS CLI named profile or SSO; see [AWS CLI SSO setup](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html).
- Avoid root access keys and long-lived secrets; AWS explains the risk in [access-key guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html).
- A future adapter needs the EC2 read permission for Spot history (verify the exact current IAM action in AWS Service Authorization), region mapping, pagination, timestamps, product/platform filters, and handling for unavailable capacity. Spot price history alone is not a guarantee that capacity is available.
- `AWS_PROFILE`/`AWS_REGION` exist as placeholders; current code does not use them.

### Google Cloud

- The official [Cloud Billing Pricing API guide](https://cloud.google.com/billing/docs/how-to/get-pricing-information-api) describes service/SKU catalog prices. Public catalog requests use the documented API-key flow; enable the Billing API as the guide specifies.
- Google [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials) explains local and workload identity authentication where private/account-scoped APIs need it. Prefer ADC/attached identities over committed service-account JSON keys.
- Catalog/listed prices are not automatically an actual workload bill, Spot capacity signal, or guaranteed rate. Verify the SKU, region, unit, currency, and price type before comparison.
- `GCP_PROJECT_ID` and `GOOGLE_APPLICATION_CREDENTIALS` are placeholders only. No GCP code reads them.

### Azure

- Azure [Retail Prices REST API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices) provides public retail price data without a subscription secret for its public retail-rate queries. Its dataset can include VM Spot meters; filter the API results carefully by service, SKU/meter, region, price type, currency, unit, and effective date.
- Public retail rates are not automatically contract-specific billed costs, live Spot availability, or a promise of capacity.
- Subscription ID is visible in Azure Portal under **Subscriptions → your subscription → Overview**. Only future account-specific cost/resource integrations require an identity such as Microsoft Entra service principal or managed identity with least-privilege RBAC; see [create a service principal](https://learn.microsoft.com/en-us/entra/identity-platform/howto-create-service-principal-portal).
- `AZURE_SUBSCRIPTION_ID` is currently a placeholder. Current code does not call this API.

### Adapter implementation checklist

Before changing the decision endpoint to use real data:

1. Implement one provider adapter at a time under `backend\app\adapters\`.
2. Use official API/SDK, server-side credentials, request timeout, safe retry/backoff, pagination, and provider rate limits.
3. Normalize only comparable records: provider, region, exact instance/SKU, vCPU/RAM, Spot/Preemptible price type, hourly unit, USD currency, source, observation timestamp, freshness, and availability evidence.
4. Validate normalized records with `PriceRecord`; reject invalid currency, unit, missing required fields, incompatible region/size, stale or unsupported records. `normalize_price` and `is_fresh` currently exist as helpers but are not wired into a provider retrieval route.
5. Persist snapshots and return provenance to UI; distinguish public retail/catalog price, Spot history, cached/stale data, and actual billed costs.
6. Add adapter/API tests and verify permission failure, timeout, no results, currency/units, stale prices, and provider outages.
7. Enable recommendations only when eligible records exist and capacity/compatibility evidence is explicit. A price difference alone is not a safe move.

## 10. Tests and checks

Run backend tests:

```powershell
Set-Location C:\CloudOptima\backend
uv run pytest
```

Run frontend checks:

```powershell
Set-Location C:\CloudOptima
npm run build
npm run lint
```

The repository test suite covers pricing normalization/freshness helpers, cost formulas and validation, no-price/threshold decisions, migration transitions/health gate, mock DNS errors, MongoDB failure fallback, and API wiring.

## 11. Troubleshooting

| Symptom | Check / fix |
|---|---|
| `uv` is not recognized | Install `uv`, open a new PowerShell, run `uv --version`; then `uv sync` from `C:\CloudOptima\backend` |
| Backend import/module error | Confirm current directory is `C:\CloudOptima\backend`; run `uv sync`; use `uv run uvicorn app.main:app ...` |
| Port 8000 already in use | Stop the old server with `Ctrl+C`; alternatively choose another port and update `VITE_API_URL` plus `FRONTEND_ORIGIN` |
| Browser CORS error | Ensure API is on port 8000 and `FRONTEND_ORIGIN` in `backend\.env` exactly matches Vite origin, usually `http://localhost:5173`; restart API |
| Frontend says backend unavailable | Start FastAPI first; check `/api/health`; browser UI may fall back to local calculator/migration simulation only if the network request itself fails |
| API returns HTTP error | UI surfaces API error messages; check backend terminal logs and request/response in `/docs` |
| MongoDB warning / `memory` status | Start local MongoDB or configure Atlas URI/IP access; memory fallback is expected but does not survive restart |
| Pricing rows are empty | Expected currently. No pricing adapter is implemented. `.env` credentials alone do not change this |
| Recommendation keeps current provider | Expected with empty price list; the API does not invent a target |
| Calculator shows validation error | Use non-negative prices/costs and duration `> 0`; required provider fields must be selected |
| Provider auth/rate-limit error | Not applicable to current build because provider requests are not implemented; future adapters must report these explicitly |

## 12. Security and extension roadmap

- No authentication/authorization is implemented. Keep API on loopback for local demonstrations.
- Keep cloud/database keys in backend-only secret configuration. `.env` files, `.venv`, caches, and build outputs are ignored by `.gitignore`.
- Do not enable resource-write permissions for a demo. Real provisioning must remain disabled until explicit user confirmation, least-privilege scopes, budget safeguards, idempotency, health gates, data consistency checks, verified traffic switch, and rollback exist.
- DNS propagation is not instantaneous. The current adapter is a mock; a future DNS integration must validate endpoint health, record propagation status/errors, verify traffic independently, and define rollback.

Suggested sequence:

1. Add and test a single read-only live pricing adapter and provenance.
2. Persist normalized price snapshots and wire refresh route/UI.
3. Wire decisions only to fresh, compatible, comparable price records.
4. Add auth for shared deployments and connection/error observability.
5. Add real infrastructure/DNS operations only after explicit approval gates, cost controls, health checks, and rollback are implemented and tested.
