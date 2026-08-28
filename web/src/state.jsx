import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { api, wsConnect } from './api.js'
import { IOkCircle,IWarn,ICrit,IInfo,IX } from './icons.jsx'
import { pushRecent as pushRecentTarget } from './engines.js'

/* ---------- Toasts ---------- */

const ToastCtx = createContext(null)
export const useToast = ()=>useContext(ToastCtx)

const TOAST_ICONS = { ok:IOkCircle, warn:IWarn, crit:ICrit, info:IInfo }

export function ToastProvider({ children }){
  const [toasts,setToasts] = useState([])
  const idRef = useRef(0)

  const dismiss = useCallback((id)=>{
    setToasts(t=>t.filter(x=>x.id!==id))
  },[])

  const push = useCallback((kind,msg)=>{
    const id = ++idRef.current
    setToasts(t=>[...t.slice(-4),{ id, kind, msg }])
    if(kind!=='crit') setTimeout(()=>dismiss(id),5000)
  },[dismiss])

  return (
    <ToastCtx.Provider value={{ push }}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map(t=>{
          const Icon = TOAST_ICONS[t.kind] || IInfo
          return (
            <div key={t.id} className={`toast toast-${t.kind}`}>
              <Icon size={16}/>
              <p>{t.msg}</p>
              <button className="iconbtn" onClick={()=>dismiss(t.id)} aria-label="Dismiss"><IX size={14}/></button>
            </div>
          )
        })}
      </div>
    </ToastCtx.Provider>
  )
}

/* ---------- Run (live investigation) ---------- */

const RunCtx = createContext(null)
export const useRun = ()=>useContext(RunCtx)

function blankRun(){
  return {
    phase:'idle', invId:null, target:'', startedAt:null,
    modules:[], events:[], report:null, error:null,
  }
}

export function RunProvider({ children }){
  const [run,setRun] = useState(blankRun)
  const [connLost,setConnLost] = useState(false)
  const wsRef = useRef(null)
  const toast = useToast()
  const runRef = useRef(run)
  runRef.current = run

  useEffect(()=>()=>wsRef.current?.close(),[])

  const patchModule = useCallback((name,patch)=>{
    setRun(r=>({
      ...r,
      modules:r.modules.map(m=>m.name===name ? {...m,...patch} : m),
    }))
  },[])

  const hydrate = useCallback(async(invId)=>{
    if(!invId) return
    try{
      const rep = await api.report(invId)
      setRun(r=>r.invId===invId ? {...r,report:rep,phase:'done'} : r)
    }catch(e){
      setRun(r=>r.invId===invId ? {...r,phase:'done',error:e.message} : r)
      toast.push('crit',e.message)
    }
  },[])

  const onEvent = useCallback((evt)=>{
    setRun(r=>({ ...r, events:[...r.events.slice(-400), evt] }))
    switch(evt.type){
      case 'investigation_start':
        setRun(r=>({
          ...r,
          modules:(evt.modules||[]).map(name=>({ name,status:'queued',count:0,pivotRuns:0 })),
        }))
        break
      case 'module_start':
        patchModule(evt.module,{ status:'running' })
        break
      case 'module_done':
        setRun(r=>({
          ...r,
          modules:r.modules.map(m=>{
            if(m.name!==evt.module) return m
            if(m.status==='done'||m.status==='error'){
              return {
                ...m,
                count:m.count+(evt.findings||0),
                pivotRuns:(m.pivotRuns||0)+1,
                duration:+(((m.duration||0)+(evt.duration||0))).toFixed(3),
              }
            }
            return {
              ...m,
              status:evt.error?'error':'done',
              count:evt.findings||0,
              duration:evt.duration,
              summary:evt.summary,
              error:evt.error||null,
            }
          }),
        }))
        break
      case 'investigation_done':
        hydrate(evt.investigation_id || runRef.current.invId)
        break
      case 'error':
        toast.push('crit',evt.message || 'Investigation failed')
        setRun(r=>({...r,phase:'error',error:evt.message}))
        break
      default:
        break
    }
  },[patchModule,hydrate])

  const start = useCallback(async(target,moduleNames,optIn=false)=>{
    wsRef.current?.close()
    setConnLost(false)
    setRun({ ...blankRun(), phase:'starting', target })
    try{
      const res = await api.investigate({
        target,
        modules: moduleNames && moduleNames.length ? moduleNames : undefined,
        allow_opt_in: optIn,
      })
      setRun(r=>({ ...r, phase:'running', invId:res.investigation_id, startedAt:Date.now() }))
      pushRecentTarget(target)
      wsRef.current = wsConnect(res.investigation_id,{
        onEvent,
        onClose:()=>setConnLost(true),
      })
    }catch(e){
      setRun(r=>({ ...r, phase:'error', error:e.message }))
      toast.push('crit',e.message)
    }
  },[onEvent,toast])

  const stop = useCallback(()=>{
    wsRef.current?.close()
    setRun(r=>({ ...r,phase:'stopped' }))
    toast.push('warn','Detached from investigation — it continues server-side.')
  },[toast])

  const reset = useCallback(()=>{
    wsRef.current?.close()
    setConnLost(false)
    setRun(blankRun())
  },[])

  const totals = {
    findings: run.modules.reduce((a,m)=>a+m.count,0),
    errors: run.modules.filter(m=>m.status==='error').length,
    done: run.modules.filter(m=>['done','error'].includes(m.status)).length,
    total: run.modules.length,
  }

  return (
    <RunCtx.Provider value={{ run,totals,connLost,start,stop,reset,hydrate }}>
      {children}
    </RunCtx.Provider>
  )
}
