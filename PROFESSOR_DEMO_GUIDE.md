# CloudOptima — Professor Presentation Guide

**Presenter:** Deepesh Navani  
**Project:** Multi-Cloud Spot Instance Arbitrage Engine

## Important demo disclosure

This project does not have AWS, GCP, or Azure pricing credentials/adapters configured. The pricing page is intentionally empty rather than displaying invented prices. The calculator runs on values entered by the presenter, and the decision engine will not recommend a cloud without provider price records. Migration steps are simulations only: no cloud or DNS resources are created or changed.

The figures in the calculator walkthrough below are a **classroom arithmetic example only**, not cloud-provider prices or data embedded in the app.

## Start the application

### Terminal 1 — FastAPI backend

```powershell
Set-Location C:\CloudOptima\backend
uv sync
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Wait for the Uvicorn startup message. The app works without MongoDB; check `/api/health` to see whether persistence is `mongodb` or explicitly `memory`.

### Terminal 2 — React frontend

```powershell
Set-Location C:\CloudOptima
npm install
npm run dev
```

Open the local Vite URL printed in the terminal, normally `http://localhost:5173`.

API docs are available at `http://localhost:8000/docs`.

## Presentation script (5–7 minutes)

1. **Introduce the goal.** CloudOptima compares spot/preemptible cloud compute costs, includes migration overhead in its calculations, and models a safer migration workflow.
2. **Show the dashboard.** Point out the logged-in name, live integration status, and the explicit unavailable-pricing message. Explain why the app avoids showing made-up cloud prices.
3. **Show Cloud Pricing.** Select **Cloud pricing**. The empty table and unavailable-source warning are expected: no provider pricing adapter is connected. Use **Check pricing** to show the backend does not fabricate a snapshot.
4. **Demonstrate the deterministic calculator.** Select **Cost calculator** and manually enter this clearly identified classroom example:

   | Field | Classroom input |
   |---|---:|
   | Current provider | AWS |
   | Target provider | GCP |
   | Current hourly cost | 0.10 |
   | Target hourly cost | 0.07 |
   | Duration | 720 hours |
   | Data transfer / egress | 12 |
   | Migration overhead | 5 |
   | Other costs | 3 |
   | Minimum savings threshold | 1% |

   Click **Calculate estimate**. Explain the calculation: current cost is `$0.10 × 720 = $72.00`; target total is `$0.07 × 720 + $12 + $5 + $3 = $70.40`; net savings are `$1.60` (about `2.22%`); break-even is approximately `666.7` hours. Remind the audience these are values entered for a math demonstration, not actual provider quotes.

5. **Show the decision engine.** Explain that it asks for workload requirements and considers actual eligible price records, rather than selecting the lowest hourly price blindly. Since no provider prices are configured, it keeps the current provider and reports that there is not enough data to recommend a move. This is the safe, intentional behavior.
6. **Show the migration simulation.** Select **Migration center**, create a simulation, and advance its steps. At **Health check**, uncheck **Health check passes** and advance to show the failure state. The source workload remains active. Optionally create another simulation and advance through the successful path. Clarify that these operations only update simulated state.
7. **Finish with Analytics and Settings.** Show that analytics reflects actual user-entered calculations and recorded simulations, and settings honestly reports MongoDB and provider integration availability.

## Environment files

- `backend\.env` contains local backend configuration: `FRONTEND_ORIGIN=http://localhost:5173`, `MONGODB_URI=mongodb://localhost:27017`, and demo-mode settings. It is ignored by Git.
- `backend\.env.example` documents the backend variable names.
- Root `.env.example` contains the public frontend API URL (`VITE_API_URL=http://localhost:8000/api`).
- No real cloud API URLs, API keys, or database credentials were supplied. Do not invent them: obtain provider endpoints/credentials from the provider consoles, keep secrets in `backend\.env`, and never put secrets in root/Vite environment variables.

## Optional checks before presenting

```powershell
Set-Location C:\CloudOptima\backend
uv run pytest

Set-Location C:\CloudOptima
npm run build
npm run lint
```

## If something does not start

- Run `uv sync` from `C:\CloudOptima\backend` to create/update `backend\.venv` from the lockfile.
- Confirm both terminals remain open and use the API URL in the browser console/network panel if the UI reports that the backend is unavailable.
- MongoDB is optional. Without it, the backend reports memory-only storage; records will not persist after the server stops.
- Stop each development server with `Ctrl+C` in its terminal.
