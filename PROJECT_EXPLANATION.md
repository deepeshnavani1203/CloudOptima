# CloudOptima — Project Explanation, Modules aur Implementation

Ye document project ko idea se implementation tak explain karta hai. Pehla hissa original **Multi-Cloud Spot Instance Arbitrage Engine** concept batata hai; agla hissa current CloudOptima build mein actually kya bana hai, woh batata hai. Presentation mein proposal aur implemented functionality ko alag rakhna—isse scope clear aur honest rahega.

## 1. Project ek nazar mein

CloudOptima ek multi-cloud cost-intelligence prototype hai. Iska goal GCP aur Azure ke public pricing evidence ko ek common view mein lana, workload inputs par estimated cost calculate karna, aur rules ke through suitable alternative cloud candidates evaluate karna hai.

Simple flow:

1. Provider catalogs se pricing observations laana.
2. Backend records normalize, validate, timestamp aur store karta hai.
3. User workload ki requirements aur cost assumptions enter karta hai.
4. Calculator estimated total/savings nikalta hai; decision engine eligible candidates evaluate karta hai.
5. Migration workflow ko safe simulation ke roop mein review karta hai.
6. Dashboard saved estimates, decisions, status aur simulation history dikhata hai.

**Ye kya nahi hai:** billing-system replacement, guaranteed savings tool, capacity reservation service, production migration platform, ya automatic cloud arbitrage bot nahi.

## 2. Original project idea — Spot Instance Arbitrage Engine

Original concept ka problem statement hai ki cloud providers aur regions ke compute prices alag hote hain aur Spot/Preemptible capacity cheaper ho sakti hai—but interrupt ho sakti hai. Workload ko doosre provider/region par move karna tabhi faidemand hai jab:

- workload target machine/region ke saath compatible ho;
- price aur pricing model dono taraf comparable hon;
- workload Spot interruption tolerate kar sake, agar Spot choose kiya gaya ho;
- transfer, migration aur one-time costs ke baad bhi savings ho;
- target health check pass ho aur rollback/source safety maintain rahe.

**Arbitrage ka simple matlab:**

> “Comparable workload ke liye ek option ka expected total cost doosre se kam ho, aur workload ke operational constraints bhi meet hon.”

Sirf cheapest hourly rate dekhna kaafi nahi. Actual savings duration, data egress, region, machine specs, price freshness, capacity aur interruption risk par depend karti hai.

## 3. Original proposal ke modules aur current implementation mapping

### A. Price telemetry / provider pricing collectors

**Purpose:** Provider catalog se price observations lena aur source, unit, model aur time ke saath comparison ke liye prepare karna.

**Current build:** Backend adapters GCP Billing Catalog aur Azure Retail Prices public API se data lete hain. GCP ke liye configured Billing Catalog API key backend mein use hoti hai. Azure catalog public endpoint region-filtered pricing deta hai. Requests time-bounded hain; Azure pagination capped hai aur rate limit par `Retry-After`-based cooldown follow hota hai.

Normalized observation mein provider, region, SKU/meter identity, pricing model, currency, unit/rate, source, effective/fetch time, freshness aur pricing evidence jaise fields preserve hote hain. Unsupported unit/model ko supported hourly instance price bana kar guess nahi kiya jata.

**Important price distinction:** GCP catalog CPU aur memory ke component rates de sakta hai. UI native rate aur unit dikhati hai aur ise clearly component rate—not full VM price—label karti hai. Azure records mein complete vCPU/RAM specs absent ho sakti hain; catalog mein price milna machine fit prove nahi karta.

**Boundaries:** Ye public retail catalog evidence hai—negotiated contract price, actual usage bill, live Spot capacity, ya availability guarantee nahi. Azure ke page cap ke kaaran result partial ho sakta hai.

### B. Cost model / calculator

**Purpose:** Workload duration ke dauran current-versus-target estimated compute cost compare karna aur one-time move costs include karna.

**Current build calculation:**

- Current compute = current hourly rate × duration.
- Target compute = target hourly rate × duration.
- Target total = target compute + transfer/egress estimate + migration overhead + other estimated costs.
- Net estimated savings = current compute − target total.
- Savings percentage = net estimated savings ÷ current compute × 100 (current cost zero ho toh percentage zero).
- Break-even duration tab calculate hota hai jab target hourly rate current se lower ho; one-time costs ko hourly saving difference se divide kiya jata hai.
- User ka minimum savings threshold result mein check hota hai.

Backend mein cost calculation deterministic function hai: same inputs par same output. User inputs deta hai; optional verified catalog observation target rate prefill kar sakta hai.

**Example:** Current `$0.12/hour`, target `$0.08/hour`, 720 hours, transfer `$5`, migration overhead `$2`:

- Current total: `$0.12 × 720 = $86.40`.
- Target compute: `$0.08 × 720 = $57.60`.
- Target total: `$57.60 + $5 + $2 = $64.60`.
- Net estimated savings: `$86.40 − $64.60 = $21.80` (lagbhag 25.23%).
- Break-even: `$7 ÷ ($0.12 − $0.08) = 175 hours`.

Savings negative bhi ho sakti hai; iska matlab target compute plus one-time expenses current cost se zyada hain. Taxes, negotiated discounts, support, licensing, storage aur unentered services include nahi hote.

### C. Spot arbitrage / Best cloud decision engine

**Purpose:** Sirf low price dekhne ke bajay workload requirements aur evidence ke basis par candidate qualify karna.

**Current build:** Explainable rules-based engine alternatives evaluate karta hai. Checks mein region match/known normalized region group, vCPU/RAM requirements, fresh price, USD currency, supported hourly rate, verified pricing model, requested Spot/OnDemand model, minimum savings threshold aur Spot interruption tolerance shamil hain. Ineligible record ke saath rejection reason return hota hai. Eligible options estimated total cost ke hisaab se rank hote hain.

**Why no candidate aa sakta hai:** Public catalog observations mein machine specs incomplete ho sakte hain. Agar region/specs/rate/model ka required evidence nahi ho, system assumption bana kar recommendation nahi deta. Iska goal false confidence se bachna hai.

**Algorithm type:** Deterministic rules; machine-learning model ya future price predictor nahi. Spot ki future availability/interruption predict nahi karta.

### D. Migration engine / orchestration flow

**Original proposal:** Workload ko source se target environment tak migrate karna, validate karna aur safe cutover orchestrate karna.

**Current build:** Migration center ek simulation state machine chalata hai:

`PENDING → PROVISIONING → DEPLOYING → HEALTH_CHECK → READY_TO_SWITCH → SWITCHING_TRAFFIC → VERIFYING → COMPLETED`

UI se state advance hoti hai. Health-check gate fail karne par simulation `FAILED` hoti hai aur source workload active bataya jata hai. Active simulation cancel bhi ho sakti hai. Har transition history mein record hoti hai.

**Safety boundary:** Ye state labels workflow explain karne ke liye hain. Current code cloud resources provision/deploy nahi karta, application migrate nahi karta, aur real traffic switch nahi karta. Live operation disabled hai.

### E. Container registry / image movement

**Original proposal:** Container image ko source registry se target registry tak copy karna, taaki target environment mein same artifact deploy kiya ja sake.

**Current build:** Real registry integration, image push/pull/copy aur deployment implemented nahi hain. Presentation mein ise future extension/proposal ke roop mein explain karein; completed module claim na karein.

### F. Shared datastore / history

**Purpose:** Pricing snapshots, cost analyses, decision results, migration simulations aur audit events ko save karke workspace history dena.

**Current build:** `DocumentStore` MongoDB connected ho toh MongoDB use karta hai; connection unavailable ho toh explicit in-memory mode mein chalta hai. API status persistence mode report karta hai. Pricing records, calculations, decisions, migration state transitions aur audit events relevant collections mein save hote hain.

**Persistence caveat:** Memory mode data process lifetime tak hi hota hai. Backend stop/restart par in-memory history aur cache reset ho sakte hain. Demo mein status check karo; memory history ko permanent storage mat bolo.

### G. DNS failover / traffic routing

**Original proposal:** Health validation ke baad DNS ko target endpoint ki taraf switch karna aur failover/cutover support karna.

**Current build:** Sirf `MockDnsAdapter` hai. Ye endpoint validate karke simulated response deta hai; health failure par request reject karta hai. Real DNS provider credentials/configuration ya DNS record changes supported nahi hain.

### H. Dashboard / user interface

**Purpose:** Technical API aur pricing evidence ko demo-friendly pages mein dikhana.

**Current pages:** Overview, Cloud pricing, Cost calculator, Best cloud decision, Migration center, Analytics & history, Settings.

UI backend endpoints call karta hai, inputs submit karta hai, pricing search/filter karta hai, aur provider status/warnings/results dikhata hai. Savings aur pricing caveats visible rakhe gaye hain.

## 4. Current app ke modules aur code organization

| Layer / module | Responsibility |
|---|---|
| `src/App.jsx`, `src/App.css` | React navigation/pages, form state, API calls, tables, results aur styling |
| `backend/app/adapters/gcp_pricing.py` | GCP Billing Catalog request aur SKU rate parsing |
| `backend/app/adapters/azure_pricing.py` | Azure Retail Prices request, region/pagination, meter classification aur rate-limit response |
| `backend/app/adapters/pricing_common.py` | Providers ke beech shared request-error contract |
| `backend/app/schemas.py` | Pydantic request/price-record shapes, input bounds aur validation |
| `backend/app/services/pricing.py` | Normalization, freshness, cache, provider status, persistence aur provider-balanced listing |
| `backend/app/services/costs.py` | Deterministic estimate, net savings aur break-even calculations |
| `backend/app/services/decisions.py` | Workload checks, candidate eligibility, rejection reasons aur ranking |
| `backend/app/services/migrations.py` | Simulation states, health gate, cancellation aur transition history |
| `backend/app/db.py` | MongoDB connection/indexes plus explicit memory fallback |
| `backend/app/routers/` | HTTP routes: pricing, costs, decisions, analytics, migrations, settings, DNS |
| `backend/app/main.py` | FastAPI app lifecycle, CORS aur router registration |
| `backend/tests/` | Adapter, service, validation aur endpoint behavior tests |

## 5. Request flow — browser se result tak

1. React page user inputs leta hai aur `/api/...` endpoint ko JSON request bhejta hai.
2. Vite proxy frontend ke `/api` requests ko backend API tak route karta hai.
3. FastAPI router request ko Pydantic schema se validate karta hai.
4. Relevant service calculation/rules chalata hai; pricing refresh mein provider adapter public catalog query karta hai.
5. Normalized result optional MongoDB ya memory-mode `DocumentStore` mein persist hota hai.
6. API JSON response deta hai; React result, status ya error ko UI mein dikhata hai.

Backend CORS configured frontend origin tak scoped hai. Provider secrets frontend ko return nahi kiye jaate.

## 6. Technology stack — current code mein kya use hota hai?

- **Frontend:** React, Vite, JavaScript/JSX, project CSS. UI native React/CSS tables aur visualizations use karta hai.
- **Backend:** Python, FastAPI, Pydantic, asynchronous `httpx`.
- **Persistence:** Async PyMongo/MongoDB optional; local/demo fallback in-memory.
- **Python tooling/tests:** `uv` environment/dependency management aur `pytest`.
- **External pricing sources:** Google Cloud Billing Catalog API aur Azure Retail Prices API.
- **API style:** `/api` prefix ke neeche JSON REST endpoints.

TypeScript, Tailwind, React Router, Recharts, Axios, TanStack Query, shadcn/ui aur live Groq-based numerical decision logic current implementation ka hissa nahi hain. Project mein unhe use kiya gaya hai aisa claim na karein.

## 7. Current build mein intentionally kya out of scope hai?

- AWS provider pricing; confirmed scope GCP + Azure hai.
- Real VM/container provisioning, migration ya teardown.
- Container registry/image copy.
- Production DNS record ya traffic changes; DNS mock-only hai.
- Future Spot-price prediction, actual capacity guarantee, ya billing-account invoice ingestion.
- Groq/LLM-based numerical decisions; calculations aur decisions deterministic hain.
- Frontend par provider secrets; secret-bearing config backend par rehti hai.

## 8. Sir ke likely questions — honest short answers

**“Project ka main use kya hai?”**

“GCP/Azure public catalog observations inspect karna, workload assumptions ka cost estimate nikalna, aur eligible alternatives ko transparent rules se evaluate karna.”

**“Kya ye actual bill batata hai?”**

“Nahi. Ye retail catalog aur user-provided assumptions ka estimate hai. Contract discounts, usage, taxes aur non-compute services actual billing ko badal sakte hain.”

**“Recommendation kyun nahi di?”**

“Recommendation ke liye price ke saath fresh compatible region, verified pricing model aur workload ke vCPU/RAM specs bhi chahiye. Evidence incomplete ho toh system reason ke saath reject karta hai; specs invent nahi karta.”

**“Spot safe hai?”**

“Spot/preemptible capacity interrupt ho sakti hai. Decision flow interruption tolerance explicitly check karta hai, lekin future availability ya interruption guarantee nahi karta.”

**“Migration real hai?”**

“Nahi, current build simulation-only hai. UI state transitions, health gate, cancellation aur history demonstrate karta hai; cloud deployment/traffic/DNS nahi badalta.”

**“Original proposal ka registry/DNS/cloud provisioning kahan hai?”**

“Woh original architecture direction ka part hain. Current implemented scope mein container registry aur real provisioning absent hain, DNS mock-only hai. Demo GCP/Azure pricing, cost/decision logic aur safe migration simulation par focus karta hai.”

**“Data permanent hai?”**

“MongoDB connected ho toh persistence MongoDB mein hoti hai. MongoDB unavailable ho toh status memory mode batata hai aur backend restart par memory history clear ho sakti hai.”

## 9. One-minute project explanation

> “CloudOptima ek GCP–Azure multi-cloud cost-intelligence prototype hai. Backend dono providers ke public pricing catalogs se data leta hai aur SKU, region, unit, source time aur pricing model ko common schema mein normalize karta hai. Cost calculator workload duration ke saath compute aur one-time transfer/migration estimates jodkar net savings aur break-even nikalta hai. Decision engine sirf fresh, compatible aur sufficiently verified catalog records accept karta hai aur rejection reasons bhi dikhata hai. Migration center state-machine workflow ko simulation mein demonstrate karta hai—real provisioning ya DNS switch nahi hota. Iska main design principle hai ki incomplete data par fake price ya unsafe recommendation na banayi jaye.”
