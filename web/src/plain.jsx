import React from 'react'
import { humanModule } from './engines.js'

/* Warm avatar palette for account cards */
const AVATAR_HUES = ['#1E6B4F','#2C5D8A','#8A5A2C','#6B4E7A','#3F6E75','#94622B','#566238','#7A4444']
export function hueFor(name){
  let h = 0
  for(const ch of String(name)) h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return AVATAR_HUES[h % AVATAR_HUES.length]
}

const TYPE_NOUN = {
  email:'email address', username:'username', phone:'phone number',
  domain:'website', ip:'IP address', unknown:'search term',
}

const ACCOUNT_CATEGORIES = new Set([
  'social','webmail','dev','coding','forum','gaming','finance','cms','shopping',
  'music','crm','software','productivity','education','misc-site','webmail-account',
])
const ACCOUNT_MODULES = /^(username_|email_enumeration|protonmail_lookup|google_email_probe|smtp_verify)/

export const FRIENDLY_KEYS = {
  ip:'IP address', city:'City', region:'Region', country:'Country',
  country_name:'Country', timezone:'Time zone', org:'Network provider',
  asn:'Network range', latitude:'Latitude', longitude:'Longitude',
  domain:'Domain', value:'Value', type:'Record type', host:'Host',
  carrier:'Carrier', valid:'Valid number', format:'Format',
  camera_make:'Camera maker', camera_model:'Camera model', date_taken:'Photo taken on',
  software:'Software used', author:'Author', description:'Description',
  gps:'Location', google_maps:'Open map', display_name:'Display name',
  followers:'Followers', following:'Following', posts:'Posts',
  created_at:'Joined on', registered:'Account exists', pgp_key_available:'Encryption key published',
  probe_status:'Probe result', size:'File size', wordlist:'Names checked',
  resolved:'Found records', ptr:'Pointer record', title:'Title',
}

export function friendlyValue(k,v){
  if(v === true) return 'Yes'
  if(v === false) return 'No'
  if(k === 'google_maps') return null
  return String(v)
}

function isBreach(f){ return f.category==='breach' || Boolean(f.extra?.breach) }
function isAccount(f,mname){
  return f.status==='found' && !isBreach(f) &&
    (ACCOUNT_CATEGORIES.has(f.category) || ACCOUNT_MODULES.test(mname||''))
}
function isFact(f){ return ['dns','geo'].includes(f.category) || f.category==='file' || f.category==='vehicle' }
function isLead(f){ return f.status==='possible' || f.category==='dorks' }

export function buildPlain(report){
  const modules = Array.isArray(report.modules) ? report.modules : []
  const accounts = []
  const breaches = []
  const facts = []
  const leads = []
  const others = []
  const errors = []
  let checks = 0

  for(const m of modules){
    const mname = m.name || ''
    for(const f of m.findings || []){
      if(f.status==='error') continue
      checks++
      if(isBreach(f)) breaches.push({ ...f,_module:mname })
      else if(isAccount(f,mname)) accounts.push({ ...f,_module:mname })
      else if(isLead(f)) leads.push({ ...f,_module:mname })
      else if(f.status==='found' && isFact(f)) facts.push({ ...f,_module:mname })
      else if(f.status==='found') others.push({ ...f,_module:mname })
    }
    if(m.error) errors.push(m)
  }

  /* dedupe accounts by site+url */
  const seen = new Set()
  const uniqAccounts = accounts.filter(a=>{
    const key = `${a.site}|${a.url||''}`
    if(seen.has(key)) return false
    seen.add(key)
    return true
  })

  const noun = TYPE_NOUN[report.input_type] || 'search term'
  let headline, stampKind, stampText
  if(breaches.length){
    headline = <>This {noun} appears in <em>{breaches.length} data breach{breaches.length>1?'es':''}</em></>
    stampKind='crit'; stampText='Exposure warning'
  }else if(uniqAccounts.length){
    headline = <>We found public traces of this {noun} on <em>{uniqAccounts.length} service{uniqAccounts.length>1?'s':''}</em></>
    stampKind='ok'; stampText='Traces found'
  }else if(checks>0){
    headline = <>No public traces of this {noun} were found</>
    stampKind='muted'; stampText='All clear'
  }else{
    headline = <>Nothing could be checked for this {noun}</>
    stampKind='warn'; stampText='Check failed'
  }

  const subParts = []
  if(uniqAccounts.length) subParts.push(`${uniqAccounts.length} registered account${uniqAccounts.length>1?'s':''}`)
  if(breaches.length) subParts.push(`${breaches.length} breach hit${breaches.length>1?'s':''}`)
  if(leads.length) subParts.push(`${leads.length} search lead${leads.length>1?'s':''}`)

  const sectionList = []
  if(breaches.length) sectionList.push({ id:'breaches', kind:'breaches', title:'Data breach exposure', count:breaches.length,
    expl:'These are known data leaks that contained this value. Anyone may have seen this information - consider changing passwords.' })
  if(uniqAccounts.length) sectionList.push({ id:'accounts', kind:'accounts', title:'Where it is registered', count:uniqAccounts.length,
    expl:'Services where an account with this value could be confirmed.' })
  if(facts.length) sectionList.push({ id:'facts', kind:'facts', title:'Details & records', count:facts.length,
    expl:'Background information discovered from public records.' })
  if(others.length) sectionList.push({ id:'others', kind:'others', title:'Other findings', count:others.length,
    expl:'Additional matches worth a look.' })
  if(leads.length) sectionList.push({ id:'leads', kind:'leads', title:'Ready-to-run searches', count:leads.length,
    expl:'Pre-built searches you can open to dig deeper manually - these have not been checked automatically.' })
  if(errors.length) sectionList.push({ id:'errors', kind:'errors', title:'Engines that could not run', count:errors.length,
    expl:'Some sources were unavailable during this scan. Adding API keys usually fixes this.',
    _static:true })

  return {
    headline, stampKind, stampText,
    sub:subParts.join(' · '),
    counts:{ accounts:uniqAccounts.length, breaches:breaches.length, leads:leads.length, facts:facts.length, others:others.length },
    sections:sectionList,
    items:{ breaches, accounts:uniqAccounts, facts, leads, others,
      errors:errors.map(e=>({ name:e.name, reason:e.error })) },
    noun,
  }
}
