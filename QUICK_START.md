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

**Expected limitation**

Current public catalog records mein GCP ke component prices aur provider machine specs incomplete ho sakte hain. Isliye recommendation na aana valid aur conservative outcome ho sakta hai—not a broken calculator. Spot choose karoge toh interruption tolerance explicitly enable karna zaroori hai.

### 5. Migration center — workflow simulation

**Kya karo**

1. Source `GCP`, target `Azure` select karo.
2. Workload name `sir-demo-app` likho.
3. **Create migration simulation** dabao.
4. **Advance simulation** ko har step par dabao aur timeline/state dekho.
5. `HEALTH_CHECK` par **Health check passes** enabled rakho aur advance karo.
6. Optional: second run mein health check off karke failure gate dikhao, ya active simulation cancel karo.

**Sir ko kya bolo**

> “Ye migration orchestration ka UI/state-machine demonstration hai. Ye provisioning, application deploy, image copy, traffic move ya real DNS update nahi karta. Health-check gate fail ho toh simulation fail hoti hai aur source workload active rehta hai.”

**Safety line:** Timeline mein `SWITCHING_TRAFFIC`/`COMPLETED` labels simulation ke states hain; real traffic ya cloud resources change nahi hote.

### 6. Analytics & history — jo actions hue wahi dikhana

Calculator save karne, decision evaluate karne, aur migration simulation banane ke baad ye page kholo.

**Kya dikhana hai**

- Saved cost estimates aur unki net estimate.
- Decision analyses aur eligible-candidate count.
- Pricing snapshots.
- Migration simulation history/state.

**Sir ko kya bolo**

> “Analytics generated sample chart nahi hai; ye workspace mein actually saved estimates, decisions, snapshots aur simulations se banta hai. MongoDB connected ho toh history durable store mein rehti hai. Memory mode mein backend restart par data reset ho sakta hai.”

### 7. Settings — integration aur limitations

Provider status aur last successful fetch dikhhao. Saath mein database/persistence mode, optional Groq status, cloud provisioning disabled, aur DNS mock status explain karo.

**Sir ko kya bolo**

> “Settings secrets show nahi karta. GCP key backend-side configuration hai; Azure public retail catalog ko subscription ID ke bina query kiya ja sakta hai. Current build mein provisioning disabled aur DNS mock-only hai. MongoDB unavailable ho toh app memory mode ko explicitly report karti hai.”

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
