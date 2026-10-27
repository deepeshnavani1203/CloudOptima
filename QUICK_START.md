# CloudOptima — Demo aur Presentation Guide

Ye guide tab use karo jab CloudOptima browser mein already khula ho. Isme server start/run commands nahi hain. Focus hai: demo ko kis order mein dikhana hai, har feature ko kaise try karna hai, aur sir ko kya bolna hai.

## Demo ka main objective

Sir ko ye flow dikhana hai:

1. GCP aur Azure ke public catalog prices dekhna.
2. Workload ke cost assumptions enter karke estimate calculate karna.
3. Workload requirements ke against cloud options evaluate karna.
4. Migration ko safe simulation ke roop mein step-by-step dikhana.
5. Apne actions ki history aur system limitations verify karna.

**Scope yaad rakho:** Current implementation GCP + Azure pricing par focused hai. AWS pricing, real cloud provisioning, container image copying, aur real DNS switching is demo mein enabled nahi hain.

## Demo se pehle

- App browser mein khuli ho aur API connected ho.
- **Settings** ya **Overview** mein backend/persistence status ek baar check kar lo.
- **Cloud pricing** par Azure region `eastus` rehne do, phir **Refresh catalogs** sirf ek baar dabao. Request complete hone ka wait karo.
- Refresh ke baad provider status, warnings, aur table rows check kar lo. Azure public API rate limit de toh baar-baar click na karo; retry-after message ke mutabik wait karo. Live catalog unavailable ho toh calculator ke manual inputs aur simulation modules phir bhi present kiye ja sakte hain.
- Demo se pehle example inputs try kar lena; live data ka exact count har refresh mein badal sakta hai.

## Page-by-page demo order

### 1. Overview — project ka one-screen summary

**Kya karo**

- Sidebar se **Overview** kholo.
- Catalog records, fresh records, saved estimated savings, migration simulations, provider status, aur latest observations dikhhao.
- **Explore prices** ya sidebar se pricing explorer par jao.

**Sir ko kya bolo**

> “Overview mein system ke current catalog coverage, data freshness aur is workspace mein save kiye gaye estimates/simulations dikhte hain. Yahan savings actual cloud bill se read nahi hoti; woh calculator ke assumptions-based estimates ka summary hai.”

**Dhyan:** “Fresh” ka matlab observation recent hai; iska matlab live capacity available hai, ye nahi.

### 2. Cloud pricing — provider evidence dikhana

**Kya karo**

1. **Azure VM catalog region** mein `eastus` rakho.
2. **Refresh catalogs** ek baar dabao aur completion ka wait karo.
3. Provider filter se pehle **GCP**, phir **Azure** select karke rows compare karo.
4. Search, pricing model, freshness, aur displayed-region filters dikhhao.
5. Row mein provider, region, SKU/meter, Spot/OnDemand, currency/unit, source aur fetch time samjhao.

**Sir ko kya bolo**

> “Backend provider ke public pricing catalog se records leta hai aur common format mein normalize karta hai. Source SKU/meter aur observation time preserve hote hain. Jo rate supported, hourly aur verified nahi hota, usko full hourly instance price nahi banaya jata.”

**GCP ka important point**

> “GCP catalog mein CPU aur memory alag component rates ho sakte hain. UI unhe component rate ke roop mein unit ke saath dikhati hai; unhe complete VM ka hourly bill nahi maana ja sakta.”

**Azure warning aaye toh**

- Azure public Retail Prices API kabhi rate limit ya partial page cap de sakti hai.
- `Retry-After`/UI message ke mutabik wait karo; repeated rapid refresh mat karo.
- Page-cap warning ka matlab returned sample incomplete ho sakta hai.
- Isse chhupane ke bajay batao: “Catalog API request bound hai; isliye region ke hisaab se results partial ho sakte hain.”

### 3. Cost calculator — assumptions se estimate

Calculator ko live catalog ke bina bhi demonstrate kar sakte ho. Example values:

| Field | Example |
|---|---:|
| Current provider | GCP |
| Target provider | Azure |
| Current hourly compute cost | 0.12 |
| Target hourly compute cost | 0.08 |
| Workload duration | 720 hours |
| Transfer / egress estimate | 5 |
| Migration overhead estimate | 2 |
| Other user-estimated costs | 0 |
| Minimum savings threshold | 10% |

Phir **Save cost estimate** dabao. Result breakdown mein current compute, target compute, one-time estimates, target total, net estimated savings, percentage aur break-even time dikhhao.

**Is example ka expected result**

- Current cost: `0.12 × 720 = $86.40`
- Target compute: `0.08 × 720 = $57.60`
- Target total: `$57.60 + $5 + $2 = $64.60`
- Net estimated savings: `$86.40 − $64.60 = $21.80`
- Savings: lagbhag `25.23%`
- Break-even: `$7 ÷ ($0.12 − $0.08) = 175 hours`

Rounding/UI formatting se last decimal thoda alag dikh sakta hai.

**Sir ko kya bolo**

> “Calculator mein current aur target hourly costs ko duration se multiply kiya jata hai. Transfer, migration overhead aur other costs one-time estimates ke roop mein add hote hain. Result deterministic hai, lekin inputs assumptions hain—provider bill ya guaranteed savings nahi.”

**Agar savings negative aaye**

Negative savings error zaroori nahi. Iska matlab selected duration/costs ke hisaab se target total current cost se zyada hai. Transfer/overhead ko one-time add karne se chhote ya short workloads mein ye ho sakta hai. Example ke liye upar wali values use karo.

**AI explanation dikhana ho toh**

- Result ke neeche **Explain this estimate with AI** dabao.
- Groq current/target totals, line items, net savings, threshold aur excluded-cost caveats ko simple words mein samjhayega. Negative result par woh target option kitna mehenga hai woh explain kar sakta hai.
- Ye optional explanation hai: AI number calculate/change nahi karta; calculation wahi deterministic backend formula hai.
- Button dabane par cost summary Groq API ko bhej di jati hai. Demo data hi use karo; sensitive workload/provider details mat daalo.

### 4. Best cloud decision — explainable candidate evaluation

Ye calculator se alag hai: decision engine sirf cheaper rate nahi dekhta, pehle workload fit aur evidence check karta hai.

**Example inputs**

- Current provider: `GCP`
- Requested model: `OnDemand`
- Current hourly cost: `0.12`
- Duration: `720`
- Required vCPU: `2`
- Required memory: `8 GB`
- Region: `eastus`
- Minimum savings: `10%`
- Transfer / migration overhead: `0`
- **Workload can tolerate Spot interruption:** unchecked rakho for OnDemand example.

**Kya karo**

- **Evaluate catalog candidates** dabao.
- Recommendation, eligible candidates aur excluded observations/reasons dikhhao.
- Agar “no eligible candidate” aaye toh excluded reason padhkar samjhao.

**Sir ko kya bolo**

> “Recommendation rules-based aur explainable hai. Candidate ko region, fresh data, USD hourly rate, verified pricing model, required vCPU/RAM aur Spot interruption tolerance jaise checks pass karne hote hain. Required specs missing hon toh engine guess nahi karta; candidate reject karke reason deta hai.”

Result ke neeche **Explain decision with AI** optional hai. Isse Groq recommendation aur rejection reasons ko plain language mein samjhayega; provider choose karne wala numerical/rules-based decision AI nahi banata. Click par limited decision summary Groq ko bheji jati hai.

**Expected limitation**

Current public catalog records mein GCP ke component prices aur provider machine specs incomplete ho sakte hain. Isliye recommendation na aana valid aur conservative outcome ho sakta hai—not a broken calculator. Spot choose karoge toh interruption tolerance explicitly enable karna zaroori hai.

### 5. Migration center — workflow simulation

**Kya karo**

1. Source `GCP`, target `Azure` select karo.
2. Workload name `sir-demo-app` likho.
3. **Create migration simulation** dabao.
4. **SIMULATED: backup confirmed** checkbox tick karo; phir **Advance simulation** dabao. Real backup create nahi hota.
5. `HEALTH_CHECK` par simulated target health check pass rehne do aur advance karo.
6. `READY_TO_SWITCH` par **SIMULATED: approve traffic-switch stage** explicitly tick karo. Approval ke bina backend transition reject karega.
7. `VERIFYING` par post-switch simulated health check fail karke **Run simulated verification** dabao. State `ROLLING_BACK` hogi; next button se rollback simulation complete karke `ROLLED_BACK` dekho. Source recovery target active rehta hai.
8. Successful path dikhana ho toh new simulation mein backup confirm karo, pre-switch health check pass, switch approval tick, aur post-switch verification pass rakho.
9. Safety timeline mein har state, timestamp, simulated backup/approval/health-check result aur failure/rollback reason dikhhao. Active simulation cancel bhi kar sakte ho.

**Sir ko kya bolo**

> “Migration center safety gates wala simulation hai. Backup confirmation, target health check, traffic-switch approval aur post-switch verification backend par validate hote hain. Post-switch health fail ho toh rollback state source ko recovery target dikhati hai. Koi real backup, deployment, data copy, traffic switch ya DNS update nahi hota.”

**Safety line:** Har checkbox aur timeline stage `SIMULATED` hai. `ROLLING_BACK`, `ROLLED_BACK` ya `COMPLETED` status bhi real cloud action ka proof nahi.

### 6. Price Arbitrage Monitor — comparable Spot rates

1. **Price Arbitrage Monitor** kholo aur **Refresh pricing** dabao; ye existing GCP/Azure catalog APIs reuse karta hai.
2. AWS card par **AWS pricing not connected** dikhega. AWS ka fabricated ya demo price is page mein nahi hai.
3. Fresh, verified hourly Spot rates hi comparison table mein aate hain. Cheapest provider tabhi highlight hota hai jab CPU, memory, currency aur pricing model comparable hon.
4. Agar **“no comparable Spot quotes qualify”** aaye, iska matlab refresh fail hua ho zaroori nahi. Catalog records aa sakte hain, lekin full instance-hour rate ya vCPU/RAM specs missing hone se monitor unhe compare nahi karta. Cloud pricing explorer mein source/unit check karo; component rate ko full VM price mat samjho.
5. Provider card par catalog-record count aur eligible count alag dekho. `LIVE API DATA` direct successful fetch, `CACHED DATA` cache reuse aur `UNAVAILABLE` qualifying data na hone ko batata hai. AWS connected nahi hai.

**Sir ko kya bolo:** “Monitor catalog evidence dikhata hai, actual Spot capacity ya guaranteed savings nahi. Region equivalence normalize nahi hai; matching capacity sirf rough comparison basis hai. AWS integration abhi connected nahi hai.”

### 7. Spot Migration Simulator — backend state machine

1. **Spot Migration Simulator** kholo, source aur target select karo, phir **Start simulated workflow** dabao.
2. Price-alert acknowledgement aur target-selection stages complete karo.
3. Backup confirmation check karo; health check ko pass ya fail karke dono branches dikhai ja sakti hain.
4. Passing health check ke baad simulated switch approve karke traffic-switch stage aur verification chalao.
5. Verification (ya target health check) fail ho toh **Simulate rollback to source** dabao, phir rollback completion. **Reset scenario** ek naya run banata hai; saved purana timeline rehta hai.

**Sir ko kya bolo:** “Har stage existing FastAPI migration endpoints se backend par validate hoti hai. Ye simulation hai—VM, data, real traffic ya DNS move nahi hota.”

### 8. Cost Savings & Evaluation — estimate report and CSV

1. **Cost Savings & Evaluation** kholo.
2. Eligible live data ho toh static baseline select karo; app matching vCPU/memory wali doosri provider ki cheapest eligible Spot rate choose karti hai.
3. Agar live records eligible nahi, form **Manual estimate mode — not live pricing** dikhayega. Demo ke liye baseline `GCP`, comparison `Azure`, static hourly `0.12`, comparison hourly `0.08`, migration overhead `10` use karo. Ye sirf example assumptions hain, provider rates nahi.
4. **Calculate & save evaluation** dabao. Example mein 730-hour month par static ~$87.60, comparison plus overhead ~$68.40, estimated savings ~$19.20 (21.92%), break-even 250 hours. Overhead `0` karoge toh monthly savings $29.20 aur break-even 0 hours.
5. Static vs comparison strategy ki estimated hourly/monthly cost, overhead, savings, percentage aur break-even time dekho.
6. **Export displayed report to CSV** se wahi current displayed calculation download karo.

**Assumptions:** Manual mode ke hourly values user assumptions hain—na live data na cheapest-provider recommendation. Month = 730 hours; transfer aur other costs = $0; entered migration overhead once add hota hai. Spot interruption risk, taxes, discounts aur non-compute services model nahi hain. Live catalog mode eligible records na milne par prices invent nahi karta.

### 9. Analytics & history — jo actions hue wahi dikhana

Calculator save karne, decision evaluate karne, aur migration simulation banane ke baad ye page kholo.

**Kya dikhana hai**

- Saved cost estimates aur unki net estimate.
- Decision analyses aur eligible-candidate count.
- Pricing snapshots.
- Migration simulation history/state.

**Sir ko kya bolo**

> “Analytics generated sample chart nahi hai; ye workspace mein actually saved estimates, decisions, snapshots aur simulations se banta hai. MongoDB connected ho toh history durable store mein rehti hai. Memory mode mein backend restart par data reset ho sakta hai.”

### 10. Settings — integration aur limitations

Provider status aur last successful fetch dikhhao. Saath mein database/persistence mode, Groq configured status, cloud provisioning disabled, aur DNS mock status explain karo.

**Sir ko kya bolo**

> “Settings secrets show nahi karta. GCP key backend-side configuration hai; Azure public retail catalog ko subscription ID ke bina query kiya ja sakta hai. Groq optional explanations ke liye hai, calculations ke liye nahi. Current build mein provisioning disabled aur DNS mock-only hai. MongoDB unavailable ho toh app memory mode ko explicitly report karti hai.”

## 60-second opening script

> “Mera project CloudOptima hai—GCP aur Azure ke public pricing data ko normalize karke cloud cost comparison aur workload decision support dene wala prototype. User apne workload ke compute cost, duration aur migration/transfer assumptions enter karke estimate nikal sakta hai. Decision engine sirf verified aur compatible records ko accept karta hai; evidence missing ho toh reason ke saath candidate reject karta hai. Migration flow abhi simulation-only hai, isliye demo mein koi real cloud resource ya DNS change nahi hota.”

## Demo ke waqt yaad rakhne wali baatein

- Public retail price ko actual invoice, negotiated discount, capacity guarantee, ya deployed VM bill mat bolo.
- User-entered costs ko “assumptions/estimates” bolo.
- GCP `core-hour`/`GiB-hour` jaise component rate ko full VM price mat bolo.
- Missing candidate/specs ka reason openly explain karo; system intentionally conservative hai.
- Azure rate limiting ko bypass nahi kiya gaya; retry wait aur bounded/partial results transparency se handle hote hain.
- Backend memory mode mein history restart ke baad persist nahi hoti.
- AWS, real provisioning, registry/image copy, production DNS failover, aur live migration current implemented scope mein nahi hain.

## Local development servers (Windows PowerShell)

Backend aur frontend ko alag PowerShell terminals mein chalao. Vite API proxy `http://127.0.0.1:5000` par configured hai.

```powershell
# Terminal 1 — FastAPI backend
Set-Location C:\CloudOptima\backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 5000
```

```powershell
# Terminal 2 — React + Vite frontend
Set-Location C:\CloudOptima
npm run dev -- --host 127.0.0.1 --port 5173
```
