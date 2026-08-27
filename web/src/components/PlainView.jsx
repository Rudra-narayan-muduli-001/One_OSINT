import React from 'react'
import { buildPlain, hueFor, FRIENDLY_KEYS, friendlyValue } from '../plain.jsx'
import { humanModule } from '../engines.js'
import { IExt,IOkCircle,IWarn,IInfo } from '../icons.jsx'

const STAMP_ICONS = { ok:IOkCircle, crit:IWarn, warn:IWarn, muted:IInfo }

export function Avatar({ name,hue }){
  const letter = String(name||'?').trim().charAt(0).toUpperCase() || '?'
  return <span className="avatar" style={{ background:hue }}>{letter}</span>
}

function BreachCard({ f,i }){
  const title = f.extra?.breach || f.site
  const date = f.extra?.breach_date || f.extra?.added_date || ''
  const classes = Array.isArray(f.extra?.data_classes) ? f.extra.data_classes : []
  return (
    <div className="breach-card anim-rise" style={{ animationDelay:`${Math.min(i*50,400)}ms` }}>
      <span className="breach-icon"><IWarn size={17}/></span>
      <div className="breach-main">
        <div className="breach-title">{title}</div>
        {date && <div className="breach-meta">Leak first published {date}</div>}
        {classes.length>0 && (
          <div className="breach-data">
            {classes.map(c=><span key={c}>{String(c).replace(/_/g,' ').toLowerCase()}</span>)}
          </div>
        )}
      </div>
    </div>
  )
}

function AccountCard({ f,i }){
  const hue = hueFor(f.site)
  const label = prettySite(f.site)
  return (
    <div className="card acct-card anim-rise" style={{ animationDelay:`${Math.min(i*40,360)}ms` }}>
      <Avatar name={f.site} hue={hue}/>
      <div className="acct-main">
        <div className="acct-site">{label}</div>
        <div className="acct-url">{f.url ? f.url.replace(/^https?:\/\//,'') : 'account confirmed'}</div>
      </div>
      {f.url && (
        <a className="acct-open" href={f.url} target="_blank" rel="noreferrer">Open<IExt size={13}/></a>
      )}
    </div>
  )
}

const SITE_LABELS = { google:'Google account', dns:'DNS record', ipapi:'IP location', file:'File details' }
function prettySite(site){
  if(SITE_LABELS[site]) return SITE_LABELS[site]
  const s = String(site)
  return s === s.toUpperCase() && s.length<=4 ? s : s.charAt(0).toUpperCase()+s.slice(1)
}

function FactsList({ items }){
  const rows = []
  for(const f of items){
    const extra = f.extra && Object.keys(f.extra).length ? f.extra : null
    if(extra){
      for(const [k,v] of Object.entries(extra)){
        const label = FRIENDLY_KEYS[k] || k.replace(/_/g,' ')
        const val = friendlyValue(k,v)
        if(val==null || val==='') continue
        if(typeof v === 'object') continue
        rows.push({ k:`${label}`, v:val })
      }
    }else{
      rows.push({ k:prettySite(f.site), v:f.reason || 'found' })
    }
  }
  const seen = new Set()
  const uniq = rows.filter(r=>{ const key=r.k+'|'+r.v; if(seen.has(key))return false; seen.add(key); return true })
  if(!uniq.length) return null
  return (
    <div className="card kv-card anim-rise">
      {uniq.map((r,i)=>(
        <div className="kv" key={i}>
          <span className="k">{r.k}</span>
          <span className="v">{r.v}</span>
        </div>
      ))}
    </div>
  )
}

function LeadGrid({ items }){
  return (
    <div className="lead-grid">
      {items.map((f,i)=>(
        <a key={i} className="card lead-card" href={f.url} target="_blank" rel="noreferrer">
          <IExt size={14}/>
          <span>{f.extra?.query || f.reason || f.site}</span>
        </a>
      ))}
    </div>
  )
}

export function PlainView({ report }){
  const plain = buildPlain(report)
  const StampIcon = STAMP_ICONS[plain.stampKind] || IInfo
  return (
    <div>
      <header className="verdict anim-rise">
        <div className="overline micro">Investigation result</div>
        <h2>{plain.headline}</h2>
        {plain.sub && <p className="verdict-sub">{plain.sub}.</p>}
        <span className={`stamp stamp-${plain.stampKind}`}>
          <StampIcon size={14}/>{plain.stampText}
        </span>
      </header>

      {plain.sections.map(sec=>{
        const items = sec._static ? plain.items[sec.kind] : sec.kind==='accounts' ? plain.items.accounts : plain.items[sec.kind]
        return (
        <section key={sec.id} id={`sec-${sec.id}`} className="plain-section">
          <div className="rule-label micro">{sec.title}</div>
          <div className="plain-head">
            <h3>{sec.title}</h3>
            <span className="count">{sec.count} found</span>
          </div>
          <p className="plain-expl">{sec.expl}</p>

          {sec.kind==='breaches' && (
            <div className="breach-list">
              {items.map((f,i)=><BreachCard key={i} f={f} i={i}/>)}
            </div>
          )}
          {sec.kind==='accounts' && (
            <div className="acct-grid">
              {items.map((f,i)=><AccountCard key={`${f.site}${f.url}${i}`} f={f} i={i}/>)}
            </div>
          )}
          {sec.kind==='facts' && <FactsList items={items}/>}
          {sec.kind==='others' && <FactsList items={items}/>}
          {sec.kind==='leads' && <LeadGrid items={items}/>}
          {sec.kind==='errors' && (
            <div className="card kv-card">
              {items.map((e,i)=>(
                <div className="kv" key={i}>
                  <span className="k">{humanModule(e.name)}</span>
                  <span className="v mono" style={{ color:'var(--crit-text)' }}>{e.reason}</span>
                </div>
              ))}
            </div>
          )}
        </section>
        )
      })}
    </div>
  )
}
