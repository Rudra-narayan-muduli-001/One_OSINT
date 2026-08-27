import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { EmptyState } from '../components/ui.jsx'
import { ICopy,IInfo,IKey } from '../icons.jsx'

const SETUP_STEPS = [
  { n:'1.', b:'Create a file called .env', p:'In the same folder as this program (next to run.py). One key per line, like:  HIBP_API_KEY=abc123' },
  { n:'2.', b:'Or use keys.yaml', p:'Windows keeps it in %APPDATA%\\one-osint\\keys.yaml. Same idea - name on the left, key on the right.' },
  { n:'3.', b:'Restart one-osint', p:'The engines light up automatically for every key it finds. No restart needed between searches.' },
]

export default function Keys(){
  const [keys,setKeys] = useState(null)
  const [error,setError] = useState(null)
  const [copiedEnv,setCopiedEnv] = useState(false)

  useEffect(()=>{
    api.keys().then(setKeys).catch(e=>setError(e.message))
  },[])

  const copyTemplate = ()=>{
    const lines = (keys||[]).map(k=>`${k.env_var}=`).join('\n')
    navigator.clipboard.writeText(lines).then(()=>{ setCopiedEnv(true); setTimeout(()=>setCopiedEnv(false),1500) })
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Optional API keys</h1>
          <p>The search works without any keys. Adding these unlocks extra sources - each one is free to create unless noted.</p>
        </div>
      </div>

      <div className="keys-note">
        <IInfo size={17}/>
        <span>
          Keys stay on your computer and are never shown in the browser after being saved.
        </span>
      </div>

      <div className="env-file-hint" style={{ display:'flex',alignItems:'center',gap:12 }}>
        <span style={{ flex:1 }}>
          <b style={{ fontFamily:'var(--font-ui)' }}>Quickest setup:</b> create a file named <b style={{ fontFamily:'var(--font-ui)' }}>.env</b> next to run.py
        </span>
        <button className="btn btn-outline btn-sm" onClick={copyTemplate}>
          {copiedEnv ? 'Copied' : 'Copy template'}
        </button>
      </div>

      <div className="how" style={{ margin:'0 auto 26px' }}>
        {SETUP_STEPS.map(s=>(
          <div key={s.n} className="card step">
            <span className="num">{s.n}</span>
            <b>{s.b}</b>
            <p>{s.p}</p>
          </div>
        ))}
      </div>

      {!keys && !error && Array.from({length:6}).map((_,i)=>(
        <div key={i} className="skeleton" style={{ height:62,marginBottom:10 }}/>
      ))}
      {error && <EmptyState title="Couldn’t load key status">{error}</EmptyState>}
      {keys && keys.length===0 && <EmptyState title="No integrations registered">This build exposes no keyed services.</EmptyState>}

      {keys && keys.length>0 && (
        <div className="keys-list">
          {keys.map(k=>(
            <div key={k.name} className={`card key-row${k.set?'':''}`}>
              <span className="kavatar"><IKey size={15}/></span>
              <div className="key-main">
                <div className="key-name">{k.description}</div>
                <div className="key-desc mono">{k.name}</div>
              </div>
              <span className="key-env">{k.env_var}</span>
              {k.set
                ? <span className="chip chip-ok">Ready</span>
                : <span className="chip chip-muted">Not set</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
