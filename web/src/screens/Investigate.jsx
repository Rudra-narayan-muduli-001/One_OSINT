import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api.js'
import { detectType, ENGINES, engineOf, fmtElapsed, humanModule, loadRecents, dropRecent } from '../engines.js'
import { useRun } from '../state.jsx'
import { FindingRow, StatusChip, TechToggle } from '../components/ui.jsx'
import { PlainView } from '../components/PlainView.jsx'
import {
  IAt,IDownload,IFileSearch,IPlay,IGlobe,IMail,INetwork,IPhone,
  IRefresh,IShapes,IStop,IX,IChevD,ISearch,IExt,
} from '../icons.jsx'

const TYPE_ICONS = { all:IShapes, username:IAt, email:IMail, phone:IPhone, domain:IGlobe, ip:INetwork, google:null, file:IFileSearch }
const TYPE_LABEL = { all:'Everything', username:'Username', email:'Email', phone:'Phone', domain:'Website', ip:'IP address', google:'Google', file:'File' }

export default function Investigate(){
  const run = useRun()
  const hasResults = run.run.phase==='done' && !!run.run.report
  const active = ['starting','running','hydrating'].includes(run.run.phase)
  if(active) return <LiveView/>
  if(hasResults) return <DoneView/>
  return <IdleView/>
}

/* ---------------- Idle ---------------- */

function IdleView(){
  const run = useRun()
  const [target,setTarget] = useState('')
  const [typeSel,setTypeSel] = useState('all')
  const [optIn,setOptIn] = useState(false)
  const [recents,setRecents] = useState(loadRecents)
  const [modules,setModules] = useState([])
  const inputRef = useRef(null)
  const detected = useMemo(()=>detectType(target),[target])

  useEffect(()=>{
    api.modules().then(setModules).catch(()=>{})
    const onFocusSearch = ()=>inputRef.current?.focus()
    const onFill = (e)=>{ if(e.detail) setTarget(e.detail); inputRef.current?.focus() }
    window.addEventListener('signal:focus-search',onFocusSearch)
    window.addEventListener('signal:fill-target',onFill)
    return ()=>{
      window.removeEventListener('signal:focus-search',onFocusSearch)
      window.removeEventListener('signal:fill-target',onFill)
    }
  },[])

  useEffect(()=>{
    if(detected!=='unknown') setTypeSel(detected)
  },[detected])

  const visibleModules = useMemo(()=>{
    if(typeSel==='all') return modules
    return modules.filter(m=>engineOf(m.name)===typeSel || m.input_types?.includes(typeSel))
  },[modules,typeSel])

  const launch = useCallback(async(t=target)=>{
    const v = (t||'').trim()
    if(!v || detected==='unknown') return
    await run.start(v, typeSel==='all' ? [] : visibleModules.map(m=>m.name), optIn)
  },[target,detected,typeSel,visibleModules,optIn,run])

  return (
    <div>
      <section className="hero">
        <div className="kicker micro">one search · every public source</div>
        <h1>Find out what the internet<br/>knows about <em>anyone</em>.</h1>
        <p className="sub">Type an email, username, phone number or website below.<br/>We check hundreds of public sources and explain what we find - in plain words.</p>

        <div className="hero-box card anim-rise" style={{ animationDelay:'60ms' }}>
          <div className="hero-chips" role="tablist">
            {Object.keys(TYPE_LABEL).map(t=>{
              const Icon = TYPE_ICONS[t]
              return (
                <button
                  key={t}
                  role="tab"
                  aria-selected={typeSel===t}
                  className={`typechip${typeSel===t?' sel':''}${detected===t&&typeSel!==t?' suggest':''}`}
                  onClick={()=>setTypeSel(t)}
                >
                  {Icon ? <Icon size={13}/> : null}
                  {TYPE_LABEL[t]}
                </button>
              )
            })}
          </div>
          <div className="hero-row">
            <input
              ref={inputRef}
              autoFocus
              className={`hero-input${target && detected==='unknown' ? ' err':''}`}
              placeholder="name@example.com"
              value={target}
              spellCheck={false}
              onChange={(e)=>setTarget(e.target.value)}
              onKeyDown={(e)=>{ if(e.key==='Enter') launch() }}
            />
            <button className="btn btn-primary btn-lg" disabled={!target.trim()||detected==='unknown'} onClick={()=>launch()}>
              {run.run.phase==='starting' ? <span className="spin"/> : <ISearch size={16}/>}
              Search
            </button>
          </div>
          <div className="hero-hint">
            {target && detected!=='unknown' && <>
              <span>This looks like</span>
              <StatusChip status="info">{TYPE_LABEL[detected]}</StatusChip>
            </>}
            {target && detected==='unknown' && <span style={{color:'var(--warn-text)'}}>Hmm, we can’t tell what this is. Try an email, website, phone number or username.</span>}
            {!target && <span>Press <kbd>enter</kbd> to start · nothing is installed on your computer</span>}
            <label className="optin-toggle" title="Also use sources that may actively contact services">
              <span>Deep scan</span>
              <span className="switch">
                <input type="checkbox" checked={optIn} onChange={(e)=>setOptIn(e.target.checked)}/>
                <i/>
              </span>
            </label>
          </div>
        </div>

        {recents.length>0 && (
          <div className="recents">
            <span className="micro">Searched before</span>
            {recents.map(t=>(
              <span key={t} className="recent-chip">
                <i className="recent-dot" style={{ background:(ENGINES[detectType(t)]||ENGINES.misc).hue }}/>
                <button onClick={()=>{ setTarget(t); launch(t) }} title={t}>{t}</button>
                <button className="iconbtn" aria-label={`Forget ${t}`} onClick={()=>{ dropRecent(t); setRecents(loadRecents()) }}>
                  <IX size={11}/>
                </button>
              </span>
            ))}
          </div>
        )}

        <div className="how">
          <div className="card step">
            <span className="num">1.</span>
            <b>Type what you know</b>
            <p>An email address, a nickname, a phone number or a website - anything works.</p>
          </div>
          <div className="card step">
            <span className="num">2.</span>
            <b>We check public sources</b>
            <p>Social networks, data-leak lists, phone registries and more - safely and anonymously.</p>
          </div>
          <div className="card step">
            <span className="num">3.</span>
            <b>Get a clear answer</b>
            <p>You see exactly where the person or site shows up, explained without jargon.</p>
          </div>
        </div>
      </section>

      <div className="engines-head">
        <h2 style={{ fontSize:19 }}>What gets checked</h2>
        <span className="micro">{visibleModules.length} sources</span>
      </div>
      <div className="engines-grid">
        {visibleModules.length===0
          ? Array.from({length:8}).map((_,i)=>(<div key={i} className="card mod-card"><div className="skeleton" style={{height:20,width:'55%'}}/><div className="skeleton" style={{height:14,width:'90%'}}/></div>))
          : visibleModules.map(m=>{
              const eng = engineOf(m.name)
              const e = ENGINES[eng]
              return (
                <div key={m.name} className="card mod-card">
                  <div className="top">
                    <EngineDotHue hue={e.hue}/>
                    <div>
                      <div className="mod-name">{humanModule(m.name)}</div>
                      <div className="mod-sub mono">{m.name}</div>
                    </div>
                  </div>
                  <p className="mod-desc">{m.description}</p>
                  <div className="mod-badges">
                    <span className="chip eng-chip" style={{ '--ec-bg':e.tint,'--ec-fg':e.text,'--ec-border':e.hue+'55' }}>{e.label}</span>
                    {m.requires_key && <span className="chip chip-warn">needs free API key</span>}
                    {m.opt_in && <span className="chip chip-info">deep scan</span>}
                  </div>
                </div>
              )
            })}
      </div>
    </div>
  )
}

function EngineDotHue({ hue,running }){
  return <span className={`engine-dot${running?' running':''}`} style={{ '--ed':hue }}/>
}

/* ---------------- Search-again bar ---------------- */

function AgainBar({ lastTarget,onSubmit }){
  const [value,setValue] = useState('')
  const inputRef = useRef(null)
  const valid = detectType(value)!=='unknown'
  return (
    <div className="againbar">
      <ISearch size={16} style={{ color:'var(--text-3)',flex:'none' }}/>
      <input
        ref={inputRef}
        placeholder={`Search for something else…`}
        value={value}
        spellCheck={false}
        onChange={(e)=>setValue(e.target.value)}
        onKeyDown={(e)=>{ if(e.key==='Enter' && valid) onSubmit(value.trim()) }}
      />
      {lastTarget && <span className="meta">previous: <span className="mono">{lastTarget.slice(0,26)}</span></span>}
      <button className="btn btn-primary btn-sm" disabled={!valid} onClick={()=>onSubmit(value.trim())}>Search</button>
    </div>
  )
}

/* ---------------- Live progress ---------------- */

function LiveView(){
  const runCtx = useRun()
  const { run,totals,start } = runCtx
  const [elapsed,setElapsed] = useState(0)
  const running = ['starting','running','hydrating'].includes(run.phase)

  useEffect(()=>{
    if(!run.startedAt || !running) return undefined
    const iv = setInterval(()=>setElapsed(Date.now()-run.startedAt),1000)
    return ()=>clearInterval(iv)
  },[run.startedAt,running])

  return (
    <div>
      <AgainBar lastTarget="" onSubmit={(t)=>start(t)}/>

      {runCtx.connLost && run.phase!=='done' && (
        <div className="conn-ribbon">Lost the connection mid-scan - results may be incomplete. The scan itself continues on the server.</div>
      )}

      <header className="verdict anim-rise" style={{ paddingTop:10 }}>
        <div className="overline micro">{running?'Checking public sources…':'Finishing up…'}</div>
        <h2>Looking up <em>{run.target}</em></h2>
        <p className="verdict-sub">
          {totals.done>0 && totals.total>0
            ? `${totals.done} of ${totals.total} source groups finished · ${fmtElapsed(elapsed)} elapsed`
            : 'Warming up…'}
        </p>
      </header>

      <div className="summary-strip">
        <Stat label="Matches so far" value={totals.findings} cls="c-ok"/>
        <Stat label="Problems" value={totals.errors} cls={totals.errors?'c-crit':''}/>
        <Stat label="Groups done" value={`${totals.done}/${totals.total||'—'}`} cls="c-run"/>
        <Stat label="Time" value={fmtElapsed(elapsed)} cls=""/>
      </div>

      <div className="run-grid">
        {run.modules.map(m=>(
          <ModuleCard key={m.name} m={m} report={run.report} invId={run.invId}/>
        ))}
      </div>

      <LogDrawer events={run.events}/>
    </div>
  )
}

function Stat({ label,value,cls='' }){
  return (
    <div className="stat">
      <div className={`num ${cls}`}>{value}</div>
      <div className="lbl">{label}</div>
    </div>
  )
}

/* ---------------- Done: plain + technical toggle ---------------- */

function DoneView(){
  const runCtx = useRun()
  const { run,totals,start,reset } = runCtx
  const report = run.report
  const [tech,setTech] = useState(()=>localStorage.getItem('signal.tech')==='1')

  useEffect(()=>{
    localStorage.setItem('signal.tech',tech?'1':'0')
  },[tech])

  const partial = report && !('found_accounts' in report)

  return (
    <div>
      <AgainBar lastTarget={run.target} onSubmit={(t)=>start(t)}/>

      {!tech && !partial && <PlainView report={report}/>}

      {!tech && partial && (
        <div className="empty"><h3>Still collecting…</h3><p>The scan has not finished yet. Reopen this page in a moment.</p></div>
      )}

      <div className="rule-label micro">
        <TechToggle on={tech} onChange={setTech}/>
      </div>

      {tech && (
        <div>
          <div className="page-head" style={{ marginBottom:14 }}>
            <div>
              <h1 style={{ fontSize:22 }}>Raw engine output</h1>
              <p>Exactly what each source returned. Same data the plain view above was built from.</p>
            </div>
            {report?.target && (
              <div style={{ display:'flex',gap:8,flexWrap:'wrap' }}>
                {run.invId && <>
                  <a className="btn btn-ghost btn-sm" href={api.exportUrl(run.invId,'json')} download><IDownload size={14}/>JSON</a>
                  <a className="btn btn-ghost btn-sm" href={api.exportUrl(run.invId,'csv')} download><IDownload size={14}/>CSV</a>
                  <a className="btn btn-secondary btn-sm" href={`#/report/${run.invId}`}><IExt size={13}/>Full report</a>
                </>}
              </div>
            )}
          </div>

          <div className="summary-strip">
            <Stat label="Confirmed matches" value={totals.findings} cls="c-ok"/>
            <Stat label="Failed sources" value={totals.errors} cls={totals.errors?'c-crit':''}/>
            <Stat label="Source groups" value={`${totals.done}/${totals.total||'—'}`} cls=""/>
          </div>

          <div className="run-grid">
            {report && Array.isArray(report.modules) && report.modules.map((rm,i)=>{
              const roster = run.modules.find(x=>x.name===rm.name)
              return <ModuleCard key={`${rm.name}-${i}`} invId={run.invId}
                       m={{ name:rm.name,status:'done',count:(rm.findings||[]).length,duration:rm.duration,summary:rm.summary,error:rm.error,pivotRuns:roster?.pivotRuns||0 }}
                       report={null} forceRows={rm.findings||[]}/>
            })}
          </div>
        </div>
      )}

      <div className="endcta">
        <button className="btn btn-outline" onClick={()=>{ reset(); window.scrollTo({top:0}) }}>
          Start a new search
        </button>
      </div>
    </div>
  )
}

function ModuleCard({ m,invId,forceRows }){
  const [open,setOpen] = useState(true)
  const eng = engineOf(m.name)
  const e = ENGINES[eng]
  const flashRef = useRef(null)
  const wasRunning = useRef(false)

  useEffect(()=>{
    if(wasRunning.current && (m.status==='done'||m.status==='error') && flashRef.current){
      flashRef.current.style.setProperty('--flash',m.status==='error' ? 'var(--crit-tint)' : 'var(--accent-tint)')
      flashRef.current.classList.add('flash')
      const t = setTimeout(()=>flashRef.current?.classList.remove('flash'),800)
      return ()=>clearTimeout(t)
    }
    wasRunning.current = m.status==='running'
  },[m.status])

  const findings = forceRows || []

  return (
    <div className="card rcard" ref={flashRef}>
      <div className="rhead" onClick={()=>setOpen(o=>!o)} role="button" tabIndex={0}
           onKeyDown={(ev)=>{ if(ev.key==='Enter'||ev.key===' ') setOpen(o=>!o) }}>
        <EngineDotHue hue={e.hue} running={m.status==='running'}/>
        <div style={{minWidth:0}}>
          <div className="rname">{humanModule(m.name)}</div>
          <div className="rsub">{m.name}{m.pivotRuns ? ` · +${m.pivotRuns} pivot` : ''}</div>
        </div>
        <div className="rmeta">
          {m.status==='queued' && <StatusChip status="skipped">queued</StatusChip>}
          {m.status==='running' && <StatusChip status="running" pulse>checking</StatusChip>}
          {m.status==='error' && <StatusChip status="error">error</StatusChip>}
          {(m.status==='done'||forceRows) && <StatusChip status="found">{(forceRows?findings.length:m.count)} hits</StatusChip>}
          {m.duration!=null && m.duration>0 && <span className="rdur">{Number(m.duration).toFixed(1)}s</span>}
          <IChevD size={15} style={{ transform:open?'none':'rotate(-90deg)',transition:'transform var(--t-fast)',color:'var(--text-disabled)' }}/>
        </div>
      </div>
      {m.status==='running' && <div className="rprog" style={{ '--hue':e.hue }}><i/></div>}
      {m.error && <div className="rerror">Error: {m.error}</div>}
      {m.summary && Object.keys(m.summary).length>0 && (
        <div className="rsummary">{JSON.stringify(m.summary)}</div>
      )}
      {open && (findings.length>0 || m.status==='running') && (
        <div className="rbody">
          {findings.length===0 && m.status==='running' &&
            Array.from({length:3}).map((_,i)=>(<div key={i} className="finding"><div className="skeleton" style={{height:14,width:i%2?'42%':'58%'}}/></div>))}
          {findings.map((f,i)=><FindingRow key={i} f={f} index={Math.min(i,12)}/>)}
          {forceRows && findings.length>6 && invId && (
            <a className="btn btn-ghost btn-sm more-btn" href={`#/report/${invId}`}>
              Open full report…
            </a>
          )}
        </div>
      )}
    </div>
  )
}

export function isAlert(f){
  const ex = f.extra || {}
  return f.status==='found' && Boolean(ex.breach || ex.breaches || ex.source==='hibp')
}

/* ---------------- Log drawer ---------------- */

function LogDrawer({ events }){
  const [collapsed,setCollapsed] = useState(false)
  const [height,setHeight] = useState(190)
  const bodyRef = useRef(null)
  const pinned = useRef(true)

  const onScroll = ()=>{
    const el = bodyRef.current
    if(el) pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40
  }
  useEffect(()=>{
    const el = bodyRef.current
    if(el && pinned.current) el.scrollTop = el.scrollHeight
  },[events,collapsed])

  const startDrag = (e)=>{
    e.preventDefault()
    const move = (ev)=>{
      const h = Math.min(Math.max(window.innerHeight - ev.clientY - 40, 80), window.innerHeight*0.6)
      setHeight(h); setCollapsed(h<=100)
    }
    const up = ()=>{ window.removeEventListener('pointermove',move); window.removeEventListener('pointerup',up) }
    window.addEventListener('pointermove',move)
    window.addEventListener('pointerup',up)
  }

  const level = (evt)=>{
    if(evt.type==='investigation_start') return 'start'
    if(evt.type==='module_done') return evt.error?'error':'done'
    if(evt.type==='error') return 'error'
    return 'info'
  }
  const line = (evt)=>{
    switch(evt.type){
      case 'investigation_start': return `▶ investigating ${evt.target} (${evt.input_type}) · ${evt.modules?.length||0} engines`
      case 'module_start': return `… ${evt.module}`
      case 'module_done': return evt.error ? `✗ ${evt.module} — ${evt.error}` : `✓ ${evt.module} — ${evt.findings} hits in ${evt.duration}s`
      case 'investigation_done': return `■ complete`
      case 'error': return `!! ${evt.message}`
      default: return JSON.stringify(evt)
    }
  }

  return (
    <div className="drawer" style={{ height:collapsed?32:height+24 }}>
      <div className="drawer-grip" onPointerDown={startDrag}/>
      <div className="drawer-head" onClick={()=>setCollapsed(c=>!c)}>
        <span className="micro">Live log</span>
        <span className="micro" style={{ fontWeight:400,textTransform:'none',letterSpacing:0 }}>{events.length} events</span>
        <span style={{ marginLeft:'auto' }}><IChevD size={15} style={{ transform:collapsed?'rotate(180deg)':'none',transition:'transform var(--t-fast)',color:'var(--text-3)' }}/></span>
      </div>
      {!collapsed && (
        <div className="drawer-body" ref={bodyRef} onScroll={onScroll}>
          {events.map((evt,i)=>(
            <div key={i} className={`logline lv-${level(evt)}`}>
              <span className="ts">{new Date().toLocaleTimeString([],{ hour12:false })}</span>
              <span>{line(evt)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
