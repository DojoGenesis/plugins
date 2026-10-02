// Stub harness for the dojo-flow workflow scripts. Run by the unittest files; not shipped as a user tool.
//
//   node harness.js run   <workflow.js> <scenario.json>   run the whole script against stub primitives
//   node harness.js block <workflow.js> <cases.json>      run checkOwnership from the marked shared block
//
// The stubs follow the documented semantics: a parallel() thunk that throws becomes null; a pipeline() stage gets
// (previous result, item, index) and a throw drops the item to null and skips its later stages; the subagent stub
// returns scripted answers keyed by label and asserts on EVERY call that model and effort are valid.
'use strict'
const fs = require('fs')

const MODELS = ['haiku', 'sonnet', 'opus']
const EFFORTS = ['low', 'medium', 'high', 'xhigh', 'max']
const START = '==== DOJO-FLOW SHARED BLOCK START'
const END = '==== DOJO-FLOW SHARED BLOCK END'

function stripExport(src) {
  return src.replace(/^export const meta = /m, 'const meta = ')
}

function sharedBlock(src) {
  const a = src.indexOf(START)
  const b = src.indexOf(END)
  if (a < 0 || b < 0) throw new Error('shared block markers not found')
  return src.slice(src.indexOf('\n', a) + 1, b)
}

async function runBlock(file, casesFile) {
  const src = fs.readFileSync(file, 'utf8')
  const cases = JSON.parse(fs.readFileSync(casesFile, 'utf8'))
  const api = new Function(sharedBlock(src) + '\nreturn { checkOwnership, normEntry }')()
  const out = cases.map(c => {
    const r = api.checkOwnership(c.tracks, c.repo || '', c.reserved || null)
    return { name: c.name, ok: r.ok, errors: r.errors }
  })
  process.stdout.write(JSON.stringify(out))
}

async function runScript(file, scenarioFile) {
  const scenario = JSON.parse(fs.readFileSync(scenarioFile, 'utf8'))
  const src = stripExport(fs.readFileSync(file, 'utf8'))
  const calls = []
  const logs = []
  const phases = []
  const violations = []
  const rules = (scenario.responses || []).map(r => ({ re: new RegExp(r.match), respond: r.respond, left: r.times === undefined ? Infinity : r.times }))

  function agent(prompt, opts) {
    const o = opts || {}
    const label = o.label || ''
    if (typeof prompt !== 'string' || !prompt) violations.push(label + ': prompt is not a non-empty string')
    if (MODELS.indexOf(o.model) < 0) violations.push(label + ': bad or missing model ' + String(o.model))
    if (EFFORTS.indexOf(o.effort) < 0) violations.push(label + ': bad or missing effort ' + String(o.effort))
    if (!o.schema || o.schema.type !== 'object' || typeof o.schema.properties !== 'object') violations.push(label + ': schema is not an object schema')
    else {
      const req = o.schema.required || []
      req.forEach(k => { if (!(k in o.schema.properties)) violations.push(label + ': required key not in properties: ' + k) })
      if ('model' in o.schema.properties) violations.push(label + ': schema has a property named model')
    }
    calls.push({ label: label, model: o.model, effort: o.effort, phase: o.phase, prompt: prompt })
    for (const r of rules) {
      if (r.left > 0 && r.re.test(label)) {
        r.left--
        const x = r.respond
        if (x && x.__throw !== undefined) return Promise.reject(new Error(x.__throw))
        if (x && x.__null === true) return Promise.resolve(null)
        return Promise.resolve(JSON.parse(JSON.stringify(x)))
      }
    }
    violations.push(label + ': no scripted response for this label')
    return Promise.resolve(null)
  }
  function parallel(thunks) {
    return Promise.all(thunks.map(t => Promise.resolve().then(t).catch(() => null)))
  }
  function pipeline(items) {
    const stages = Array.prototype.slice.call(arguments, 1)
    return Promise.all(items.map(async (item, i) => {
      let prev = item
      for (const st of stages) {
        try { prev = await st(prev, item, i) } catch (e) { return null }
      }
      return prev
    }))
  }
  function phase(t) { phases.push(t) }
  function log(m) { logs.push(String(m)) }
  const budget = { total: null, spent() { return 0 }, remaining() { return Infinity } }

  let fn
  try {
    fn = new Function('return async function(agent, parallel, pipeline, phase, log, args, budget) {\n' + src + '\n}')()
  } catch (e) {
    process.stdout.write(JSON.stringify({ harnessError: 'syntax: ' + e.message }))
    return
  }

  // Date.now, Math.random and an argless new Date() throw while the script runs.
  const RealDate = Date
  const realRandom = Math.random
  class GuardedDate extends RealDate {
    constructor(...a) {
      if (a.length === 0) throw new Error('argless new Date() used')
      super(...a)
    }
    static now() { throw new Error('Date.now() used') }
  }
  globalThis.Date = GuardedDate
  Math.random = () => { throw new Error('Math.random() used') }
  let result = null
  let error = null
  try {
    const argsIn = scenario.argsRaw !== undefined ? scenario.argsRaw : scenario.args
    result = await fn(agent, parallel, pipeline, phase, log, argsIn, budget)
  } catch (e) {
    error = String((e && e.message) || e)
  }
  globalThis.Date = RealDate
  Math.random = realRandom
  process.stdout.write(JSON.stringify({ result: result === undefined ? null : result, error: error, calls: calls, logs: logs, phases: phases, violations: violations }))
}

const [mode, file, extra] = process.argv.slice(2)
const job = mode === 'block' ? runBlock(file, extra) : runScript(file, extra)
job.catch(e => { process.stderr.write(String((e && e.stack) || e) + '\n'); process.exit(3) })
