/* Browser globals shim - must be imported before any app code */
const store = new Map()
global.window = {
  addEventListener(){}, removeEventListener(){}, dispatchEvent(){},
  scrollTo(){}, innerHeight:900,
}
global.document = { getElementById:()=>null, createElement:()=>({ select(){}, remove(){} }), body:{ appendChild(){}, } }
global.localStorage = {
  getItem:(k)=>store.has(k)?store.get(k):null,
  setItem:(k,v)=>store.set(k,String(v)),
  removeItem:(k)=>store.delete(k),
}
global.location = { hash:'', host:'localhost', protocol:'http:' }
global.navigator = {}
global.CustomEvent = class CustomEvent { constructor(type,opts){ this.type=type; this.detail=opts?.detail } }
global.fetch = ()=>Promise.reject(new Error('no network in smoke'))
