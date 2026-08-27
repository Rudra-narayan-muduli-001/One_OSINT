import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import { absTime, ENGINES, engineOf, relTime } from '../engines.js'
import { useRun, useToast } from '../state.jsx'
import { EmptyState, Modal, StatusChip } from '../components/ui.jsx'
import { IExt,IPlay,IRefresh,ISearch,ITrash } from '../icons.jsx'

const TYPE_FILTERS = ['all','username','email','phone','domain','ip','unknown']
const DATE_PRESETS = [
  { key:'all', label:'All time', ms:Infinity },
  { key:'today', label:'Today', ms:86400e3 },
  { key:'7d', label:'7 days', ms:7*86400e3 },
  { key:'30d', label:'30 days', ms:30*86400e3 },
]

export default function History({ navigate }){
  const [rows,setRows] = useState(null)
  const [error,setError] = useState(null)
  const [q,setQ] = useState('')
  const [types,setTypes] = useState([])
  const [dateKey,setDateKey] = useState('all')
  const [selected,setSelected] = useState(new Set())
  const [confirmIds,setConfirmIds] = useState([])
  const run = useRun()
  const toast = useToast()

  const refresh = useCallback(()=>{
    api.investigations(200).then(setRows).catch(e=>setError(e.message))
  },[])
  useEffect(refresh,[refresh])

  const filtered = useMemo(()=>{
    if(!rows) return null
    const preset = DATE_PRESETS.find(p=>p.key===dateKey)
    const cutoff = preset.ms===Infinity ? 0 : Date.now()-preset.ms
    return rows.filter(r=>{
      if(q && !r.target.toLowerCase().includes(q.toLowerCase())) return false
      if(types.length && !types.includes(r.input_type)) return false
      const created = new Date((r.created_at||'').replace(' ','T')).getTime() || 0
      if(cutoff && created < cutoff) return false
      return true
    })
  },[rows,q,types,dateKey])

  const toggleType = (t)=>setTypes(ts=>ts.includes(t) ? ts.filter(x=>x!==t) : [...ts,t])
  const allChecked = !!filtered?.length && filtered.every(r=>selected.has(r.id))

  const toggleAll = ()=>{
    setSelected(prev=>{
      const next = new Set(allChecked ? [] : filtered.map(r=>r.id))
      return next
    })
  }
  const toggleOne = (id)=>{
    setSelected(prev=>{
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const doDelete = async(ids)=>{
    let ok = 0
    for(const id of ids){
      try{ await api.remove(id); ok++ }catch(e){ toast.push('crit',e.message) }
    }
    if(ok) toast.push('ok',`Deleted ${ok} investigation${ok>1?'s':''}.`)
    setRows(rs=>rs?rs.filter(r=>!ids.includes(r.id)):rs)
    setSelected(prev=>{ const n=new Set(prev); ids.forEach(id=>n.delete(id)); return n })
    setConfirmIds([])
  }

  const rerun = async(target)=>{
    await run.start(target)
    navigate('investigate')
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>History</h1>
          <p>Every investigation stored on this machine — reopen or re-run in one click.</p>
        </div>
      </div>

      <div className="toolbar">
        <div style={{ position:'relative',width:280 }}>
          <span style={{ position:'absolute',left:10,top:10,color:'var(--text-3)' }}><ISearch size={16}/></span>
          <input className="input" style={{ paddingLeft:34 }} placeholder="Filter targets…" value={q} onChange={(e)=>setQ(e.target.value)}/>
        </div>
        <div className="seg" role="group" aria-label="Date range">
          {DATE_PRESETS.map(p=>(
            <button key={p.key} className={dateKey===p.key?'on':''} onClick={()=>setDateKey(p.key)}>{p.label}</button>
          ))}
        </div>
        <div style={{ display:'flex',gap:6,flexWrap:'wrap' }}>
          {TYPE_FILTERS.slice(1).map(t=>(
            <button key={t} className={`typechip${types.includes(t)?' sel':''}`} onClick={()=>toggleType(t)}>
              {t}
            </button>
          ))}
        </div>
      </div>

      {selected.size>0 && (
        <div className="bulkbar">
          <span>{selected.size} selected</span>
          <button className="btn btn-danger btn-sm" onClick={()=>setConfirmIds([...selected])}>
            Delete…
          </button>
          <button className="btn btn-ghost btn-sm" onClick={()=>setSelected(new Set())}>Clear</button>
        </div>
      )}

      {!rows && !error &&
        Array.from({length:5}).map((_,i)=>(<div key={i} className="skeleton" style={{height:44,marginBottom:8}}/>))}
      {error && <EmptyState title="Couldn’t load history">{error}</EmptyState>}
      {rows && filtered && filtered.length===0 &&
        <EmptyState title="No investigations yet">Run your first scan from the Investigate screen — results will collect here.</EmptyState>}

      {filtered && filtered.length>0 && (
        <div className="card tblwrap">
          <table className="tbl">
            <thead>
              <tr>
                <th style={{width:36}}>
                  <input type="checkbox" className="rowcheck" checked={allChecked} onChange={toggleAll} aria-label="Select all"/>
                </th>
                <th>Target</th>
                <th>Type</th>
                <th>Status</th>
                <th>Started</th>
                <th className="num">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(r=>(
                <tr key={r.id}>
                  <td><input type="checkbox" className="rowcheck" checked={selected.has(r.id)} onChange={()=>toggleOne(r.id)} aria-label={`Select ${r.target}`}/></td>
                  <td className="mono" style={{ maxWidth:320,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap' }}>{r.target}</td>
                  <td>
                    <span className="chip" style={chipStyleFor(engineOf(r.input_type))}>{(ENGINES[engineOf(r.input_type)]||ENGINES.misc).label}</span>
                  </td>
                  <td><InvStatus status={r.status}/></td>
                  <td className="rel-time" title={absTime(r.created_at)}>{relTime(r.created_at)}</td>
                  <td>
                    <div className="cell-actions">
                      <a className="iconbtn" href={`#/report/${r.id}`} title="Open report"><IExt size={15}/></a>
                      <button className="iconbtn" title="Re-run" onClick={()=>rerun(r.target)}><IRefresh size={15}/></button>
                      <button className="iconbtn" title="Delete" onClick={()=>setConfirmIds([r.id])}><ITrash size={15}/></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal
        open={confirmIds.length>0}
        onClose={()=>setConfirmIds([])}
        title={confirmIds.length>1 ? `Delete ${confirmIds.length} investigations?` : 'Delete investigation?'}
        actions={<>
          <button className="btn btn-ghost" onClick={()=>setConfirmIds([])}>Cancel</button>
          <button className="btn btn-danger" onClick={()=>doDelete(confirmIds)}><ITrash size={14}/>Delete</button>
        </>}
      >
        The stored report{confirmIds.length>1?'s':''} and all findings will be permanently removed.
      </Modal>
    </div>
  )
}

function chipStyleFor(engine){
  const e = ENGINES[engine] || ENGINES.misc
  return { background:e.tint,color:e.text,borderColor:e.hue+'44' }
}

function InvStatus({ status }){
  if(status==='running') return <StatusChip status="running" pulse>running</StatusChip>
  if(status==='error') return <StatusChip status="error">failed</StatusChip>
  if(status==='done') return <StatusChip status="found">done</StatusChip>
  return <StatusChip status="skipped">{status}</StatusChip>
}
