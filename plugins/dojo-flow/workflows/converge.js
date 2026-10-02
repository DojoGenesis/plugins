export const meta = {
  name: 'converge',
  description: 'Audit by lens, then three opus verifiers try to refute each critical or high finding, then an optional fix and a gate that re-runs your checks. Audit-only by default; the scorecard counts returns.',
  whenToUse: 'Use when you want findings checked before anyone acts on them: sonnet lenses in parallel, adversarial verification, and a fix only when you pass fix as true.',
  phases: [
    { title: 'Audit', detail: 'sonnet per lens, read-only, in parallel' },
    { title: 'Verify', detail: 'three opus verifiers per critical or high finding; a majority of refutes kills it' },
    { title: 'Fix', detail: 'only when args.fix is true: sonnet on disjoint files' },
    { title: 'Gate', detail: 'sonnet re-runs your checks, opus re-runs them again and checks the tree; sonnet and haiku passes check the verdict' },
  ],
}

// args: { lenses: [{name, prompt}], gates?: [shell commands], fix?: true, fixTracks?: [{name, prompt, files}], repo?,
//         topPerLens?: 1-20, models?: {role: alias}, effort?: level | {role: level} }
// fix runs only when it is the boolean true and gates is not empty. Without it the run changes nothing.
const picked = {}

// ==== DOJO-FLOW SHARED BLOCK START (same text in build.js and converge.js; a test keeps the two copies identical) ====
const MODEL_ALIASES = ['haiku', 'sonnet', 'opus']
const EFFORT_LEVELS = ['low', 'medium', 'high', 'xhigh', 'max']

// Text that came from a subagent is clipped, and the capitalised verdict word is lowered, so a subagent can never
// make an unverified scorecard read as a verified one.
function clip(s, n) {
  return String(s === undefined || s === null ? '' : s).replace(/\bVERIFIED\b/g, 'verified').slice(0, n || 300)
}

// Closest allowed key to a misspelled one: same letters ignoring case, or at most two edits away. '' when nothing is close.
function nearestKey(key, allowed) {
  const a = String(key).toLowerCase()
  let best = ''
  let bestD = 3
  allowed.forEach(k => {
    const b = k.toLowerCase()
    let prev = []
    for (let j = 0; j <= b.length; j++) prev.push(j)
    for (let i = 1; i <= a.length; i++) {
      const cur = [i]
      for (let j = 1; j <= b.length; j++) cur.push(Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a.charAt(i - 1) === b.charAt(j - 1) ? 0 : 1)))
      prev = cur
    }
    if (prev[b.length] < bestD) { bestD = prev[b.length]; best = k }
  })
  return best
}

// allowed: the top-level keys this workflow takes. Any other key is refused here, before anything is dispatched, with
// the bad key named and the allowed ones listed (a typo such as "gate" for "gates" would otherwise run a whole paid run).
function parseArgs(raw, allowed) {
  let a = raw
  if (typeof a === 'string') {
    try { a = JSON.parse(a) } catch (e) { return { error: 'args arrived as a string that is not valid JSON (' + e.message + ')' } }
  }
  if (!a || typeof a !== 'object' || Array.isArray(a)) return { error: 'args must be a JSON object' }
  const unknown = Object.keys(a).filter(k => allowed.indexOf(k) < 0)
  if (unknown.length) {
    return { error: 'unknown args key' + (unknown.length > 1 ? 's' : '') + ': ' + unknown.map(k => {
      const near = nearestKey(k, allowed)
      return '"' + clip(k, 60) + '"' + (near ? ' (did you mean "' + near + '"?)' : '')
    }).join(', ') + '. Allowed keys: ' + allowed.join(', ') }
  }
  return { value: a }
}

// defaults: { role: [alias, effort] }. Unknown role keys and bad values are usage errors, never ignored.
function resolveRoles(rawModels, rawEffort, defaults) {
  const roles = Object.keys(defaults)
  const picked = {}
  const errors = []
  roles.forEach(r => { picked[r] = [defaults[r][0], defaults[r][1]] })
  if (rawModels !== undefined && rawModels !== null) {
    if (typeof rawModels !== 'object' || Array.isArray(rawModels)) {
      errors.push('models must be an object of role -> alias')
    } else {
      Object.keys(rawModels).forEach(k => {
        if (roles.indexOf(k) < 0) errors.push('unknown role "' + k + '" in models (roles: ' + roles.join(', ') + ')')
        else if (MODEL_ALIASES.indexOf(rawModels[k]) < 0) errors.push('models.' + k + ' must be one of ' + MODEL_ALIASES.join('|'))
        else picked[k][0] = rawModels[k]
      })
    }
  }
  if (rawEffort !== undefined && rawEffort !== null) {
    if (typeof rawEffort === 'string') {
      if (EFFORT_LEVELS.indexOf(rawEffort) < 0) errors.push('effort must be one of ' + EFFORT_LEVELS.join('|'))
      else roles.forEach(r => { picked[r][1] = rawEffort })
    } else if (typeof rawEffort === 'object' && !Array.isArray(rawEffort)) {
      Object.keys(rawEffort).forEach(k => {
        if (roles.indexOf(k) < 0) errors.push('unknown role "' + k + '" in effort (roles: ' + roles.join(', ') + ')')
        else if (EFFORT_LEVELS.indexOf(rawEffort[k]) < 0) errors.push('effort.' + k + ' must be one of ' + EFFORT_LEVELS.join('|'))
        else picked[k][1] = rawEffort[k]
      })
    } else {
      errors.push('effort must be a level or an object of role -> level')
    }
  }
  return errors.length ? { error: errors.join('; ') } : { picked: picked }
}

// ---- path normalisation and the ownership check ------------------------------------------------------------------
// Normalised form: no leading ./, doubled slashes collapsed, no trailing slash, lower-case (a false overlap on a
// case-insensitive disk is the safe direction). Globs, '..' segments and absolute paths outside the repo are refused.
function cleanRoot(repo) {
  if (typeof repo !== 'string' || !repo.trim()) return ''
  return repo.trim().replace(/\\/g, '/').replace(/\/{2,}/g, '/').replace(/\/+$/, '').toLowerCase()
}

function normEntry(raw, repo) {
  if (typeof raw !== 'string' || !raw.trim()) return { err: 'empty or non-string path' }
  const original = raw.trim()
  if (/[*?[\]]/.test(original)) return { err: 'glob characters are not allowed: ' + original }
  let s = original.replace(/\\/g, '/').replace(/\/{2,}/g, '/')
  if (s.charAt(0) === '/' || /^[A-Za-z]:\//.test(s)) {
    const root = cleanRoot(repo)
    const low = s.toLowerCase()
    if (!root || (low !== root && low.indexOf(root + '/') !== 0)) return { err: 'absolute path outside the repo: ' + original }
    s = s.slice(root.length)
  }
  const segs = s.split('/').filter(x => x !== '' && x !== '.')
  if (segs.indexOf('..') >= 0) return { err: 'a ".." segment is not allowed: ' + original }
  if (!segs.length) return { err: 'path names the repo root or nothing: ' + original }
  return { p: segs.join('/').toLowerCase() }
}

function overlaps(a, b) {
  return a === b || a.indexOf(b + '/') === 0 || b.indexOf(a + '/') === 0
}

// reservedPath: a repo-relative path reserved under the owner "contract", or null.
function checkOwnership(tracks, repo, reservedPath) {
  const errors = []
  const entries = []
  const seen = Object.create(null)
  if (!Array.isArray(tracks) || !tracks.length) return { ok: false, errors: ['tracks must be a non-empty array'], map: {}, entries: [] }
  tracks.forEach((t, i) => {
    const name = t && typeof t.name === 'string' ? t.name.trim() : ''
    if (!name) { errors.push('track #' + (i + 1) + ' has no name'); return }
    const key = name.toLowerCase()
    if (seen[key] === true) errors.push('duplicate track name: ' + name)
    seen[key] = true
    if (key === 'contract') errors.push('the track name "contract" is reserved')
    if (!Array.isArray(t.files) || !t.files.length) { errors.push('track ' + name + ' lists no files'); return }
    t.files.forEach(f => {
      const n = normEntry(f, repo)
      if (n.err) errors.push('track ' + name + ': ' + n.err)
      else entries.push({ owner: name, p: n.p, raw: String(f).trim() })
    })
  })
  if (reservedPath) {
    const rn = normEntry(reservedPath, repo)
    if (!rn.err) entries.push({ owner: 'contract', p: rn.p, raw: reservedPath })
  }
  for (let i = 0; i < entries.length; i++) {
    for (let j = i + 1; j < entries.length; j++) {
      const a = entries[i]
      const b = entries[j]
      if (a.owner !== b.owner && overlaps(a.p, b.p)) {
        errors.push('overlap: ' + a.raw + ' (' + a.owner + ') and ' + b.raw + ' (' + b.owner + ')')
      }
    }
  }
  const map = Object.create(null)
  entries.forEach(e => {
    if (!Object.prototype.hasOwnProperty.call(map, e.owner)) map[e.owner] = []
    if (map[e.owner].indexOf(e.p) < 0) map[e.owner].push(e.p)
  })
  return { ok: errors.length === 0, errors: errors, map: map, entries: entries }
}

// Files a subagent says it changed that are not inside the owner's entries (an entry covers itself and anything under it).
function outsideOf(reported, ownerPaths, repo) {
  return (Array.isArray(reported) ? reported : []).filter(f => {
    const n = normEntry(f, repo)
    if (n.err) return true
    return !ownerPaths.some(p => n.p === p || n.p.indexOf(p + '/') === 0)
  }).map(f => clip(f, 200))
}

// ---- gate evidence ------------------------------------------------------------------------------------------------
// wanted: the commands the person gave. reported: [{cmd, ran, exit, tail}] from a subagent. An empty list of wanted
// commands is a problem, never a pass ([].every is true; that trap is closed here).
function gateCheck(wanted, reported, who) {
  if (!Array.isArray(wanted) || !wanted.length) return ['no checks were given']
  if (!Array.isArray(reported)) return [who + ' returned no check results']
  const problems = []
  wanted.forEach(cmd => {
    const hits = reported.filter(g => g && g.cmd === cmd)
    if (hits.length === 0) problems.push(who + ' did not report the check: ' + clip(cmd, 120))
    else if (hits.length > 1) problems.push(who + ' reported the check more than once: ' + clip(cmd, 120))
    else if (hits[0].ran !== true) problems.push(who + ' did not run the check: ' + clip(cmd, 120))
    else if (hits[0].exit !== 0) problems.push('the check failed under ' + who + ' (exit ' + clip(hits[0].exit, 20) + '): ' + clip(cmd, 120))
  })
  return problems
}

// ---- the counting wrapper: every subagent in this script goes through spawn() -------------------------------------
// dispatched = calls made, returned = non-null answers, failed[] = everything else, with a reason. spawn() never
// throws: a spent turn budget throws inside the runtime, and a throw in a top-level await would end the script
// before any scorecard exists.
function makeRunner(picked) {
  const ledger = { dispatched: 0, returned: 0, failed: [] }
  let budgetNoted = false
  function fail(label, role, reason) {
    ledger.failed.push({ label: label, role: role, reason: reason })
  }
  async function spawn(label, role, prompt, phaseTitle, schema) {
    ledger.dispatched++
    const pick = picked[role]
    if (!pick || MODEL_ALIASES.indexOf(pick[0]) < 0 || EFFORT_LEVELS.indexOf(pick[1]) < 0) {
      fail(label, role, 'refused: the role has no valid model alias and effort')
      return null
    }
    if (typeof budget !== 'undefined' && budget && budget.total && budget.remaining() <= 0) {
      if (!budgetNoted) { budgetNoted = true; log('token budget is spent: later subagent calls are recorded as failed') }
      fail(label, role, 'token budget spent before the call')
      return null
    }
    let res
    try {
      res = await agent(prompt, { label: label, phase: phaseTitle, model: pick[0], effort: pick[1], schema: schema })
    } catch (e) {
      fail(label, role, 'threw: ' + clip((e && e.message) || e, 200))
      return null
    }
    if (res === null || res === undefined) {
      fail(label, role, 'returned null')
      return null
    }
    ledger.returned++
    return res
  }
  // An answer that came back but is unusable (wrong shape) counts as failed, not returned.
  function markBad(label, role, reason) {
    ledger.returned--
    fail(label, role, reason)
  }
  function snapshot() {
    const failed = ledger.failed.slice().sort((x, y) => (x.label < y.label ? -1 : x.label > y.label ? 1 : 0))
    return { dispatched: ledger.dispatched, returned: ledger.returned, failed: failed }
  }
  return { spawn: spawn, markBad: markBad, snapshot: snapshot }
}

// ---- judgment passes over an opus verdict: faithfulness (sonnet) and accuracy (haiku) ------------------------------
// ran and clean are computed here, in plain code, so a dead pass can never read as a clean one.
const FAITHFUL_SCHEMA = {
  type: 'object',
  properties: { faithful: { type: 'boolean' }, drift: { type: 'array', items: { type: 'string' } }, unsupported: { type: 'array', items: { type: 'string' } }, note: { type: 'string' } },
  required: ['faithful', 'drift', 'unsupported'],
}
const ACCURATE_SCHEMA = {
  type: 'object',
  properties: {
    accurate: { type: 'boolean' },
    errors: { type: 'array', items: { type: 'object', properties: { claim: { type: 'string' }, expected: { type: 'string' }, found: { type: 'string' } }, required: ['claim'] } },
    note: { type: 'string' },
  },
  required: ['accurate', 'errors'],
}

async function judgmentPasses(runner, node, inputsText, output, phaseTitle) {
  const out = JSON.stringify(output)
  const passes = await parallel([
    () => runner.spawn(
      'faithful:' + node, 'reviewer',
      'You check ALIGNMENT, not facts, in a judge verdict about the ' + node + ' step. INPUTS THE JUDGE WAS GIVEN:\n' + inputsText +
      '\n\nTHE VERDICT:\n' + out +
      '\n\nReturn faithful=false if the verdict asserts something those inputs do not support, drifts beyond the brief, presents outside knowledge as derived, or reaches a decision its own stated reasons do not support. List each problem in drift[] or unsupported[]. When unsure, return faithful=false.',
      phaseTitle, FAITHFUL_SCHEMA),
    () => runner.spawn(
      'accurate:' + node, 'checker',
      'You check ATOMIC FACTS only, against the real tree: read files and run git yourself. THE VERDICT:\n' + out +
      '\n\nFor every path, line reference, count, quoted value and check result the verdict cites, confirm it against ground truth. Return accurate=false with errors[{claim, expected, found}] for anything that does not hold. Do not judge reasoning.',
      phaseTitle, ACCURATE_SCHEMA),
  ])
  const f = passes[0]
  const a = passes[1]
  const ran = !!(f && a)
  const clean = ran && f.faithful === true && a.accurate === true
  return { node: node, faithfulness: f, accuracy: a, ran: ran, clean: clean }
}
// ==== DOJO-FLOW SHARED BLOCK END ====

const runner = makeRunner(picked)

const ROLE_DEFAULTS = {
  lens: ['sonnet', 'medium'],
  fixer: ['sonnet', 'medium'],
  integrator: ['sonnet', 'medium'],
  reviewer: ['sonnet', 'medium'],
  checker: ['haiku', 'medium'],
  judge: ['opus', 'xhigh'],
}
const USAGE = 'args {lenses: [{name, prompt}], gates?: [shell commands], fix?: true, fixTracks?: [{name, prompt, files}], repo?, topPerLens?: 1-20, models?: {role: alias}, effort?}'
const SEVERITIES = ['critical', 'high', 'medium', 'low']
const VERIFIERS = 3
const MAX_LENSES = 10

const STR_LIST = { type: 'array', items: { type: 'string' } }
const LENS_SCHEMA = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          claim: { type: 'string' },
          evidence: { type: 'string' },
          severity: { type: 'string', enum: ['critical', 'high', 'medium', 'low'] },
          fix: { type: 'string' },
          files: STR_LIST,
        },
        required: ['claim', 'evidence', 'severity'],
      },
    },
    summary: { type: 'string' },
  },
  required: ['findings', 'summary'],
}
const VERDICT_SCHEMA = {
  type: 'object',
  properties: { refuted: { type: 'boolean' }, note: { type: 'string' } },
  required: ['refuted'],
}
const FIX_SCHEMA = {
  type: 'object',
  properties: { complete: { type: 'boolean' }, filesChanged: STR_LIST, deviations: STR_LIST, summary: { type: 'string' } },
  required: ['complete', 'filesChanged', 'summary'],
}
const GATE_ITEM = {
  type: 'object',
  properties: { cmd: { type: 'string' }, ran: { type: 'boolean' }, exit: { type: 'integer' }, tail: { type: 'string' } },
  required: ['cmd', 'ran'],
}
const BASELINE_SCHEMA = {
  type: 'object',
  properties: { isGit: { type: 'boolean' }, dirtyFiles: STR_LIST },
  required: ['isGit', 'dirtyFiles'],
}
const RUN_SCHEMA = {
  type: 'object',
  properties: { gates: { type: 'array', items: GATE_ITEM }, summary: { type: 'string' } },
  required: ['gates', 'summary'],
}
const ACCEPT_SCHEMA = {
  type: 'object',
  properties: {
    proceed: { type: 'boolean' },
    blockers: STR_LIST,
    treeChecked: { type: 'boolean' },
    unownedChanges: STR_LIST,
    gates: { type: 'array', items: GATE_ITEM },
    notes: { type: 'string' },
  },
  required: ['proceed', 'blockers', 'treeChecked', 'unownedChanges', 'gates'],
}

// ---- prompt builders (each is called once in the probe below, before the first dispatch) --------------------------
function lensPrompt(lens) {
  return lens.prompt + '\n\nYou are a READ-ONLY auditor. Do not modify any file and do not run commands that change anything. ' +
    'Report findings with concrete evidence (paths, line references, sizes, command output). No speculation. ' +
    'Give each finding a severity of critical, high, medium or low, and list in files the repo-relative paths a fix would touch.'
}
function verifierPrompt(f, n) {
  return 'You are verifier ' + n + ' of ' + VERIFIERS + '. Try to REFUTE this audit finding by reading the actual files and running the commands yourself. ' +
    'Return refuted=true if the claim is false, overstated or unsupported, and refuted=false only if you reproduced it. When the evidence is weak, return refuted=true.\n' +
    'CLAIM: ' + f.claim + '\nEVIDENCE OFFERED: ' + f.evidence + '\nSEVERITY CLAIMED: ' + f.severity
}
function baselinePrompt() {
  return 'Run git status --porcelain from the repo root and change nothing. Return isGit (false if this is not a git repository or git is unavailable) and dirtyFiles: the repo-relative paths already modified or untracked right now.'
}
function fixPrompt(t, findings) {
  return 'You are fixing confirmed audit findings.\nFINDINGS (confirmed by majority vote):\n' +
    findings.map((f, i) => (i + 1) + '. [' + f.severity + '] ' + f.claim + '\n   evidence: ' + f.evidence + '\n   suggested fix: ' + (f.fix || '(none)')).join('\n') +
    '\n\nYOUR TRACK: ' + t.prompt +
    '\n\nOWNERSHIP: you own these files and paths and no others: ' + (t.files || []).join(', ') +
    '. Change only those; the gate compares the files that changed with this list, and a change outside it is reported as a defect. ' +
    'Other fixers are working in the same tree. Do not run git add, commit, push, stash, checkout or reset. Report filesChanged as paths relative to the repo root, and report any deviation plainly.'
}
function gateRunPrompt(fixReports, gates) {
  return 'You are the serial integrator after a fix pass. FIX REPORTS: ' + JSON.stringify(fixReports) +
    '\n\nRun each of these checks exactly as written, from the repo root, one at a time, and report one entry per check in gates: {cmd, ran, exit, tail}. ' +
    'cmd is the command string exactly as given. ran is true only if you actually executed it. exit is its real exit code. tail is the last 20 lines of its output. ' +
    'Never edit a check to make it pass and never substitute an easier one. Do not pipe a check through tail, head or grep, because that hides its exit code. Change no file.\nCHECKS:\n' +
    gates.map(g => '- ' + g).join('\n')
}
function acceptPrompt(fixReports, rawOwned, baseline, gates) {
  return 'You are the acceptance gate after a fix pass. Do not trust any report: look at the tree.\nOWNERSHIP MAP: ' + JSON.stringify(rawOwned) +
    '\nFILES ALREADY DIRTY BEFORE THE FIX PASS (baseline, not a defect): ' + JSON.stringify(baseline.dirtyFiles || []) +
    '\nFIX REPORTS: ' + JSON.stringify(fixReports) +
    '\n\n1. Run git status and git diff yourself. Return treeChecked=false if this is not a git repository or git is unavailable. List in unownedChanges every changed or new file that is not in the ownership map and not in the baseline.\n' +
    '2. Re-run each of these checks yourself, exactly as written, one at a time, and report one entry per check in gates: {cmd, ran, exit, tail}. cmd is the command string exactly as given; ran is true only if you executed it; do not pipe a check through tail, head or grep.\nCHECKS:\n' +
    gates.map(g => '- ' + g).join('\n') +
    '\n\nReport every discrepancy in blockers. proceed=true only if the tree matches the claims and every check passed.'
}

// ---- scorecard ---------------------------------------------------------------------------------------------------
function makeCard(verdict, headline, reasons, detail) {
  const snap = runner.snapshot()
  const d = detail || {}
  const lines = ['DOJO-FLOW CONVERGE SCORECARD', 'verdict: ' + verdict + (headline ? ' ' + headline : '')]
  lines.push('subagent calls: ' + snap.dispatched + ' dispatched, ' + snap.returned + ' returned, ' + snap.failed.length + ' failed')
  snap.failed.forEach(f => lines.push('  failed: ' + f.label + ' (' + f.role + '): ' + f.reason))
  ;(d.lines || []).forEach(l => lines.push(l))
  reasons.forEach(r => lines.push('  - ' + r))
  lines.push('Check results are reported by subagents: this script has no shell of its own, so re-run one check yourself before you say done.')
  return {
    verdict: verdict,
    reasons: reasons,
    dispatched: snap.dispatched,
    returned: snap.returned,
    failed: snap.failed,
    counts: d.counts || null,
    gates: d.gates || null,
    text: lines.join('\n'),
  }
}

function refuse(reason, extra) {
  log('dojo-flow converge refused: ' + reason)
  return Object.assign({ refused: true, reason: reason }, extra || {}, { droppedByCap: [], scorecard: makeCard('REFUSED', '', [reason]) })
}

// ---- finding helpers ---------------------------------------------------------------------------------------------
function normFinding(f, lensName, index) {
  const raw = f && typeof f.severity === 'string' ? f.severity.trim().toLowerCase() : ''
  const malformed = SEVERITIES.indexOf(raw) < 0
  return {
    lens: lensName,
    index: index,
    claim: clip(f && f.claim, 600),
    evidence: clip(f && f.evidence, 800),
    fix: clip(f && f.fix, 600),
    files: Array.isArray(f && f.files) ? f.files.filter(x => typeof x === 'string' && x.trim()).map(x => x.trim()) : [],
    severity: malformed ? 'high' : raw,
    severityMalformed: malformed,
    severityGiven: f ? clip(f.severity, 40) : '',
    status: 'not verified (below threshold)',
    votes: null,
  }
}

function tally(results) {
  const v = { refute: 0, confirm: 0, none: 0 }
  results.forEach(r => { if (r === true) v.refute++; else if (r === false) v.confirm++; else v.none++ })
  // Votes are counted against the verifiers dispatched, so missing votes can never decide a finding.
  const status = v.refute >= 2 ? 'refuted' : v.confirm >= 2 ? 'confirmed' : 'unresolved'
  return { votes: v, status: status }
}

// Disjoint fix tracks from file overlap: findings that touch overlapping paths land in one track (union-find).
function deriveFixTracks(findings, repo) {
  const parent = findings.map((_, i) => i)
  function find(i) { while (parent[i] !== i) { parent[i] = parent[parent[i]]; i = parent[i] } return i }
  const norm = findings.map(f => f.files.map(x => ({ raw: x, n: normEntry(x, repo) })))
  for (let i = 0; i < findings.length; i++) {
    for (let j = i + 1; j < findings.length; j++) {
      const hit = norm[i].some(a => !a.n.err && norm[j].some(b => !b.n.err && overlaps(a.n.p, b.n.p)))
      if (hit) parent[find(j)] = find(i)
    }
  }
  const groups = Object.create(null)
  const order = []
  findings.forEach((f, i) => {
    const r = find(i)
    if (!groups[r]) { groups[r] = { idx: [], files: [], seen: Object.create(null) }; order.push(r) }
    groups[r].idx.push(i)
    norm[i].forEach(x => { if (!groups[r].seen[x.n.p]) { groups[r].seen[x.n.p] = true; groups[r].files.push(x.raw) } })
  })
  return order.map((r, k) => ({
    name: 'fix-' + (k + 1),
    prompt: 'Fix the confirmed findings listed above that touch these files. Make the smallest change that resolves each finding.',
    files: groups[r].files,
    findings: groups[r].idx,
  }))
}

// ---- eager probe -------------------------------------------------------------------------------------------------
try {
  const probeFinding = { claim: 'c', evidence: 'e', severity: 'high', fix: 'f', files: ['probe.txt'] }
  const probeTrack = { name: 'probe', prompt: 'p', files: ['probe.txt'] }
  lensPrompt({ name: 'probe', prompt: 'p' })
  verifierPrompt(probeFinding, 1)
  baselinePrompt()
  fixPrompt(probeTrack, [probeFinding])
  gateRunPrompt([], ['check'])
  acceptPrompt([], {}, { dirtyFiles: [] }, ['check'])
  tally([true, false, null])
  deriveFixTracks([normFinding(probeFinding, 'probe', 0)], '')
} catch (e) {
  return refuse('internal error while preparing prompts: ' + clip(e && e.message, 200))
}

// ---- arguments ---------------------------------------------------------------------------------------------------
const ALLOWED_ARGS = ['lenses', 'gates', 'fix', 'fixTracks', 'repo', 'topPerLens', 'models', 'effort']
const parsed = parseArgs(args, ALLOWED_ARGS)
if (parsed.error) return refuse(parsed.error + '. Usage: ' + USAGE)
const A = parsed.value

if (!Array.isArray(A.lenses) || !A.lenses.length) return refuse('lenses is required: a non-empty list of {name, prompt}. Usage: ' + USAGE)
if (A.lenses.length > MAX_LENSES) return refuse(A.lenses.length + ' lenses is more than the limit of ' + MAX_LENSES)
const lensNames = Object.create(null)
for (let i = 0; i < A.lenses.length; i++) {
  const l = A.lenses[i]
  if (!l || typeof l.name !== 'string' || !l.name.trim() || typeof l.prompt !== 'string' || !l.prompt.trim()) return refuse('lens #' + (i + 1) + ' needs a name and a prompt')
  const key = l.name.trim().toLowerCase()
  if (lensNames[key] === true) return refuse('duplicate lens name: ' + l.name)
  lensNames[key] = true
}
const LENSES = A.lenses.map(l => ({ name: l.name.trim(), prompt: l.prompt }))

if (A.repo !== undefined && A.repo !== null && (typeof A.repo !== 'string' || !A.repo.trim())) return refuse('repo must be a non-empty string')
const REPO = typeof A.repo === 'string' ? A.repo.trim() : ''

const roleSettings = resolveRoles(A.models, A.effort, ROLE_DEFAULTS)
if (roleSettings.error) return refuse(roleSettings.error)
Object.assign(picked, roleSettings.picked)

let TOP = 5
if (A.topPerLens !== undefined && A.topPerLens !== null) {
  if (!Number.isInteger(A.topPerLens) || A.topPerLens < 1 || A.topPerLens > 20) return refuse('topPerLens must be an integer from 1 to 20')
  TOP = A.topPerLens
}

let GATES = []
if (A.gates !== undefined && A.gates !== null) {
  if (!Array.isArray(A.gates) || A.gates.some(g => typeof g !== 'string' || !g.trim())) return refuse('gates must be a list of non-empty command strings')
  GATES = A.gates.map(g => g.trim())
  if (new Set(GATES).size !== GATES.length) return refuse('gates lists the same command twice; each check must appear exactly once')
}

const FIX = A.fix === true
if (A.fix !== undefined && A.fix !== null && A.fix !== true && A.fix !== false) {
  log('fix was given as ' + typeof A.fix + ', not the boolean true, so no fix phase will run (audit only)')
}
let givenFixTracks = null
let givenOwnMap = null
if (!FIX && A.fixTracks !== undefined && A.fixTracks !== null) {
  log('fixTracks was given but fix is not true, so it is ignored (audit only)')
}
if (FIX) {
  if (!GATES.length) return refuse('fix needs gates: with no checks there is nothing to confirm a fix, so the fix phase is refused')
  if (A.fixTracks !== undefined && A.fixTracks !== null) {
    if (!Array.isArray(A.fixTracks) || A.fixTracks.some(t => !t || typeof t.prompt !== 'string' || !t.prompt.trim())) return refuse('fixTracks must be a list of {name, prompt, files}')
    const fo = checkOwnership(A.fixTracks, REPO, null)
    if (!fo.ok) return refuse('fixTracks ownership check failed: ' + fo.errors.join('; '), { ownershipErrors: fo.errors })
    givenFixTracks = A.fixTracks
    givenOwnMap = fo.map
  }
}

// ---- Audit and Verify (one pipeline: a lens verifies while the others still audit) --------------------------------
phase('Audit')
const droppedByCap = []
let malformedSeverity = 0
let malformedFinding = 0
const malformedByLens = []
const perLens = await pipeline(
  LENSES,
  async (_, lens) => {
    const report = await runner.spawn('audit:' + lens.name, 'lens', lensPrompt(lens), 'Audit', LENS_SCHEMA)
    return { lens: lens.name, report: report }
  },
  async (rec, lens) => {
    if (!rec.report) return { lens: lens.name, ok: false, summary: '', findings: [] }
    if (!Array.isArray(rec.report.findings)) {
      runner.markBad('audit:' + lens.name, 'lens', 'malformed report: findings is not a list')
      return { lens: lens.name, ok: false, summary: '', findings: [] }
    }
    // A finding that is not an object, or has no claim, is logged and counted, never sent to verifiers.
    const items = rec.report.findings.map((f, i) => ({ f: f, i: i + 1 })).filter(x => {
      const ok = x.f && typeof x.f === 'object' && !Array.isArray(x.f) && typeof x.f.claim === 'string' && x.f.claim.trim() !== ''
      if (!ok) {
        malformedFinding++
        log('lens ' + lens.name + ': finding ' + x.i + ' is not an object with a claim; it was skipped and no verifier was dispatched for it')
      }
      return ok
    }).map(x => normFinding(x.f, lens.name, x.i))
    const skipped = rec.report.findings.length - items.length
    if (skipped > 0 && items.length > 0) malformedByLens.push({ lens: lens.name, skipped: skipped })
    // A lens that reported findings and every one was unusable is a dead reviewer, not a clean one.
    if (rec.report.findings.length > 0 && items.length === 0) {
      runner.markBad('audit:' + lens.name, 'lens', 'malformed report: none of its ' + rec.report.findings.length + ' findings was an object with a claim')
      return { lens: lens.name, ok: false, summary: '', findings: [] }
    }
    items.forEach(f => {
      if (f.severityMalformed) {
        malformedSeverity++
        log('lens ' + lens.name + ': finding ' + f.index + ' has a severity outside critical|high|medium|low (' + f.severityGiven + '); it is treated as high so it is verified, not dropped')
      }
    })
    const rank = { critical: 0, high: 1 }
    const eligible = items.filter(f => f.severity === 'critical' || f.severity === 'high')
      .sort((a, b) => (rank[a.severity] - rank[b.severity]) || (a.index - b.index))
    const top = eligible.slice(0, TOP)
    const dropped = eligible.slice(TOP)
    dropped.forEach(f => {
      f.status = 'not verified (dropped by topPerLens cap)'
      droppedByCap.push({ lens: lens.name, index: f.index, claim: f.claim, severity: f.severity })
    })
    if (dropped.length) log('lens ' + lens.name + ': ' + eligible.length + ' critical or high findings and the cap is ' + TOP + '; not verified: ' + dropped.map(f => '#' + f.index + ' ' + clip(f.claim, 80)).join(' | '))
    await parallel(top.map(f => async () => {
      const results = await parallel(Array.from({ length: VERIFIERS }, (__, k) => async () => {
        const label = 'verify:' + lens.name + ':' + f.index + ':' + (k + 1)
        const v = await runner.spawn(label, 'judge', verifierPrompt(f, k + 1), 'Verify', VERDICT_SCHEMA)
        if (!v) return null
        if (typeof v.refuted !== 'boolean') { runner.markBad(label, 'judge', 'malformed verdict: refuted is not a boolean'); return null }
        return v.refuted
      }))
      const t = tally(results)
      f.votes = t.votes
      f.status = t.status
    }))
    return { lens: lens.name, ok: true, summary: clip(rec.report.summary, 400), findings: items }
  }
)

const lensResults = LENSES.map((l, i) => perLens[i] || { lens: l.name, ok: false, summary: '', findings: [] })
const allFindings = lensResults.flatMap(r => r.findings)
const count = s => allFindings.filter(f => f.status === s).length
const counts = {
  findings: allFindings.length,
  confirmed: count('confirmed'),
  refuted: count('refuted'),
  unresolved: count('unresolved'),
  belowThreshold: count('not verified (below threshold)'),
  droppedByCap: droppedByCap.length,
  malformedSeverity: malformedSeverity,
  malformedFinding: malformedFinding,
}
if (counts.refuted) log('refuted by majority vote and kept in the result with status refuted: ' + counts.refuted)
const deadLenses = lensResults.filter(r => !r.ok).map(r => r.lens)

function summaryLines() {
  const out = ['  findings: ' + counts.findings + ' (confirmed ' + counts.confirmed + ', refuted ' + counts.refuted + ', unresolved ' + counts.unresolved +
    ', below threshold and not verified ' + counts.belowThreshold + ', dropped by cap ' + counts.droppedByCap + ', malformed severity ' + counts.malformedSeverity + ', malformed finding skipped ' + counts.malformedFinding + ')']
  if (deadLenses.length) out.push('  lenses with no usable report: ' + deadLenses.join(', '))
  return out
}

const base = { mode: FIX ? 'audit-fix' : 'audit-only', lenses: lensResults, findings: allFindings, droppedByCap: droppedByCap }

// ---- audit-only ends here ----------------------------------------------------------------------------------------
const confirmed = allFindings.filter(f => f.status === 'confirmed')
const fixable = []
const notAutoFixable = []
// With given fix tracks, a finding is fixable only if every one of its files sits inside some track's entries
// (an entry covers itself and anything under it). A finding no track owns is never handed to a fixer.
function ownedBySomeTrack(file) {
  const n = normEntry(file, REPO)
  if (n.err) return false
  return Object.keys(givenOwnMap).some(name => givenOwnMap[name].some(p => n.p === p || n.p.indexOf(p + '/') === 0))
}
confirmed.forEach(f => {
  const ok = f.files.length > 0 && f.files.every(x => !normEntry(x, REPO).err) && (!givenOwnMap || f.files.every(ownedBySomeTrack))
  if (ok) fixable.push(f)
  else notAutoFixable.push(f)
})

// One reason per lens that sent findings the script had to skip, so a half-usable report never reads as a clean one.
function malformedReasons() {
  return malformedByLens.map(m => 'lens ' + m.lens + ' sent ' + m.skipped + ' finding(s) that were not an object with a claim; they were skipped')
}

function finishReview(extraReasons, note) {
  const snap = runner.snapshot()
  const reasons = extraReasons.slice()
  if (snap.failed.length) reasons.push(snap.failed.length + ' subagent call(s) did not return a usable answer: ' + snap.failed.map(f => f.label).join(', '))
  if (snap.returned !== snap.dispatched) reasons.push('returned (' + snap.returned + ') is not equal to dispatched (' + snap.dispatched + ')')
  malformedReasons().forEach(r => reasons.push(r))
  const verdict = reasons.length ? 'UNVERIFIED' : 'REVIEWED'
  const headline = '(' + note + ')'
  const extra = FIX ? { notAutoFixable: notAutoFixable.map(f => ({ lens: f.lens, claim: f.claim })) } : {}
  return Object.assign({}, base, extra, { counts: counts, scorecard: makeCard(verdict, headline, reasons, { lines: summaryLines(), counts: counts }) })
}

if (!FIX) {
  log('audit only: nothing was changed. Pass fix as the boolean true, with gates, to fix confirmed findings.')
  return finishReview([], 'audit only, nothing changed')
}
if (!fixable.length) {
  const why = notAutoFixable.length ? [notAutoFixable.length + ' confirmed finding(s) were not fixed because they list no usable files or touch files no fix track owns'] : []
  return finishReview(why, 'no finding could be fixed automatically, nothing changed')
}

// ---- Fix ---------------------------------------------------------------------------------------------------------
phase('Fix')
const baselineRes = await runner.spawn('baseline', 'checker', baselinePrompt(), 'Fix', BASELINE_SCHEMA)
const BASELINE = baselineRes ? { isGit: baselineRes.isGit === true, dirtyFiles: Array.isArray(baselineRes.dirtyFiles) ? baselineRes.dirtyFiles : [] } : { isGit: false, dirtyFiles: [] }

let fixTracks
if (givenFixTracks) {
  // Each given track gets only the findings with a file inside its own entries; a track with none is not dispatched.
  const inTrack = (t, x) => { const n = normEntry(x, REPO); return !n.err && (givenOwnMap[t.name.trim()] || []).some(p => n.p === p || n.p.indexOf(p + '/') === 0) }
  fixTracks = []
  givenFixTracks.forEach(t => {
    const mine = []
    fixable.forEach((f, i) => { if (f.files.some(x => inTrack(t, x))) mine.push(i) })
    if (mine.length) fixTracks.push({ name: t.name.trim(), prompt: t.prompt, files: t.files, findings: mine })
    else log('fix track ' + t.name.trim() + ' owns no file of any fixable finding, so it is not dispatched')
  })
} else fixTracks = deriveFixTracks(fixable, REPO)
if (notAutoFixable.length) log('not auto-fixable (no usable file list, or no fix track owns a file): ' + notAutoFixable.map(f => clip(f.claim, 80)).join(' | '))

const ownFix = fixTracks.length ? checkOwnership(fixTracks, REPO, null) : { ok: true, errors: [], map: {} }
if (!ownFix.ok) {
  return Object.assign({}, base, { counts: counts, fixTracks: fixTracks, scorecard: makeCard('REFUSED', '', ['the fix tracks overlap: ' + ownFix.errors.join('; ')], { lines: summaryLines(), counts: counts }) })
}
const rawOwned = Object.create(null)
fixTracks.forEach(t => { rawOwned[t.name] = t.files })

const fixes = fixTracks.length
  ? await parallel(fixTracks.map(t => () => runner.spawn('fix:' + t.name, 'fixer', fixPrompt(t, t.findings.map(i => fixable[i])), 'Fix', FIX_SCHEMA)))
  : []
const fixReports = fixes.map((r, i) => r ? { track: fixTracks[i].name, complete: r.complete, filesChanged: r.filesChanged, summary: clip(r.summary, 400) } : { track: fixTracks[i].name, complete: false, filesChanged: [], summary: 'no report' })

// ---- Gate --------------------------------------------------------------------------------------------------------
phase('Gate')
const gateRun = fixTracks.length ? await runner.spawn('gate:run', 'integrator', gateRunPrompt(fixReports, GATES), 'Gate', RUN_SCHEMA) : null
const accept = fixTracks.length ? await runner.spawn('gate:accept', 'judge', acceptPrompt(fixReports, rawOwned, BASELINE, GATES), 'Gate', ACCEPT_SCHEMA) : null
let judgment = null
if (accept) {
  judgment = await judgmentPasses(runner, 'accept',
    'OWNERSHIP MAP: ' + JSON.stringify(rawOwned) + '\nFIX REPORTS: ' + JSON.stringify(fixReports), accept, 'Gate')
}

const reasons = []
fixTracks.forEach((t, i) => {
  const r = fixes[i]
  if (!r) { reasons.push('fix track ' + t.name + ' returned nothing'); return }
  if (r.complete !== true) reasons.push('fix track ' + t.name + ' reported complete=false')
  const outside = outsideOf(r.filesChanged, ownFix.map[t.name] || [], REPO)
  if (outside.length) reasons.push('fix track ' + t.name + ' reported changing files it does not own: ' + outside.join(', '))
})
if (!fixTracks.length) reasons.push('no fix track could be built from the confirmed findings')
if (notAutoFixable.length) reasons.push(notAutoFixable.length + ' confirmed finding(s) were not fixed because they list no usable files or touch files no fix track owns')
const stillOpen = allFindings.filter(f => f.status === 'unresolved').length
if (stillOpen) reasons.push(stillOpen + ' finding(s) are unresolved: the verifiers did not reach a majority')
if (!BASELINE.isGit) reasons.push('the baseline shows no git repository (or the baseline call failed), so the tree check could not compare')
const snapNow = runner.snapshot()
if (snapNow.failed.length) reasons.push(snapNow.failed.length + ' subagent call(s) did not return a usable answer: ' + snapNow.failed.map(f => f.label).join(', '))
if (snapNow.returned !== snapNow.dispatched) reasons.push('returned (' + snapNow.returned + ') is not equal to dispatched (' + snapNow.dispatched + ')')
malformedReasons().forEach(r => reasons.push(r))
if (!gateRun) reasons.push('the gate run returned nothing')
else gateCheck(GATES, gateRun.gates, 'the gate run').forEach(p => reasons.push(p))
if (!accept) reasons.push('the acceptance gate returned nothing')
else {
  gateCheck(GATES, accept.gates, 'the acceptance gate').forEach(p => reasons.push(p))
  if (accept.proceed !== true) reasons.push('the acceptance gate did not approve (proceed is not true)')
  if (Array.isArray(accept.blockers) && accept.blockers.length) reasons.push('the acceptance gate listed ' + accept.blockers.length + ' blocker(s): ' + accept.blockers.map(b => clip(b, 160)).join('; '))
  if (accept.treeChecked !== true) reasons.push('the tree check did not run (not a git repository, or git was unavailable)')
  if (Array.isArray(accept.unownedChanges) && accept.unownedChanges.length) reasons.push('files changed outside the fix ownership map: ' + accept.unownedChanges.map(f => clip(f, 160)).join(', '))
}
if (judgment) {
  if (!judgment.ran) reasons.push('the faithfulness and accuracy passes over the acceptance verdict did not both run')
  else if (!judgment.clean) reasons.push('the faithfulness or accuracy pass found a problem with the acceptance verdict')
}

const verdict = reasons.length ? 'UNVERIFIED' : 'VERIFIED'
const card = makeCard(verdict, '', reasons, {
  lines: summaryLines().concat(fixTracks.map((t, i) => '  fix track ' + t.name + ': returned ' + (fixes[i] ? 'yes' : 'NO') + ', complete ' + (fixes[i] && fixes[i].complete === true ? 'yes' : 'NO'))),
  counts: counts,
  gates: { given: GATES, run: gateRun ? gateRun.gates : null, accept: accept ? accept.gates : null },
})
log(card.text)

return Object.assign({}, base, {
  counts: counts,
  fixTracks: fixTracks,
  notAutoFixable: notAutoFixable.map(f => ({ lens: f.lens, claim: f.claim })),
  fixes: fixReports,
  baseline: BASELINE,
  gateRun: gateRun,
  accept: accept,
  judgment: judgment,
  scorecard: card,
})
