import { useCallback, useEffect, useState } from 'react'
import './App.css'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'
const navItems = [
  ['Dashboard', 'Overview', '⌂'],
  ['Cloud pricing', 'Pricing', '◈'],
  ['Cost calculator', 'Calculator', '⌗'],
  ['Decision engine', 'Decision', '✳'],
  ['Migration center', 'Migrations', '⇄'],
  ['Analytics', 'Analytics', '▥'],
  ['Settings', 'Settings', '⚙'],
]
const money = (value, digits = 2) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(value) || 0)
const shortMoney = (value) => money(value, 4)
const providerColor = { AWS: '#f39a37', GCP: '#4588f5', Azure: '#36b2a2' }
const displayDate = (value) => value ? new Date(value).toLocaleString() : 'Not available'
const initialCalculator = { current_provider: 'AWS', current_hourly_cost: '', target_provider: 'GCP', target_hourly_cost: '', duration_hours: '', transfer_cost: '', migration_overhead: '', other_costs: '', minimum_savings_percent: '', required_vcpu: '', required_memory_gb: '', region: '' }

function localRecommendation(prices, assumptions) {
  if (!prices.length) {
    return {
      recommended_provider: assumptions.current_provider,
      reason: 'No pricing records are available; no alternative can be verified. Stay on the current provider until pricing is configured.',
      candidates: [],
      estimated_net_savings: null,
      savings_percent: null,
      mode: 'demo',
    }
  }
  const currentTotal = Number(assumptions.current_hourly_cost) * Number(assumptions.duration_hours)
  const eligible = prices.filter((item) => item.provider !== assumptions.current_provider && item.vcpu >= Number(assumptions.required_vcpu) && item.memory_gb >= Number(assumptions.required_memory_gb) && item.region.toLowerCase() === String(assumptions.region || '').toLowerCase() && item.freshness === 'fresh')
    .map((item) => {
      const total = item.hourly_price * Number(assumptions.duration_hours) + Number(assumptions.transfer_cost) + Number(assumptions.migration_overhead) + Number(assumptions.other_costs || 0)
      const savings = currentTotal - total
      const savingsPercent = currentTotal ? savings / currentTotal * 100 : 0
      return { provider: item.provider, total_cost: total, hourly_price: item.hourly_price, eligible: savings > 0 && savingsPercent >= Number(assumptions.minimum_savings_percent), savings, savings_percent: savingsPercent, reason: 'Estimated total cost includes one-time transfer and migration costs.' }
    }).sort((a, b) => a.total_cost - b.total_cost)
  const selected = eligible.find((item) => item.eligible)
  return {
    recommended_provider: selected?.provider || assumptions.current_provider,
    reason: selected ? `${selected.provider} has the lowest eligible total cost and meets your savings threshold.` : 'No alternative meets your minimum savings threshold; stay on the current provider.',
    candidates: eligible,
    estimated_net_savings: selected?.savings ?? 0,
    savings_percent: selected?.savings_percent ?? 0,
    mode: 'demo',
  }
}

function Icon({ children }) {
  return <span aria-hidden="true" className="nav-icon">{children}</span>
}

function App() {
  const [page, setPage] = useState('Dashboard')
  const [pricing, setPricing] = useState([])
  const [migrations, setMigrations] = useState([])
  const [serviceStatus, setServiceStatus] = useState({ mode: 'demo', database: 'checking', persistence: 'memory' })
  const [pricingBusy, setPricingBusy] = useState(false)
  const [toast, setToast] = useState('')
  const [analysis, setAnalysis] = useState(null)
  const [recommendation, setRecommendation] = useState(null)
  const [calculator, setCalculator] = useState(initialCalculator)
  const [formError, setFormError] = useState('')
  const [healthCheckPassed, setHealthCheckPassed] = useState(true)

  const notify = (message) => {
    setToast(message)
    window.setTimeout(() => setToast(''), 3800)
  }

  const request = useCallback(async (path, options = {}) => {
    const response = await fetch(`${API}${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...options.headers },
    })
    const body = await response.json().catch(() => ({}))
    if (!response.ok) {
      const message = typeof body.detail === 'string' ? body.detail : body.message
      const error = new Error(message || `Request failed (${response.status})`)
      error.status = response.status
      throw error
    }
    return body
  }, [])

  const loadData = useCallback(async () => {
    try {
      const [health, priceData, migrationData] = await Promise.all([
        request('/health'),
        request('/pricing'),
        request('/migrations'),
      ])
      setServiceStatus({ mode: health.mode || 'demo', database: health.database?.status || 'unavailable', persistence: health.database?.persistence || 'memory' })
      setPricing(priceData.items || [])
      setMigrations(migrationData.items || [])
    } catch (error) {
      setServiceStatus({ mode: 'demo', database: error.status ? 'error' : 'unavailable', persistence: 'browser demo' })
      if (error.status) notify(`Backend request failed (${error.status}). ${error.message}`)
    }
  }, [request])

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadData() }, 0)
    return () => window.clearTimeout(timer)
  }, [loadData])

  const refreshPricing = async () => {
    setPricingBusy(true)
    try {
      const result = await request('/pricing/refresh', { method: 'POST' })
      setPricing(result.items || [])
      notify(result.message || 'Demo pricing refreshed. Live provider APIs are not configured.')
    } catch (error) {
      if (error.status) {
        notify(`Pricing refresh failed. ${error.message}`)
        return
      }
      setPricing([])
      notify(`Pricing is unavailable because the backend could not be reached. ${error.message}`)
    } finally {
      setPricingBusy(false)
    }
  }

  const calculate = async (event) => {
    event?.preventDefault()
    setFormError('')
    try {
      const result = await request('/cost/calculate', {
        method: 'POST',
        body: JSON.stringify({
          current_hourly_cost: Number(calculator.current_hourly_cost),
          target_hourly_cost: Number(calculator.target_hourly_cost),
          duration_hours: Number(calculator.duration_hours),
          transfer_cost: Number(calculator.transfer_cost),
          migration_overhead: Number(calculator.migration_overhead),
          other_costs: Number(calculator.other_costs),
          minimum_savings_percent: Number(calculator.minimum_savings_percent),
          current_provider: calculator.current_provider,
          target_provider: calculator.target_provider,
        }),
      })
      setAnalysis(result)
    } catch (error) {
      if (error.status) {
        setFormError(error.message)
        return
      }
      const current = Number(calculator.current_hourly_cost) * Number(calculator.duration_hours)
      const target = Number(calculator.target_hourly_cost) * Number(calculator.duration_hours) + Number(calculator.transfer_cost) + Number(calculator.migration_overhead) + Number(calculator.other_costs)
      if ([current, target, Number(calculator.duration_hours)].some((value) => !Number.isFinite(value) || value < 0) || Number(calculator.duration_hours) <= 0) {
        setFormError('Enter valid non-negative costs and a duration greater than zero.')
        return
      }
      const savings = current - target
      setAnalysis({ current_cost: current, target_total_cost: target, target_compute_cost: Number(calculator.target_hourly_cost) * Number(calculator.duration_hours), transfer_cost: Number(calculator.transfer_cost), migration_overhead: Number(calculator.migration_overhead), other_costs: Number(calculator.other_costs), net_savings: savings, savings_percent: current ? savings / current * 100 : 0, break_even_hours: Number(calculator.current_hourly_cost) > Number(calculator.target_hourly_cost) ? (Number(calculator.transfer_cost) + Number(calculator.migration_overhead) + Number(calculator.other_costs)) / (Number(calculator.current_hourly_cost) - Number(calculator.target_hourly_cost)) : null, note: 'Calculated in browser because the API is unavailable; estimates only.' })
      notify(`Using a browser-only calculation because the API is unavailable. ${error.message}`)
    }
  }

  const recommend = async () => {
    const requiredValues = ['current_hourly_cost', 'duration_hours', 'required_vcpu', 'required_memory_gb', 'minimum_savings_percent']
    if (requiredValues.some((key) => calculator[key] === '' || !Number.isFinite(Number(calculator[key]))) || Number(calculator.duration_hours) <= 0 || !calculator.region) {
      notify('Enter the current hourly price, duration, capacity, threshold, and region before analyzing.')
      return
    }
    try {
      const result = await request('/decisions/recommend', {
        method: 'POST',
        body: JSON.stringify({
          current_provider: calculator.current_provider,
          duration_hours: Number(calculator.duration_hours),
          current_hourly_cost: Number(calculator.current_hourly_cost),
          required_vcpu: Number(calculator.required_vcpu),
          required_memory_gb: Number(calculator.required_memory_gb),
          transfer_cost: Number(calculator.transfer_cost),
          migration_overhead: Number(calculator.migration_overhead),
          minimum_savings_percent: Number(calculator.minimum_savings_percent),
          region: calculator.region,
        }),
      })
      setRecommendation(result)
    } catch (error) {
      if (error.status) {
        notify(`Recommendation failed. ${error.message}`)
        return
      }
      setRecommendation(localRecommendation(pricing, calculator))
      notify('Evaluated locally because the API is unavailable; estimates only.')
    }
  }

  const createMigration = async (target) => {
    const migrationTarget = target === calculator.current_provider
      ? (calculator.current_provider === 'AWS' ? 'GCP' : 'AWS')
      : target || (calculator.current_provider === 'AWS' ? 'GCP' : 'AWS')
    try {
      const result = await request('/migrations', {
        method: 'POST',
        body: JSON.stringify({ source_provider: calculator.current_provider, target_provider: migrationTarget, simulation: true, workload_name: 'unspecified' }),
      })
      setMigrations((items) => [result, ...items])
      notify('Simulation created. No cloud resources were provisioned.')
    } catch (error) {
      if (error.status) {
        notify(`Could not create simulation. ${error.message}`)
        return
      }
      const newItem = { migration_id: `sim-${Date.now()}`, source_provider: calculator.current_provider, target_provider: migrationTarget, workload_name: 'unspecified', state: 'PENDING', simulation: true, created_at: new Date().toISOString(), history: [{ state: 'PENDING', at: new Date().toISOString(), message: 'Simulation created locally; no cloud resources provisioned.' }] }
      setMigrations((items) => [newItem, ...items])
      notify(`Backend unavailable; migration is a browser-only simulation. ${error.message}`)
    }
    setPage('Migration center')
  }

  const advanceMigration = async (migration) => {
    try {
      const result = await request(`/migrations/${migration.migration_id}/advance`, {
        method: 'POST',
        body: JSON.stringify({ health_check_passed: healthCheckPassed, confirm_live: false }),
      })
      setMigrations((items) => items.map((item) => item.migration_id === migration.migration_id ? result : item))
    } catch (error) {
      if (error.status) {
        notify(`Could not advance simulation. ${error.message}`)
        return
      }
      const path = ['PENDING', 'PROVISIONING', 'DEPLOYING', 'HEALTH_CHECK', 'READY_TO_SWITCH', 'SWITCHING_TRAFFIC', 'VERIFYING', 'COMPLETED']
      const next = migration.state === 'HEALTH_CHECK' && !healthCheckPassed ? 'FAILED' : path[Math.min(path.indexOf(migration.state) + 1, path.length - 1)]
      setMigrations((items) => items.map((item) => item.migration_id === migration.migration_id ? { ...item, state: next, updated_at: new Date().toISOString(), history: [...(item.history || []), { state: next, at: new Date().toISOString(), message: next === 'FAILED' ? 'Health check failed.' : 'Browser-only simulation transition.' }] } : item))
      notify('Advanced browser-only simulation. No cloud resources were changed.')
    }
  }

  const cancelMigration = async (migration) => {
    try {
      const result = await request(`/migrations/${migration.migration_id}/cancel`, { method: 'POST' })
      setMigrations((items) => items.map((item) => item.migration_id === migration.migration_id ? result : item))
    } catch (error) {
      if (error.status) {
        notify(`Could not cancel simulation. ${error.message}`)
        return
      }
      setMigrations((items) => items.map((item) => item.migration_id === migration.migration_id ? { ...item, state: 'CANCELLED', updated_at: new Date().toISOString() } : item))
      notify('Simulation cancelled locally.')
    }
  }

  const recommended = recommendation?.recommended_provider

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">◈</span><span>cloud<span className="brand-light">optima</span></span></div>
        <div className="workspace-label">WORKSPACE</div>
        <div className="workspace-switch"><span className="workspace-avatar">C</span><span><b>CloudOptima</b><small>Local workspace</small></span></div>
        <nav aria-label="Main navigation">
          {navItems.map(([label, short, icon]) => (
            <button key={label} className={`nav-item ${page === label ? 'active' : ''}`} onClick={() => setPage(label)}><Icon>{icon}</Icon><span>{short}</span>{label === 'Migration center' && migrations.length > 0 && <span className="nav-count">{migrations.length}</span>}</button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="help-card"><span className="help-icon">?</span><b>Need a hand?</b><p>Explore the getting started guide.</p><button onClick={() => notify('Connect the FastAPI backend for the full guided demo.')}>Open guide <span>↗</span></button></div>
          <div className="user-profile"><span className="user-avatar">DN</span><span><b>Deepesh Navani</b><small>Workspace owner</small></span><span className="more">···</span></div>
        </div>
      </aside>
      <main className="main-area">
        <header className="topbar"><div className="breadcrumbs">Workspace <span>/</span> <b>{page}</b></div><div className="top-actions"><span className={`mode-pill ${serviceStatus.mode === 'demo' ? 'demo' : ''}`}><i />Demo mode</span><button className="icon-button" aria-label="Notifications" onClick={() => notify('You’re all caught up.')}>♧<i className="notification-dot" /></button><span className="top-avatar">DN</span></div></header>
        <div className="content">
          {page === 'Dashboard' && <Dashboard pricing={pricing} migrations={migrations} analysis={analysis} recommendation={recommendation} currentProvider={calculator.current_provider} recommended={recommended} setPage={setPage} />}
          {page === 'Cloud pricing' && <PricingPage pricing={pricing} busy={pricingBusy} refresh={refreshPricing} />}
          {page === 'Cost calculator' && <CalculatorPage calculator={calculator} setCalculator={setCalculator} calculate={calculate} analysis={analysis} formError={formError} />}
          {page === 'Decision engine' && <DecisionPage calculator={calculator} setCalculator={setCalculator} run={recommend} result={recommendation} createMigration={createMigration} />}
          {page === 'Migration center' && <MigrationPage migrations={migrations} advance={advanceMigration} cancel={cancelMigration} create={createMigration} healthCheckPassed={healthCheckPassed} setHealthCheckPassed={setHealthCheckPassed} />}
          {page === 'Analytics' && <AnalyticsPage pricing={pricing} migrations={migrations} analysis={analysis} />}
          {page === 'Settings' && <SettingsPage status={serviceStatus} />}
          <footer className="footer"><span>© {new Date().getFullYear()} CloudOptima</span><span>Cost intelligence for the multi-cloud era <i>•</i> Costs use your entered assumptions</span></footer>
        </div>
      </main>
      {toast && <div className="toast" role="status"><span>✓</span>{toast}<button onClick={() => setToast('')} aria-label="Dismiss notification">×</button></div>}
    </div>
  )
}

function PageHeader({ eyebrow, title, subtitle, action }) {
  return <div className="page-header"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{subtitle}</p></div>{action}</div>
}

function Dashboard({ pricing, migrations, analysis, recommendation, currentProvider, recommended, setPage }) {
  const savings = analysis?.net_savings ?? recommendation?.estimated_net_savings
  const savingsPercent = analysis?.savings_percent ?? recommendation?.savings_percent
  const stayingOnCurrent = recommended === currentProvider
  return <>
    <PageHeader eyebrow={new Intl.DateTimeFormat('en-US', { dateStyle: 'full' }).format(new Date()).toUpperCase()} title="Welcome, Deepesh" subtitle="Your cloud cost workspace is ready." action={<button className="button secondary" onClick={() => setPage('Cloud pricing')}>↻ <span>Check pricing status</span></button>} />
    <div className="notice"><span className="notice-icon">i</span><span><b>No provider pricing is configured.</b> Live prices are unavailable, so no cost or migration recommendation is being fabricated. <button onClick={() => setPage('Settings')}>View integration status →</button></span></div>
    <section className="metric-grid">
      <MetricCard label="Pricing records" value={String(pricing.length)} delta="No live pricing source configured" icon="$" color="violet" />
      <MetricCard label="Estimated net savings" value={savings == null ? '—' : money(savings)} delta={savings == null ? 'Run a cost calculation' : `${savingsPercent.toFixed(1)}% vs. current`} icon="↘" color="green" />
      <MetricCard label="Decision status" value={recommended ? (stayingOnCurrent ? `Stay on ${currentProvider}` : `Move to ${recommended}`) : 'Not evaluated'} delta={recommendation?.reason || 'No provider prices available'} icon="✳" color="blue" provider={recommended} />
      <MetricCard label="Active migrations" value={String(migrations.filter((item) => !['COMPLETED', 'FAILED', 'CANCELLED'].includes(item.state)).length).padStart(2, '0')} delta={`${migrations.length} total operations`} icon="⇄" color="orange" />
    </section>
    <section className="dashboard-grid">
      <div className="panel cost-panel"><div className="panel-heading"><div><h2>Provider cost comparison</h2><p>Available records · no sample prices</p></div><button className="select-like" onClick={() => setPage('Cloud pricing')}>Pricing status <span>→</span></button></div><CostChart pricing={pricing} /><div className="chart-legend">{pricing.map((item) => <span key={item.provider}><i style={{ background: providerColor[item.provider] }} />{item.provider}<b>{shortMoney(item.hourly_price)}/hr</b></span>)}</div></div>
      <div className="panel recommendation-card"><div className="recommendation-top"><span className="sparkle">✳</span><span className="recommendation-tag">DECISION STATUS</span></div><h2>{recommendation ? (stayingOnCurrent ? `Stay on ${currentProvider} for now` : `${recommended} is the lowest eligible target`) : 'No recommendation yet'}</h2><p>{recommendation?.reason || 'Connect a supported pricing source and enter your workload requirements to evaluate providers.'}</p>{savings == null ? <div className="saving-highlight"><div><small>ESTIMATED NET SAVINGS</small><strong>—</strong></div><span className="saving-badge neutral">Unavailable</span></div> : <div className="saving-highlight"><div><small>ESTIMATED NET SAVINGS</small><strong>{money(savings)}<em> / period</em></strong></div><span className={`saving-badge ${stayingOnCurrent ? 'neutral' : savings < 0 ? 'negative' : ''}`}>{stayingOnCurrent ? 'Stay put' : `↘ ${savingsPercent.toFixed(1)}%`}</span></div>}<button className="button primary full" onClick={() => setPage('Decision engine')}>Review decision engine <span>→</span></button><div className="recommendation-foot">No cloud operations are enabled</div></div>
    </section>
    <section className="dashboard-grid lower-grid">
      <div className="panel table-panel"><div className="panel-heading"><div><h2>Latest pricing snapshot</h2><p>No records retrieved</p></div><button className="text-link" onClick={() => setPage('Cloud pricing')}>Pricing settings <span>→</span></button></div><PriceTable pricing={pricing.slice(0, 3)} compact /></div>
      <div className="panel activity-panel"><div className="panel-heading"><div><h2>Recent activity</h2><p>Your latest migration operations</p></div><button className="icon-button subtle" onClick={() => setPage('Migration center')}>↗</button></div>{migrations.length ? migrations.slice(0, 3).map((item) => <div className="activity-row" key={item.migration_id}><span className={`activity-icon ${item.state === 'COMPLETED' ? 'success' : 'pending'}`}>{item.state === 'COMPLETED' ? '✓' : '⇄'}</span><span><b>{item.source_provider} → {item.target_provider}</b><small>{item.simulation ? 'Simulated migration' : 'Migration operation'} · {displayDate(item.updated_at || item.created_at)}</small></span><StateBadge state={item.state} /></div>) : <EmptyState title="No migrations yet" text="Safe workload simulations will appear here." />}</div>
    </section>
  </>
}

function MetricCard({ label, value, delta, icon, color, provider }) {
  return <div className="metric-card"><div className={`metric-icon ${color}`}>{provider ? <i style={{ background: providerColor[provider] }} /> : icon}</div><div className="metric-label">{label}</div><div className="metric-value">{value}</div><div className="metric-delta">{delta}</div></div>
}

function CostChart({ pricing }) {
  if (!pricing.length) return <EmptyState title="No price records available" text="Live pricing adapters are not configured, so there is no provider comparison to chart." />
  const bars = pricing.slice(0, 3)
  const max = Math.max(...bars.map((item) => item.hourly_price), 0.05)
  return <div className="cost-chart"><div className="chart-y-labels"><span>$0.05</span><span>$0.04</span><span>$0.03</span><span>$0.02</span><span>$0.01</span></div><div className="chart-plot"><div className="chart-gridlines"><i /><i /><i /><i /><i /></div><div className="bar-group">{bars.map((item) => <div className="bar-column" key={item.provider}><div className="bar-value">{shortMoney(item.hourly_price)}</div><div className="bar" style={{ height: `${Math.max(18, item.hourly_price / max * 76)}%`, background: providerColor[item.provider] }} /><span>{item.provider}</span></div>)}</div><div className="chart-axis"><span>Sample pricing</span><span>Hourly estimate · USD</span></div></div></div>
}

function PricingPage({ pricing, busy, refresh }) {
  return <>
    <PageHeader eyebrow="PRICE TELEMETRY" title="Cloud pricing" subtitle="Compare spot and preemptible compute across providers." action={<button className="button primary" onClick={refresh} disabled={busy}>{busy ? <span className="spinner" /> : '↻'} {busy ? 'Refreshing…' : 'Check pricing'}</button>} />
    <div className="notice"><span className="notice-icon">!</span><span><b>Pricing unavailable.</b> Provider pricing adapters are not configured. The application will not substitute fabricated prices.</span></div>
    {pricing.length > 0 && <div className="pricing-summary">{pricing.map((item) => <div className="provider-price-card" key={`${item.provider}-${item.region}-${item.instance_type}`}><div className="provider-title"><i style={{ background: providerColor[item.provider] }} /><b>{item.provider}</b></div><strong>{shortMoney(item.hourly_price)}<small>/ hr</small></strong><div className="provider-card-foot">{item.instance_type}<span>{item.vcpu} vCPU · {item.memory_gb} GB</span></div></div>)}</div>}
    <div className="panel table-panel full-panel"><div className="panel-heading"><div><h2>Normalized price records</h2><p>Common schema · USD per instance-hour</p></div><span className="update-label"><i />{pricing.length ? 'Provider source' : 'No source connected'}</span></div><PriceTable pricing={pricing} /></div>
    <div className="info-banner"><span>ⓘ</span><div><b>Provider adapters are not connected</b><p>Checking pricing currently reports adapter status only. No API calls or price records are produced until a provider integration is implemented and configured.</p></div></div>
  </>
}

function PriceTable({ pricing, compact = false }) {
  const rows = pricing.map((item) => (
    <tr key={`${item.provider}-${item.region}-${item.instance_type}`}>
      <td><span className="provider-cell"><i style={{ background: providerColor[item.provider] }} />{item.provider}</span></td>
      <td>{item.region}</td>
      <td><code>{item.instance_type}</code></td>
      <td>{item.vcpu} vCPU · {item.memory_gb} GB</td>
      <td className="price-cell">{shortMoney(item.hourly_price)}</td>
      <td><span className="type-pill">{item.pricing_type}</span></td>
      {!compact && <td><span className="source-cell">{item.source} <i className="fresh-dot" />{item.freshness}</span></td>}
    </tr>
  ))
  return (
    <div className="table-wrap">
      <table>
        <thead><tr><th>PROVIDER</th><th>REGION</th><th>INSTANCE</th><th>VCPU / RAM</th><th>HOURLY PRICE</th><th>PRICING TYPE</th>{!compact && <th>SOURCE / FRESHNESS</th>}</tr></thead>
        <tbody>{rows.length ? rows : <tr><td className="table-empty" colSpan={compact ? 6 : 7}>No price records available. Connect a provider integration to populate this table.</td></tr>}</tbody>
      </table>
    </div>
  )
}

function CalculatorPage({ calculator, setCalculator, calculate, analysis, formError }) {
  const update = (key) => (event) => setCalculator((previous) => ({ ...previous, [key]: event.target.value }))
  return <>
    <PageHeader eyebrow="COST MODEL" title="Cost calculator" subtitle="Enter real provider prices or an explicit classroom scenario. No prices are prefilled." />
    <form onSubmit={calculate} className="calculator-layout">
      <div className="panel form-panel"><h2>Workload assumptions</h2><p className="panel-subtitle">All amounts are USD. These values are supplied by you; no cloud resources are created.</p><div className="form-grid">
        <Field label="Current provider"><select value={calculator.current_provider} onChange={update('current_provider')}><Options /></select></Field>
        <Field label="Target provider"><select value={calculator.target_provider} onChange={update('target_provider')}><Options /></select></Field>
        <Field label="Current hourly compute cost" prefix="$"><input type="number" min="0" step="0.0001" value={calculator.current_hourly_cost} onChange={update('current_hourly_cost')} required /></Field>
        <Field label="Target hourly compute cost" prefix="$"><input type="number" min="0" step="0.0001" value={calculator.target_hourly_cost} onChange={update('target_hourly_cost')} required /></Field>
        <Field label="Workload duration" suffix="hours"><input type="number" min="0.01" step="any" value={calculator.duration_hours} onChange={update('duration_hours')} required /></Field>
        <Field label="Data transfer / egress" prefix="$"><input type="number" min="0" step="0.01" value={calculator.transfer_cost} onChange={update('transfer_cost')} required /></Field>
        <Field label="Migration overhead" prefix="$"><input type="number" min="0" step="0.01" value={calculator.migration_overhead} onChange={update('migration_overhead')} required /></Field>
        <Field label="Other estimated costs" prefix="$"><input type="number" min="0" step="0.01" value={calculator.other_costs} onChange={update('other_costs')} required /></Field>
        <Field label="Minimum savings threshold" suffix="%"><input type="number" min="0" max="100" step="1" value={calculator.minimum_savings_percent} onChange={update('minimum_savings_percent')} required /></Field>
      </div><div className="assumption-note"><span>ⓘ</span> Estimates use one-time transfer and migration costs. They are added once and are not multiplied by workload duration.</div><button className="button primary" type="submit">Calculate estimate <span>→</span></button>{formError && <p className="form-error" role="alert">{formError}</p>}</div>
      <CostResult analysis={analysis} />
    </form>
  </>
}

function Options() { return <><option>AWS</option><option>GCP</option><option>Azure</option></> }
function Field({ label, prefix, suffix, children }) { return <label className="field"><span>{label}</span><div className="input-wrap">{prefix && <span>{prefix}</span>}{children}{suffix && <span>{suffix}</span>}</div></label> }

function CostResult({ analysis }) {
  if (!analysis) return <div className="panel result-panel empty-result"><div className="result-placeholder">⌗</div><h2>Your estimate will appear here</h2><p>Configure your workload assumptions and calculate to see an itemized cost breakdown.</p></div>
  const rows = [['Current compute', analysis.current_cost], ['Target compute', analysis.target_compute_cost], ['Data transfer & egress', analysis.transfer_cost], ['Migration overhead', analysis.migration_overhead], ['Other costs', analysis.other_costs]]
  return <div className="panel result-panel"><div className="result-heading"><div><span className="eyebrow">ESTIMATED OUTCOME</span><h2>Cost breakdown</h2></div><span className={`result-status ${analysis.net_savings >= 0 ? 'positive' : 'negative'}`}>{analysis.net_savings >= 0 ? 'Potential savings' : 'Higher total cost'}</span></div><div className="breakdown">{rows.map(([label, value]) => <div key={label}><span>{label}</span><b>{money(value)}</b></div>)}<div className="breakdown-total"><span>Target total cost</span><b>{money(analysis.target_total_cost)}</b></div></div><div className={`net-result ${analysis.net_savings >= 0 ? '' : 'loss'}`}><span>Net savings</span><strong>{money(analysis.net_savings)}</strong><small>{Number(analysis.savings_percent).toFixed(1)}% of current cost</small></div><div className="break-even"><span>Estimated break-even</span><b>{analysis.break_even_hours == null ? 'Not reached' : `${Number(analysis.break_even_hours).toFixed(1)} hours`}</b></div><p className="result-note">{analysis.note || 'Deterministic estimate. Actual prices, taxes, and transfer fees may differ.'}</p></div>
}

function DecisionPage({ calculator, setCalculator, run, result, createMigration }) {
  return <>
    <PageHeader eyebrow="DETERMINISTIC ANALYSIS" title="Decision engine" subtitle="Rank candidates by total estimated cost, not hourly price alone." action={<button className="button primary" onClick={run}>✳ Run analysis</button>} />
    <div className="decision-layout">        <div className="panel form-panel"><h2>Decision constraints</h2><p className="panel-subtitle">Candidates must satisfy workload capacity and minimum savings requirements.</p><Field label="Current provider"><select value={calculator.current_provider} onChange={(event) => setCalculator((old) => ({ ...old, current_provider: event.target.value }))}><Options /></select></Field><div className="form-grid"><Field label="Region"><div className="input-wrap"><input type="text" value={calculator.region} onChange={(event) => setCalculator((old) => ({ ...old, region: event.target.value }))} /></div></Field><Field label="Duration" suffix="hours"><input type="number" min="1" value={calculator.duration_hours} onChange={(event) => setCalculator((old) => ({ ...old, duration_hours: event.target.value }))} /></Field><Field label="Current hourly cost" prefix="$"><input type="number" min="0" step=".0001" value={calculator.current_hourly_cost} onChange={(event) => setCalculator((old) => ({ ...old, current_hourly_cost: event.target.value }))} /></Field><Field label="Required vCPU"><input type="number" min="1" value={calculator.required_vcpu} onChange={(event) => setCalculator((old) => ({ ...old, required_vcpu: event.target.value }))} /></Field><Field label="Required memory" suffix="GB"><input type="number" min="1" value={calculator.required_memory_gb} onChange={(event) => setCalculator((old) => ({ ...old, required_memory_gb: event.target.value }))} /></Field><Field label="Minimum savings" suffix="%"><input type="number" min="0" max="100" value={calculator.minimum_savings_percent} onChange={(event) => setCalculator((old) => ({ ...old, minimum_savings_percent: event.target.value }))} /></Field><Field label="Transfer + migration cost" prefix="$"><input type="number" min="0" value={Number(calculator.transfer_cost) + Number(calculator.migration_overhead)} onChange={(event) => setCalculator((old) => ({ ...old, transfer_cost: event.target.value, migration_overhead: 0 }))} /></Field></div><button className="button primary" onClick={run}>Evaluate providers <span>→</span></button></div>
      <div className="panel decision-result">{result ? <><span className="eyebrow">RECOMMENDATION</span><div className="decision-provider"><span className="provider-logo" style={{ color: providerColor[result.recommended_provider] || '#73809a' }}>✳</span><div><small>{result.recommended_provider === calculator.current_provider ? 'STAY ON CURRENT PROVIDER' : 'BEST-FIT PROVIDER'}</small><h2>{result.recommended_provider}</h2></div><span className="sample-tag">DEMO MODE</span></div><p>{result.reason}</p><div className="saving-highlight"><div><small>EST. NET SAVINGS</small><strong>{result.estimated_net_savings == null ? '—' : money(result.estimated_net_savings)}{result.estimated_net_savings != null && <em> / period</em>}</strong></div><span className={`saving-badge ${result.estimated_net_savings == null || result.recommended_provider === calculator.current_provider ? 'neutral' : ''}`}>{result.estimated_net_savings == null ? 'No price data' : result.recommended_provider === calculator.current_provider ? 'Stay put' : `↘ ${Number(result.savings_percent || 0).toFixed(1)}%`}</span></div><h3>Ranked alternatives</h3>{result.candidates?.length ? result.candidates.map((candidate) => <div className="candidate-row" key={candidate.provider}><span><i style={{ background: providerColor[candidate.provider] }} />{candidate.provider}</span><b>{money(candidate.total_cost)}</b><small>{candidate.eligible ? 'Meets threshold.' : 'Below threshold.'} {candidate.reason}</small></div>) : <EmptyState title="No provider price records" text="No alternative can be evaluated until a real provider price source is connected." />}{result.recommended_provider !== calculator.current_provider && result.candidates?.length > 0 ? <button className="button secondary full" onClick={() => createMigration(result.recommended_provider)}>Create migration simulation <span>→</span></button> : <p className="result-note">No migration is recommended under the current pricing data.</p>}<p className="result-note">Regional availability, capacity and interruption risk are not validated by demo estimates.</p></> : <div className="empty-result"><div className="result-placeholder">✳</div><h2>Ready to evaluate</h2><p>Enter workload requirements and run analysis. Without provider prices, no target will be recommended.</p></div>}</div></div>
  </>
}

const stateLabels = { PENDING: 'Pending', PROVISIONING: 'Provisioning', DEPLOYING: 'Deploying', HEALTH_CHECK: 'Health check', READY_TO_SWITCH: 'Ready to switch', SWITCHING_TRAFFIC: 'Switching', VERIFYING: 'Verifying', COMPLETED: 'Completed', FAILED: 'Failed', CANCELLED: 'Cancelled' }
function StateBadge({ state }) { return <span className={`state-badge ${['COMPLETED'].includes(state) ? 'complete' : ['FAILED', 'CANCELLED'].includes(state) ? 'failed' : 'running'}`}><i />{stateLabels[state] || state}</span> }

function MigrationPage({ migrations, advance, cancel, create, healthCheckPassed, setHealthCheckPassed }) {
  return <>
    <PageHeader eyebrow="SAFE WORKLOAD OPERATIONS" title="Migration center" subtitle="Track step-by-step migration simulations. No real cloud operations are enabled." action={<button className="button primary" onClick={() => create('GCP')}>＋ New simulation</button>} />
    <div className="notice"><span className="notice-icon">!</span><span><b>Simulation mode.</b> Advancing a migration changes only its recorded state. No compute, DNS, or cloud resources are provisioned or modified.</span></div>
    <div className="migration-grid">{migrations.length ? migrations.map((migration) => <div className="panel migration-card" key={migration.migration_id}><div className="migration-card-head"><div><span className="eyebrow">MIGRATION · {migration.migration_id.slice(0, 12)}</span><h2>{migration.source_provider} <span>→</span> {migration.target_provider}</h2></div><StateBadge state={migration.state} /></div><div className="migration-meta"><span>Created <b>{displayDate(migration.created_at)}</b></span><span className="sim-label">◉ Simulated</span></div><MigrationTimeline migration={migration} /><div className="migration-controls"><label className="check-control"><input type="checkbox" checked={healthCheckPassed} onChange={(event) => setHealthCheckPassed(event.target.checked)} /> Health check passes</label><div>{!['COMPLETED', 'FAILED', 'CANCELLED'].includes(migration.state) && <><button className="button secondary small" onClick={() => cancel(migration)}>Cancel</button><button className="button primary small" onClick={() => advance(migration)}>Advance step →</button></>}</div></div>{migration.error && <p className="form-error">{migration.error}</p>}</div>) : <div className="panel migration-empty"><EmptyState title="No migrations to show" text="Start a safe simulation to explore the migration workflow." /><button className="button primary" onClick={() => create('GCP')}>＋ Create simulation</button></div>}</div>
  </>
}

function MigrationTimeline({ migration }) {
  const steps = ['PENDING', 'PROVISIONING', 'DEPLOYING', 'HEALTH_CHECK', 'READY_TO_SWITCH', 'SWITCHING_TRAFFIC', 'VERIFYING', 'COMPLETED']
  const currentIndex = steps.indexOf(migration.state)
  const history = migration.history || []
  return <div className="timeline">{steps.map((step, index) => {
    const event = history.find((entry) => entry.state === step)
    const done = currentIndex >= index
    return <div key={step} className={`timeline-step ${done ? 'done' : ''} ${migration.state === 'FAILED' && index >= currentIndex ? 'error' : ''}`}><span className="timeline-marker">{migration.state === 'FAILED' && index === currentIndex ? '!' : done ? '✓' : index + 1}</span><div><b>{stateLabels[step]}</b>{event && <small>{displayDate(event.at || event.timestamp)}</small>}</div></div>
  })}</div>
}

function AnalyticsPage({ pricing, migrations, analysis }) {
  const completed = migrations.filter((item) => item.state === 'COMPLETED').length
  const failed = migrations.filter((item) => item.state === 'FAILED').length
  return <>
    <PageHeader eyebrow="HISTORICAL INSIGHTS" title="Analytics" subtitle="Understand estimated cloud costs and migration outcomes." action={<button className="button secondary" onClick={() => window.print()}>⇩ Export report</button>} />
    <div className="metric-grid analytics-metrics"><MetricCard label="Estimated savings" value={analysis ? money(analysis.net_savings) : '—'} delta={analysis ? 'Latest user calculation' : 'No calculation yet'} icon="↘" color="green" /><MetricCard label="Migrations completed" value={String(completed)} delta={`${failed} failed · simulation only`} icon="✓" color="blue" /><MetricCard label="Providers with prices" value={String(new Set(pricing.map((item) => item.provider)).size)} delta="Connected pricing records" icon="◈" color="violet" /><MetricCard label="Pricing records" value={String(pricing.length)} delta="Retrieved from configured sources" icon="$" color="orange" /></div>
    <div className="dashboard-grid analytics-grid"><div className="panel cost-panel"><div className="panel-heading"><div><h2>Hourly provider comparison</h2><p>Only retrieved provider price records are shown.</p></div></div><CostChart pricing={pricing} /><div className="chart-legend">{pricing.map((item) => <span key={item.provider}><i style={{ background: providerColor[item.provider] }} />{item.provider}<b>{shortMoney(item.hourly_price)}/hr</b></span>)}</div></div><div className="panel analytics-notes"><div className="panel-heading"><div><h2>Data quality</h2><p>Inputs for current analysis</p></div></div>{pricing.length ? pricing.map((item) => <div className="quality-row" key={item.provider}><span><i style={{ background: providerColor[item.provider] }} />{item.provider}</span><b>{item.source}</b><small>{item.freshness} · {item.availability_evidence}</small></div>) : <EmptyState title="No pricing data" text="Analytics will use actual provider records after an integration is configured." />}<div className="info-banner"><span>ⓘ</span><div><b>No historical provider feed</b><p>Historical pricing is empty until a real adapter retrieves and stores timestamped provider prices.</p></div></div></div></div>
  </>
}

function SettingsPage({ status }) {
  return <>
    <PageHeader eyebrow="WORKSPACE CONFIGURATION" title="Settings" subtitle="Review application mode, connectivity, and estimate assumptions." />
    <div className="settings-grid"><div className="panel settings-panel"><div className="panel-heading"><div><h2>Integrations & status</h2><p>Server-side credentials are never shown in the browser.</p></div></div><StatusRow name="Application mode" value="Demo" tone="demo" detail="No live cloud operations enabled" /><StatusRow name="Backend API" value={status.database === 'checking' ? 'Checking' : status.database === 'error' ? 'Request error' : status.database === 'unavailable' ? 'Unavailable' : 'Connected'} tone={['unavailable', 'error'].includes(status.database) ? 'warning' : 'healthy'} detail={status.database === 'unavailable' ? 'Start FastAPI to connect; browser displays no fabricated prices.' : status.database === 'error' ? 'FastAPI responded with an error; check its logs.' : 'FastAPI status endpoint responded.'} /><StatusRow name="MongoDB persistence" value={status.persistence} tone={status.persistence === 'mongodb' ? 'healthy' : 'warning'} detail={status.persistence === 'mongodb' ? 'Records persist in the configured database.' : 'Not connected; API reports memory-only persistence explicitly.'} /><StatusRow name="AWS / GCP / Azure pricing" value="Unavailable" tone="warning" detail="Live spot pricing adapters are not implemented or configured." /><StatusRow name="Cloud provisioning" value="Disabled" tone="warning" detail="No resources can be created or terminated in this build." /><StatusRow name="DNS failover" value="Mock only" tone="demo" detail="No real DNS endpoint or credentials are configured." /></div><div className="panel settings-panel"><div className="panel-heading"><div><h2>Cost model assumptions</h2><p>Enter real quotes or a clearly labeled classroom scenario.</p></div></div><div className="settings-assumption"><span>Currency</span><b>USD</b></div><div className="settings-assumption"><span>Compute unit</span><b>Per instance-hour</b></div><div className="settings-assumption"><span>Workload duration</span><b>Entered by user</b></div><div className="settings-assumption"><span>Transfer / migration costs</span><b>Entered by user, added once</b></div><div className="info-banner"><span>ⓘ</span><div><b>Configuration via backend environment</b><p>Set MONGODB_URI and FRONTEND_ORIGIN in backend/.env. Provider adapters are not included. Never put secrets in VITE_ variables.</p></div></div></div></div>
  </>
}

function StatusRow({ name, value, tone, detail }) { return <div className="status-row"><div><b>{name}</b><small>{detail}</small></div><span className={`status-label ${tone}`}><i />{value}</span></div> }
function EmptyState({ title, text }) { return <div className="empty-state"><span>◌</span><b>{title}</b><p>{text}</p></div> }

export default App
