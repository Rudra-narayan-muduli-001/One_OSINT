async function jf(res){
  if(!res.ok){
    const body = await res.json().catch(()=>({}))
    throw new Error(body.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

const get = (url)=>fetch(url).then(jf)

export const api = {
  health: ()=>get('/health'),
  modules: ()=>get('/api/modules'),
  keys: ()=>get('/api/keys'),
  investigations: (limit=200)=>get(`/api/investigations?limit=${limit}`),
  report: (id)=>get(`/api/report/${encodeURIComponent(id)}`),
  remove: (id)=>fetch(`/api/investigation/${encodeURIComponent(id)}`,{method:'DELETE'}).then(jf),
  investigate: (body)=>fetch('/api/investigate',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(body),
  }).then(jf),
  exportUrl:(id,fmt)=>`/api/report/${encodeURIComponent(id)}/export?format=${fmt}`,
}

export function wsConnect(id,{ onEvent, onClose }){
  const proto = location.protocol==='https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${location.host}/ws/investigate/${encodeURIComponent(id)}`)
  ws.onmessage = (msg)=>{
    try{ onEvent(JSON.parse(msg.data)) }catch{ /* ignore malformed frame */ }
  }
  ws.onclose = ()=>onClose && onClose()
  return ws
}
