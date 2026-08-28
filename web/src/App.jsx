import React, { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import { RunProvider, useRun } from './state.jsx'
import CommandPalette from './components/CommandPalette.jsx'
import Investigate from './screens/Investigate.jsx'
import History from './screens/History.jsx'
import Report from './screens/Report.jsx'
import Keys from './screens/Keys.jsx'
import {
  ICrosshair,IHistory,IKey,IActivity,IPanel,ISearch,
} from './icons.jsx'

const NAV = [
  { route:'investigate', label:'New search', Icon:ISearch },
  { route:'history', label:'Past searches', Icon:IHistory },
  { route:'keys', label:'Optional keys', Icon:IKey },
]

function parseHash(){
  const h = location.hash.replace(/^#\/?/,'')
  const [route,query] = h.split('?')
  const parts = (route||'').split('/').filter(Boolean)
  return { page:parts[0]||'investigate', arg:parts[1]||null, query }
}

export default function App(){
  const [route,setRoute] = useState(parseHash)
  const [rail,setRail] = useState(()=>localStorage.getItem('signal.rail')==='1')
  const [health,setHealth] = useState({ ok:null,version:'' })
  const [paletteOpen,setPaletteOpen] = useState(false)

  useEffect(()=>{
    const onHash = ()=>setRoute(parseHash())
    window.addEventListener('hashchange',onHash)
    return ()=>window.removeEventListener('hashchange',onHash)
  },[])

  useEffect(()=>{
    localStorage.setItem('signal.rail',rail?'1':'0')
  },[rail])

  useEffect(()=>{
    let stop = false
    const ping = ()=>api.health()
      .then(h=>{ if(!stop) setHealth({ ok:true,version:h.version }) })
      .catch(()=>{ if(!stop) setHealth({ ok:false,version:'' }) })
    ping()
    const iv = setInterval(ping,20000)
    return ()=>{ stop = true; clearInterval(iv) }
  },[])

  useEffect(()=>{
    const onKey = (e)=>{
      const editable = ['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName) || e.target.isContentEditable
      if((e.metaKey||e.ctrlKey) && e.key.toLowerCase()==='k'){
        e.preventDefault(); setPaletteOpen(o=>!o); return
      }
      if(e.key==='/' && !editable){
        e.preventDefault()
        location.hash = '#/investigate'
        setTimeout(()=>window.dispatchEvent(new Event('signal:focus-search')),50)
      }
    }
    window.addEventListener('keydown',onKey)
    return ()=>window.removeEventListener('keydown',onKey)
  },[])

  const navigate = useCallback((r)=>{ location.hash = `#/${r}` },[])
  const crumb = CRUMBS[route.page] || 'Search'

  return (
    <RunProvider>
      <div className={`shell${rail?' rail':''}`}>
        <aside className="sidebar">
          <div className="side-logo">
            <span className="logo-mark"><ISearch size={16}/></span>
            <span className="logo-word"><b>one-osint</b><span>find anything</span></span>
          </div>
          <nav className="sidenav">
            {NAV.map(n=>(
              <a
                key={n.route}
                className={`navitem${route.page===n.route?' active':''}`}
                href={`#/${n.route}`}
              >
                <n.Icon size={18}/>
                <span className="navlabel">{n.label}</span>
              </a>
            ))}
            <span className="microlabel">System</span>
            <button
              className="navitem"
              onClick={()=>setPaletteOpen(true)}
            >
              <IActivity size={18}/>
              <span className="navlabel">Commands</span>
            </button>
          </nav>
          <div className="side-foot" title={health.ok?'API reachable':'API unreachable'}>
            <i className={`health-dot${health.ok===false?' down':''}`}/>
            <span className="health-label">{health.ok===false?'API offline':'API online'}{health.version?` · v${health.version}`:''}</span>
          </div>
        </aside>

        <div className="main">
          <TopProgress/>
          <header className="topbar">
            <button className="iconbtn" onClick={()=>setRail(r=>!r)} aria-label="Toggle sidebar" title="Toggle sidebar">
              <IPanel size={17}/>
            </button>
            <span className="crumb"><b>{crumb}</b></span>
            <span className="topbar-spacer"/>
            <button className="kbd-btn" onClick={()=>setPaletteOpen(true)}>
              <ISearch size={14}/>
              Search or jump to…
              <kbd>⌘K</kbd>
            </button>
          </header>
          <main className="content" key={`${route.page}/${route.arg||''}`}>
            <ErrorBoundary>
              <Screen route={route} navigate={navigate}/>
            </ErrorBoundary>
          </main>
        </div>
      </div>

      <PaletteHost open={paletteOpen} onClose={()=>setPaletteOpen(false)} navigate={navigate}/>
    </RunProvider>
  )
}

function Screen({ route,navigate }){
  switch(route.page){
    case 'history': return <History navigate={navigate}/>
    case 'report': return route.arg ? <Report id={route.arg} navigate={navigate}/> : <Investigate/>
    case 'keys': return <Keys/>
    default: return <Investigate/>
  }
}

class ErrorBoundary extends React.Component{
  constructor(props){
    super(props)
    this.state = { error:null }
  }
  static getDerivedStateFromError(error){ return { error } }
  componentDidCatch(error,info){ console.error('UI crash:',error,info?.componentStack) }
  render(){
    if(this.state.error){
      return (
        <div className="card" style={{ padding:24 }}>
          <h2 style={{ fontFamily:'var(--font-serif)',fontSize:19,marginBottom:8 }}>Something went wrong showing this page</h2>
          <p style={{ fontSize:13,color:'var(--text-3)',marginBottom:12 }}>The error below was logged to the browser console (F12). Your data is safe.</p>
          <pre className="mono" style={{ whiteSpace:'pre-wrap',wordBreak:'break-word',fontSize:11.5,color:'var(--crit-text)',background:'var(--panel)',border:'1px solid var(--border)',borderRadius:10,padding:14 }}>{String(this.state.error?.message||this.state.error)}</pre>
          <button className="btn btn-primary btn-sm" style={{ marginTop:14 }} onClick={()=>{ this.setState({error:null}); location.hash='#/investigate' }}>Back to search</button>
        </div>
      )
    }
    return this.props.children
  }
}

const CRUMBS = { investigate:'New search', history:'Past searches', report:'Report', keys:'Optional keys' }

function TopProgress(){
  const run = useRun()
  if(!['starting','running'].includes(run.run.phase)) return null
  return <div className="progressline"><i/></div>
}

function PaletteHost({ open,onClose,navigate }){
  const run = useRun()
  const lastReportId = run.run.invId || null
  const onRun = async(target)=>{
    await run.start(target)
    navigate('investigate')
  }
  return (
    <CommandPalette
      open={open}
      onClose={onClose}
      navigate={(r)=>navigate(r)}
      onRun={onRun}
      lastReportId={lastReportId}
    />
  )
}
