# CloudOptima — Run aur Professor Demo Guide (Hinglish)

**Presenter:** Deepesh Navani  
**Project:** Multi-Cloud Spot Instance Arbitrage Engine

## Pehle important baat

Abhi app mein AWS, GCP, ya Azure ka **live price adapter connected/implemented nahi hai**. Isliye Pricing screen par prices blank dikhna sahi behavior hai. App dummy prices use nahi karti.

Calculator aapke manually enter kiye numbers se kaam karta hai. Decision Engine ko actual provider price records nahi milte, isliye woh cloud migration recommend nahi karega. Migration Center sirf simulation hai—koi actual VM, cloud resource, ya DNS change create nahi hota.

**`.env` mein key bharna alone live pricing start nahi karega.** Provider API call, response parsing, normalization, error handling, aur tests ke liye backend adapter code bhi likhna/configure karna padega.

---

## Project start kaise karein

`uv` aur frontend server ke liye **do PowerShell terminals** khol kar rakhein.

### Backend — Terminal 1

```powershell
Set-Location C:\CloudOptima\backend
uv sync
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- `uv sync` `pyproject.toml` aur `uv.lock` se packages install karta hai aur `backend\.venv` banata hai.
- `uv run` isi venv ke Python se command chalata hai; alag se `Activate.ps1` ki zaroorat nahi.
- Successful start par terminal mein `Uvicorn running on http://127.0.0.1:8000` dikhega.
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health status: [http://localhost:8000/api/health](http://localhost:8000/api/health)

### Frontend — Terminal 2

```powershell
Set-Location C:\CloudOptima
npm install
npm run dev
```

Vite terminal jo URL dikhaye—usually [http://localhost:5173](http://localhost:5173)—browser mein kholen. Dono terminals chalte rehne dein. Server rokne ke liye us terminal mein `Ctrl+C` dabayein.

### Agar `uv` command nahi milta

Pehle verify karein:

```powershell
uv --version
```

Windows par `winget` available ho to install:

```powershell
winget install --id astral-sh.uv -e
```

Install ke baad naya PowerShell terminal kholen, phir `uv --version` aur backend start commands chalayein. Python interpreter specify karna ho to:

```powershell
Set-Location C:\CloudOptima\backend
uv python install 3.12
uv sync --python 3.12
```

### Tests/checks chalana

```powershell
Set-Location C:\CloudOptima\backend
uv run pytest

Set-Location C:\CloudOptima
npm run build
npm run lint
```

---

## Environment (`.env`) ka sahi use

- Backend config: [backend/.env](./backend/.env) — yahin server-side settings/secret placeholders honge.
- Backend template: [backend/.env.example](./backend/.env.example).
- Frontend template: [.env.example](./.env.example) — sirf public API URL `VITE_API_URL=http://localhost:8000/api`.
- Backend `.env` Git mein commit nahi hota. Apni real credentials kabhi chat, screenshot, Git, ya `VITE_...` variable mein mat daalein.

`backend\.env` mein AWS profile/region, GCP project/credential file, aur Azure subscription ke **variable placeholders** hain. Lekin current code mein live pricing adapters nahi hain aur in provider settings ka use karke prices fetch nahi hote. Koi API URL guess karke `.env` mein na daalein.

---

## Professor ko 5-minute demo kaise dikhayein

1. Upar diye commands se backend aur frontend dono start karein.
2. Dashboard par **Deepesh Navani**, demo mode, aur “No provider pricing is configured” message dikhayein. Batayein ki fake price dene ki jagah app unavailable state dikhati hai.
3. **Cloud Pricing** kholen. `Check pricing` dabayein; table empty rehna expected hai, kyunki provider adapters abhi connected nahi hain.
4. **Cost Calculator** par user-entered calculation dikhayein. Neeche ke numbers sirf **classroom arithmetic example** hain—not AWS/Azure/GCP quotes:

   | Input | Classroom example |
   |---|---:|
   | Current provider | AWS |
   | Target provider | GCP |
   | Current hourly cost | `0.10` USD |
   | Target hourly cost | `0.07` USD |
   | Duration | `720` hours |
   | Data transfer / egress | `12` USD |
   | Migration overhead | `5` USD |
   | Other costs | `3` USD |
   | Minimum savings threshold | `1%` |

   Har field manually enter karke **Calculate estimate** dabayein. Expected result:

   - Current: `0.10 × 720 = $72.00`
   - Target compute: `0.07 × 720 = $50.40`
   - Target total: `$50.40 + $12 + $5 + $3 = $70.40`
   - Net savings: `$72.00 − $70.40 = $1.60` (lagbhag `2.22%`)
   - Break-even: `($12 + $5 + $3) ÷ ($0.10 − $0.07) = 666.7 hours`

   Clearly kahen: “Yeh hand-entered example hai calculation dikhane ke liye; yeh provider se aaya hua price nahi hai.”

5. **Decision Engine** par actual prices ke bina analysis chalane ki koshish dikhayein. App no-price-data batayegi aur migration recommend nahi karegi.
6. **Migration Center** mein simulation create karke steps advance karein. Health-check failure bhi dikhayein; source workload active rehna chahiye. Confirm karein ki yeh real deployment nahi hai.
7. **Settings** aur `/api/health` par MongoDB status dikha sakte hain. MongoDB install/configure na ho to `memory` storage dikhna normal hai; server band hone par memory data persist nahi hota.

---

## Cloud accounts aur credentials kahan milenge?

Demo chalane ke liye inmein se kisi cloud ki credentials ki zaroorat nahi. **Sirf apne account/project par permission ho tabhi** credentials banayein; class demo ke liye keys create karna zaroori nahi.

### AWS Spot price history

1. [AWS Console](https://console.aws.amazon.com/) mein account ke andar **IAM Identity Center / AWS IAM** se user ya role access set karein. Root account ke access keys use na karein.
2. Local machine par behtar option AWS CLI SSO/profile hai; official guide: [AWS CLI SSO configuration](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html).
3. Official [DescribeSpotPriceHistory API](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeSpotPriceHistory.html) Spot prices ki history deta hai. Request ko AWS credentials se sign karna hota hai; permission ko least privilege ke saath scope karein (EC2 `DescribeSpotPriceHistory`).
4. Agar app mein adapter baad mein likha jaye, AWS profile backend process ko available karna hoga. Is project mein `AWS_PROFILE` placeholder hai; current code ise abhi read/use nahi karta.

AWS access-key safety: [AWS access-key security guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html). Long-lived key bana kar source code ya Git mein rakhne ke bajaye temporary credentials/role prefer karein.

### Google Cloud pricing information

1. [Google Cloud Console](https://console.cloud.google.com/) mein project select/create karein.
2. [Cloud Billing Pricing API guide](https://cloud.google.com/billing/docs/how-to/get-pricing-information-api) ke mutabik Billing API enable karein. Public service/SKU information retrieve karne ke liye official guide API key ka flow dikhati hai; API key ko API restrictions ke saath rakhein.
3. Google ka [Application Default Credentials (ADC)](https://cloud.google.com/docs/authentication/application-default-credentials) development/production ke liye auth lookup explain karta hai. App ko baad mein private billing/resource APIs access karne par ADC ya attached service identity sahi tareeke se set karni hogi.
4. Pricing SKU ka rate aur actual workload bill alag ho sakte hain (region, SKU, discounts, billing account/contract, usage conditions). Sirf price API response ko “guaranteed Spot availability” na samjhein.
5. `GCP_PROJECT_ID` aur `GOOGLE_APPLICATION_CREDENTIALS` is waqt sirf placeholders hain; current app inhe read karke price fetch nahi karti. Service-account JSON private rakhein aur Git mein commit na karein.

### Azure

1. [Azure Portal](https://portal.azure.com/) mein subscription select karein. Subscription ID **Subscriptions → selected subscription → Overview** mein milegi.
2. Azure ka [Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices) public retail-rate API hai; public retail price query karne ke liye aam taur par Azure login/secret ki zaroorat nahi hoti. Official API examples mein Virtual Machines aur `Spot` meter names ka data mil sakta hai.
3. Retail rate ko apne Azure agreement ke final bill, discounts, taxes, ya real-time capacity/availability ka substitute na samjhein. API response ko SKU, region, currency, unit, `Spot` meter, aur effective date se filter/validate karna zaroori hai.
4. Agar future integration ko subscription ke private/account-specific cost data ya resources access karne hain, tab **Microsoft Entra ID app registration / managed identity** aur us par limited Azure RBAC role chahiye. Official guide: [Create app registration and service principal](https://learn.microsoft.com/en-us/entra/identity-platform/howto-create-service-principal-portal). Client secret ko sirf backend secret store/`.env` mein rakhein.
5. `AZURE_SUBSCRIPTION_ID` abhi placeholder hai. Current project Retail Prices API call ya Azure resource operation nahi karta.

### MongoDB Atlas (optional)

1. [MongoDB Atlas](https://www.mongodb.com/cloud/atlas/register) par account/cluster banayein.
2. Database user banayein aur Network Access mein sirf apne development IP ko allow karein.
3. Cluster ke **Connect → Drivers** se MongoDB connection URI lein.
4. URI ko `MONGODB_URI` mein [backend/.env](./backend/.env) mein set karke backend restart karein.
5. `/api/health` par `persistence=mongodb` check karein. MongoDB connection na ho to demo `memory` mode mein chalta hai.

---

## Live prices app mein asal mein kaise aayengi?

Provider account/credential lena sirf pehla hissa hai; backend code bhi chahiye. Current implementation status:

1. `/api/pricing` abhi empty `items` list aur “Live provider pricing adapters are not configured” warning return karta hai.
2. `/api/pricing/refresh` bhi clearly batata hai ki adapters nahi hain; woh fake snapshot save nahi karta.
3. AWS, GCP, Azure adapter modules, scheduled refresh, aur live-price UI mapping abhi implement nahi huye.
4. Isliye `.env` mein key bharne se abhi **koi live price appear nahi hoga**.

Actual implementation ke liye har cloud ka alag backend adapter likhna hoga, jo:

- AWS Spot history, GCP SKU/pricing data, aur Azure Retail Rates ko official API se retrieve kare;
- timeout, pagination, provider errors, credentials aur rate limits handle kare;
- exact region, machine/SKU, vCPU/RAM, Spot pricing type, unit, currency aur observation timestamp normalize/validate kare;
- incompatible rates reject kare aur stale/unsupported values ko clearly flag kare;
- snapshots ko persist karke UI ke `/pricing`/`refresh` endpoints mein dikhaye;
- provider price aur availability/capacity ko alag concepts ki tarah report kare;
- unit/API tests ke baad hi recommendations enable kare.

Provider documentation:

- AWS: [DescribeSpotPriceHistory](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeSpotPriceHistory.html)
- Google Cloud: [Get pricing information using the Cloud Billing API](https://cloud.google.com/billing/docs/how-to/get-pricing-information-api)
- Azure: [Retail Prices REST API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices)

---

## Safety reminders

- Provider secrets `backend\.env` ke bahar share/commit mat karein. Screenshot ya professor demo mein key values hide rakhein.
- Root `.env` / `VITE_...` variables browser bundle mein expose ho sakte hain—unmein secrets mat rakhein.
- App mein auth nahi hai; local computer ke bahar backend expose mat karein.
- AWS/GCP/Azure par resource create/terminate karne ki permissions is demo ke liye mat dein. Current build mein provisioning disabled hai.
- Prices, permissions, billing aur availability account, region, SKU, discounts aur API behavior ke hisaab se badal sakte hain. Live integration ko account/provider docs ke against test karna hoga.
