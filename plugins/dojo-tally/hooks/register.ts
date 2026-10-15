import { atom, read, update } from 'claude-code'
import type { AgentInfo, EngineInterface, Register } from 'claude-code'

import type { TallyAgent, TallyJudge, TallyOutcome, TallyState } from '../types'

// dojo-tally: Dojo rule 6 (count returns, not dispatches), rule 9 (silence is not a finding) and rule 5 (done means
// verified). dojo-verify counts any non-empty answer as returned; this mod judges WHAT came back, tells the model
// the tally when a fan-out settles, and sends one report to a judge on request (/tally refute <n>; /refute where the name is free).
//
// Everything it knows lives in $.state ('dojo-tally' / 'ledger'), so a hot reload keeps the waves. It never calls
// $.ui.status (dojo-verify owns the status line) and never hooks AbovePrompt.

// What counts as the agent having looked at something (the `reads` count, which the `silent` test needs): any tool call
// that is not a write, so Read/Grep/Glob/Bash/Web*/LSP and also every mcp__ tool, Skill and Agent. Bookkeeping that
// looks at nothing (a todo list, loading a tool's schema) does not count.
const WRITE_TOOLS = new Set(['Edit', 'Write', 'NotebookEdit', 'MultiEdit'])
const BOOKKEEPING = new Set(['TodoWrite', 'ToolSearch', 'ExitPlanMode'])

const KEEP_WAVES = 5
const ANSWER_CLIP = 8000
const VERDICT_CLIP = 6000
const JUDGE_TYPE = 'dojo-protocol:judge'
const FALLBACK_TYPE = 'general-purpose'

// Reconcile (see `reconcile`): how long before an agent the engine no longer lists, or a workflow agent that went quiet,
// is written off.
const TICK_MS = 15_000
// After a turn.complete the agent may still be alive: a Bash moved to a background shell ends the turn with an interim
// answer and the agent wakes for another turn when the work finishes. The roster is read this long after an end.
const RECHECK_MS = 2_500
const GONE_AFTER_MS = 60_000
const WORKFLOW_GIVE_UP_MS = 30 * 60_000
const WORKFLOW_QUIET_MS = 10 * 60_000
const EARLY_CAP = 50

// "I looked and found nothing" - worth nothing when the agent looked at nothing.
const CLEAN_VERDICT = [
  /\bno (?:defects|issues|problems|findings|bugs)(?: (?:were )?found)?\b/i,
  /\bLGTM\b/i,
  /\blooks good\b/i,
  /\bnothing (?:to report|found)\b/i,
  /\ball (?:checks|tests) pass/i,
]

// "I ran a check" - worth nothing when the agent ran no command.
const CHECK_CLAIM = [
  /\b(?:tests?|specs?)(?: (?:all|are|were|now|still))* (?:pass|passed|passing|green)\b/i,
  /\b(?:build|lint|typecheck|type-check)s?(?: (?:now|also|all))? (?:pass|passed|passes|clean|green)\b/i,
  /\bverified\b/i,
  /\bexit(?:ed)?(?: with)?(?: code| status)? 0\b/i,
]

// "could not be verified", "never verified", "haven't verified" are not claims of a check.
const NEGATED = /(?:\bnot|\bnever|n't|\bcannot|\bunable to|\bno)\s+(?:(?:be|been|yet|fully|actually|independently)\s+)*$/i

const EMPTY: TallyState = { agents: [], waves: [], judges: [], nextNo: 1, nextWave: 1, open: 0 }
const ledger = atom({ plugin: 'dojo-tally', key: 'ledger' } as const, EMPTY)
// The answers live apart from the ledger: a tool call rewrites the ledger, and it should not carry 8 KB a report.
const answers = atom({ plugin: 'dojo-tally', key: 'answers' } as const, {} as Record<string, string>)

type Config = { minWave: number; settleNote: boolean; judgeModel: string }
type Done = { reason: string; isAborted: boolean; answer: string; durationMs: number }
type Verdict = { outcome: TallyOutcome; reason: string }
type SpawnInfo = { id: string; label: string; type: string; model: string; isWorkflow: boolean }
// How an agent ended. `byReconcile` marks an end the mod inferred (no turn.complete was seen), which a real
// turn.complete that turns up later may correct.
type Ending = { verdict: Verdict; byReconcile: boolean }
// What the hooks share: the options, the turn.completes that came before their agent was registered, and a flag that
// keeps two reconcile passes from overlapping. One per load of the module.
type Ctx = { cfg: Config; early: Map<string, Done>; isReconciling: boolean }

// `$` may only be handed to a function declared at the top of this file, and `$.env.get` takes string literals.
type EnvReader = { env: { get: (name: string) => Promise<string | undefined> } }
type Dollar = Pick<EngineInterface, 'state' | 'ui' | 'session' | 'agent' | 'clock' | 'env'>

// ------------------------------------------------------------------------------------------------ options

function asFlag(value: unknown, fallback: boolean): boolean {
  if (typeof value === 'boolean') return value
  if (typeof value === 'string') {
    const t = value.trim().toLowerCase()
    if (t === 'false' || t === '0' || t === 'no' || t === 'off') return false
    if (t === 'true' || t === '1' || t === 'yes' || t === 'on') return true
  }
  return fallback
}

function asCount(value: unknown, fallback: number): number {
  const n = typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : NaN
  return Number.isFinite(n) && n >= 1 ? Math.floor(n) : fallback
}

function isOn(value: string | undefined): boolean {
  return typeof value === 'string' && ['1', 'true', 'yes'].includes(value.trim().toLowerCase())
}

async function standDown($: EnvReader): Promise<boolean> {
  const all = await $.env.get('DOJO_OFF')
  const mine = await $.env.get('DOJO_TALLY_OFF')
  return isOn(all) || isOn(mine)
}

// ------------------------------------------------------------------------------------------------ judging what came back

function clip(text: string, max: number): string {
  return text.length <= max ? text : text.slice(0, max - 1) + '…'
}

type SpawnEvent = { name?: string; description?: string; subagentType?: string; subagent_type?: string }

// A spawn another plugin's $.agent.spawn raises can carry the Agent tool's spelling (`subagent_type`).
function typeOf(e: SpawnEvent): string {
  for (const c of [e.subagentType, e.subagent_type]) {
    if (typeof c === 'string' && c.trim() !== '') return c.trim()
  }
  return 'general-purpose'
}

function labelOf(e: SpawnEvent): string {
  for (const c of [e.name, e.description, e.subagentType, e.subagent_type]) {
    if (typeof c === 'string' && c.trim() !== '') return c.trim()
  }
  return 'agent'
}

function claimsCheck(text: string): boolean {
  for (const p of CHECK_CLAIM) {
    for (const m of text.matchAll(new RegExp(p.source, 'gi'))) {
      const at = m.index ?? 0
      if (!NEGATED.test(text.slice(Math.max(0, at - 40), at))) return true
    }
  }
  return false
}

// First match wins: failed, silent, unchecked, returned.
function classify(d: Done, reads: number, bash: number): Verdict {
  if (d.reason === 'error') return { outcome: 'failed', reason: 'its turn ended in an error' }
  if (d.reason === 'refusal') return { outcome: 'failed', reason: 'the model refused' }
  if (d.isAborted || d.reason === 'aborted') return { outcome: 'failed', reason: 'it was interrupted before it answered' }
  const text = d.answer.trim()
  if (text === '') return { outcome: 'failed', reason: 'it returned an empty answer' }
  if (reads === 0 && CLEAN_VERDICT.some(p => p.test(text))) {
    return { outcome: 'silent', reason: 'clean verdict after reading nothing (rule 9)' }
  }
  if (bash === 0 && claimsCheck(text)) {
    return { outcome: 'unchecked', reason: 'claims a check it never ran (rule 5)' }
  }
  return { outcome: 'returned', reason: '' }
}

function countOf(agents: TallyAgent[], outcome: TallyOutcome): number {
  return agents.filter(a => a.outcome === outcome).length
}

function waveLine(members: TallyAgent[]): string {
  return (
    `dispatched ${members.length} · returned ${countOf(members, 'returned')} · failed ${countOf(members, 'failed')}` +
    ` · silent ${countOf(members, 'silent')} · unchecked ${countOf(members, 'unchecked')}`
  )
}

// ------------------------------------------------------------------------------------------------ ledger (pure)

// A wave opens at the first spawn while none is open; every spawn while it is open joins it.
function addAgent(s: TallyState, info: SpawnInfo, now: number): TallyState {
  let open = s.open
  let nextWave = s.nextWave
  let waves = s.waves
  if (open === 0) {
    open = nextWave
    nextWave += 1
    waves = [...waves, { id: open, openedAt: now, settledAt: 0, nos: [] }]
  }
  const no = s.nextNo
  const agent: TallyAgent = {
    no,
    id: info.id,
    label: info.label,
    type: info.type,
    model: info.model,
    wave: open,
    isWorkflow: info.isWorkflow,
    startedAt: now,
    lastCallAt: now,
    reads: 0,
    writes: 0,
    bash: 0,
    total: 0,
    errors: 0,
    outcome: 'running',
    reason: '',
    settledAt: 0,
    hasEnded: false,
    isParked: false,
    isSettled: false,
    isReconciled: false,
  }
  const joined = waves.map(w => (w.id === open ? { ...w, nos: [...w.nos, no] } : w))
  const kept = joined.slice(-KEEP_WAVES)
  const ids = new Set(kept.map(w => w.id))
  return {
    ...s,
    agents: [...s.agents, agent].filter(a => ids.has(a.wave)),
    waves: kept,
    nextNo: no + 1,
    nextWave,
    open,
  }
}

function bump(a: TallyAgent, tool: string, failed: boolean, now: number): TallyAgent {
  return {
    ...a,
    lastCallAt: now,
    isParked: false, // a call means it is awake again
    total: a.total + 1,
    reads: a.reads + (WRITE_TOOLS.has(tool) || BOOKKEEPING.has(tool) ? 0 : 1),
    writes: a.writes + (WRITE_TOOLS.has(tool) ? 1 : 0),
    bash: a.bash + (tool === 'Bash' ? 1 : 0),
    errors: a.errors + (failed ? 1 : 0),
  }
}

// Settles the agent and, when it was the last member of its wave, the wave: `settled` is that wave's id. An agent the
// mod settled by inference (`isReconciled`) is settled again by a real end that turns up late: `late` is then the
// corrected agent, and its wave is not settled twice.
function settle(
  s: TallyState,
  id: string,
  end: (a: TallyAgent) => Ending,
  now: number,
): { state: TallyState; settled: number; late?: TallyAgent } {
  const a = s.agents.find(x => x.id === id)
  if (a === undefined || (a.isSettled && !a.isReconciled)) return { state: s, settled: 0 }
  const e = end(a)
  const done: TallyAgent = {
    ...a,
    isSettled: true,
    isReconciled: e.byReconcile,
    outcome: e.verdict.outcome,
    reason: e.verdict.reason,
    settledAt: a.isSettled ? a.settledAt : now, // a correction does not move the moment the agent first settled
  }
  const agents = s.agents.map(x => (x.id === id ? done : x))
  if (a.isSettled) return { state: { ...s, agents }, settled: 0, late: done }
  if (!agents.filter(x => x.wave === a.wave).every(x => x.isSettled)) return { state: { ...s, agents }, settled: 0 }
  return {
    state: {
      ...s,
      agents,
      open: s.open === a.wave ? 0 : s.open,
      waves: s.waves.map(w => (w.id === a.wave ? { ...w, settledAt: now } : w)),
    },
    settled: a.wave,
  }
}

// An agent's turn ended: record the outcome, provisionally. It is reported only once a recheck finds the agent done.
function recordEnd(s: TallyState, id: string, d: Done): TallyState {
  const a = s.agents.find(x => x.id === id)
  if (a === undefined || a.isSettled) return s
  const v = classify(d, a.reads, a.bash)
  const noted: TallyAgent = { ...a, hasEnded: true, isParked: false, outcome: v.outcome, reason: v.reason }
  return { ...s, agents: s.agents.map(x => (x.id === id ? noted : x)) }
}

function parkAgent(s: TallyState, id: string): TallyState {
  return { ...s, agents: s.agents.map(x => (x.id === id && !x.isSettled ? { ...x, isParked: true } : x)) }
}

function recordJudgeEnd(s: TallyState, id: string, d: Done): TallyState {
  const ended = { hasEnded: true, isParked: false, endReason: d.reason, endAborted: d.isAborted, endAnswer: clip(d.answer, VERDICT_CLIP) }
  return { ...s, judges: s.judges.map(j => (j.id === id ? { ...j, ...ended } : j)) }
}

function parkJudge(s: TallyState, id: string): TallyState {
  return { ...s, judges: s.judges.map(j => (j.id === id ? { ...j, isParked: true } : j)) }
}

// ------------------------------------------------------------------------------------------------ talking

// A meta row the model reads. A refusal or a failure must not break anything: the same text goes to the person's log.
async function post($: Dollar, text: string): Promise<void> {
  try {
    const r = await $.session.append({ message: { type: 'user', content: [{ type: 'text', text }] } })
    if (r.deny === undefined) return
  } catch {
    // fall through to the log
  }
  $.ui.log('could not add this to the conversation, so it is only here.\n' + text)
}

async function announce($: Dollar, s: TallyState, wave: number, cfg: Config): Promise<void> {
  const members = s.agents.filter(a => a.wave === wave)
  if (members.length < cfg.minWave) return
  const line = waveLine(members)
  $.ui.toast(`wave settled — ${line}`)
  if (!cfg.settleNote) return
  const rows = [`[dojo-tally] Fan-out settled: ${line}`]
  for (const a of members) {
    if (a.outcome !== 'returned') rows.push(`#${a.no} ${a.label} (${a.type}): ${a.outcome} — ${a.reason}`)
  }
  rows.push(
    'Treat each report as a claim until a check backs it (Dojo rules 5, 6, 9). The person can send one to a judge with /tally refute <n>.',
  )
  await post($, rows.join('\n'))
}

// An agent's life, spawn to settle (or to now while it lives): 800ms, 4s, 2m28s.
function fmtDuration(ms: number): string {
  if (ms < 1000) return `${Math.max(0, Math.round(ms))}ms`
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m${String(s % 60).padStart(2, '0')}s`
}

// claude-haiku-5-5 -> "haiku 5.5"; an alias (sonnet) as it is; anything else cut to 16 characters.
function shortModel(model: string): string {
  const m = /^(?:claude-)?([a-z]+)-(\d+)-(\d+)/.exec(model)
  return m !== null ? `${m[1]} ${m[2]}.${m[3]}` : model.slice(0, 16)
}

function plural(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? '' : 's'}`
}

// "7 reads · 1 write · 2 bash": three separate counts, so a Bash (which is also a look at the world, and counts as a
// read for the `silent` test) is shown once, as bash.
function workOf(a: TallyAgent): string {
  return `${plural(Math.max(0, a.reads - a.bash), 'read')} · ${plural(a.writes, 'write')} · ${a.bash} bash`
}

const LABEL_CAP = 24

function labelCell(label: string): string {
  const one = label.replace(/\s+/g, ' ').trim()
  return one.length > LABEL_CAP ? one.slice(0, LABEL_CAP - 1).trimEnd() + '…' : one
}

// An outcome recorded at a turn's end is provisional until the agent is found done: it is not shown as one.
function stateOf(a: TallyAgent): string {
  return a.isSettled ? a.outcome : a.isParked ? 'waiting' : 'running'
}

// Its life: spawn to settle, or to now while it lives. Not the last turn's length: a parked agent lives on.
function lifeOf(a: TallyAgent, now: number): number {
  return Math.max(0, (a.isSettled ? a.settledAt : now) - a.startedAt)
}

const WAITING_LINE = 'waiting on its own background work: it ended a turn but is still alive, so nothing is reported yet'

// A column is as wide as its widest cell; `life` is right-aligned, the rest left-aligned, two spaces between columns.
function table(members: TallyAgent[][], now: number): string[] {
  const all = members.flat()
  const cells = (a: TallyAgent): string[] => [
    `#${a.no}`,
    labelCell(a.label),
    a.type,
    shortModel(a.model),
    stateOf(a),
    workOf(a),
    fmtDuration(lifeOf(a, now)),
  ]
  const width = [0, 1, 2, 3, 4, 5, 6].map(c => Math.max(0, ...all.map(a => (cells(a)[c] ?? '').length)))
  const line = (a: TallyAgent): string => {
    const c = cells(a)
    const lead = [0, 1, 2, 3, 4, 5].map(i => (c[i] ?? '').padEnd(width[i] ?? 0))
    const life = (c[6] ?? '').padStart(width[6] ?? 0)
    return '  ' + [...lead, life].join('  ')
  }
  return members.flatMap(group => group.map(line))
}

function tallyText(s: TallyState, now: number): string {
  if (s.agents.length === 0) return 'No fan-out yet.'
  const rows = [`${s.agents.length} agent${s.agents.length === 1 ? '' : 's'} in ${s.waves.length} wave${s.waves.length === 1 ? '' : 's'}`]
  const waves = [...s.waves].reverse().map(w => ({ w, members: s.agents.filter(a => a.wave === w.id) }))
  // one table for the whole listing, so the columns line up across waves
  const lines = table(waves.map(x => x.members), now)
  const noWidth = Math.max(...s.agents.map(a => `#${a.no}`.length))
  const sub = ' '.repeat(2 + noWidth + 2) // sub-lines hang under the label
  let at = 0
  for (const { w, members } of waves) {
    if (w.settledAt === 0) {
      const settled = members.filter(a => a.isSettled).length
      const parked = members.filter(a => !a.isSettled && a.isParked).length
      rows.push(
        `Open wave ${w.id} (live): dispatched ${members.length} · settled ${settled} · running ${members.length - settled - parked}` +
          (parked > 0 ? ` · waiting ${parked}` : ''),
      )
    } else {
      rows.push(`Wave ${w.id} (settled): ${waveLine(members)}`)
    }
    for (const a of members) {
      rows.push(lines[at++] ?? '')
      if (a.isSettled && a.reason !== '') rows.push(sub + a.reason)
      if (!a.isSettled && a.isParked) rows.push(sub + WAITING_LINE)
    }
  }
  rows.push("/tally refute <n> sends a settled agent's report to a judge.")
  return rows.join('\n')
}

function listing(agents: TallyAgent[]): string {
  if (agents.length === 0) return 'No settled agents yet. /tally shows what is running.'
  return 'Settled agents:\n' + agents.map(a => `  #${a.no} ${a.label} (${a.type}) — ${a.outcome}`).join('\n')
}

// ------------------------------------------------------------------------------------------------ hooks' work

async function track($: Dollar, info: SpawnInfo): Promise<void> {
  const now = await $.clock.now()
  const after = await update($, ledger, s => addAgent(s, info, now))
  // a wave that fell out of the last five takes its reports with it
  const keep = new Set(after.agents.map(a => String(a.no)))
  await update($, answers, cur => Object.fromEntries(Object.entries(cur).filter(([no]) => keep.has(no))))
}

async function countCall($: Dollar, id: string, tool: string, failed: boolean): Promise<void> {
  const s = await read($, ledger)
  if (!s.agents.some(a => a.id === id && !a.isSettled)) return
  const now = await $.clock.now()
  await update($, ledger, cur => ({
    ...cur,
    agents: cur.agents.map(a => (a.id === id && !a.isSettled ? bump(a, tool, failed, now) : a)),
  }))
}

// Posts a judge's verdict. `d` is its recorded end, or one the mod made up ("stopped (killed)", no answer).
async function postVerdict($: Dollar, j: TallyJudge, d: Done): Promise<void> {
  const answered = d.reason === 'answer' && !d.isAborted && d.answer.trim() !== ''
  const text = answered
    ? `[dojo-tally] Judge verdict on #${j.no} ${j.label}:\n${clip(d.answer, VERDICT_CLIP)}`
    : `[dojo-tally] The judge on #${j.no} ${j.label} returned no verdict (${d.reason === 'answer' ? 'an empty answer' : d.reason}). ` +
      'The report is unrefuted, not confirmed (Dojo rule 9: silence is not a finding).'
  await post($, text)
  $.ui.toast(
    answered
      ? `judge verdict on #${j.no} ${j.label} is in the conversation`
      : `the judge on #${j.no} ${j.label} returned no verdict`,
  )
}

// A wave that was reported with an agent marked failed by inference, and that agent then answered after all: say so.
async function correct($: Dollar, s: TallyState, a: TallyAgent, cfg: Config): Promise<void> {
  const members = s.agents.filter(x => x.wave === a.wave)
  const wave = s.waves.find(w => w.id === a.wave)
  if (!cfg.settleNote || wave === undefined || wave.settledAt === 0 || members.length < cfg.minWave) return
  const why = a.reason !== '' ? ` — ${a.reason}` : ''
  await post(
    $,
    `[dojo-tally] Correction: #${a.no} ${a.label} (${a.type}) did end after the fan-out was reported: ${a.outcome}${why}. ` +
      `The wave now stands at ${waveLine(members)}.`,
  )
}

// The one way an agent is settled: stores the report (when there is one), settles the agent, and announces the wave
// when this was its last member.
async function finish($: Dollar, ctx: Ctx, id: string, end: (a: TallyAgent) => Ending, report: string): Promise<void> {
  const before = await read($, ledger)
  const target = before.agents.find(a => a.id === id)
  if (target === undefined || (target.isSettled && !target.isReconciled)) return
  if (report !== '') await update($, answers, cur => ({ ...cur, [String(target.no)]: report }))
  const now = await $.clock.now()
  const out: { wave: number; late?: TallyAgent } = { wave: 0 }
  const after = await update($, ledger, s => {
    const r = settle(s, id, end, now)
    out.wave = r.settled
    out.late = r.late
    return r.state
  })
  if (out.wave !== 0) await announce($, after, out.wave, ctx.cfg)
  else if (out.late !== undefined) await correct($, after, out.late, ctx.cfg)
}

// A turn.complete is not the end of an agent: a Bash moved to a background shell ends the turn with an interim answer
// ("started, waiting") and the agent wakes for another turn when the work is done. So an end is recorded, not
// reported, and a recheck of the engine's roster a moment later decides (see `conclude`).
async function onDone($: Dollar, ctx: Ctx, id: string, d: Done): Promise<void> {
  const before = await read($, ledger)
  const judge = before.judges.find(j => j.id === id)
  if (judge !== undefined) {
    await update($, ledger, s => recordJudgeEnd(s, id, d))
    scheduleRecheck($, ctx, id)
  }
  const target = before.agents.find(a => a.id === id)
  if (target === undefined) {
    // Not a judge or a member yet? Its spawn may not have resolved. Keep the end (a small map, oldest out) so the
    // registration can apply it; an agent that never registers just ages out.
    if (judge === undefined) {
      ctx.early.set(id, { ...d, answer: clip(d.answer, ANSWER_CLIP) })
      if (ctx.early.size > EARLY_CAP) {
        const oldest = ctx.early.keys().next().value
        if (oldest !== undefined) ctx.early.delete(oldest)
      }
    }
    return
  }
  const report = clip(d.answer, ANSWER_CLIP)
  if (target.isSettled) {
    // Settled by inference and now it ends for real: the real end corrects it. A settled agent's later turns are not
    // judged: the first end decides.
    if (target.isReconciled) {
      await finish($, ctx, id, a => ({ verdict: classify(d, a.reads, a.bash), byReconcile: false }), report)
    }
    return
  }
  await update($, answers, cur => ({ ...cur, [String(target.no)]: report }))
  await update($, ledger, s => recordEnd(s, id, d))
  scheduleRecheck($, ctx, id)
}

// Called once a spawn is registered (a member or a judge): applies the end that came in before it was.
async function applyEarly($: Dollar, ctx: Ctx, id: string): Promise<void> {
  const d = ctx.early.get(id)
  if (d === undefined) return
  ctx.early.delete(id)
  await onDone($, ctx, id, d)
}

function scheduleRecheck($: Dollar, ctx: Ctx, id: string): void {
  $.clock.after(RECHECK_MS, () => {
    void recheck($, ctx, id).catch(() => undefined)
  })
}

// ------------------------------------------------------------------------------------------------ conclude

// What the engine's roster says about an agent the mod has not settled.
//   alive    it is still going (pending, running, waiting), so there is nothing to settle
//   ended    it is done: `verdict` is why it counts as failed, or none to settle with the outcome it recorded
//   unknown  not enough to say
type Fate = { is: 'alive' } | { is: 'ended'; verdict?: Verdict } | { is: 'unknown' }

const failedBecause = (reason: string): Verdict => ({ outcome: 'failed', reason })

function fateOf(a: TallyAgent, listed: AgentInfo | undefined, now: number): Fate {
  if (listed !== undefined) {
    const status = listed.status
    if (status === 'pending' || status === 'running' || status === 'waiting') return { is: 'alive' }
    if (status === 'failed') return { is: 'ended', verdict: failedBecause('its task failed') }
    if (status === 'killed') return { is: 'ended', verdict: failedBecause('stopped (killed)') }
    // completed, or idle: done if it delivered an end, else it ended without a final answer
    if (a.hasEnded) return { is: 'ended' }
    return status === 'completed' ? { is: 'ended', verdict: failedBecause('ended without a final answer') } : { is: 'unknown' }
  }
  // Not listed. One that delivered an end and was then dropped is done. The engine lists no workflow agents, so for a
  // workflow agent absence says nothing: only a long silence does.
  if (a.hasEnded) return { is: 'ended' }
  if (a.isWorkflow) {
    return now - a.startedAt >= WORKFLOW_GIVE_UP_MS && now - a.lastCallAt >= WORKFLOW_QUIET_MS
      ? { is: 'ended', verdict: failedBecause('no end seen') }
      : { is: 'unknown' }
  }
  return now - a.startedAt >= GONE_AFTER_MS ? { is: 'ended', verdict: failedBecause("no longer in the engine's task list") } : { is: 'unknown' }
}

// Settles an agent that has ended a turn (or is gone) once the roster says it is done; parks it while the roster says
// it is alive. `roster` is undefined when it could not be read: an agent that delivered an end then settles with it.
async function concludeAgent($: Dollar, ctx: Ctx, a: TallyAgent, roster: AgentInfo[] | undefined, now: number, canPark: boolean): Promise<void> {
  const fate: Fate =
    roster === undefined ? (a.hasEnded ? { is: 'ended' } : { is: 'unknown' }) : fateOf(a, roster.find(i => i.id === a.id), now)
  if (fate.is === 'alive') {
    if (canPark && a.hasEnded && !a.isParked) await update($, ledger, s => parkAgent(s, a.id))
    return
  }
  if (fate.is !== 'ended') return
  const verdict = fate.verdict
  await finish(
    $,
    ctx,
    a.id,
    x =>
      verdict === undefined
        ? { verdict: { outcome: x.outcome, reason: x.reason }, byReconcile: false }
        : { verdict, byReconcile: true },
    '',
  )
}

// The same for a judge: its verdict is posted only when it is really done. A judge that was killed or failed after an
// interim answer has no verdict, and says so.
async function concludeJudge($: Dollar, j: TallyJudge, roster: AgentInfo[] | undefined, canPark: boolean): Promise<void> {
  if (!j.hasEnded) return
  const listed = roster === undefined ? undefined : roster.find(i => i.id === j.id)
  const status = listed?.status
  if (status === 'pending' || status === 'running' || status === 'waiting') {
    if (canPark && !j.isParked) await update($, ledger, s => parkJudge(s, j.id))
    return
  }
  let end: Done = { reason: j.endReason, isAborted: j.endAborted, answer: j.endAnswer, durationMs: 0 }
  if (status === 'killed') end = { reason: 'stopped (killed)', isAborted: false, answer: '', durationMs: 0 }
  if (status === 'failed') end = { reason: 'its task failed', isAborted: false, answer: '', durationMs: 0 }
  // whoever removes the judge from the ledger posts: a recheck and a reconcile pass may meet here
  const out: { had: boolean } = { had: false }
  await update($, ledger, s => {
    out.had = s.judges.some(x => x.id === j.id)
    return { ...s, judges: s.judges.filter(x => x.id !== j.id) }
  })
  if (out.had) await postVerdict($, j, end)
}

// The recheck after a turn.complete: is the agent really done?
async function recheck($: Dollar, ctx: Ctx, id: string): Promise<void> {
  if (await standDown($)) return
  let roster: AgentInfo[] | undefined
  try {
    roster = await $.agent.list()
  } catch {
    roster = undefined // no roster: settle as if it were done
  }
  const s = await read($, ledger)
  const now = await $.clock.now()
  const a = s.agents.find(x => x.id === id)
  if (a !== undefined && !a.isSettled && a.hasEnded) await concludeAgent($, ctx, a, roster, now, true)
  const j = s.judges.find(x => x.id === id)
  if (j !== undefined) await concludeJudge($, j, roster, true)
}

// A wave settles when every member has: an agent that is killed or stopped never sends turn.complete, and one that
// ended a turn and parked settles only when it is found done, so the wave would wait for ever. Compares the open
// wave's unsettled agents (and the judges that ended a turn) with the engine's roster and settles the ones that are
// done or gone, through the same path a recheck takes (one toast, one meta row per wave).
async function reconcile($: Dollar, ctx: Ctx): Promise<void> {
  if (ctx.isReconciling || (await standDown($))) return
  ctx.isReconciling = true
  try {
    const s = await read($, ledger)
    const agents = s.open === 0 ? [] : s.agents.filter(a => !a.isSettled)
    const judges = s.judges.filter(j => j.hasEnded)
    if (agents.length === 0 && judges.length === 0) return
    let roster: AgentInfo[]
    try {
      roster = await $.agent.list()
    } catch {
      return // no roster, no change
    }
    const now = await $.clock.now()
    for (const a of agents) await concludeAgent($, ctx, a, roster, now, false)
    for (const j of judges) await concludeJudge($, j, roster, false)
  } finally {
    ctx.isReconciling = false
  }
}

// ------------------------------------------------------------------------------------------------ /refute

function findAgent(s: TallyState, q: string): { agent?: TallyAgent; help: string } {
  const settled = s.agents.filter(a => a.isSettled)
  if (q === '') return { help: `usage /tally refute <agent #>.\n${listing(settled)}` }
  const num = /^#?(\d+)$/.exec(q)
  if (num !== null) {
    // A number is only ever a number: never fall through to a label that happens to contain it.
    const n = Number(num[1])
    const one = s.agents.find(a => a.no === n)
    if (one !== undefined) return { agent: one, help: '' }
    if (n >= 1 && n < s.nextNo) return { help: `#${n} is no longer kept (only the last ${KEEP_WAVES} waves are).\n${listing(settled)}` }
    return { help: `no agent matches "${q}".\n${listing(settled)}` }
  }
  let hit = s.agents.filter(a => a.id === q)
  if (hit.length === 0) {
    const low = q.toLowerCase()
    hit = s.agents.filter(a => a.label.toLowerCase() === low)
    if (hit.length === 0) hit = s.agents.filter(a => a.label.toLowerCase().includes(low))
  }
  if (hit.length > 1) {
    const done = hit.filter(a => a.isSettled)
    if (done.length === 1) hit = done
  }
  const one = hit[0]
  if (hit.length === 1 && one !== undefined) return { agent: one, help: '' }
  if (hit.length > 1) return { help: `"${q}" matches more than one agent; use its number.\n${listing(hit.filter(a => a.isSettled))}` }
  return { help: `no agent matches "${q}".\n${listing(settled)}` }
}

async function spawnJudge(
  $: Dollar,
  subagentType: string,
  model: string,
  no: number,
  prompt: string,
): Promise<{ deny?: string; agentId?: string; model?: string }> {
  try {
    const r = await $.agent.spawn({ subagentType, model, description: `refute #${no}`, prompt })
    return r.deny !== undefined ? { deny: r.deny } : { agentId: r.agentId, model: r.model }
  } catch (err) {
    return { deny: err instanceof Error ? err.message : String(err) }
  }
}

async function refute($: Dollar, ctx: Ctx, args: string): Promise<string> {
  const s = await read($, ledger)
  const found = findAgent(s, args.trim())
  const a = found.agent
  if (a === undefined) return found.help
  if (!a.isSettled) {
    const what = a.isParked ? 'waiting on its own background work' : 'still running'
    return `#${a.no} ${a.label} is ${what}; refute takes a settled agent.\n${listing(s.agents.filter(x => x.isSettled))}`
  }
  const report = (await read($, answers))[String(a.no)] ?? ''
  if (report.trim() === '') return `#${a.no} ${a.label} returned no report (${a.reason}), so there is nothing to refute.`
  const prompt =
    'Refute or confirm the claims in this subagent report. Re-run the checks it cites or that would back it (read the files, run the commands); never take its word. ' +
    'Return a verdict per claim — confirmed | refuted | unverified — with path:line and the check you ran.\n\n' +
    `Report from ${a.label} (${a.type}):\n${report}`
  let type = JUDGE_TYPE
  let r = await spawnJudge($, type, ctx.cfg.judgeModel, a.no, prompt)
  if (r.deny !== undefined) {
    type = FALLBACK_TYPE
    r = await spawnJudge($, type, ctx.cfg.judgeModel, a.no, prompt)
  }
  const id = r.agentId
  if (r.deny !== undefined || id === undefined) return `could not start a judge for #${a.no} ${a.label}: ${r.deny ?? 'the engine returned no agent id'}`
  await update($, ledger, cur => ({ ...cur, judges: [...cur.judges.filter(j => j.id !== id), { id, no: a.no, label: a.label, type, hasEnded: false, isParked: false, endReason: '', endAborted: false, endAnswer: '' }] }))
  // a judge that was quick may have ended before it was registered: its verdict was kept, so it lands now
  await applyEarly($, ctx, id)
  return `sent #${a.no} ${a.label}'s report to ${type} (${r.model ?? ctx.cfg.judgeModel}). The verdict lands in the conversation when it returns.`
}

// ------------------------------------------------------------------------------------------------ hooks

const OFF_TEXT = 'off (DOJO_OFF or DOJO_TALLY_OFF is set).'

export const register: Register = (on, options) => {
  const ctx: Ctx = {
    cfg: {
      minWave: asCount(options.min_wave, 2),
      settleNote: asFlag(options.settle_note, true),
      judgeModel: options.judge_model === 'sonnet' ? 'sonnet' : 'opus',
    },
    early: new Map(),
    isReconciling: false,
  }
  let tick: { cancel: () => void } | undefined

  on('session.start', async ($, e, next) => {
    try {
      await $.command.register({
        name: 'tally',
        description: 'Show the fan-out waves: what each agent returned, and how. `refute <n>` sends a report to a judge.',
        argumentHint: '[refute <agent #>]',
        immediate: true,
      })
      // A shortcut only: another plugin may hold the name (dojo-protocol's refute skill does), and then the engine
      // keeps it; `/tally refute <n>` is the form that always works.
      await $.command.register({
        name: 'refute',
        description: 'Send a settled agent\'s report to a judge that re-runs its checks.',
        argumentHint: '<agent #>',
        immediate: true,
      })
    } catch {
      // the commands are a convenience: the hooks below still work
    }
    try {
      // one timer for the session: a start that runs again replaces it, and a reload drops it with the module
      tick?.cancel()
      tick = $.clock.every(TICK_MS, () => {
        void reconcile($, ctx).catch(() => undefined)
      })
    } catch {
      // without the timer a wave still settles on turn.complete, and /tally reconciles
    }
    return next(e)
  })

  // Counts after the call settles. A call that came back denied or errored was still attempted.
  on('tool.call', async ($, e, next) => {
    const r = await next(e)
    const id = e.agentId
    if (id !== undefined) {
      try {
        if (!(await standDown($))) await countCall($, id, String(e.tool), r.deny !== undefined || r.isError === true)
      } catch {
        // counting is best effort
      }
    }
    return r
  }).catch(($, e, next) => next(e))

  on('agent.spawn', async ($, e, next) => {
    const r = await next(e)
    try {
      // A judge /refute started does not open or join a wave; neither does a teammate, which never settles. The types
      // say a plugin's own $.agent.spawn skips its own hook frame, so the origin test is belt-and-braces: the kit does
      // run this hook for the plugin's own spawn, and a test fails without it.
      const isMine = next.origin.plugin === $.plugin.name
      if (r.deny === undefined && r.agentId !== undefined && e.isTeammate !== true && !isMine && !(await standDown($))) {
        await track($, { id: r.agentId, label: labelOf(e), type: typeOf(e), model: r.model, isWorkflow: e.workflow !== undefined })
        await applyEarly($, ctx, r.agentId)
      }
    } catch {
      // best effort
    }
    return r
  }).catch(($, e, next) => next(e))

  on('turn.complete', async ($, e, next) => {
    const r = await next(e)
    const id = e.agentId
    if (id !== undefined) {
      try {
        if (!(await standDown($))) await onDone($, ctx, id, e)
      } catch {
        // best effort
      }
    }
    return r
  }).catch(($, e, next) => next(e))

  on('command.run', { command: ['tally', 'dojo-tally:tally'] }, async ($, e) => {
    if (await standDown($)) return { text: OFF_TEXT }
    // `/tally refute <n>`: the form that works whoever holds the bare `refute` name.
    const sub = /^\s*refute\b\s*([\s\S]*)$/i.exec(e.args)
    if (sub !== null) return { text: await refute($, ctx, sub[1] ?? '') }
    if (e.args.trim() !== '') return { text: `Unknown argument "${e.args.trim().slice(0, 20)}". Use /tally, or /tally refute <agent #>.` }
    try {
      await reconcile($, ctx)
    } catch {
      // show what is known
    }
    return { text: tallyText(await read($, ledger), await $.clock.now()) }
  }).catch(() => ({ text: 'could not read the ledger.' }))

  on('command.run', { command: 'refute' }, async ($, e) => {
    if (await standDown($)) return { text: OFF_TEXT }
    return { text: await refute($, ctx, e.args) }
  }).catch(() => ({ text: 'refute failed before it could start a judge.' }))
}
