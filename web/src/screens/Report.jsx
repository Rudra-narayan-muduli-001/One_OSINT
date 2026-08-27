import React, { useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import { detectType, ENGINES, engineOf, humanModule } from '../engines.js'
import { useRun, useToast } from '../state.jsx'
import { CopyBtn, EmptyState, FindingRow, StatusChip, TechToggle } from '../components/ui.jsx'
import { PlainView } from '../components/PlainView.jsx'
import { ICopy,IDownload,IRefresh,IWarn } from '../icons.jsx'

export default function Report({ id,navigate }){
  const runCtx = useRun()
  const toast = useToast()
  const [rep,setRep] = useState(null)
  const [error,setError] = useState(null)
  const [tech,setTech] = useState(()=>localStorage.getItem('signal.tech')==='1')
  const liveReport = runCtx.run.report && runCtx.run.invId===id ? runCtx.run.report : null

  useEffect(()=>{
    if(liveReport){ setRep(liveReport); return }
    setRep(null); setError(null)
    api.report(id).then(setRep).catch(e=>setError(e.message))
  },[id,liveReport])

  useEffect(()=>{
    localStorage.setItem('signal.tech',tech?'1':'0')
  },[tech])

  const sections = useMemo(()=>{
    if(!rep || !Array.isArray(rep.modules)) return []
    return rep.modules
      .map(m=>({ ...m,_findings:m.findings||[] }))
      .sort((a,b)=>{
        if(!!a.error!==!!b.error) return a.error ? -1 : 1
        return b._findings.length-a._findings.length
      })
  },[rep])

  if(error) return <EmptyState title="Report unavailable">{error}</EmptyState>
  if(!rep){
    return <div>{Array.from({length:4}).map((_,i)=>(<div key={i} className="skeleton" style={{height:64,marginBottom:12}}/>))}</div>
  }

  const partial = !('found_accounts' in rep)
  const errCount = sections.filter(s=>s.error).length

  const rerun = async()=>{
    await runCtx.start(rep.target)
    navigate('investigate')
  }

  const copySummary = ()=>{
    const lines = [
      `one-osint report - ${rep.target}`,
      `type: ${rep.input_type} · created: ${rep.created_at}`,
      ...sections.map(s=>`- ${s.name}: ${s.error?`ERROR (${s.error})`:`${s._findings.length} hits`} ${s.duration?`(${s.duration}s)`:''}`),
    ]
    navigator.clipboard.writeText(lines.join('\n')).then(()=>toast.push('ok','Summary copied.'))
  }

  return (
    <div>
      {errCount>0 && !partial && (
        <div className="rep-banner"><IWarn size={16}/>{errCount} source{errCount>1?'s':''} could not be checked during this scan</div>
      )}

      {!tech && !partial && (
        <>
          <PlainView report={rep}/>
          <div className="endcta" style={{ paddingTop:8 }}>
            <button className="btn btn-outline btn-sm" onClick={()=>setTech(true)}>Show raw data</button>
          </div>
        </>
      )}

      {!tech && partial && (
        <div className="card rcard" style={{ padding:18 }}>
          <StatusChip status="running" pulse>investigation still running</StatusChip>
          {Array.isArray(rep.modules_so_far) && rep.modules_so_far.map((m,i)=>(
            <div key={i} className="finding">
              <StatusChip status={m.status==='running'?'running':m.status}>{m.module}</StatusChip>
              <span className="rdur">{Number(m.duration||0).toFixed(2)}s</span>
            </div>
          ))}
        </div>
      )}

      <div className="page-head" style={{ marginTop:26 }}>
        <div style={{ minWidth:0 }}>
          <h1 className="mono" style={{ fontSize:19,wordBreak:'break-all' }}>{rep.target}</h1>
          <p style={{ display:'flex',gap:8,flexWrap:'wrap',alignItems:'center',marginTop:7 }}>
            <span className="chip chip-muted">{rep.input_type}</span>
            <span className="chip chip-muted">{rep.created_at}</span>
            {!partial && <span className="chip chip-ok">{rep.found_accounts} confirmed matches</span>}
            {!partial && <span className="chip chip-info">{rep.module_count} sources</span>}
          </p>
        </div>
        <div style={{ display:'flex',gap:8,flexWrap:'wrap',alignItems:'center' }}>
          <TechToggle on={tech} onChange={setTech}/>
          {!partial && <>
            <CopyBtn text={`${rep.target} - one-osint report`} label="Copy"/>
            <button className="btn btn-ghost btn-sm" onClick={copySummary}><ICopy size={14}/>Summary</button>
            <a className="btn btn-ghost btn-sm" href={api.exportUrl(id,'json')} download><IDownload size={14}/>JSON</a>
            <a className="btn btn-ghost btn-sm" href={api.exportUrl(id,'csv')} download><IDownload size={14}/>CSV</a>
            <a className="btn btn-ghost btn-sm" href={api.exportUrl(id,'md')} download><IDownload size={14}/>MD</a>
          </>}
          <button className="btn btn-primary btn-sm" onClick={rerun}><IRefresh size={14}/>Re-run</button>
        </div>
      </div>

      {tech && (
        <div className="rep-layout">
          <nav className="rep-rail" aria-label="Report sections">
            <span className="micro">Sources</span>
            {sections.map(s=>(
              <button key={s.name} className="rail-item" onClick={()=>scrollToId(`sec-${s.name}`)}>
                <i style={{ width:8,height:8,borderRadius:50,background:(ENGINES[engineOf(s.name)]||ENGINES.misc).hue }}/>
                {humanModule(s.name)}
                <span className="rail-count">{s.error?'!':s._findings.length}</span>
              </button>
            ))}
          </nav>

          <div style={{ minWidth:0 }}>
            {sections.map(s=>(
              <section key={s.name} id={`sec-${s.name}`} className="card rep-section">
                <div className="rhead">
                  <span className="engine-dot" style={{ '--ed':(ENGINES[engineOf(s.name)]||ENGINES.misc).hue }}/>
                  <div style={{minWidth:0}}>
                    <div className="rname">{humanModule(s.name)}</div>
                    <div className="rsub">{s.name}</div>
                  </div>
                  <div className="rmeta">
                    {s.error && <StatusChip status="error">error</StatusChip>}
                    {!s.error && s.skipped && <StatusChip status="skipped">skipped</StatusChip>}
                    {!s.error && !s.skipped && <StatusChip status={s._findings.length?'found':'skipped'}>{s._findings.length} hits</StatusChip>}
                    {Number(s.duration)>0 && <span className="rdur">{Number(s.duration).toFixed(1)}s</span>}
                  </div>
                </div>
                {s.error && <div className="rerror">Error: {s.error}</div>}
                {!s.error && s.summary && Object.keys(s.summary).length>0 &&
                  <div className="rsummary">{JSON.stringify(s.summary)}</div>}
                {!s.error && s._findings.length>0 && (
                  <div className="rbody">
                    {s._findings.map((f,i)=><FindingRow key={i} f={f} index={Math.min(i,10)} alert={isCritModule(s.name)&&f.status==='found'}/>)}
                  </div>
                )}
              </section>
            ))}

            {sections.length===0 && <EmptyState title="Nothing recorded">This investigation completed without module results.</EmptyState>}
          </div>
        </div>
      )}
    </div>
  )
}

function scrollToId(domId){
  document.getElementById(domId)?.scrollIntoView({ behavior:'smooth',block:'start' })
}
function isCritModule(name){
  const n = (name||'').toLowerCase()
  return n.startsWith('breach') || n.includes('stealer')
}
