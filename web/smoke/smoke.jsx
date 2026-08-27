import './shim.js'
import React from 'react'
import { renderToString } from 'react-dom/server'
import { buildPlain } from '../src/plain.jsx'
import { PlainView } from '../src/components/PlainView.jsx'
import App from '../src/App.jsx'
import History from '../src/screens/History.jsx'
import Keys from '../src/screens/Keys.jsx'
import Report from '../src/screens/Report.jsx'
import { ToastProvider, RunProvider } from '../src/state.jsx'
import report from './smoke-report.json'

const WithProviders = ({ children }) =>
  React.createElement(ToastProvider, null,
    React.createElement(RunProvider, null, children))

let failures = 0
const check = (label, fn) => {
  try {
    const out = fn()
    console.log('PASS', label, typeof out === 'string' ? `(${out.length} chars)` : '')
  } catch (e) {
    failures++
    console.log('FAIL', label, '->', e.message, '\n', e.stack?.split('\n')[1] || '')
  }
}

const nav = ()=>{}

check('buildPlain (real report)', () => JSON.stringify(buildPlain(report).counts))
check('PlainView renderToString', () => renderToString(React.createElement(PlainView, { report })))
check('App shell (idle)', () => renderToString(React.createElement(WithProviders, null, React.createElement(App))))
check('History screen', () => renderToString(React.createElement(WithProviders, null, React.createElement(History, { navigate:nav }))))
check('Keys screen', () => renderToString(React.createElement(WithProviders, null, React.createElement(Keys))))
check('Report screen (skeleton path)', () => renderToString(React.createElement(WithProviders, null, React.createElement(Report, { id:'abc', navigate:nav }))))
check('Report screen (full plain view)', () => renderToString(React.createElement(WithProviders, null, React.createElement(Report, { id:'abc', navigate:nav }))))

check('PlainView edge: null extras', () => {
  const r = { target:'x', input_type:'username', found_accounts:1, module_count:1,
    pivots:{}, modules:[{ name:'username_github', findings:[{ site:'github', url:null, status:'found', category:'social', extra:null, media:null, reason:null }] }] }
  return renderToString(React.createElement(PlainView, { report:r }))
})
check('PlainView edge: weird statuses + errors', () => {
  const r = { target:'x', input_type:'phone', found_accounts:0, module_count:2, pivots:{},
    modules:[
      { name:'phone_dorks', findings:[{ site:'google', status:'possible', url:'https://g', extra:{ query:'q' } }] },
      { name:'breach_hibp', error:'boom', findings:[] },
    ] }
  return renderToString(React.createElement(PlainView, { report:r }))
})

if (failures) { console.log(`\n${failures} FAILURES`); process.exit(1) }
console.log('\nall smoke checks passed')
