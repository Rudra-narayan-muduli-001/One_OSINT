import React, { useCallback, useEffect, useRef, useState } from 'react'

const STATUS_ICON = { found: '🟢', not_found: '⚪', error: '🔴', skipped: '🟡' }

function detectType(value) {
  if (/^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/.test(value)) return 'email'
  if (/^\+?[0-9][0-9\s().-]{5,}$/.test(value) && value.replace(/\D/g, '').length > 10) return 'phone'
  if (/^(\d{1,3}\.){3}\d{1,3}$/.test(value)) return 'ip'
  if (/^(?!-)([a-z0-9-]{1,63}\.)+[a-z]{2,}$/i.test(value)) return 'domain'
  if (/^[A-Za-z0-9_.-]{3,64}$/.test(value)) return 'username'
  return 'unknown'
}

function FindingRow({ f }) {
  const extra = f.extra && Object.keys(f.extra).length
    ? JSON.stringify(f.extra).slice(0, 250)
    : null
  return (
    <div className="finding">
      <span className={`st st-${f.status}`}>{STATUS_ICON[f.status] || ''} {f.status}</span>
      <span className="site">{f.site}</span>
      {f.url && <a className="url" href={f.url} target="_blank" rel="noreferrer">{f.url}</a>}
      {extra && <span className="extra">{extra}</span>}
    </div>
  )
}

function ModuleCard({ mod, events }) {
  const status = mod.error ? 'error' : mod.findings?.length > 0 ? 'done' : mod.skipped ? 'skipped' : 'done'
  const findings = mod.findings || []
  const isRunning = events.some((e) => e.type === 'module_start' && e.module === mod.name && !events.some(
    (e2) => e2.type === 'module_done' && e2.module === mod.name
  ))
  return (
    <div className="module">
      <div className="module-header">
        <span className={`dot ${isRunning ? 'running' : status === 'error' ? 'error' : 'done'}`} />
        <span className="module-name">{mod.name}</span>
        {mod.error && <span style={{ color: '#f87171', fontSize: '0.78rem' }}>error: {mod.error}</span>}
        {mod.summary && Object.keys(mod.summary).length > 0 && (
          <span className="module-meta">{JSON.stringify(mod.summary).slice(0, 120)}</span>
        )}
        <span className="module-meta">{mod.duration?.toFixed(1)}s · {findings.length} findings</span>
      </div>
      {findings.slice(0, 50).map((f, i) => <FindingRow key={i} f={f} />)}
      {findings.length > 50 && (
        <div className="finding" style={{ color: '#8b93a3' }}>+{findings.length - 50} more…</div>
      )}
    </div>
  )
}

export default function App() {
  const [target, setTarget] = useState('')
  const [invId, setInvId] = useState(null)
  const [report, setReport] = useState(null)
  const [events, setEvents] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const wsRef = useRef(null)

  const connect = useCallback((id) => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${location.host}/ws/investigate/${id}`)
    ws.onmessage = (msg) => {
      const event = JSON.parse(msg.data)
      setEvents((prev) => [...prev, event])
      if (event.type === 'investigation_done') {
        fetch(`/api/report/${id}`).then((r) => r.json()).then((data) => {
          setReport(data)
          setLoading(false)
        }).catch(() => setLoading(false))
      }
    }
    ws.onerror = () => { setLoading(false) }
    wsRef.current = ws
  }, [])

  useEffect(() => () => wsRef.current?.close(), [])

  const start = async () => {
    setError(null)
    setEvents([])
    setReport(null)
    setLoading(true)
    const res = await fetch('/api/investigate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      setError(body.detail || `HTTP ${res.status}`)
      setLoading(false)
      return
    }
    const data = await res.json()
    setInvId(data.investigation_id)
    connect(data.investigation_id)
  }

  const type = detectType(target)
  const running = events.some((e) => e.type === 'module_start')

  return (
    <div className="app">
      <h1>one-<span>osint</span></h1>
      <p className="subtitle">Unified OSINT investigations — email · username · phone · domain · IP · file</p>

      <div className="searchbar">
        <input
          placeholder="user@example.com, @username, +33612345678, example.com, 1.2.3.4, /path/to/file.jpg"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && start()}
        />
        <button onClick={start} disabled={loading || !target.trim()}>
          {loading ? 'Running…' : 'Investigate'}
        </button>
      </div>
      {type !== 'unknown' && target && <span className="type-badge">{type}</span>}
      {error && <div className="error-box">{error}</div>}

      {!report && !loading && !error && <div className="empty">Enter a target to begin.</div>}

      {loading && !report && <div className="empty" style={{ color: '#f0b429' }}>Investigating…</div>}

      {report && (
        <>
          <div className="stats">
            <div className="stat"><div className="num">{report.found_accounts}</div><div className="lbl">Findings</div></div>
            <div className="stat"><div className="num">{report.module_count}</div><div className="lbl">Modules</div></div>
            <div className="stat"><div className="num">{report.pivots?.emails?.length || 0}</div><div className="lbl">Pivots</div></div>
            <div className="stat"><div className="num">{report.created_at?.slice(0, 10)}</div><div className="lbl">Date</div></div>
          </div>
          <div className="modules">
            {report.modules.map((mod, i) => (
              <ModuleCard key={i} mod={mod} events={events} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
