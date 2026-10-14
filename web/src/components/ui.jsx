import React, { useEffect, useState } from 'react'
import { ENGINES, engineOf, humanModule, statusVariant } from '../engines.js'
import { ICheck,IChevD,IExt,IWarn } from '../icons.jsx'
import { RadarArt } from '../icons.jsx'
import { motion, AnimatePresence } from 'framer-motion'

export function StatusChip({ status, children, pulse }){
  const v = statusVariant(status)
  return (
    <span className={`chip chip-${v}`}>
      {pulse && <i className="dotp"/>}
      {children || status}
    </span>
  )
}

export function EngineDot({ engine, running, size=8 }){
  const e = ENGINES[engine] || ENGINES.misc
  return (
    <span
      className={`engine-dot${running?' running':''}`}
      style={{ width:size,height:size,background:e.hue }}
    />
  )
}

export function ModuleTag({ name }){
  const e = ENGINES[engineOf(name)] || ENGINES.misc
  return (
    <span className="chip" style={{ background:e.tint,color:e.text,borderColor:e.hue+'44' }}>
      <EngineDot engine={engineOf(name)} size={6}/>
      {humanModule(name)}
    </span>
  )
}

export function EmptyState({ title, children, art='radar' }){
  return (
    <div className="empty">
      {art==='radar' && <RadarArt/>}
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  )
}

export function Modal({ open,onClose,title,children,actions }){
  useEffect(()=>{
    if(!open) return undefined
    const onKey = (e)=>{ if(e.key==='Escape') onClose() }
    window.addEventListener('keydown',onKey)
    return ()=>window.removeEventListener('keydown',onKey)
  },[open,onClose])
  if(!open) return null
  return (
    <AnimatePresence>
      <motion.div
        className="scrim"
        onMouseDown={(e)=>{ if(e.target===e.currentTarget) onClose() }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.15 }}
      >
        <motion.div
          className="modal"
          role="dialog"
          aria-modal="true"
          aria-label={title}
          initial={{ opacity: 0, y: 20, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -20, scale: 0.95 }}
          transition={{ duration: 0.2, ease: [0.25, 0.1, 0.25, 1] }}
        >
          <h3>{title}</h3>
          <p>{children}</p>
          <div className="modal-actions">{actions}</div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  )
}

export function CopyBtn({ text,label='Copy',size=14 }){
  const [done,setDone] = useState(false)
  const copy = async()=>{
    try{
      await navigator.clipboard.writeText(text)
    }catch{
      const ta = document.createElement('textarea')
      ta.value = text; document.body.appendChild(ta); ta.select()
      document.execCommand('copy'); ta.remove()
    }
    setDone(true)
    setTimeout(()=>setDone(false),1200)
  }
  return (
    <button className="btn btn-ghost btn-sm" onClick={copy} title={label}>
      {done ? <ICheck size={size}/> : null}
      {done ? 'Copied' : label}
    </button>
  )
}

const STATUS_LABEL = {
  found:'found', possible:'possible', not_found:'not found',
  rate_limited:'rate limited', error:'error', skipped:'skipped',
}

export function FindingRow({ f, index=0, alert=false }){
  const [open,setOpen] = useState(false)
  const extra = f.extra && Object.keys(f.extra).length ? f.extra : null
  return (
    <>
      <div className={`finding anim-rise${alert?' alertrow':''}`} style={{ animationDelay:`${Math.min(index*40,400)}ms` }}>
        <StatusChip status={f.status}>{STATUS_LABEL[f.status]||f.status}</StatusChip>
        <span className="f-site">{f.site}</span>
        {f.url
          ? <a className="f-url" href={f.url} target="_blank" rel="noreferrer">{f.url}</a>
          : (f.reason ? <span className="f-url">{f.reason}</span> : <span className="f-url"/>)}
        {extra && (
          <button className="iconbtn f-expand" onClick={()=>setOpen(o=>!o)} aria-label="Toggle evidence" aria-expanded={open}>
            <IChevD size={14} style={{ transform:open?'rotate(180deg)':'none',transition:'transform var(--t-fast)',color:'var(--text-disabled)' }}/>
          </button>
        )}
      </div>
      <AnimatePresence>
        {open && extra && (
          <motion.pre
            className="f-extra"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2, ease: [0.25, 0.1, 0.25, 1] }}
          >
            {JSON.stringify(extra,null,2)}
          </motion.pre>
        )}
      </AnimatePresence>
    </>
  )
}

export function WarnChip({ children }){
  return <span className="chip chip-warn"><IWarn size={12}/>{children}</span>
}

export function TechToggle({ on,onChange }){
  return (
    <label className="techtoggle">
      <span className={`lbl${on?' on':''}`}>Technical details</span>
      <span className="switch">
        <input type="checkbox" checked={on} onChange={(e)=>onChange(e.target.checked)}/>
        <i/>
      </span>
    </label>
  )
}

export function ExtLink({ href,children }){
  return <a className="btn btn-ghost btn-sm" href={href} target="_blank" rel="noreferrer"><IExt size={13}/>{children}</a>
}
