import { useCallback, useEffect, useMemo, useState } from 'react'
import './App.css'

const API = import.meta.env.VITE_API_URL || '/api'
const navigation = [
  ['Overview', '⌂'],
  ['Cloud pricing', '◈'],
  ['Cost calculator', '⌗'],
  ['Best cloud decision', '✳'],
  ['Migration center', '⇄'],
  ['Analytics & history', '▥'],
  ['Settings', '⚙'],
]
const providers = ['GCP', 'Azure']
const colors = { GCP: '#4285f4', Azure: '#16a6a1' }
const formatMoney = (value, digits = 4, currency = 'USD') => {
  if (value == null || !Number.isFinite(Number(value))) return '—'
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }).format(Number(value))
  } catch {
    return `${Number(value).toFixed(digits)} ${currency}`
  }
}
const formatDate = (value) => value ? new Date(value).toLocaleString() : 'Not fetched'
const terminalStates = ['COMPLETED', 'FAILED', 'CANCELLED']
const initialCost = {
  current_provider: 'GCP',
  current_hourly_cost: '',
  target_provider: 'Azure',
  target_hourly_cost: '',
  duration_hours: '',
  transfer_cost: '0',
  migration_overhead: '0',
  other_costs: '0',
  minimum_savings_percent: '0',
  pricing_snapshot_id: '',
}
const emptyStatus = {
  mode: 'demo',
  database: { status: 'checking', persistence: 'memory' },
  integrations: {},
  pricing: { providers: {} },
}

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    const message = typeof body.detail === 'string' ? body.detail : body.message
    throw new Error(message || `Request failed (${response.status})`)
  }
  return body
}

function App() {
  const [page, setPage] = useState('Overview')
  const [pricing, setPricing] = useState([])
  const [status, setStatus] = useState(emptyStatus)
  const [migrations, setMigrations] = useState([])
  const [history, setHistory] = useState({ items: [], migration_counts: {} })
  const [cost, setCost] = useState(initialCost)
  const [analysis, setAnalysis] = useState(null)
  const [costExplanation, setCostExplanation] = useState('')
  const [costExplanationBusy, setCostExplanationBusy] = useState(false)
  const [decision, setDecision] = useState(null)
  const [aiExplanation, setAiExplanation] = useState('')
  const [explanationBusy, setExplanationBusy] = useState(false)
  const [pricingBusy, setPricingBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')
  const [region, setRegion] = useState('')
  const [azureRegion, setAzureRegion] = useState('eastus')
  const [healthCheckPassed, setHealthCheckPassed] = useState(true)
  const [decisionInputs, setDecisionInputs] = useState({
    current_provider: 'GCP',
    current_hourly_cost: '',
    duration_hours: '720',
    required_vcpu: '',
    required_memory_gb: '',
    transfer_cost: '0',
    migration_overhead: '0',
    minimum_savings_percent: '10',
    region: '',
    pricing_type: 'OnDemand',
    workload_tolerates_interruptions: false,
  })
  const [migrationInputs, setMigrationInputs] = useState({
    source_provider: 'GCP',
    target_provider: 'Azure',
    workload_name: '',
  })

  const notify = useCallback((message) => {
    setToast(message)
    window.setTimeout(() => setToast(''), 4500)
  }, [])

  const loadData = useCallback(async () => {
    setLoading(true)
    setError('')
    const results = await Promise.allSettled([
      api('/health'),
      api('/pricing?limit=500'),
      api('/pricing/status'),
      api('/migrations'),
      api('/analytics/savings'),
    ])
    if (results[0].status === 'fulfilled') setStatus((current) => ({ ...current, ...results[0].value }))
    if (results[1].status === 'fulfilled') setPricing(results[1].value.items || [])
    if (results[2].status === 'fulfilled') setStatus((current) => ({ ...current, pricing: results[2].value }))
    if (results[3].status === 'fulfilled') setMigrations(results[3].value.items || [])
    if (results[4].status === 'fulfilled') setHistory(results[4].value)
    const failed = results.find((result) => result.status === 'rejected')
    if (failed) setError(`Some workspace data could not be loaded: ${failed.reason.message}`)
    setLoading(false)
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadData() }, 0)
    return () => window.clearTimeout(timer)
  }, [loadData])

  const refreshPricing = async () => {
    setPricingBusy(true)
    setError('')
    try {
      const query = azureRegion ? `?region=${encodeURIComponent(azureRegion)}` : ''
      const result = await api(`/pricing/refresh${query}`, { method: 'POST' })
      setPricing(result.items || [])
      const latestStatus = await api('/pricing/status')
      setStatus((current) => ({ ...current, pricing: latestStatus }))
      const succeeded = Object.values(result.providers || {}).filter((item) => item.records_normalized > 0).length
      notify(succeeded ? `Refresh finished. ${result.records_normalized} catalog records normalized.` : 'Refresh finished without supported price records. See provider status and warnings.')
      if (result.errors?.length) setError(result.errors.join(' '))
    } catch (requestError) {
      setError(`Pricing refresh failed: ${requestError.message}`)
    } finally {
      setPricingBusy(false)
    }
  }

  const calculate = async (event) => {
    event.preventDefault()
    setError('')
    try {
      const result = await api('/cost/calculate', {
        method: 'POST',
        body: JSON.stringify(Object.fromEntries(
          Object.entries(cost).map(([key, value]) => [
            key,
            ['current_provider', 'target_provider', 'pricing_snapshot_id'].includes(key) ? (value || null) : Number(value),
          ]),
        )),
      })
      setAnalysis(result)
      setCostExplanation('')
      setHistory((current) => ({ ...current, items: [result, ...(current.items || [])] }))
      notify('Estimate saved. It is based on your supplied inputs, not billing data.')
    } catch (requestError) {
      setError(`Could not calculate estimate: ${requestError.message}`)
    }
  }

  const explainCost = async () => {
    if (!analysis) return
    setCostExplanationBusy(true)
    setError('')
    try {
      const result = await api('/cost/explain', {
        method: 'POST',
        body: JSON.stringify({
          current_provider: analysis.current_provider,
          target_provider: analysis.target_provider,
          current_hourly_cost: analysis.inputs.current_hourly_cost,
          target_hourly_cost: analysis.inputs.target_hourly_cost,
          duration_hours: analysis.inputs.duration_hours,
          current_cost: analysis.current_cost,
          target_compute_cost: analysis.target_compute_cost,
          transfer_cost: analysis.transfer_cost,
          migration_overhead: analysis.migration_overhead,
          other_costs: analysis.other_costs,
          target_total_cost: analysis.target_total_cost,
          net_savings: analysis.net_savings,
          savings_percent: analysis.savings_percent,
          break_even_hours: analysis.break_even_hours,
          minimum_savings_percent: analysis.minimum_savings_percent,
          meets_savings_threshold: analysis.meets_savings_threshold,
          missing_cost_categories: analysis.missing_cost_categories || [],
        }),
      })
      setCostExplanation(result.explanation)
    } catch (requestError) {
      setError(`AI explanation unavailable: ${requestError.message}`)
    } finally {
      setCostExplanationBusy(false)
    }
  }

  const runDecision = async (event) => {
    event.preventDefault()
    setError('')
    try {
      const request = {
        ...decisionInputs,
        duration_hours: Number(decisionInputs.duration_hours),
        current_hourly_cost: Number(decisionInputs.current_hourly_cost),
        required_vcpu: Number(decisionInputs.required_vcpu),
        required_memory_gb: Number(decisionInputs.required_memory_gb),
        transfer_cost: Number(decisionInputs.transfer_cost),
        migration_overhead: Number(decisionInputs.migration_overhead),
        minimum_savings_percent: Number(decisionInputs.minimum_savings_percent),
      }
      const result = await api('/decisions/recommend', { method: 'POST', body: JSON.stringify(request) })
      setDecision(result)
      setAiExplanation('')
    } catch (requestError) {
      setError(`Decision could not be evaluated: ${requestError.message}`)
    }
  }

  const explainDecision = async () => {
    if (!decision) return
    setExplanationBusy(true)
    setError('')
    try {
      const toExplanationCandidate = (candidate) => ({
        provider: candidate.provider,
        instance_type: candidate.instance_type || 'Unknown',
        eligible: Boolean(candidate.eligible),
        reason: candidate.reason || '',
        hourly_price: candidate.hourly_price ?? null,
        currency: candidate.currency ?? null,
      })
      const result = await api('/decisions/explain', {
        method: 'POST',
        body: JSON.stringify({
          recommended_provider: decision.recommended_provider,
          reason: decision.reason,
          estimated_net_savings: decision.estimated_net_savings,
          candidates: (decision.candidates || []).slice(0, 25).map(toExplanationCandidate),
          rejected_candidates: (decision.rejected_candidates || []).slice(0, 25).map(toExplanationCandidate),
          limitations: decision.limitations || [],
        }),
      })
      setAiExplanation(result.explanation)
    } catch (requestError) {
      setError(`AI explanation unavailable: ${requestError.message}`)
    } finally {
      setExplanationBusy(false)
    }
  }

  const createMigration = async (event) => {
    event.preventDefault()
    if (migrationInputs.source_provider === migrationInputs.target_provider) {
      setError('Choose different source and target providers for the simulation.')
      return
    }
    setError('')
    try {
      const result = await api('/migrations', {
        method: 'POST',
        body: JSON.stringify({ ...migrationInputs, simulation: true }),
      })
      setMigrations((current) => [result, ...current])
      notify('Simulation created. No cloud resources were created or moved.')
    } catch (requestError) {
      setError(`Simulation could not be created: ${requestError.message}`)
    }
  }

  const advanceMigration = async (migration) => {
    try {
      const result = await api(`/migrations/${migration.migration_id}/advance`, {
        method: 'POST',
        body: JSON.stringify({ health_check_passed: healthCheckPassed, confirm_live: false }),
      })
      setMigrations((current) => current.map((item) => item.migration_id === result.migration_id ? result : item))
    } catch (requestError) {
      setError(`Simulation was not advanced: ${requestError.message}`)
    }
  }

  const cancelMigration = async (migration) => {
    try {
      const result = await api(`/migrations/${migration.migration_id}/cancel`, { method: 'POST' })
      setMigrations((current) => current.map((item) => item.migration_id === result.migration_id ? result : item))
    } catch (requestError) {
      setError(`Simulation was not cancelled: ${requestError.message}`)
    }
  }

  const prepareMigration = (sourceProvider, targetProvider) => {
    setMigrationInputs((current) => ({
      ...current,
      source_provider: sourceProvider,
      target_provider: targetProvider,
      workload_name: current.workload_name || 'decision-candidate',
    }))
    setPage('Migration center')
  }

  const savedSavings = (history.items || []).reduce((total, item) => total + (Number(item.net_savings) || 0), 0)
  const currentStatus = Object.values(status.pricing?.providers || {})
  const latestFetch = currentStatus
    .map((item) => item.last_successful_fetch_at)
    .filter(Boolean)
    .sort((a, b) => new Date(b) - new Date(a))[0]

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#" onClick={(event) => { event.preventDefault(); setPage('Overview') }}>
          <span className="brand-mark">C</span><span>cloud<span className="brand-light">optima</span></span>
        </a>
        <div className="workspace-caption">WORKSPACE</div>
        <div className="workspace-switch"><span className="workspace-avatar">C</span><span><b>CloudOptima</b><small>Local workspace</small></span></div>
        <nav aria-label="Main navigation">
          {navigation.map(([label, icon]) => (
            <button key={label} className={`nav-item ${page === label ? 'active' : ''}`} onClick={() => setPage(label)}>
              <span className="nav-icon">{icon}</span><span>{label}</span>
              {label === 'Migration center' && migrations.length > 0 && <span className="nav-count">{migrations.length}</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom"><span className="sidebar-note">Catalog prices are estimates, not your negotiated rates or bill.</span><span className="sidebar-version">CloudOptima · GCP + Azure</span></div>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs">Workspace <span>/</span> <b>{page}</b></div>
          <div className="top-actions">
            <span className={`mode-pill ${status.mode === 'demo' ? 'demo' : ''}`}><i />{status.mode === 'demo' ? 'Demo-safe mode' : 'Live catalog mode'}</span>
            <button className="button secondary compact" onClick={loadData} disabled={loading}>{loading ? 'Loading…' : '↻ Sync status'}</button>
          </div>
        </header>
        <section className="content">
          {error && <div className="alert error-alert" role="alert"><span>{error}</span><button onClick={() => setError('')} aria-label="Dismiss error">×</button></div>}
          {page === 'Overview' && <OverviewPage
            pricing={pricing} status={status} migrations={migrations} analyses={history.items || []}
            savedSavings={savedSavings} latestFetch={latestFetch} loading={loading}
            refresh={refreshPricing} busy={pricingBusy} navigate={setPage}
          />}
          {page === 'Cloud pricing' && <PricingPage
            pricing={pricing} status={status.pricing || { providers: {} }} busy={pricingBusy}
            refresh={refreshPricing} region={region} setRegion={setRegion}
            azureRegion={azureRegion} setAzureRegion={setAzureRegion}
          />}
          {page === 'Cost calculator' && <CalculatorPage
            cost={cost} setCost={setCost} calculate={calculate} analysis={analysis} pricing={pricing} history={history.items || []}
            explain={explainCost} explanation={costExplanation} explanationBusy={costExplanationBusy}
          />}
          {page === 'Best cloud decision' && <DecisionPage
            inputs={decisionInputs} setInputs={setDecisionInputs} run={runDecision} result={decision}
            pricing={pricing} prepareMigration={prepareMigration} explain={explainDecision}
            explanation={aiExplanation} explanationBusy={explanationBusy}
          />}
          {page === 'Migration center' && <MigrationPage
            migrations={migrations} inputs={migrationInputs} setInputs={setMigrationInputs}
            create={createMigration} advance={advanceMigration} cancel={cancelMigration}
            healthCheckPassed={healthCheckPassed} setHealthCheckPassed={setHealthCheckPassed}
          />}
          {page === 'Analytics & history' && <AnalyticsPage
            pricing={pricing} history={history} migrations={migrations} savedSavings={savedSavings}
          />}
          {page === 'Settings' && <SettingsPage status={status} refresh={refreshPricing} busy={pricingBusy} />}
        </section>
        <footer className="footer"><span>© {new Date().getFullYear()} CloudOptima</span><span>Provider retail catalogs · estimates only · migration simulations</span></footer>
      </main>
      {toast && <div className="toast" role="status">{toast}<button onClick={() => setToast('')} aria-label="Dismiss notification">×</button></div>}
    </div>
  )
}

function PageHeader({ eyebrow, title, subtitle, action }) {
  return <div className="page-header"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{subtitle}</p></div>{action}</div>
}

function OverviewPage({ pricing, status, migrations, analyses, savedSavings, latestFetch, loading, refresh, busy, navigate }) {
  const fresh = pricing.filter((item) => item.freshness === 'fresh').length
  const connected = Object.values(status.pricing?.providers || {}).filter((provider) => provider.status === 'connected' || provider.status === 'cached').length
  const priced = pricing.filter((item) => item.hourly_price != null).length
  const latest = pricing.slice(0, 6)
  return <>
    <PageHeader eyebrow="CLOUD COST OPERATIONS" title="Overview" subtitle="A clear view of catalog coverage, price freshness, and estimated savings." action={<button className="button primary" onClick={refresh} disabled={busy}>{busy ? 'Refreshing…' : '↻ Refresh pricing'}</button>} />
    {connected < 2 && <div className="alert warning-alert"><b>Provider coverage is partial.</b><span>Check GCP and Azure connection states. No catalog price is treated as a negotiated rate or deployed-resource cost.</span><button className="text-button" onClick={() => navigate('Settings')}>View settings →</button></div>}
    <div className="metric-grid">
      <Metric label="Catalog records" value={loading ? '…' : pricing.length} detail={`${priced} with supported hourly rates`} icon="◈" tone="blue" />
      <Metric label="Fresh records" value={loading ? '…' : `${fresh} / ${pricing.length}`} detail="Observed in the last 24 hours" icon="◷" tone="green" />
      <Metric label="Saved estimated savings" value={formatMoney(savedSavings, 2)} detail={`${analyses.length} saved calculations · estimates only`} icon="↘" tone="purple" />
      <Metric label="Migration simulations" value={migrations.length} detail={`${migrations.filter((item) => !terminalStates.includes(item.state)).length} in progress`} icon="⇄" tone="orange" />
    </div>
    <div className="dashboard-grid">
      <section className="panel">
        <div className="panel-heading"><div><h2>Verified hourly catalog prices</h2><p>Supported hourly rates from stored catalog snapshots · USD only</p></div><button className="text-button" onClick={() => navigate('Cloud pricing')}>Explore prices →</button></div>
        <PriceBars items={pricing.filter((item) => item.hourly_price != null && item.currency === 'USD' && item.pricing_model_status === 'verified').slice(0, 8)} />
      </section>
      <section className="panel">
        <div className="panel-heading"><div><h2>Integration health</h2><p>Backend configuration, not credential disclosure</p></div><button className="text-button" onClick={() => navigate('Settings')}>Details →</button></div>
        <ProviderStatusRows providers={status.pricing?.providers || {}} />
        <div className="last-refresh"><span>Last successful refresh</span><b>{formatDate(latestFetch)}</b></div>
      </section>
    </div>
    <section className="panel table-panel">
      <div className="panel-heading"><div><h2>Latest pricing observations</h2><p>{latest.length ? 'Catalog records with their source and observed time' : 'No stored catalog records yet'}</p></div><button className="text-button" onClick={() => navigate('Cloud pricing')}>View all →</button></div>
      <PriceTable items={latest} compact />
    </section>
    <div className="dashboard-grid lower-grid">
      <section className="panel"><div className="panel-heading"><div><h2>Recent estimates</h2><p>Saved calculations from this workspace</p></div><button className="text-button" onClick={() => navigate('Analytics & history')}>History →</button></div>
        {(analyses || []).length ? <div className="compact-list">{analyses.slice(0, 4).map((item, index) => <div className="compact-row" key={item.created_at || index}><span><b>{item.current_provider} → {item.target_provider}</b><small>{formatDate(item.created_at)}</small></span><strong>{formatMoney(item.net_savings, 2)}</strong></div>)}</div> : <EmptyState title="No saved estimates" text="Run a cost calculation to start a real workspace history." />}
      </section>
      <section className="panel"><div className="panel-heading"><div><h2>Simulation activity</h2><p>Simulations only · no cloud resource changes</p></div><button className="text-button" onClick={() => navigate('Migration center')}>Open center →</button></div>
        {migrations.length ? migrations.slice(0, 4).map((item) => <div className="compact-row" key={item.migration_id}><span><b>{item.source_provider} → {item.target_provider}</b><small>{item.workload_name} · {formatDate(item.updated_at || item.created_at)}</small></span><StatusBadge value={item.state} /></div>) : <EmptyState title="No simulations" text="Create a simulation to review the guarded workflow." />}
      </section>
    </div>
  </>
}

function Metric({ label, value, detail, icon, tone }) {
  return <article className="metric-card"><span className={`metric-icon ${tone}`}>{icon}</span><div className="metric-label">{label}</div><div className="metric-value">{value}</div><div className="metric-delta">{detail}</div></article>
}

function PriceBars({ items }) {
  const groups = useMemo(() => {
    const values = providers.map((provider) => {
      const rows = items.filter((item) => item.provider === provider)
      return { provider, count: rows.length, average: rows.length ? rows.reduce((sum, item) => sum + item.hourly_price, 0) / rows.length : null }
    })
    const max = Math.max(...values.map((item) => item.average || 0), 0.0001)
    return values.map((item) => ({ ...item, height: item.average == null ? 0 : Math.max(4, item.average / max * 100) }))
  }, [items])
  if (!items.length) return <EmptyState title="No comparable hourly prices yet" text="Refresh the provider catalogs. Unsupported units, currencies, and incomplete VM pricing remain clearly marked instead of being guessed." />
  return <div className="price-chart" aria-label="Average verified catalog hourly price by provider">
    {groups.map((group) => <div className="price-chart-column" key={group.provider}><div className="price-chart-value">{group.average == null ? 'No rows' : `${formatMoney(group.average, 5)}/h`}</div><div className="price-chart-track"><div style={{ height: `${group.height}%`, background: colors[group.provider] }} /></div><b>{group.provider}</b><small>{group.count} observations</small></div>)}
    <p className="chart-footnote">Averages include only the visible verified hourly USD observations; catalog products may not be like-for-like.</p>
  </div>
}

function ProviderStatusRows({ providers: providerStatuses }) {
  return <div className="provider-status-list">{providers.map((provider) => {
    const state = providerStatuses[provider] || {}
    return <div className="provider-status-row" key={provider}><span className={`provider-dot ${provider.toLowerCase()}`} /><span className="provider-status-name"><b>{provider === 'GCP' ? 'Google Cloud' : 'Microsoft Azure'}</b><small>{state.error || `Last success: ${formatDate(state.last_successful_fetch_at)}`}</small></span><StatusBadge value={state.status || 'unknown'} /></div>
  })}</div>
}

function StatusBadge({ value }) {
  const label = String(value || 'unknown').replaceAll('_', ' ')
  const state = ['connected', 'cached', 'completed'].includes(String(value).toLowerCase()) ? 'success' : ['error', 'failed', 'rate_limited'].includes(String(value).toLowerCase()) ? 'danger' : 'neutral'
  return <span className={`status-badge ${state}`}>{label}</span>
}

function PricingPage({ pricing, status, busy, refresh, region, setRegion, azureRegion, setAzureRegion }) {
  const [provider, setProvider] = useState('All')
  const [model, setModel] = useState('All')
  const [search, setSearch] = useState('')
  const [freshness, setFreshness] = useState('All')
  const rows = pricing.filter((item) => (provider === 'All' || item.provider === provider)
    && (model === 'All' || item.pricing_type === model)
    && (freshness === 'All' || item.freshness === freshness.toLowerCase())
    && (!search || `${item.instance_type} ${item.sku_id || ''} ${item.product_id || ''} ${item.meter_name || ''}`.toLowerCase().includes(search.toLowerCase()))
    && (!region || item.region.toLowerCase().includes(region.toLowerCase())))
  return <>
    <PageHeader eyebrow="PRICE TELEMETRY" title="Cloud pricing explorer" subtitle="Inspect provider catalog evidence, pricing model, units, and freshness." action={<button className="button primary" onClick={refresh} disabled={busy}>{busy ? 'Refreshing…' : '↻ Refresh catalogs'}</button>} />
    <div className="alert info-alert"><b>Public retail catalog data.</b><span>Azure VM pricing is fetched for a region (default: eastus). Choose a region before refreshing to narrow requests and reduce rate limiting. Rates are not negotiated contract prices, actual bills, or guarantees of deployed capacity.</span></div>
    <div className="filter-bar">
      <label className="filter-field"><span>Azure VM catalog region</span><input value={azureRegion} onChange={(event) => setAzureRegion(event.target.value)} placeholder="eastus" /></label>
      <span className="muted">Refresh fetches Azure VM prices for this region; the table filter below only filters displayed records.</span>
    </div>
    <div className="filter-bar">
      <label className="search-field"><span>Search catalog</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="SKU, product, or meter" /></label>
      <Filter label="Provider" value={provider} onChange={setProvider} values={['All', ...providers]} />
      <Filter label="Pricing model" value={model} onChange={setModel} values={['All', 'Spot', 'OnDemand', 'Unclassified']} />
      <Filter label="Freshness" value={freshness} onChange={setFreshness} values={['All', 'Fresh', 'Stale']} />
      <label className="filter-field"><span>Region</span><input value={region} onChange={(event) => setRegion(event.target.value)} placeholder="All regions (e.g. eastus)" /></label>
    </div>
    <div className="provider-inline-status"><ProviderStatusRows providers={status.providers || {}} /></div>
    <section className="panel table-panel">
      <div className="panel-heading"><div><h2>Normalized catalog records</h2><p>{rows.length} shown · source timestamps and SKU identity preserved</p></div><span className="data-label">LIVE CATALOG SNAPSHOTS</span></div>
      <PriceTable items={rows} />
    </section>
  </>
}

function Filter({ label, value, onChange, values, emptyLabel }) {
  return <label className="filter-field"><span>{label}</span><select value={value} onChange={(event) => onChange(event.target.value)}>{values.map((item) => <option key={item || 'all'} value={item}>{item || emptyLabel || 'All'}</option>)}</select></label>
}

function PriceTable({ items, compact = false }) {
  return <div className="table-wrap"><table>
    <thead><tr><th>PROVIDER</th><th>REGION</th><th>SKU / PRODUCT</th><th>CAPACITY</th><th>PRICING MODEL</th><th>HOURLY PRICE</th>{!compact && <><th>CURRENCY / UNIT</th><th>SOURCE / FRESHNESS</th></>}</tr></thead>
    <tbody>{items.length ? items.map((item, index) => <tr key={item.snapshot_id || `${item.provider}-${item.sku_id}-${item.region}-${index}`}>
      <td><span className="provider-cell"><i style={{ background: colors[item.provider] }} />{item.provider}</span></td>
      <td>{item.region}</td>
      <td className="sku-cell"><b>{item.instance_type || item.sku_id || 'Catalog item'}</b><small>{item.sku_id || 'SKU not provided'}{item.arm_sku_name ? ` · ${item.arm_sku_name}` : ''}{item.meter_id ? ` · meter ${item.meter_id}` : ''}{item.meter_name ? ` · ${item.meter_name}` : ''}</small></td>
      <td>{item.specifications_complete ? `${item.vcpu} vCPU · ${item.memory_gb} GB` : <span className="muted">Specs unavailable</span>}</td>
      <td><span className={`type-pill ${item.pricing_type === 'Spot' ? 'spot' : ''}`}>{item.pricing_type}</span><small className="table-subline">{item.pricing_model_status}</small></td>
      <td className="price-cell">{item.hourly_price != null ? formatMoney(item.hourly_price, 5, item.currency) : item.native_price != null ? formatMoney(item.native_price, 5, item.currency) : '—'}{item.hourly_price != null ? <small className="table-subline">per instance-hour</small> : item.native_price != null ? <small className="table-subline">per {item.native_unit_description || item.native_unit || 'catalog unit'} · component rate, not full VM</small> : null}</td>
      {!compact && <><td>{item.currency || 'Unknown'}<small className="table-subline">{item.native_unit_description || item.native_unit || 'Unit not stated'}</small></td><td><span className="source-cell">{item.source}</span><small className="table-subline">{formatDate(item.fetched_at || item.observed_at)} · {item.freshness}</small></td></>}
    </tr>) : <tr><td className="table-empty" colSpan={compact ? 6 : 8}>No catalog records match these filters. Refresh the catalogs or adjust your filters.</td></tr>}</tbody>
  </table></div>
}

function CalculatorPage({ cost, setCost, calculate, analysis, pricing, history, explain, explanation, explanationBusy }) {
  const candidates = pricing.filter((item) => item.hourly_price != null && item.currency === 'USD' && item.pricing_model_status === 'verified')
  const update = (key) => (event) => setCost((current) => ({
    ...current,
    [key]: event.target.value,
    ...(['target_provider', 'target_hourly_cost'].includes(key) ? { pricing_snapshot_id: '' } : {}),
  }))
  const pickCandidate = (event) => {
    const candidate = candidates[Number(event.target.value)]
    if (!candidate) return
    setCost((current) => ({
      ...current,
      target_provider: candidate.provider,
      target_hourly_cost: String(candidate.hourly_price),
      pricing_snapshot_id: candidate.snapshot_id || '',
    }))
  }
  return <>
    <PageHeader eyebrow="DETERMINISTIC ESTIMATE" title="Cost calculator" subtitle="Calculate a workload estimate from your inputs and optional catalog rate evidence." />
    <div className="calculator-layout">
      <form onSubmit={calculate} className="panel form-panel">
        <div className="panel-heading"><div><h2>Workload assumptions</h2><p>Values are estimates supplied by you unless selected from catalog evidence.</p></div></div>
        {candidates.length > 0 && <label className="field candidate-select"><span>Use a verified catalog observation (optional)</span><select defaultValue="" onChange={pickCandidate}><option value="">Choose a catalog rate</option>{candidates.map((item, index) => <option key={`${item.provider}-${item.sku_id}-${index}`} value={index}>{item.provider} · {item.pricing_type} · {item.instance_type} · {formatMoney(item.hourly_price, 5)}</option>)}</select></label>}
        <div className="form-grid">
          <Field label="Current provider"><select value={cost.current_provider} onChange={update('current_provider')}><ProviderOptions /></select></Field>
          <Field label="Target provider"><select value={cost.target_provider} onChange={update('target_provider')}><ProviderOptions /></select></Field>
          <Field label="Current hourly compute cost" prefix="$"><input type="number" min="0" step="any" value={cost.current_hourly_cost} onChange={update('current_hourly_cost')} required /></Field>
          <Field label="Target hourly compute cost" prefix="$"><input type="number" min="0" step="any" value={cost.target_hourly_cost} onChange={update('target_hourly_cost')} required /></Field>
          <Field label="Workload duration" suffix="hours"><input type="number" min="0.01" step="any" value={cost.duration_hours} onChange={update('duration_hours')} required /></Field>
          <Field label="Transfer / egress estimate" prefix="$"><input type="number" min="0" step="any" value={cost.transfer_cost} onChange={update('transfer_cost')} required /></Field>
          <Field label="Migration overhead estimate" prefix="$"><input type="number" min="0" step="any" value={cost.migration_overhead} onChange={update('migration_overhead')} required /></Field>
          <Field label="Other user-estimated costs" prefix="$"><input type="number" min="0" step="any" value={cost.other_costs} onChange={update('other_costs')} required /></Field>
          <Field label="Minimum savings threshold" suffix="%"><input type="number" min="0" max="100" step="any" value={cost.minimum_savings_percent} onChange={update('minimum_savings_percent')} required /></Field>
        </div>
        <p className="assumption-note">Transfer, migration, and other costs are added once. Taxes, discounts, storage, support, and licensing are excluded unless included in your own estimates.</p>
        <button className="button primary" type="submit">Save cost estimate →</button>
      </form>
      <CostResult analysis={analysis} explain={explain} explanation={explanation} explanationBusy={explanationBusy} />
    </div>
    <section className="panel table-panel history-panel"><div className="panel-heading"><div><h2>Saved cost estimates</h2><p>{history.length} saved in current persistence mode</p></div></div><AnalysisTable items={history} /></section>
  </>
}

function ProviderOptions() { return providers.map((provider) => <option key={provider} value={provider}>{provider}</option>) }
function Field({ label, prefix, suffix, children }) { return <label className="field"><span>{label}</span><div className="input-wrap">{prefix && <span>{prefix}</span>}{children}{suffix && <span>{suffix}</span>}</div></label> }

function CostResult({ analysis, explain, explanation, explanationBusy }) {
  if (!analysis) return <section className="panel result-panel empty-result"><span className="result-placeholder">⌗</span><h2>Your estimate appears here</h2><p>Submit the assumptions to see the full cost breakdown and save the result.</p></section>
  const rows = [['Current compute', analysis.current_cost], ['Target compute', analysis.target_compute_cost], ['Transfer estimate', analysis.transfer_cost], ['Migration overhead', analysis.migration_overhead], ['Other estimated costs', analysis.other_costs]]
  return <section className="panel result-panel"><div className="result-heading"><div><span className="eyebrow">ESTIMATED OUTCOME</span><h2>Cost breakdown</h2></div><StatusBadge value="estimate" /></div><div className="breakdown">{rows.map(([label, value]) => <div key={label}><span>{label}</span><b>{formatMoney(value, 2)}</b></div>)}<div className="breakdown-total"><span>Target total cost</span><b>{formatMoney(analysis.target_total_cost, 2)}</b></div></div><div className={`net-result ${analysis.net_savings < 0 ? 'loss' : ''}`}><span>Estimated net savings</span><strong>{formatMoney(analysis.net_savings, 2)}</strong><small>{Number(analysis.savings_percent).toFixed(2)}% · assumptions only</small></div><div className="break-even"><span>Break-even duration</span><b>{analysis.break_even_hours == null ? 'Not reached' : `${Number(analysis.break_even_hours).toFixed(2)} hours`}</b></div><p className="result-note">Optional AI explanation sends this estimate summary to Groq. It does not change the calculation.</p><button className="button secondary full" onClick={explain} disabled={explanationBusy}>{explanationBusy ? 'Generating explanation…' : 'Explain this estimate with AI'}</button>{explanation && <div className="ai-explanation"><b>AI explanation · Groq</b><p>{explanation}</p></div>}<p className="result-note">Estimate only; not an actual bill or guaranteed savings. Excluded categories may materially change the outcome.</p></section>
}

function DecisionPage({ inputs, setInputs, run, result, pricing, prepareMigration, explain, explanation, explanationBusy }) {
  const update = (key) => (event) => setInputs((current) => ({ ...current, [key]: event.target.type === 'checkbox' ? event.target.checked : event.target.value }))
  return <>
    <PageHeader eyebrow="RULE-BASED COMPARISON" title="Best cloud decision" subtitle="Recommendations require verified pricing, known capacity, compatible region, freshness, and like-for-like pricing models." />
    <div className="decision-layout">
      <form onSubmit={run} className="panel form-panel">
        <h2>Workload requirements</h2><p className="panel-subtitle">Spot candidates are only allowed when the workload is explicitly interruption tolerant.</p>
        <div className="form-grid">
          <Field label="Current provider"><select value={inputs.current_provider} onChange={update('current_provider')}><ProviderOptions /></select></Field>
          <Field label="Requested pricing model"><select value={inputs.pricing_type} onChange={update('pricing_type')}><option>OnDemand</option><option>Spot</option><option>Any</option></select></Field>
          <Field label="Current hourly cost" prefix="$"><input type="number" min="0" step="any" value={inputs.current_hourly_cost} onChange={update('current_hourly_cost')} required /></Field>
          <Field label="Duration" suffix="hours"><input type="number" min="0.01" step="any" value={inputs.duration_hours} onChange={update('duration_hours')} required /></Field>
          <Field label="Required vCPU"><input type="number" min="1" step="1" value={inputs.required_vcpu} onChange={update('required_vcpu')} required /></Field>
          <Field label="Required memory" suffix="GB"><input type="number" min="0.1" step="any" value={inputs.required_memory_gb} onChange={update('required_memory_gb')} required /></Field>
          <Field label="Region (provider ID)"><input value={inputs.region} onChange={update('region')} placeholder="e.g. us-east1 or eastus" required /></Field>
          <Field label="Minimum savings" suffix="%"><input type="number" min="0" max="100" step="any" value={inputs.minimum_savings_percent} onChange={update('minimum_savings_percent')} required /></Field>
          <Field label="Transfer estimate" prefix="$"><input type="number" min="0" step="any" value={inputs.transfer_cost} onChange={update('transfer_cost')} /></Field>
          <Field label="Migration overhead" prefix="$"><input type="number" min="0" step="any" value={inputs.migration_overhead} onChange={update('migration_overhead')} /></Field>
        </div>
        <label className="checkbox-field"><input type="checkbox" checked={inputs.workload_tolerates_interruptions} onChange={update('workload_tolerates_interruptions')} />Workload can tolerate Spot/preemptible interruption</label>
        <button className="button primary" type="submit">Evaluate catalog candidates →</button>
      </form>
      <DecisionResult result={result} pricingCount={pricing.length} prepareMigration={prepareMigration} currentProvider={inputs.current_provider} explain={explain} explanation={explanation} explanationBusy={explanationBusy} />
    </div>
  </>
}

function DecisionResult({ result, pricingCount, prepareMigration, currentProvider, explain, explanation, explanationBusy }) {
  if (!result) return <section className="panel decision-result empty-result"><span className="result-placeholder">✳</span><h2>No decision run yet</h2><p>The engine will stay on the current provider unless valid like-for-like candidates qualify.</p><p>{pricingCount} stored catalog records available for evaluation.</p></section>
  return <section className="panel decision-result"><span className="eyebrow">DETERMINISTIC RESULT</span><div className="decision-provider"><span className="provider-logo">{result.recommended_provider}</span><div><small>RECOMMENDATION</small><h2>{result.recommended_provider}</h2></div><StatusBadge value={result.mode || 'unavailable'} /></div><p>{result.reason}</p><div className="decision-summary"><span>Estimated net savings</span><b>{result.estimated_net_savings == null ? 'Unavailable' : formatMoney(result.estimated_net_savings, 2)}</b></div><h3>Evaluated candidates ({result.candidates?.length || 0})</h3>{result.candidates?.length ? result.candidates.map((item, index) => <div className="candidate-row" key={`${item.provider}-${item.sku_id}-${index}`}><span><i style={{ background: colors[item.provider] }} />{item.provider} · {item.instance_type}</span><b>{formatMoney(item.hourly_price, 5)}</b><small>{item.reason}</small></div>) : <EmptyState title="No eligible candidate" text="No current record has all verified hourly price, USD currency, region, pricing model, freshness, and capacity data required for this workload." />}<h3>Excluded observations ({result.rejected_candidates?.length || 0})</h3>{result.rejected_candidates?.slice(0, 8).map((item, index) => <div className="candidate-row rejected-row" key={`${item.provider}-${index}`}><span>{item.provider}</span><small>{item.reason}</small></div>)}<p className="result-note">Optional AI explanation sends this decision summary to Groq. It does not affect the numerical result.</p><button className="button secondary full" onClick={explain} disabled={explanationBusy}>{explanationBusy ? 'Generating explanation…' : 'Explain decision with AI'}</button>{explanation && <div className="ai-explanation"><b>AI explanation · Groq</b><p>{explanation}</p></div>}<button className="button secondary full" disabled={!result.candidates?.some((item) => item.eligible)} onClick={() => prepareMigration(currentProvider, result.recommended_provider)}>Prepare migration simulation</button><p className="result-note">The rules engine—not AI—makes the recommendation. It never provisions resources. Retail rates are not actual bills or negotiated prices.</p></section>
}

function MigrationPage({ migrations, inputs, setInputs, create, advance, cancel, healthCheckPassed, setHealthCheckPassed }) {
  const update = (key) => (event) => setInputs((current) => ({ ...current, [key]: event.target.value }))
  return <>
    <PageHeader eyebrow="SAFE WORKFLOW" title="Migration center" subtitle="Exercise the workflow state machine only. No real workloads, networks, or DNS records are changed." />
    <div className="alert warning-alert"><b>Simulation only.</b><span>This UI does not provision, migrate, or switch live traffic. Simulated completion is not proof of a real migration.</span></div>
    <form className="panel migration-create" onSubmit={create}><div className="form-grid">
      <Field label="Source provider"><select value={inputs.source_provider} onChange={update('source_provider')}><ProviderOptions /></select></Field>
      <Field label="Target provider"><select value={inputs.target_provider} onChange={update('target_provider')}><ProviderOptions /></select></Field>
      <Field label="Workload label"><input value={inputs.workload_name} onChange={update('workload_name')} maxLength="120" placeholder="e.g. analytics-worker" required /></Field>
      <label className="checkbox-field"><input type="checkbox" checked readOnly />Simulation mode enforced</label>
    </div><button className="button primary" type="submit">Create migration simulation →</button></form>
    <div className="migration-list">{migrations.length ? migrations.map((migration) => <MigrationCard key={migration.migration_id} migration={migration} advance={advance} cancel={cancel} healthCheckPassed={healthCheckPassed} setHealthCheckPassed={setHealthCheckPassed} />) : <section className="panel"><EmptyState title="No migration simulations" text="Create a simulation above to view the guarded step-by-step progression." /></section>}</div>
  </>
}

function MigrationCard({ migration, advance, cancel, healthCheckPassed, setHealthCheckPassed }) {
  const states = ['PENDING', 'PROVISIONING', 'DEPLOYING', 'HEALTH_CHECK', 'READY_TO_SWITCH', 'SWITCHING_TRAFFIC', 'VERIFYING', 'COMPLETED']
  const currentIndex = states.indexOf(migration.state)
  return <section className="panel migration-card"><div className="migration-card-head"><div><span className="eyebrow">{migration.workload_name}</span><h2>{migration.source_provider} <span>→</span> {migration.target_provider}</h2></div><StatusBadge value={migration.state} /></div><div className="migration-meta"><span>Created <b>{formatDate(migration.created_at)}</b></span><span className="sim-label">SIMULATION · NO RESOURCE CHANGES</span></div><div className="timeline">{states.map((state, index) => <div key={state} className={`timeline-step ${index <= currentIndex ? 'done' : ''} ${migration.state === 'FAILED' && index === currentIndex ? 'error' : ''}`}><span className="timeline-marker">{index < currentIndex ? '✓' : index + 1}</span><b>{state.replaceAll('_', ' ')}</b></div>)}</div>{migration.history?.length > 0 && <div className="history-message">{migration.history[migration.history.length - 1].message}</div>}<div className="migration-controls">{migration.state === 'HEALTH_CHECK' ? <label className="checkbox-field"><input type="checkbox" checked={healthCheckPassed} onChange={(event) => setHealthCheckPassed(event.target.checked)} />Health check passes</label> : <span className="muted">{migration.source_workload_active === false ? 'Source deactivated in simulation state only' : 'Source remains active'}</span>}<div>{!terminalStates.includes(migration.state) && <><button className="button secondary compact" onClick={() => cancel(migration)}>Cancel</button><button className="button primary compact" onClick={() => advance(migration)}>Advance simulation</button></>}</div></div></section>
}

function AnalyticsPage({ pricing, history, migrations, savedSavings }) {
  const decisions = history.decision_items || []
  return <>
    <PageHeader eyebrow="OBSERVED WORKSPACE HISTORY" title="Analytics & history" subtitle={`Historical snapshots and saved estimates · ${formatMoney(savedSavings, 2)} net estimated savings · no generated sample metrics.`} />
    <div className="metric-grid"><Metric label="Price snapshots" value={pricing.length} detail="Stored records returned by the API" icon="◈" tone="blue" /><Metric label="Cost analyses" value={history.items?.length || 0} detail="Saved deterministic estimates" icon="⌗" tone="purple" /><Metric label="Decision analyses" value={decisions.length} detail="Saved rules-based evaluations" icon="✳" tone="blue" /><Metric label="Migration runs" value={migrations.length} detail="Simulations only" icon="⇄" tone="orange" /></div>
    <section className="panel table-panel"><div className="panel-heading"><div><h2>Cost analysis history</h2><p>Input-based estimates; not billing evidence</p></div></div><AnalysisTable items={history.items || []} /></section>
    <section className="panel table-panel"><div className="panel-heading"><div><h2>Decision history</h2><p>Deterministic recommendations with evaluated candidate and rejection records</p></div></div><DecisionHistoryTable items={decisions} /></section>
    <section className="panel table-panel history-panel"><div className="panel-heading"><div><h2>Recent pricing snapshots</h2><p>Provider-reported observations</p></div></div><PriceTable items={pricing.slice(0, 100)} /></section>
    <section className="panel"><div className="panel-heading"><div><h2>Simulation history</h2><p>State transitions do not represent an actual cloud migration</p></div></div>{migrations.length ? migrations.map((item) => <div className="compact-row" key={item.migration_id}><span><b>{item.source_provider} → {item.target_provider} · {item.workload_name}</b><small>{formatDate(item.created_at)}</small></span><StatusBadge value={item.state} /></div>) : <EmptyState title="No simulation history" text="Created simulations appear here." />}</section>
  </>
}

function DecisionHistoryTable({ items }) {
  return <div className="table-wrap"><table><thead><tr><th>EVALUATED</th><th>CURRENT PROVIDER</th><th>RECOMMENDATION</th><th>ELIGIBLE CANDIDATES</th><th>ESTIMATED SAVINGS</th></tr></thead><tbody>{items.length ? items.map((item, index) => <tr key={item.created_at || index}><td>{formatDate(item.evaluated_at || item.created_at)}</td><td>{item.inputs?.current_provider || '—'}</td><td>{item.recommended_provider}</td><td>{item.candidates?.filter((candidate) => candidate.eligible).length || 0}</td><td>{item.estimated_net_savings == null ? 'Unavailable' : formatMoney(item.estimated_net_savings, 2)}</td></tr>) : <tr><td className="table-empty" colSpan="5">No decision analyses have been saved yet.</td></tr>}</tbody></table></div>
}

function AnalysisTable({ items }) {
  return <div className="table-wrap"><table><thead><tr><th>CREATED</th><th>FROM → TO</th><th>CURRENT COST</th><th>TARGET TOTAL</th><th>NET ESTIMATE</th><th>SAVINGS</th></tr></thead><tbody>{items.length ? items.map((item, index) => <tr key={item.created_at || index}><td>{formatDate(item.created_at)}</td><td>{item.current_provider} → {item.target_provider}</td><td>{formatMoney(item.current_cost, 2)}</td><td>{formatMoney(item.target_total_cost, 2)}</td><td className="price-cell">{formatMoney(item.net_savings, 2)}</td><td>{Number(item.savings_percent || 0).toFixed(2)}%</td></tr>) : <tr><td className="table-empty" colSpan="6">No saved estimates yet.</td></tr>}</tbody></table></div>
}

function SettingsPage({ status, refresh, busy }) {
  return <>
    <PageHeader eyebrow="CONFIGURATION STATUS" title="Settings & integrations" subtitle="Configuration and operational health only. Secrets are never returned to this page." action={<button className="button secondary" onClick={refresh} disabled={busy}>{busy ? 'Refreshing…' : '↻ Refresh catalogs'}</button>} />
    <div className="settings-grid">
      <section className="panel settings-panel"><div className="panel-heading"><div><h2>Provider pricing</h2><p>Backend catalog connection state and last successful fetch</p></div></div><ProviderStatusRows providers={status.pricing?.providers || {}} /><div className="settings-assumption"><span>Pricing source</span><b>Public retail catalogs</b></div><div className="settings-assumption"><span>Authentication</span><b>GCP API key is backend-only; Azure public catalog needs no subscription ID</b></div><div className="settings-assumption"><span>Pricing disclaimer</span><b>Not negotiated rates or actual usage bills</b></div></section>
      <section className="panel settings-panel"><div className="panel-heading"><div><h2>Persistence & runtime</h2><p>Degraded mode is reported explicitly</p></div></div><StatusRow name="FastAPI runtime" detail={`Mode: ${status.mode || 'unknown'}`} value="connected" /><StatusRow name="MongoDB" detail={`Persistence: ${status.database?.persistence || 'unknown'}${status.database?.connection_error ? ` · ${status.database.connection_error}` : ''}`} value={status.database?.status || 'unknown'} /><StatusRow name="Groq explanations" detail="Optional explanations for cost estimates and decisions; AI does not calculate costs or choose providers." value={status.integrations?.groq_explanations || 'not_configured'} /><StatusRow name="Cloud provisioning" detail="Disabled; migration workflow is simulation-only." value="disabled" /><StatusRow name="DNS" detail="Mock behavior only; no production traffic changes." value={status.integrations?.dns || 'mock'} /></section>
    </div>
  </>
}

function StatusRow({ name, detail, value }) { return <div className="status-row"><span><b>{name}</b><small>{detail}</small></span><StatusBadge value={value} /></div> }

function EmptyState({ title, text }) { return <div className="empty-state"><span>◌</span><b>{title}</b><p>{text}</p></div> }

export default App
