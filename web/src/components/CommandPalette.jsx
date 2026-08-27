import React, { useEffect, useMemo, useRef, useState } from 'react'
import { detectType, ENGINES } from '../engines.js'
import { ICrosshair,IGlobe,IHistory,IKey,IPlay,ISearch } from '../icons.jsx'

export default function CommandPalette({ open,onClose,navigate,onRun,lastReportId }){
  const [q,setQ] = useState('')
  const [sel,setSel] = useState(0)
  const listRef = useRef(null)

  useEffect(()=>{
    if(open){ setQ(''); setSel(0) }
  },[open])

  const items = useMemo(()=>{
    const out = []
    const nav = (label,route,Icon)=>({ kind:'nav', label, route, Icon })
    out.push(nav('Start a new search','investigate',ICrosshair))
    out.push(nav('Show past searches','history',IHistory))
    out.push(nav('Set up optional API keys','keys',IKey))
    if(lastReportId) out.push({ kind:'nav', label:'Open latest report', route:`report/${lastReportId}`, Icon:IGlobe })
    const t = q.trim()
    if(t.length>2 && detectType(t)!=='unknown'){
      out.push({ kind:'run', label:`Investigate “${t}”`, target:t, Icon:IPlay })
      out.push({ kind:'fill', label:`Load “${t}” into search`, target:t, Icon:ISearch })
    }
    return out.filter(it=>it.label.toLowerCase().includes(q.toLowerCase()))
  },[q,lastReportId])

  useEffect(()=>{ setSel(s=>Math.min(s,Math.max(0,items.length-1))) },[items.length])
  useEffect(()=>{
    const el = listRef.current?.children[sel]
    el?.scrollIntoView({ block:'nearest' })
  },[sel])

  if(!open) return null

  const exec = (item)=>{
    onClose()
    if(!item) return
    if(item.kind==='nav') navigate(item.route)
    if(item.kind==='run') onRun(item.target)
    if(item.kind==='fill'){
      onClose()
      window.dispatchEvent(new CustomEvent('signal:fill-target',{ detail:item.target }))
    }
  }

  const onKeyDown = (e)=>{
    if(e.key==='ArrowDown'){ e.preventDefault(); setSel(s=>(s+1)%Math.max(items.length,1)) }
    else if(e.key==='ArrowUp'){ e.preventDefault(); setSel(s=>(s-1+items.length)%Math.max(items.length,1)) }
    else if(e.key==='Enter'){ exec(items[sel]) }
    else if(e.key==='Escape'){ onClose() }
  }

  return (
    <div className="scrim" style={{ zIndex:120 }} onMouseDown={(e)=>{ if(e.target===e.currentTarget) onClose() }}>
      <div className="palette" role="dialog" aria-modal="true" aria-label="Command palette">
        <input
          autoFocus className="palette-input"
          placeholder="Search screens or type a target to investigate…"
          value={q}
          onChange={(e)=>setQ(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <div className="palette-list" ref={listRef}>
          {items.length===0 && <div className="pal-empty">No matches — paste a target above to run it.</div>}
          {items.map((it,i)=>(
            <button
              key={i}
              className={`pal-item${i===sel?' sel':''}`}
              onMouseEnter={()=>setSel(i)}
              onClick={()=>exec(it)}
            >
              <it.Icon size={16}/>
              <span>{it.label}</span>
              {it.kind==='run' && <span className="hint">enter ⏎</span>}
            </button>
          ))}
        </div>
        <div className="palette-foot">
          <span><kbd>↑↓</kbd> navigate</span>
          <span><kbd>⏎</kbd> select</span>
          <span><kbd>esc</kbd> close</span>
        </div>
      </div>
    </div>
  )
}

export function engineChipStyle(engine){
  const e = ENGINES[engine] || ENGINES.misc
  return { background:e.tint,color:e.text,borderColor:e.hue+'44' }
}
