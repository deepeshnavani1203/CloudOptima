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

**Is workspace ka verified MongoDB status (25 Oct 2026):** `backend\.env` mein `MONGODB_URI` maujood hai, lekin local `/api/health` ne `status=unavailable`, `persistence=memory` report kiya. Configured URI se ek alag sanitized ping bhi `ServerSelectionTimeoutError` ke saath fail hua. Iska matlab URI set hai, par 5-second server-selection window mein MongoDB host reachable/selected nahi hua. Sirf URL paste karna successful connection ka proof nahi hai. Ye result apne aap mein credentials galat hone ka proof bhi nahi; common causes cluster stopped/unavailable, URI ka wrong host, DNS/network/firewall, ya MongoDB Atlas IP access list mein current machine ka IP missing hona hain. Error type/message ke alawa URI ya credentials print/share nahi kiye gaye.

**MongoDB ko troubleshoot karne ka safe order:**

1. MongoDB Atlas mein cluster status `Available` check karo, aur `Network Access` mein sirf apne current public IP ko allow karo. Temporary `0.0.0.0/0` access mat chhodo.
2. Atlas se application ke liye correct `mongodb+srv://...` connection string lo; username/password database user ke hone chahiye, Atlas website login ke nahi.
3. Agar password mein `@`, `:`, `/`, `#`, `%` jaise reserved characters hain, URI mein password ko URL-encode karo. Poora URI chat/log mein share mat karo.
4. Confirm karo backend `backend\.env` padh raha hai. Is project mein config path `backend\.env` hai; value frontend `.env` mein rakhne se backend MongoDB connect nahi karega.
5. Backend restart karke `/api/health` dobara check karo. Connected hone par database status `connected` aur persistence `mongodb` aani chahiye. Timeout aaye toh Atlas IP access, cluster state, DNS/outbound firewall aur URI host pehle verify karo; authentication error aaye toh database username/password aur password encoding verify karo.

### G. DNS failover / traffic routing

**Original proposal:** Health validation ke baad DNS ko target endpoint ki taraf switch karna aur failover/cutover support karna.

**Current build:** Sirf `MockDnsAdapter` hai. Ye endpoint validate karke simulated response deta hai; health failure par request reject karta hai. Real DNS provider credentials/configuration ya DNS record changes supported nahi hain.

### H. Real migration: current implementation aur future procedure

### Abhi kya actually implemented hai?

Migration center backend ki simulation state machine use karta hai. Create, advance, health-check pass/fail, cancel, transition history aur audit records implemented hain. UI ke `PROVISIONING`, `DEPLOYING`, `SWITCHING_TRAFFIC` aur `COMPLETED` labels simulated state names hain—inke dauran cloud API, VM, container registry, application, database, load balancer ya DNS ko change karne wala code nahi chalta. Is build ko real migration-ready ya production cutover system mat present karo.

### Real migration ke liye recommended technique: blue/green with staged cutover

Real cloud migration ek implementation roadmap hoga; ye current project ki completed functionality nahi. Safe high-level procedure:

1. **Discover and plan:** workload owner, source/target, OS/runtime, CPU/RAM, ports, secrets, persistent data, dependencies, RPO/RTO, legal/data-location constraints aur rollback owner document karo. Source aur target ka like-for-like cost model banao.
2. **Prepare target:** least-privilege cloud identity, network/subnets, firewall rules, secrets, monitoring, budgets/quotas aur target runtime define karo. IaC plan/diff review karo; pehle production resources create mat karo.
3. **Build and copy artifact:** containerized app ho toh immutable image digest pin karo, source registry se target registry mein authenticated copy/replication karo, signature/scanning policy verify karo. Non-container app ke liye versioned, reproducible build artifact use karo. Credentials log/UI mein expose na hon.
4. **Provision green environment:** target par infrastructure create karo, application deploy karo aur configuration/secrets securely inject karo. Idempotent deployment aur ownership tags rakho.
5. **Synchronize data:** database/file state ke liye approved initial snapshot/backup restore ya replication workflow use karo; checksums/row counts aur application-level consistency verify karo. Writes ke liye supported replication/fencing strategy define karo—sirf DNS switch data synchronize nahi karta.
6. **Test without production traffic:** readiness/liveness, dependency connectivity, representative smoke/integration tests, performance, security and observability checks chalao. Target ko production-ready tabhi mark karo jab explicit health criteria pass hon.
7. **Canary/weighted cutover:** load balancer ya DNS provider par chhote traffic fraction se start karo, metrics/errors/latency check karo, phir approved stages mein traffic badhao. DNS TTL pehle se plan karo; DNS propagation instant nahi hoti. Cutover ke dauran data writes duplicate ya split-brain na hon.
8. **Rollback gate:** error budget/health threshold cross ho toh traffic source blue environment par wapas le jao, write ownership/data consistency verify karo, aur source ko turant destroy na karo. Rollback rehearsed aur authorized hona chahiye.
9. **Stabilize and decommission:** agreed observation window ke baad owner approval, backup/restore verification aur cost/security review lo. Tabhi old resources ko controlled change mein retire karo; audit evidence preserve karo.

**Required engineering before enabling this in CloudOptima:** provider-specific auth/adapters with least privilege; explicit operator authorization and environment guards; a durable job/state store; infrastructure-as-code and plan review; artifact registry integration; data replication/consistency design; real health/metrics checks; load-balancer/DNS adapter with staged traffic and rollback; idempotency, retries, audit logs, secret redaction, budget/quota guardrails; and integration tests in a non-production account. GCP/Azure pricing APIs alone migration execute nahi karte. Current confirmation-gated API intentionally rejects live operations.

### Migration decision ka simple rule

Migration tabhi propose karo jab verified workload fit aur full estimated cost benefit ho, data transfer/consistency plan approved ho, target health validated ho, aur rollback available ho. Agar inmein se koi required proof missing ho, simulation/current source par raho—automatic cutover nahi.

### I. Dashboard / user interface

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

TypeScript, Tailwind, React Router, Recharts, Axios, TanStack Query aur shadcn/ui current implementation ka hissa nahi hain. Groq optional cost-estimate aur decision explanation ke liye use hota hai; numerical logic Groq use nahi karta.

## 7. Current build mein intentionally kya out of scope hai?

- AWS provider pricing; confirmed scope GCP + Azure hai.
- Real VM/container provisioning, migration ya teardown.
- Container registry/image copy.
- Production DNS record ya traffic changes; DNS mock-only hai.
- Future Spot-price prediction, actual capacity guarantee, ya billing-account invoice ingestion.
- Groq/LLM-based pricing, savings calculation, recommendation, prediction ya migration execution; AI sirf optional explanation likhta hai.
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

## 10. Detailed tech stack — kya use kiya aur kahan?

Yahan **used** ka matlab repository ke current code mein actual dependency/implementation hai. **Configured but not connected** ka matlab environment setting ho sakti hai, lekin feature abhi call/execute nahi hota.

### Frontend

| Technology | Kahan aur kis kaam ke liye |
|---|---|
| React 19 | `src/App.jsx` mein single-page dashboard, reusable UI pieces, page switching aur interactive forms |
| JavaScript + JSX | Frontend components, event handlers, calculations display aur API response rendering; TypeScript nahi |
| React hooks (`useState`, `useEffect`, `useCallback`, `useMemo`) | Form/page state, initial API load, callbacks aur displayed price filtering/aggregation |
| Vite 8 + React plugin | Frontend dev/build tool; `/api` requests ko backend tak proxy karna `vite.config.js` mein |
| CSS (`src/App.css`, `src/index.css`) | Layout, cards, responsive views, forms, tables, status badges aur dashboard styling |
| Browser Fetch API | `src/App.jsx` ke `api()` helper se backend ko JSON requests; Axios use nahi |
| ESLint | JavaScript/React lint check |

UI ke seven feature pages: Overview, Cloud pricing, Cost calculator, Best cloud decision, Migration center, Analytics & history, Settings. Current project React Router, Redux, Tailwind, Recharts, Axios ya TanStack Query use nahi karta.

### Backend aur shared API

| Technology | Kahan aur kis kaam ke liye |
|---|---|
| Python 3.11+ | Backend language |
| FastAPI | HTTP API, route handlers, OpenAPI docs aur startup/shutdown lifecycle |
| Pydantic 2 | Request validation, constraints, normalized pricing-record schema |
| `httpx` async client | GCP Billing Catalog aur Azure Retail Prices ke outbound HTTP requests |
| PyMongo AsyncMongoClient | Optional MongoDB connection, ping, index creation aur collection operations |
| `python-dotenv` | `backend\.env` se local backend configuration load karna |
| `uv` | Python project/dependency management aur lockfile workflow |
| `pytest` + FastAPI TestClient | Adapter, service, API behavior tests |

API routers request ko validate karke feature service call karte hain; services results ko store karke JSON response dete hain. Secret-bearing keys backend configuration tak seemit hain; frontend ko return nahi hote.

### Pricing / price telemetry feature

- `httpx` provider catalog APIs call karta hai: Google Cloud Billing Catalog aur Azure Retail Prices.
- Provider adapters response parsing, currency/unit/rate interpretation, provider-specific pricing model evidence aur source metadata handle karte hain.
- Pydantic `PriceRecord` common normalized record validate karta hai.
- Pricing service freshness, cache/status, provider errors, snapshots aur balanced provider listing manage karti hai.
- MongoDB connected ho toh snapshots persistent collection mein likhe jaate hain; otherwise memory fallback.
- Azure requests region-scoped aur page-bounded hain; rate limit par `Retry-After` based cooldown status hota hai.
- GCP CPU/memory native component rates ko full VM hourly price mein guess nahi kiya jata; UI unhe component rate label karti hai.

**Price data ka matlab:** Public catalog observation. Actual account bill, negotiated discount, workload usage, capacity guarantee ya guaranteed Spot availability nahi.

### Cost model / calculator feature

- UI se current/target provider, hourly costs, duration, transfer, migration overhead, other costs aur threshold aate hain.
- FastAPI cost route request ko Pydantic `CostRequest` se validate karta hai.
- `backend/app/services/costs.py` plain Python deterministic arithmetic karta hai; AI result ko calculate ya modify nahi karta.
- Formula: current total = current rate × duration; target total = target rate × duration + one-time costs; net savings = current total − target total; break-even one-time costs / positive hourly saving difference.
- Optional catalog snapshot select kiya ho toh route check karta hai ki snapshot exists, fresh, USD, verified aur target rate/provider se match ho.
- Result aur inputs `cost_analyses` collection mein save hote hain; creation event `audit_logs` mein jaata hai.
- User **Explain this estimate with AI** dabaye tab `/api/cost/explain` bounded result details Groq ko bhejta hai. Negative savings ko target estimate current se kitna zyada hai, line items aur threshold ko plain language mein explain karta hai.
- Tax, discounts aur user-entered na ki gayi storage/licensing/support costs automatically include nahi hoti.

### Best cloud decision feature

- UI workload constraints collect karta hai: current provider/cost, duration, required vCPU/RAM, region, requested OnDemand/Spot model, minimum savings, transfer/migration costs aur Spot-interruption tolerance.
- FastAPI request ko Pydantic `DecisionRequest` se validate karta hai.
- Decision service stored price snapshots par deterministic checks lagata hai: provider alternative, region match, capacity specs, freshness, USD, supported hourly rate, verified model, requested model, Spot tolerance aur savings threshold.
- Eligible candidates ko estimated total cost ke hisaab se rank karta hai; rejected observations ke saath reason deta hai.
- Required evidence unavailable ho toh candidate qualify nahi hota; recommendation/current provider result conservative reh sakta hai.
- Decision request/result `decision_analyses` aur related event `audit_logs` mein persist hote hain.
- User **Explain decision with AI** dabaye tab `/api/decisions/explain` recommendation/candidate reasons ko Groq se plain language mein summarize karata hai.
- Ye machine learning, future-price prediction ya live capacity check nahi hai; pricing adapter akela regional capacity prove nahi karta.

### Migration center feature

- Frontend migration form create/advance/cancel actions backend ke migration endpoints ko bhejta hai.
- Pydantic `MigrationCreate`/`MigrationAdvance` request fields validate karte hain.
- `backend/app/services/migrations.py` state machine aur health-check pass/fail behavior implement karta hai.
- Current implementation **simulation-only**: cloud SDK provision/deploy, data/image copy, real health endpoint, load balancer traffic shift, ya DNS update nahi karta.
- Simulation record `migrations` collection mein create/update hota hai; create/state-change/cancel actions `audit_logs` mein record hote hain.
- Real migration future feature hogi: blue/green setup, artifact copy, data consistency/replication, real target health checks, canary/weighted routing, rollback, approvals aur least-privilege provider integrations required honge. Ye procedures actual current operations nahi hain.

### DNS feature

- FastAPI DNS router `MockDnsAdapter` call karta hai.
- Adapter HTTP(S) endpoint aur health flag validate karke simulated response deta hai.
- Real DNS SDK/API integration ya DNS records modification nahi hoti.

### Analytics, settings aur persistence

- Analytics endpoint MongoDB/memory store se cost analyses, decision analyses, migration records aur recent pricing snapshots read karta hai. Ye actual saved workspace events ka summary hai, generated billing chart nahi.
- Health/settings endpoints runtime mode, provider integration state aur DB persistence mode dikhate hain; secret values return nahi karte.
- `DocumentStore` MongoDB Atlas/local MongoDB ko try karta hai; connect/ping/index creation fail ho toh explicit memory mode use hota hai.
- MongoDB collections: `pricing_snapshots`, `cost_analyses`, `decision_analyses`, `migrations`, `audit_logs`. `workload_configs` par index bana hai, lekin current app flow mein workload CRUD/storage feature active nahi.
- `users` collection par unique `username` index hai. Optional local profile seed `backend\.env.profile` se load hota hai; MongoDB connect hone par startup is profile ko username ke basis par upsert karta hai (`username`, `display_name`, `email`, `role`, `created_at`, `updated_at`). Is profile ke liye public read/write API nahi banayi gayi.
- Memory fallback temporary hai; backend process restart par in-memory records reset ho sakte hain.

## 11. AI / API key ka actual use

**AI ka limited use hai: optional cost-estimate aur decision explanations.** Cost calculator ka exact result Python formula se banta hai; Best cloud decision ka numerical recommendation deterministic rules engine banata hai. User relevant **Explain with AI** button dabaye tab backend bounded summary Groq Chat Completions API ko bhejta hai; model result/negative savings/candidate rejection reasons ko simple language mein explain karta hai. AI na price calculate karta hai, na candidate choose karta hai, na migration trigger karta hai. AI explanation fail ho toh original calculation/recommendation waise hi rehta hai.

`GROQ_API_KEY` backend-only secret hai aur `GROQ_MODEL` request mein selected model batata hai. Groq request sirf user ke explicit button click par hoti hai—calculator ke provider labels, amount/line items, net result aur missing-cost caveats; ya decision ka recommendation, reason, estimated savings, limited candidate/rejection summaries aur limitations bheje jaate hain. API key, Mongo URI, ya credentials payload mein nahi hote. UI batata hai ki summary Groq ko bheji jayegi; sensitive workload/provider details enter na karein.

Cost calculator formula-based hai; Best cloud decision deterministic rules-based hai; migration state transitions deterministic simulation hain. AI inference sirf optional explanation text banata hai, numerical/operational outcomes nahi. Pricing fetch, analytics, migration/DNS transitions, aur database persistence mein AI call nahi hoti. Settings health status `configured` ka matlab key configured hai, har future model request ka success guarantee nahi.

**Provider API key alag cheez hai:** `GCP_BILLING_API_KEY` GCP Billing Catalog adapter ke outbound request mein actual use hoti hai. Azure Retail Prices request public catalog par hai aur is integration ke liye Azure subscription ID/key use nahi hoti. Provider keys AI nahi hain; woh catalog access/configuration ke liye hoti hain.

## 12. MongoDB mein exactly kya store hota hai?

| Collection | Current data |
|---|---|
| `pricing_snapshots` | Normalized provider pricing observation: provider/region/SKU or meter, instance label, hourly/native price and unit, currency, pricing model/evidence, source URL, observed/effective/fetched times, freshness, specs/availability fields, generated snapshot ID. |
| `cost_analyses` | Calculator result plus input assumptions: providers, hourly rates, duration, one-time estimates, totals, net savings/percent, break-even, threshold, assumptions/missing-cost notes, optional snapshot IDs, created time and persistence metadata. |
| `decision_analyses` | Decision inputs plus recommendation, candidate/rejected-candidate explanations, prices/cost estimates, evaluation time, limitations and persistence metadata. |
| `migrations` | Simulation ID, source/target provider, workload label, simulation flag, current state, timestamps, source-active flag, transition history and simulation error. No VM image/data is stored. |
| `audit_logs` | Lightweight action records for pricing refresh, cost analysis, decision evaluation and migration create/advance/cancel; includes action/resource/time and relevant status/summary fields. |
| `users` | Sirf configured local profile seed: username, display name, email, role, created/updated timestamps. Startup username se upsert karta hai, duplicate profile create nahi karta; ye login/authentication collection nahi hai. |

`backend\.env` mein URI value present hai. Latest verified checks mein Atlas SRV DNS resolve hua aur seed TCP ports reachable the, lekin TLS handshake `TLSV1_ALERT_INTERNAL_ERROR` se fail hua; Mongo ping ne `ServerSelectionTimeoutError` diya aur `/api/health` ne `persistence=memory` report kiya. Isliye URI present hone ke bawajood current writes MongoDB mein nahi ja rahe. TLS interception/proxy/firewall ya Atlas-side TLS/network policy investigate karni hogi; TLS verification disable karke connection force mat karo. Settings ab safe `connection_error` category bhi dikhata hai. Atlas TLS issue fix hone aur backend restart par connection retry hoga; connected hone ke baad pricing/calculator/decision/migration events aur configured `users` profile MongoDB mein persist honge. Jab tak health `persistence=mongodb` na dikhaye, writes live Atlas mein nahi pahunchte.

`backend\.env.profile` local-only ignored config hai jisme profile seed values rakhe jaate hain; usse Git mein commit nahi kiya jata. `backend\.env.example` mein profile keys blank/reference-only rehte hain. Profile seed fields missing hon toh users collection mein koi profile auto-create nahi hoti. Profile values public API se read/write nahi hoti; current app mein authentication nahi hai, isliye ise account/login system na samjhein.
