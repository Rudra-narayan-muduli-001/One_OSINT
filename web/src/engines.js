export const ENGINES = {
  username:{ label:'Username', hue:'#0F766E', tint:'#D9F0EC', text:'#0C5F59' },
  email:   { label:'Email',    hue:'#2563EB', tint:'#DEE9FA', text:'#1D4FB8' },
  phone:   { label:'Phone',    hue:'#7A3E8F', tint:'#EFE2F5', text:'#66337A' },
  domain:  { label:'Domain',   hue:'#177245', tint:'#DDF0E4', text:'#135E39' },
  ip:      { label:'IP',       hue:'#92610A', tint:'#F5EBD3', text:'#78500C' },
  google:  { label:'Google',   hue:'#B8434F', tint:'#F8E3E5', text:'#99343F' },
  file:    { label:'File',     hue:'#0E7490', tint:'#DAEDF2', text:'#0B5D74' },
  misc:    { label:'Misc',     hue:'#57534E', tint:'#ECEAE3', text:'#44403C' },
}

export const TYPE_ORDER = ['all','username','email','phone','domain','ip','google','file']

const EMAIL_RE = /^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$/
const PHONE_RE = /^\+?[0-9][0-9\s().\-]{5,}$/
const DOMAIN_RE = /^(?!\-)(?:[A-Za-z0-9\-]{1,63}\.)+[A-Za-z]{2,}$/
const IPV4_RE = /^(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])(\.(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])){3}$/
const IPV6_RE = /^[0-9A-Fa-f:]{2,39}$/
const USERNAME_RE = /^[A-Za-z0-9_.\-]{3,64}$/

export function detectType(value){
  const v = (value||'').trim()
  if(!v) return 'unknown'
  if(EMAIL_RE.test(v)) return 'email'
  if(PHONE_RE.test(v) && /\d/.test(v)){
    const digits = v.replace(/\D/g,'')
    if(digits.length>=7 && digits.length<=15 && (v.startsWith('+') || digits.length>10)) return 'phone'
  }
  if(IPV4_RE.test(v) || IPV6_RE.test(v)) return 'ip'
  if(DOMAIN_RE.test(v) && v.includes('.')) return 'domain'
  if(USERNAME_RE.test(v)) return 'username'
  return 'unknown'
}

export function engineOf(moduleName){
  const n = (moduleName||'').toLowerCase()
  if(n.startsWith('username')) return 'username'
  if(n.startsWith('email')) return 'email'
  if(n.startsWith('phone')) return 'phone'
  if(n.startsWith('domain')) return 'domain'
  if(n.startsWith('ip')) return 'ip'
  if(n.startsWith('google')) return 'google'
  if(n.startsWith('file')) return 'file'
  return 'misc'
}

export function humanModule(name){
  const parts = (name||'').split('_')
  if(parts.length>1) parts.shift()
  return parts.map(p=>p.charAt(0).toUpperCase()+p.slice(1)).join(' ') || name
}

const STATUS_MAP = {
  found:'ok', possible:'info', not_found:'muted', rate_limited:'warn',
  error:'crit', skipped:'muted', running:'run', done:'ok',
}
export function statusVariant(s){ return STATUS_MAP[s] || 'muted' }

export function relTime(iso){
  if(!iso) return '—'
  const then = new Date(iso.endsWith('Z')||iso.includes('+') ? iso : iso+'Z')
  const s = Math.max(0,(Date.now()-then.getTime())/1000)
  if(s<60) return 'just now'
  if(s<3600) return `${Math.floor(s/60)}m ago`
  if(s<86400) return `${Math.floor(s/3600)}h ago`
  if(s<2592000) return `${Math.floor(s/86400)}d ago`
  return then.toISOString().slice(0,10)
}

export function absTime(iso){
  if(!iso) return ''
  const d = new Date(iso.endsWith('Z')||iso.includes('+') ? iso : iso+'Z')
  return d.toLocaleString()
}

export function fmtElapsed(ms){
  const s = Math.max(0,Math.floor(ms/1000))
  return `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`
}

const RECENTS_KEY = 'signal.recents'
export function loadRecents(){
  try{ return JSON.parse(localStorage.getItem(RECENTS_KEY)) || [] }catch{ return [] }
}
export function pushRecent(target){
  const list = loadRecents().filter(t=>t!==target)
  list.unshift(target)
  localStorage.setItem(RECENTS_KEY, JSON.stringify(list.slice(0,8)))
}
export function dropRecent(target){
  localStorage.setItem(RECENTS_KEY, JSON.stringify(loadRecents().filter(t=>t!==target)))
}
