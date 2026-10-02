export const meta = {
  name: 'build',
  description: 'Parallel build with a contract gate: opus writes the contract, haiku scouts, opus advises, sonnet builds and integrates, opus audits, and the scorecard counts returns.',
  whenToUse: 'Use when a goal splits into two or more tracks that own different files and you want a contract first, small models looking, builders in the middle and judges at the ends.',
  phases: [
    { title: 'Contract', detail: 'opus: contract file, ownership map, independence check' },
    { title: 'Scout', detail: 'haiku per track, read-only: plan and questions' },
    { title: 'Advise', detail: 'opus per question, dispatched by the script, ledger recorded by the script' },
    { title: 'Build', detail: 'sonnet per track, owns only its files; one consult and one resume if stuck' },
    { title: 'Integrate', detail: 'sonnet, serial: runs the checks and reports each result' },
    { title: 'Audit', detail: 'opus re-runs the checks and compares the tree to the ownership map; sonnet and haiku passes check the verdict' },
  ],
}

// args: { goal, tracks?: [{name, prompt, files}], gates?: [shell commands], repo?, models?: {role: alias},
//         effort?: level | {role: level}, adviceCap?: 0-6, maxTracks?: 1-16, contractPath?, contractDraft? }
// Without tracks the run stops after the Contract phase and returns a plan for the person to confirm.
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
  scout: ['haiku', 'low'],
  builder: ['sonnet', 'medium'],
  integrator: ['sonnet', 'medium'],
  reviewer: ['sonnet', 'medium'],
  checker: ['haiku', 'medium'],
  judge: ['opus', 'xhigh'],
}
const USAGE = 'args {goal, tracks?: [{name, prompt, files}], gates?: [shell commands], repo?, models?: {role: alias}, effort?, adviceCap?: 0-6, maxTracks?: 1-16, contractPath?, contractDraft?}'
const DEFAULT_CONTRACT_PATH = '.dojo/dag-contract.md'

const STR_LIST = { type: 'array', items: { type: 'string' } }
const CONTRACT_SCHEMA = {
  type: 'object',
  properties: {
    proceed: { type: 'boolean' },
    blockers: STR_LIST,
    contractText: { type: 'string' },
    contractWritten: { type: 'boolean' },
    baseline: {
      type: 'object',
      properties: { isGit: { type: 'boolean' }, dirtyFiles: STR_LIST, note: { type: 'string' } },
      required: ['isGit', 'dirtyFiles'],
    },
    tracks: {
      type: 'array',
      items: {
        type: 'object',
        properties: { name: { type: 'string' }, prompt: { type: 'string' }, files: STR_LIST },
        required: ['name', 'prompt', 'files'],
      },
    },
    trackGuidance: { type: 'object', additionalProperties: { type: 'string' } },
    trackIndependence: {
      type: 'array',
      items: {
        type: 'object',
        properties: { pair: STR_LIST, coupled: { type: 'boolean' }, sharedContract: { type: 'string' } },
        required: ['pair', 'coupled'],
      },
    },
    notes: { type: 'string' },
  },
  required: ['proceed', 'blockers', 'contractText', 'contractWritten', 'baseline', 'trackIndependence'],
}
const SCOUT_SCHEMA = {
  type: 'object',
  properties: {
    plan: { type: 'string' },
    filesRead: STR_LIST,
    questions: { type: 'array', items: { type: 'object', properties: { briefing: { type: 'string' } }, required: ['briefing'] } },
  },
  required: ['plan', 'questions'],
}
const ADVICE_SCHEMA = { type: 'object', properties: { advice: { type: 'string' } }, required: ['advice'] }
const BUILD_SCHEMA = {
  type: 'object',
  properties: {
    complete: { type: 'boolean' },
    filesChanged: STR_LIST,
    deviations: STR_LIST,
    adviceFollowed: {
      type: 'array',
      items: { type: 'object', properties: { consult: { type: 'integer' }, followed: { type: 'boolean' }, why: { type: 'string' } }, required: ['consult', 'followed'] },
    },
    stuckQuestion: { type: 'string' },
    summary: { type: 'string' },
  },
  required: ['complete', 'filesChanged', 'summary', 'adviceFollowed'],
}
const GATE_ITEM = {
  type: 'object',
  properties: { cmd: { type: 'string' }, ran: { type: 'boolean' }, exit: { type: 'integer' }, tail: { type: 'string' } },
  required: ['cmd', 'ran'],
}
const INTEGRATE_SCHEMA = {
  type: 'object',
  properties: {
    complete: { type: 'boolean' },
    filesChanged: STR_LIST,
    gates: { type: 'array', items: GATE_ITEM },
    summary: { type: 'string' },
  },
  required: ['complete', 'filesChanged', 'gates', 'summary'],
}
const AUDIT_SCHEMA = {
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

const BRIEFING_SHAPE =
  'GOAL (one line) / OWNED FILES / EVIDENCE SO FAR (what you read, ran or saw, with short excerpts) / ' +
  'CURRENT PLAN OR BLOCKER / SPECIFIC QUESTION. The advisor sees nothing else, so the briefing is its whole context.'
const WEIGHT_RULE =
  'Give the advice serious weight. If you follow a step and it fails when you try it, or you hold direct evidence ' +
  'against a specific claim (the file says otherwise), adapt, and say so in adviceFollowed with the evidence. Never switch silently.'

// ---- prompt builders. Every one is called once before the first dispatch (see the probe below) so a typo throws
// at second zero and not two hours in. ----------------------------------------------------------------------------
function repoWords(repo) { return repo ? repo : 'the current working directory' }

function contractPrompt(goal, repo, tracks, contractPath, maxTracks, draft) {
  const head = [
    'You are the contract gate for a parallel build. Read the real repository before you judge; do not trust the plan text.',
    'GOAL: ' + goal,
    'REPO: ' + repoWords(repo),
  ]
  if (!tracks) {
    return head.concat([
      'No tracks were given. Propose them. Write NOTHING to disk: no files, no git commands that change anything.',
      '1. Read enough of the repo to cut the goal into between 2 and ' + maxTracks + ' tracks that can run side by side.',
      '2. For each track return {name, prompt, files}: a short unique name, a prompt a builder can follow alone, and the explicit files or directories only that track will write (no globs, repo-relative). Tracks must not share any file or any decision one settles and another reads: this workflow runs every track at the same time, so if two tracks depend on each other, merge them.',
      '3. Put the shared decisions every track must assume (names, shapes, interfaces, file names) in contractText, as the draft contract.',
      '4. Return baseline from git status --porcelain (isGit false if this is not a git repository), trackIndependence [] and contractWritten=false. Set proceed=false with blockers if the goal cannot be split this way.',
      draft ? 'DRAFT FROM THE PERSON (start from it and correct it against the repo):\n' + draft : '',
    ]).filter(Boolean).join('\n')
  }
  return head.concat([
    'TRACKS (name and owned files): ' + JSON.stringify(tracks.map(t => ({ name: t.name, files: t.files }))),
    'CONTRACT FILE PATH: ' + contractPath,
    'Do these in order:',
    '1. Baseline. Run git status --porcelain from the repo root. Return baseline.isGit (false if this is not a git repository) and baseline.dirtyFiles (repo-relative paths already modified or untracked before any track starts).',
    '2. Independence. For EVERY unordered pair of tracks decide whether the two are independent: neither consumes the other\'s output, and they share no decision that one settles and the other reads (a function name, a JSON shape, a config key, a file name, an agreed value). Disjoint files alone is not independence. Return one trackIndependence entry per pair: {pair: [nameA, nameB], coupled, sharedContract}. If any pair is coupled, set proceed=false and name the pair and the shared decision in blockers.',
    '3. Contract file. If a file already exists at the contract path, leave it alone and set proceed=false with a blocker. Otherwise write the contract file there: the shared decisions every track may rely on (names, shapes, interfaces, file names), the ownership table, and the checks that must pass. Put the same text in contractText and set contractWritten=true. Write no other file.',
    '4. trackGuidance: for each track, two to four sentences keyed by track name: what to read first, sharp edges, traps.',
    'Also check that owned files exist or can be created and that each track prompt matches the code. Set proceed=false with blockers when something is unsafe. Return tracks as [].',
    draft ? 'DRAFT FROM THE PERSON (use it as the starting point and correct it against the repo):\n' + draft : '',
  ]).filter(Boolean).join('\n')
}

function ownershipRule(t) {
  return '\n\nOWNERSHIP: you own these files and paths and no others: ' + (t.files || []).join(', ') +
    '. Change only those. After the build, the audit compares the files that changed with this list, and a change outside it is reported as a defect. ' +
    'The working tree is shared with the other tracks. Do not run git add, commit, push, stash, checkout or reset. Report any deviation plainly, and report filesChanged as paths relative to the repo root.'
}
function guidanceBlock(guidance, t) {
  return '\n\nGUIDANCE for your track from the contract gate: ' + ((guidance && typeof guidance === 'object' && Object.prototype.hasOwnProperty.call(guidance, t.name) && guidance[t.name]) || '(none)')
}
function contractBlock(contractText) {
  return '\n\nCONTRACT (shared decisions, frozen; assume exactly these):\n' + contractText
}

function scoutPrompt(goal, t, contractText, guidance, cap) {
  return 'You are the scout for track "' + t.name + '" of a parallel build.\nGOAL: ' + goal + contractBlock(contractText) +
    '\n\nYOUR TRACK:\n' + t.prompt + guidanceBlock(guidance, t) + ownershipRule(t) +
    '\n\nTHIS IS THE SCOUT STEP. Write nothing: no edits, no new files, no git commands that change anything. Read what you need, form a plan, and return the plan and the files you read. ' +
    'Then decide whether a stronger model would change your approach: return up to ' + cap + ' questions (none is fine on a simple track). Each question is a self-contained briefing in this shape: ' + BRIEFING_SHAPE
}

function advisePrompt(briefing) {
  return 'You advise a builder on one track of a parallel build. You cannot see their work beyond this briefing. ' +
    'Answer the SPECIFIC QUESTION with a focused decision in under 150 words, not a full plan. ' +
    'If the briefing lacks evidence you would want, say which evidence, and still give your best call.\n\nBRIEFING:\n' + briefing
}

function adviceBlock(entries) {
  if (!entries.length) return '\n\nNo advice was requested for this track. Return adviceFollowed: [].'
  return '\n\nADVICE (opus, dispatched by the script on your questions):\n' +
    entries.map(e => '#' + e.consult + ' Q: ' + e.question + '\n   A: ' + (e.failed ? '(THE ADVISOR CALL FAILED: no advice; go on your own evidence and say so)' : e.advice)).join('\n') +
    '\n\n' + WEIGHT_RULE + ' In adviceFollowed, return one entry per consult number above: {consult, followed, why}.'
}

function buildPrompt(goal, t, contractText, guidance, scout, entries) {
  return 'You are the builder for track "' + t.name + '" of a parallel build.\nGOAL: ' + goal + contractBlock(contractText) +
    '\n\nYOUR TRACK:\n' + t.prompt + guidanceBlock(guidance, t) +
    '\n\nYOUR OWN SCOUT PLAN (from the read-only step before this one):\n' + scout.plan +
    adviceBlock(entries) + ownershipRule(t) +
    '\n\nIf you get stuck on something an advisor could unblock, stop, leave your partial work on disk, and return complete=false with stuckQuestion as a self-contained briefing (' + BRIEFING_SHAPE + ').'
}

function resumePrompt(goal, t, contractText, guidance, first, entries) {
  return 'You are resuming track "' + t.name + '" of a parallel build.\nGOAL: ' + goal + contractBlock(contractText) +
    '\n\nYOUR TRACK:\n' + t.prompt + guidanceBlock(guidance, t) +
    '\n\nA previous builder on this track stopped with: ' + clip(first.summary, 600) +
    '\nFiles it changed so far: ' + JSON.stringify(first.filesChanged || []) + '. Read them; do not redo finished work.' +
    adviceBlock(entries) + ownershipRule(t)
}

function integratePrompt(goal, builds, gates) {
  return 'You are the serial integrator for a parallel build.\nGOAL: ' + goal + '\nTRACK REPORTS: ' + JSON.stringify(builds) +
    '\n\nRun each of these checks exactly as written, from the repo root, one at a time, and report one entry per check in gates: {cmd, ran, exit, tail}. ' +
    'cmd is the command string exactly as given. ran is true only if you actually executed it. exit is its real exit code. tail is the last 20 lines of its output. ' +
    'Never edit a check to make it pass and never substitute an easier one. Do not pipe a check through tail, head or grep, because that hides its exit code.\nCHECKS:\n' +
    gates.map(g => '- ' + g).join('\n') +
    '\n\nIf a check fails because of a seam between tracks, you may make the smallest fix, list every file you touched in filesChanged, and say why in summary. Otherwise change nothing. Do not run git add, commit, push, stash, checkout or reset. complete=true only if every check ran and passed.'
}

function auditPrompt(goal, own, rawOwned, contractPath, baseline, integ, builds, ledgerEntries, cert, gates) {
  return 'You are the integration audit for a parallel build. Do not trust any report: look at the tree.\nGOAL: ' + goal +
    '\nOWNERSHIP MAP (computed by the script from the tracks given): ' + JSON.stringify(rawOwned) +
    '\nCONTRACT FILE (owner "contract"): ' + (contractPath || '(none)') +
    '\nFILES ALREADY DIRTY BEFORE THE BUILD (baseline, not a defect): ' + JSON.stringify(baseline.dirtyFiles || []) +
    '\nFILES THE INTEGRATOR SAYS IT TOUCHED (allowed, but check them): ' + JSON.stringify((integ && integ.filesChanged) || []) +
    '\nBUILDER REPORTS: ' + JSON.stringify(builds) +
    '\nADVICE LEDGER (recorded by the script, not self-reported): ' + JSON.stringify(ledgerEntries) +
    '\nINDEPENDENCE CERTIFIED BEFORE THE BUILD: ' + JSON.stringify(cert || []) +
    '\n\nDo these:\n1. Run git status and git diff yourself. Return treeChecked=false if this is not a git repository or git is unavailable. List in unownedChanges every changed or new file that is not in the ownership map, not the contract file, not in the baseline and not integrator-reported.\n' +
    '2. Re-run each of these checks yourself, exactly as written, one at a time, and report one entry per check in gates: {cmd, ran, exit, tail}. cmd is the command string exactly as given; ran is true only if you executed it; do not pipe a check through tail, head or grep.\nCHECKS:\n' +
    gates.map(g => '- ' + g).join('\n') +
    '\n3. Review the advice ledger: flag any consult a builder overrode without evidence, and any failed consult whose track went on as if it had advice.\n' +
    '4. From the real diffs, confirm no track depended on another track\'s output or on a shared decision the certification called independent (a renamed symbol, a settled JSON shape, a config key, an agreed value). Flag any coupling as a blocker.\n' +
    'Report every discrepancy in blockers. proceed=true only if the tree matches the claims and every check passed.'
}

function independenceProblems(names, cert) {
  const list = Array.isArray(cert) ? cert : []
  const problems = []
  for (let i = 0; i < names.length; i++) {
    for (let j = i + 1; j < names.length; j++) {
      const a = names[i]
      const b = names[j]
      const hits = list.filter(e => e && Array.isArray(e.pair) && e.pair.length === 2 &&
        ((e.pair[0] === a && e.pair[1] === b) || (e.pair[0] === b && e.pair[1] === a)))
      if (!hits.length) problems.push('independence was not certified for ' + a + ' / ' + b)
      else if (hits.some(e => e.coupled !== false)) {
        const shared = hits.map(e => e.sharedContract).filter(Boolean)[0]
        problems.push(a + ' and ' + b + ' are coupled (' + clip(shared || 'no shared decision named', 200) + '): merge them or run one before the other')
      }
    }
  }
  return problems
}

// ---- the scorecard ----------------------------------------------------------------------------------------------
// A run is called VERIFIED only when reasons is empty. Every reason is a way the run could be wrong.
function makeCard(verdict, reasons, detail) {
  const snap = runner.snapshot()
  const d = detail || {}
  const lines = ['DOJO-FLOW BUILD SCORECARD', 'verdict: ' + verdict]
  lines.push('subagent calls: ' + snap.dispatched + ' dispatched, ' + snap.returned + ' returned, ' + snap.failed.length + ' failed')
  snap.failed.forEach(f => lines.push('  failed: ' + f.label + ' (' + f.role + '): ' + f.reason))
  ;(d.trackLines || []).forEach(l => lines.push(l))
  reasons.forEach(r => lines.push('  - ' + r))
  lines.push('Check results are reported by subagents: this script has no shell of its own, so re-run one check yourself before you say done.')
  return {
    verdict: verdict,
    reasons: reasons,
    dispatched: snap.dispatched,
    returned: snap.returned,
    failed: snap.failed,
    gates: d.gates || null,
    tracks: d.tracks || [],
    text: lines.join('\n'),
  }
}

function refuse(reason, extra) {
  log('dojo-flow build refused: ' + reason)
  return Object.assign({ refused: true, reason: reason }, extra || {}, { scorecard: makeCard('REFUSED', [reason]) })
}

// ---- eager probe: build every prompt once with dummy values -------------------------------------------------------
try {
  const probeTrack = { name: 'probe', prompt: 'probe', files: ['probe.txt'] }
  const probeScout = { plan: 'probe', questions: [] }
  const probeEntry = [{ consult: 1, question: 'q', advice: 'a', failed: false }]
  contractPrompt('g', '', null, DEFAULT_CONTRACT_PATH, 8, 'd')
  contractPrompt('g', 'r', [probeTrack], DEFAULT_CONTRACT_PATH, 8, '')
  scoutPrompt('g', probeTrack, 'c', { probe: 'x' }, 3)
  advisePrompt('b')
  buildPrompt('g', probeTrack, 'c', {}, probeScout, probeEntry)
  resumePrompt('g', probeTrack, 'c', {}, { summary: 's', filesChanged: [] }, probeEntry)
  integratePrompt('g', [], ['check'])
  auditPrompt('g', {}, {}, 'p', { dirtyFiles: [] }, null, [], [], [], ['check'])
  independenceProblems(['a', 'b'], [])
} catch (e) {
  return refuse('internal error while preparing prompts: ' + clip(e && e.message, 200))
}

// ---- arguments ----------------------------------------------------------------------------------------------------
const ALLOWED_ARGS = ['goal', 'tracks', 'gates', 'repo', 'models', 'effort', 'adviceCap', 'maxTracks', 'contractPath', 'contractDraft']
const parsed = parseArgs(args, ALLOWED_ARGS)
if (parsed.error) return refuse(parsed.error + '. Usage: ' + USAGE)
const A = parsed.value

if (typeof A.goal !== 'string' || !A.goal.trim()) return refuse('goal is required (a non-empty string). Usage: ' + USAGE)
const GOAL = A.goal.trim()
if (A.repo !== undefined && A.repo !== null && (typeof A.repo !== 'string' || !A.repo.trim())) return refuse('repo must be a non-empty string')
const REPO = typeof A.repo === 'string' ? A.repo.trim() : ''

const roleSettings = resolveRoles(A.models, A.effort, ROLE_DEFAULTS)
if (roleSettings.error) return refuse(roleSettings.error)
Object.assign(picked, roleSettings.picked)

let ADVICE_CAP = 3
if (A.adviceCap !== undefined && A.adviceCap !== null) {
  if (!Number.isInteger(A.adviceCap) || A.adviceCap < 0 || A.adviceCap > 6) return refuse('adviceCap must be an integer from 0 to 6')
  ADVICE_CAP = A.adviceCap
}
let MAX_TRACKS = 8
if (A.maxTracks !== undefined && A.maxTracks !== null) {
  if (!Number.isInteger(A.maxTracks) || A.maxTracks < 1 || A.maxTracks > 16) return refuse('maxTracks must be an integer from 1 to 16')
  MAX_TRACKS = A.maxTracks
}

let GATES = []
if (A.gates !== undefined && A.gates !== null) {
  if (!Array.isArray(A.gates) || A.gates.some(g => typeof g !== 'string' || !g.trim())) return refuse('gates must be a list of non-empty command strings')
  GATES = A.gates.map(g => g.trim())
  if (new Set(GATES).size !== GATES.length) return refuse('gates lists the same command twice; each check must appear exactly once')
}

const CONTRACT_PATH = typeof A.contractPath === 'string' && A.contractPath.trim() ? A.contractPath.trim() : DEFAULT_CONTRACT_PATH
if (A.contractPath !== undefined && A.contractPath !== null && typeof A.contractPath !== 'string') return refuse('contractPath must be a string')
const contractNorm = normEntry(CONTRACT_PATH, REPO)
const CONTRACT_ABS = /^([A-Za-z]:)?[\\/]/.test(CONTRACT_PATH)
if (CONTRACT_ABS && !REPO) return refuse('contractPath is absolute: pass repo so the path can be checked against track ownership')
if (contractNorm.err && !(CONTRACT_ABS && contractNorm.err.indexOf('absolute path outside the repo') === 0)) return refuse('contractPath: ' + contractNorm.err)
// An absolute path outside the repo (a scratch file) is allowed and is not part of the ownership map.
const RESERVED = contractNorm.err ? null : CONTRACT_PATH
const DRAFT = typeof A.contractDraft === 'string' ? A.contractDraft : ''

const PLAN_ONLY = A.tracks === undefined || A.tracks === null
let own = null
if (!PLAN_ONLY) {
  if (!Array.isArray(A.tracks) || !A.tracks.length) return refuse('tracks must be a non-empty list when given')
  if (A.tracks.length > MAX_TRACKS) return refuse(A.tracks.length + ' tracks is more than maxTracks (' + MAX_TRACKS + '): merge tracks, or raise maxTracks (16 at most)')
  const missingPrompt = A.tracks.filter(t => !t || typeof t.prompt !== 'string' || !t.prompt.trim()).length
  if (missingPrompt) return refuse(missingPrompt + ' track(s) have no prompt')
  own = checkOwnership(A.tracks, REPO, RESERVED)
  if (!own.ok) return refuse('ownership check failed: ' + own.errors.join('; '), { ownershipErrors: own.errors })
}

// ---- Contract -----------------------------------------------------------------------------------------------------
phase('Contract')
log('contract gate: ' + (PLAN_ONLY ? 'no tracks given, proposing a plan (nothing is built)' : 'writing the contract and certifying independence for ' + A.tracks.length + ' track(s)'))
const contract = await runner.spawn('contract', 'judge', contractPrompt(GOAL, REPO, PLAN_ONLY ? null : A.tracks, CONTRACT_PATH, MAX_TRACKS, DRAFT), 'Contract', CONTRACT_SCHEMA)
if (!contract) return refuse('the contract subagent returned nothing, so no contract exists and nothing was dispatched after it')

if (PLAN_ONLY) {
  const proposed = Array.isArray(contract.tracks) ? contract.tracks : []
  const planCheck = proposed.length ? checkOwnership(proposed, REPO, RESERVED) : { ok: false, errors: ['the contract subagent proposed no tracks'], map: {} }
  const problems = planCheck.errors.slice()
  if (proposed.length > MAX_TRACKS) problems.push(proposed.length + ' proposed tracks is more than maxTracks (' + MAX_TRACKS + ')')
  if (contract.proceed !== true) problems.push('the contract subagent set proceed=false: ' + (contract.blockers || []).map(b => clip(b, 200)).join('; '))
  return {
    planOnly: true,
    plan: { tracks: proposed, contractText: contract.contractText, contractPath: CONTRACT_PATH, ownershipMap: planCheck.map, problems: problems, baseline: contract.baseline, notes: contract.notes || '' },
    nextStep: 'Show the person these tracks. Check the width with scripts/dag_ops.py tracks, then run again with the confirmed tracks, gates and contractDraft set to plan.contractText.',
    scorecard: makeCard('PLAN ONLY', ['no track was scouted or built: this run only proposed a plan'].concat(problems)),
  }
}

if (contract.proceed !== true) return refuse('contract gate stopped the build: ' + (contract.blockers || []).map(b => clip(b, 200)).join('; '), { contract: contract })
const trackNames = A.tracks.map(t => t.name.trim())
const indep = independenceProblems(trackNames, contract.trackIndependence)
if (indep.length) return refuse('the tracks are not an independent set: ' + indep.join('; '), { contract: contract })
if (contract.contractWritten !== true || typeof contract.contractText !== 'string' || !contract.contractText.trim()) {
  return refuse('the contract file was not written (contractWritten is not true or the text is empty); builders need it', { contract: contract })
}
const CONTRACT_TEXT = contract.contractText
const GUIDANCE = contract.trackGuidance || {}
const bl = contract.baseline && typeof contract.baseline === 'object' ? contract.baseline : {}
const BASELINE = { isGit: bl.isGit === true, dirtyFiles: Array.isArray(bl.dirtyFiles) ? bl.dirtyFiles : [] }

// ---- Scout, Advise, Build (one pipeline: a fast track does not wait for a slow one) -------------------------------
phase('Scout')
function ledgerEntry(track, stage, index, question, res) {
  return { track: track, stage: stage, consult: index, question: question, advice: res ? res.advice : null, failed: !res }
}
async function consult(track, stage, index, briefing) {
  const res = await runner.spawn('advise:' + track + ':' + stage + index, 'judge', advisePrompt(briefing), 'Advise', ADVICE_SCHEMA)
  return ledgerEntry(track, stage, index, briefing, res)
}

const records = await pipeline(
  A.tracks,
  async (_, t) => {
    const scout = await runner.spawn('scout:' + t.name, 'scout', scoutPrompt(GOAL, t, CONTRACT_TEXT, GUIDANCE, ADVICE_CAP), 'Scout', SCOUT_SCHEMA)
    return { name: t.name, scout: scout, ledger: [], dropped: 0, build: null }
  },
  async (rec, t) => {
    if (!rec.scout) return rec
    const asked = Array.isArray(rec.scout.questions) ? rec.scout.questions : []
    if (asked.length > ADVICE_CAP) {
      rec.dropped = asked.length - ADVICE_CAP
      log('track ' + t.name + ': the scout asked ' + asked.length + ' questions and adviceCap is ' + ADVICE_CAP + '; the last ' + rec.dropped + ' were dropped')
    }
    const entries = await parallel(asked.slice(0, ADVICE_CAP).map((q, i) => () => consult(t.name, 'pre', i + 1, q && q.briefing)))
    rec.ledger = entries.filter(Boolean)
    return rec
  },
  async (rec, t) => {
    if (!rec.scout) return rec
    rec.build = await runner.spawn('build:' + t.name, 'builder', buildPrompt(GOAL, t, CONTRACT_TEXT, GUIDANCE, rec.scout, rec.ledger), 'Build', BUILD_SCHEMA)
    return rec
  },
  async (rec, t) => {
    const b = rec.build
    if (!b || b.complete === true || !b.stuckQuestion || rec.ledger.length >= ADVICE_CAP) return rec
    const extra = await consult(t.name, 'stuck', rec.ledger.length + 1, b.stuckQuestion)
    rec.ledger = rec.ledger.concat([extra])
    const resumed = await runner.spawn('resume:' + t.name, 'builder', resumePrompt(GOAL, t, CONTRACT_TEXT, GUIDANCE, b, rec.ledger), 'Build', BUILD_SCHEMA)
    rec.firstAttempt = b
    rec.build = resumed || b
    return rec
  }
)

// Every file a builder reported across all of its attempts (the first one and the resumed one), without repeats.
// The ownership check and the integrator and audit reports use this union, so a resume that reports only its own files
// cannot hide what the first attempt said it changed.
function changedAcrossAttempts(rec) {
  const seen = new Set()
  const out = []
  ;[rec && rec.firstAttempt, rec && rec.build].forEach(b => {
    if (!b || !Array.isArray(b.filesChanged)) return
    // A non-string entry is kept as a marker that never lies inside any owner's entries, so the ownership check flags it.
    b.filesChanged.forEach(f => {
      const e = typeof f === 'string' ? f : '<non-string entry: ' + (f === null ? 'null' : typeof f) + '>'
      if (!seen.has(e)) { seen.add(e); out.push(e) }
    })
  })
  return out
}

// True when a build or resume answer exists but its filesChanged is not a list: the ownership check had nothing to
// read, so the track can never count as clean.
function malformedFilesChanged(rec) {
  return [rec && rec.firstAttempt, rec && rec.build].some(b => !!b && !Array.isArray(b.filesChanged))
}

// A record can be null only if a stage callback itself threw (a script bug); count it as lost, never as fine.
const reasons = []
const trackRecords = A.tracks.map((t, i) => {
  const rec = records[i]
  if (!rec) {
    reasons.push('track ' + t.name + ' was lost inside the pipeline (a stage threw)')
    return { name: t.name, scouted: false, built: false, complete: false, outsideOwned: [], filesChanged: [], summary: '', droppedQuestions: 0, ledger: [] }
  }
  const b = rec.build
  const changed = changedAcrossAttempts(rec)
  const outside = b ? outsideOf(changed, own.map[t.name.trim()] || [], REPO) : []
  if (!rec.scout) reasons.push('track ' + t.name + ' was not scouted, so it was not built')
  else if (!b) reasons.push('track ' + t.name + ' was scouted but its builder returned nothing')
  else if (b.complete !== true) reasons.push('track ' + t.name + ' reported complete=false' + (b.stuckQuestion ? ' (it was stuck: ' + clip(b.stuckQuestion, 160) + ')' : ''))
  if (outside.length) reasons.push('track ' + t.name + ' reported changing files it does not own: ' + outside.join(', '))
  if (malformedFilesChanged(rec)) reasons.push('track ' + t.name + ' returned a malformed filesChanged (not a list), so its ownership could not be checked')
  return {
    name: t.name, scouted: !!rec.scout, built: !!b, complete: !!(b && b.complete === true), outsideOwned: outside,
    filesChanged: b ? changed.map(f => clip(f, 200)) : [], summary: b ? clip(b.summary, 400) : '',
    droppedQuestions: rec.dropped || 0, ledger: rec.ledger || [],
  }
})
const builds = records.filter(r => r && r.build).map(r => ({ track: r.name, complete: r.build.complete, filesChanged: changedAcrossAttempts(r), summary: clip(r.build.summary, 600), deviations: r.build.deviations || [] }))
const adviceLedger = records.filter(Boolean).flatMap(r => (r.ledger || []).map(e => {
  const f = ((r.build && r.build.adviceFollowed) || []).find(a => a && a.consult === e.consult)
  return Object.assign({}, e, { followed: f ? f.followed : null, why: f ? clip(f.why, 300) : 'the builder did not report' })
}))
const rawOwned = Object.create(null)
A.tracks.forEach(t => { rawOwned[t.name.trim()] = t.files })

function trackLines() {
  return trackRecords.map(t => '  track ' + t.name + ': scouted ' + (t.scouted ? 'yes' : 'NO') + ', built ' + (t.built ? 'yes' : 'NO') + ', complete ' + (t.complete ? 'yes' : 'NO') +
    (t.droppedQuestions ? ', ' + t.droppedQuestions + ' question(s) dropped by adviceCap' : ''))
}

if (!builds.length) {
  reasons.unshift('no track was built, so there was nothing to integrate or audit')
  return Object.assign({ contractPath: CONTRACT_PATH, contractText: CONTRACT_TEXT, ownershipMap: own.map, tracks: trackRecords, adviceLedger: adviceLedger },
    { scorecard: makeCard('UNVERIFIED', reasons, { trackLines: trackLines(), tracks: trackRecords }) })
}

// ---- Integrate ----------------------------------------------------------------------------------------------------
phase('Integrate')
const integ = await runner.spawn('integrate', 'integrator', integratePrompt(GOAL, builds, GATES), 'Integrate', INTEGRATE_SCHEMA)

// ---- Audit --------------------------------------------------------------------------------------------------------
phase('Audit')
const audit = await runner.spawn('audit', 'judge', auditPrompt(GOAL, own.map, rawOwned, RESERVED, BASELINE, integ, builds, adviceLedger, contract.trackIndependence, GATES), 'Audit', AUDIT_SCHEMA)
let judgment = null
if (audit) {
  judgment = await judgmentPasses(runner, 'audit',
    'GOAL: ' + GOAL + '\nOWNERSHIP MAP: ' + JSON.stringify(rawOwned) + '\nBUILD REPORTS: ' + JSON.stringify(builds.map(b => ({ track: b.track, complete: b.complete, filesChanged: b.filesChanged }))),
    audit, 'Audit')
}

// ---- Verdict ------------------------------------------------------------------------------------------------------
const snapNow = runner.snapshot()
if (snapNow.failed.length) reasons.push(snapNow.failed.length + ' subagent call(s) did not return a usable answer: ' + snapNow.failed.map(f => f.label).join(', '))
if (snapNow.returned !== snapNow.dispatched) reasons.push('returned (' + snapNow.returned + ') is not equal to dispatched (' + snapNow.dispatched + ')')
if (!GATES.length) reasons.push('no checks were given, so nothing could confirm the build')
else {
  if (!integ) reasons.push('the integrator returned nothing')
  else {
    gateCheck(GATES, integ.gates, 'the integrator').forEach(p => reasons.push(p))
    if (integ.complete !== true) reasons.push('the integrator reported complete=false')
  }
  if (!audit) reasons.push('the audit returned nothing')
  else gateCheck(GATES, audit.gates, 'the audit').forEach(p => reasons.push(p))
}
if (audit) {
  if (audit.proceed !== true) reasons.push('the audit did not approve the build (proceed is not true)')
  if (Array.isArray(audit.blockers) && audit.blockers.length) reasons.push('the audit listed ' + audit.blockers.length + ' blocker(s): ' + audit.blockers.map(b => clip(b, 160)).join('; '))
  if (audit.treeChecked !== true) reasons.push('the tree check did not run (not a git repository, or git was unavailable)')
  if (Array.isArray(audit.unownedChanges) && audit.unownedChanges.length) reasons.push('files changed outside the ownership map: ' + audit.unownedChanges.map(f => clip(f, 160)).join(', '))
}
if (!BASELINE.isGit) reasons.push('the repo is not a git repository, so the ownership check could not compare the tree')
if (judgment) {
  if (!judgment.ran) reasons.push('the faithfulness and accuracy passes over the audit did not both run')
  else if (!judgment.clean) reasons.push('the faithfulness or accuracy pass found a problem with the audit verdict')
}

const verdict = reasons.length ? 'UNVERIFIED' : 'VERIFIED'
const integratorEdits = integ && Array.isArray(integ.filesChanged) ? integ.filesChanged.map(f => clip(f, 200)) : []
const card = makeCard(verdict, reasons, {
  trackLines: trackLines().concat(integratorEdits.length ? ['  integrator edited: ' + integratorEdits.join(', ')] : []),
  tracks: trackRecords,
  gates: { given: GATES, integrator: integ ? integ.gates : null, audit: audit ? audit.gates : null },
})
log(card.text)

return {
  contractPath: CONTRACT_PATH,
  contractText: CONTRACT_TEXT,
  ownershipMap: own.map,
  baseline: BASELINE,
  tracks: trackRecords,
  adviceLedger: adviceLedger,
  integration: integ,
  audit: audit,
  judgment: judgment,
  scorecard: card,
}
