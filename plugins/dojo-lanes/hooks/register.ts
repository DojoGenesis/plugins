import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Board, Contest, Ended, Lane, LaneAgent } from '../types'

// dojo-lanes mod (early access). Dojo rule 4 says give each agent files no one else writes; in practice that is "a
// practice, not a lock". This makes it a lock between agents that run at the same time, and hands each new agent the
// fan-out's contract.
//
//  - tool.call (Edit, Write, NotebookEdit, MultiEdit) from a subagent: the first agent to write a path owns it for as
//    long as it runs. A second running agent writing the same path is refused (mode lock), allowed with a log line
//    (warn) or left alone (off). A settled holder's lane is free. The claim is made BEFORE `next`, in one
//    compare-and-set on the session state, so two near-simultaneous writes resolve first come, first served.
//  - the main loop is never refused; writing into a running agent's lane is logged once per path.
//  - turn.complete with an agentId does not release the agent's lanes at once: an agent whose Bash moved to a background
//    shell ends a turn and stays alive, and may write again when it wakes. 2.5 s later the engine's list is read: an
//    agent it still shows as waiting, running or pending is PARKED and keeps its lanes; any other (completed, failed,
//    killed, absent, or a list that cannot be read) is settled and its lanes released (kept in history for /lanes).
//    The engine's own agent list is also consulted when a lane's holder is in doubt (reconcile): an agent it lists as
//    completed, failed or killed is settled, and so is one it no longer lists at all once it is 60 s old, so a killed
//    agent does not hold a file for ever. A workflow agent is never settled by absence (the list may not name it), nor
//    is an agent first seen at a write until the list has named it once.
//  - agent.spawn: a short note is appended to the prompt when a contract file exists, or another writing agent is
//    already running. A workflow agent's prompt and a fork are never rewritten (a workflow's content is not
//    rewritable, a fork already carries the parent's context).
//  - /lanes shows who holds what and what was refused. The engine prefixes a plugin command's output with the
//    plugin's name, so the answer itself does not start with "dojo-lanes: " (log lines, toasts and refusals do).
//
// Limit: paths are compared lexically, so symlinks and letter case (a case-insensitive file system) are not resolved
// and two spellings of one file can slip past the lock.
//
// It stands down under DOJO_OFF / DOJO_LANES_OFF. Every hook fails open: these are coordination aids, not security.
// The status line and the band above the prompt are other mods' (shared decisions 4 and 5): this one never draws there.

type Dollar = EngineInterface
type Mode = 'lock' | 'warn' | 'off'

const EMPTY: Board = { agents: [], lanes: [], contested: [], refused: 0, warned: 0, mainWrites: 0, noted: [], waveToasted: false, ended: [] }
const board = atom({ plugin: 'dojo-lanes', key: 'board' } as const, EMPTY)

const DEFAULT_CONTRACTS = 'CONTRACT.md,.dojo/CONTRACT.md,.dojo/dag-contract.md,.parallel-tracks/manifest.json'
const MARK = 'dojo-lanes:'

// Agent statuses the engine's list reports for an agent that is over.
const OVER = new Set(['completed', 'failed', 'killed'])

// An agent the engine's list no longer names is let go once it is this old; and a turn.complete that beat the spawn's
// own record is honoured for this long.
const ABSENT_MS = 60_000
const NO_LONGER_LISTED = "no longer in the engine's task list"
const ENDED_MS = 10_000

// After a turn ends, how long to wait before asking the engine's list whether the agent is really done, and which of
// its statuses mean it is not (a parked agent: its background work has not finished and it will wake for another turn).
const RECHECK_MS = 2500
const PARKED = new Set(['waiting', 'running', 'pending'])

// Types that are not expected to write (shared decision 9).
const READ_ONLY_TYPES = new Set(['Explore', 'Plan', 'claude-code-guide', 'statusline-setup'])
const READ_ONLY_SUFFIXES = [':scout', ':reviewer', ':judge', ':researcher']

// The tools that write a file (shared decision 9). MultiEdit is not in every build, so the hook is not matched on it.
const WRITE_TOOLS = new Set(['Edit', 'Write', 'NotebookEdit', 'MultiEdit'])

const CAP_AGENTS = 100
const CAP_LANES = 300
const CAP_CONTESTED = 20
const CAP_NOTED = 300
const CAP_ENDED = 50

// ------------------------------------------------------------------------------------------------ small helpers

// `fromSpawn`: the seed comes from the spawn itself (its facts win over an adoption's guesses). `adopted`: first seen at
// a write. `listed`: the engine's list named it. `workflow`: a workflow script started it.
type Seed = { id: string; label: string; type: string; canWrite: boolean; fromSpawn?: boolean; adopted?: boolean; listed?: boolean; workflow?: boolean }
type Outcome = { kind: 'claimed' } | { kind: 'own' } | { kind: 'held'; holder: LaneAgent; since: number }
type WriteCall = { tool: string; agentId?: string; file_path?: unknown; notebook_path?: unknown }
type SpawnView = {
  prompt: string
  description?: string
  subagentType?: string
  name?: string
  fork?: boolean
  workflow?: unknown
}

function isOn(value: string | undefined): boolean {
  return typeof value === 'string' && ['1', 'true', 'yes'].includes(value.trim().toLowerCase())
}

function asMode(value: unknown): Mode {
  const text = typeof value === 'string' ? value.trim().toLowerCase() : ''
  return text === 'warn' || text === 'off' ? text : 'lock'
}

function asFlag(value: unknown, fallback: boolean): boolean {
  if (typeof value === 'boolean') return value
  if (typeof value === 'string') {
    const text = value.trim().toLowerCase()
    if (['false', '0', 'no', 'off'].includes(text)) return false
    if (['true', '1', 'yes', 'on'].includes(text)) return true
  }
  return fallback
}

function asPaths(value: unknown): string[] {
  const text = typeof value === 'string' && value.trim() !== '' ? value : DEFAULT_CONTRACTS
  return text.split(',').map(part => part.trim()).filter(part => part !== '')
}

function pickLabel(...candidates: unknown[]): string {
  for (const one of candidates) {
    if (typeof one === 'string' && one.trim() !== '') return one.trim().slice(0, 60)
  }
  return ''
}

function isReadOnlyType(type: string): boolean {
  return READ_ONLY_TYPES.has(type) || READ_ONLY_SUFFIXES.some(suffix => type.endsWith(suffix))
}

// Light, lexical: collapse `//`, `/./` and `x/..`, drop a trailing slash, resolve a relative path against `cwd`.
// Symlinks and letter case are not looked at.
function normalizePath(raw: string, cwd?: string): string {
  let path = raw.trim()
  if (path === '') return path
  if (!path.startsWith('/') && cwd !== undefined && cwd.startsWith('/')) path = `${cwd}/${path}`
  const absolute = path.startsWith('/')
  const out: string[] = []
  for (const part of path.split('/')) {
    if (part === '' || part === '.') continue
    if (part === '..') {
      if (out.length > 0 && out[out.length - 1] !== '..') out.pop()
      else if (!absolute) out.push('..')
      continue
    }
    out.push(part)
  }
  return (absolute ? '/' : '') + out.join('/')
}

function short(path: string, cwd: string | undefined): string {
  return cwd !== undefined && cwd !== '' && path.startsWith(`${cwd}/`) ? path.slice(cwd.length + 1) : path
}

function ago(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000))
  if (s < 90) return `${s}s ago`
  const m = Math.round(s / 60)
  return m < 90 ? `${m}m ago` : `${Math.round(m / 60)}h ago`
}

function pathOf(e: WriteCall): string | undefined {
  const raw = e.tool === 'NotebookEdit' ? e.notebook_path : e.file_path
  return typeof raw === 'string' && raw.trim() !== '' ? raw : undefined
}

function denyText(path: string, holder: string, sinceMs: number): string {
  const n = Math.max(0, Math.round(sinceMs / 1000))
  return (
    `dojo-lanes: ${path} is in ${holder}'s lane (claimed ${n}s ago). Two agents writing one file clobber each other ` +
    `(Dojo rule 4). Don't write it: put the change you need in your report so the orchestrator applies it after ${holder} returns.`
  )
}

function noteText(contract: string | undefined): string {
  const lane =
    'Files you write first become your lane (Dojo rule 4: each agent gets files no one else writes); a file another ' +
    'running agent holds will be refused, so put the change you need in your report instead of forcing it.'
  return contract !== undefined
    ? `${MARK} shared decisions for this fan-out are frozen in ${contract}; read it before you write and do not contradict it. ${lane}`
    : `${MARK} other agents are writing in parallel with you. ${lane}`
}

// ------------------------------------------------------------------------------------------------ the board (pure)

const agentOf = (b: Board, id: string): LaneAgent | undefined => b.agents.find(a => a.id === id)
const activeLane = (b: Board, path: string): Lane | undefined => b.lanes.find(l => l.path === path && l.releasedAt === undefined)

function trimAgents(list: LaneAgent[]): LaneAgent[] {
  let drop = list.length - CAP_AGENTS
  if (drop <= 0) return list
  const out: LaneAgent[] = []
  for (const a of list) {
    if (drop > 0 && a.status === 'settled') {
      drop--
      continue
    }
    out.push(a)
  }
  return out
}

function trimLanes(list: Lane[]): Lane[] {
  let drop = list.length - CAP_LANES
  if (drop <= 0) return list
  const out: Lane[] = []
  for (const l of list) {
    if (drop > 0 && l.releasedAt !== undefined) {
      drop--
      continue
    }
    out.push(l)
  }
  return out
}

const endedOf = (b: Board): Ended[] => (Array.isArray(b.ended) ? b.ended : [])

// Folds what the seed knows into a row: its label and type win when it has them; flags only ever turn on, except
// `adopted`, which a spawn's own seed turns off.
function merged(cur: LaneAgent, s: Seed): LaneAgent {
  const row: LaneAgent = {
    ...cur,
    label: s.label !== '' ? s.label : cur.label,
    type: s.type !== '' ? s.type : cur.type,
    canWrite: s.canWrite || cur.canWrite,
  }
  if (s.workflow === true) row.workflow = true
  if (s.listed === true) row.listed = true
  if (s.fromSpawn === true) delete row.adopted
  return row
}

// The agent is running (again) from here on, unless `revive` is false and the board already has it settled: then only
// what the seed knows is filled in (a turn.complete may have beaten the spawn's own record).
function upsert(b: Board, s: Seed, now: number, revive = true): Board {
  const at = b.agents.findIndex(a => a.id === s.id)
  if (at < 0) {
    const fresh: LaneAgent = { id: s.id, label: s.label, type: s.type, canWrite: s.canWrite, status: 'running', startedAt: now }
    if (s.workflow === true) fresh.workflow = true
    if (s.adopted === true) fresh.adopted = true
    if (s.listed === true) fresh.listed = true
    return { ...b, agents: trimAgents([...b.agents, fresh]) }
  }
  const cur = b.agents[at] as LaneAgent
  let row: LaneAgent
  if (cur.status === 'settled' && !revive) {
    row = merged(cur, s)
  } else {
    const { settledAt: _settledAt, how: _how, endedAt: _endedAt, parkedAt: _parkedAt, ...rest } = cur
    // a continued agent gets a fresh grace period before its absence from the list means anything
    row = { ...merged(rest, s), status: 'running', startedAt: cur.status === 'settled' ? now : cur.startedAt }
  }
  return { ...b, agents: b.agents.map((a, i) => (i === at ? row : a)) }
}

function settleMany(b: Board, over: ReadonlyMap<string, string>, now: number): Board {
  const ended = new Set<string>()
  const agents = b.agents.map(a => {
    const how = over.get(a.id)
    if (how === undefined || a.status === 'settled') return a
    ended.add(a.id)
    const { endedAt: _endedAt, parkedAt: _parkedAt, ...rest } = a
    return { ...rest, status: 'settled' as const, settledAt: now, how }
  })
  if (ended.size === 0) return b
  const lanes = b.lanes.map(l => (l.releasedAt === undefined && ended.has(l.agentId) ? { ...l, releasedAt: now } : l))
  return { ...b, agents, lanes }
}

// A turn.complete for `id`. The agent keeps its lanes until the recheck has asked the engine whether it is really done
// (`endedAt` is the token the recheck must find unchanged: a write in between means the agent woke). An agent the
// board does not know yet is remembered, briefly, so that its spawn - recorded a moment later - finds it already over.
function turnEnded(b: Board, id: string, how: string, now: number): Board {
  const cur = agentOf(b, id)
  if (cur === undefined) {
    const ended = endedOf(b)
    if (ended.some(x => x.id === id)) return b
    return { ...b, ended: [...ended, { id, at: now, how }].slice(-CAP_ENDED) }
  }
  if (cur.status === 'settled') return b
  return { ...b, agents: b.agents.map(a => (a.id === id ? { ...a, endedAt: now, how } : a)) }
}

// The recheck, `listed` being the engine's status for the agent (undefined: absent, or the list could not be read).
function finishRecheck(b: Board, id: string, endedAt: number, listed: string | undefined, now: number): Board {
  const cur = agentOf(b, id)
  if (cur === undefined || cur.status === 'settled' || cur.endedAt !== endedAt) return b
  if (listed !== undefined && PARKED.has(listed)) {
    const { endedAt: _endedAt, ...rest } = cur
    return { ...b, agents: b.agents.map(a => (a.id === id ? { ...rest, status: 'parked' as const, parkedAt: now } : a)) }
  }
  return settleMany(b, new Map([[id, cur.how ?? 'answer']]), now)
}

// The reconcile rule. For each agent the board holds as running or parked, against the engine's list (`status` by id):
//  (a) listed as completed, failed or killed: settled;
//  (b) not listed, not a workflow agent, not an adopted one the list never named, and at least ABSENT_MS old: settled
//      ("no longer in the engine's task list"). A workflow agent is never settled by absence.
// An adopted agent the list does name is marked `listed`, which makes (b) apply to it later.
function reconcileBoard(b: Board, status: ReadonlyMap<string, string>, now: number): Board {
  const over = new Map<string, string>()
  let marked = false
  const agents = b.agents.map(a => {
    if (a.status === 'settled') return a
    const st = status.get(a.id)
    if (st !== undefined) {
      if (OVER.has(st)) {
        over.set(a.id, st)
        return a
      }
      if (a.adopted === true && a.listed !== true) {
        marked = true
        return { ...a, listed: true }
      }
      return a
    }
    if (a.workflow === true || (a.adopted === true && a.listed !== true)) return a
    // a parked agent has been seen alive up to the moment it was parked
    if (now - (a.status === 'parked' ? (a.parkedAt ?? a.startedAt) : a.startedAt) >= ABSENT_MS) over.set(a.id, NO_LONGER_LISTED)
    return a
  })
  const base = marked ? { ...b, agents } : b
  return over.size === 0 ? base : settleMany(base, over, now)
}

// First come, first served. A holder that is not running (or not known) has let go of its lane.
function claimPath(b: Board, s: Seed, path: string, now: number): { board: Board; outcome: Outcome } {
  let next = upsert(b, { ...s, canWrite: true }, now)
  const lane = activeLane(next, path)
  const claim: Lane = { path, agentId: s.id, claimedAt: now }
  if (lane === undefined) return { board: { ...next, lanes: trimLanes([...next.lanes, claim]) }, outcome: { kind: 'claimed' } }
  if (lane.agentId === s.id) return { board: next, outcome: { kind: 'own' } }
  const holder = agentOf(next, lane.agentId)
  if (holder === undefined || holder.status === 'settled') {
    next = { ...next, lanes: next.lanes.map(l => (l === lane ? { ...l, releasedAt: now } : l)) }
    return { board: { ...next, lanes: trimLanes([...next.lanes, claim]) }, outcome: { kind: 'claimed' } }
  }
  return { board: next, outcome: { kind: 'held', holder, since: lane.claimedAt } }
}

// `key` makes the log line once-only: `first` is false when the key was already seen.
function recordContest(b: Board, c: Contest, key: string | undefined): { board: Board; first: boolean } {
  const first = key === undefined || !b.noted.includes(key)
  const noted = key !== undefined && first ? [...b.noted, key].slice(-CAP_NOTED) : b.noted
  return {
    first,
    board: {
      ...b,
      contested: [...b.contested, c].slice(-CAP_CONTESTED),
      refused: b.refused + (c.kind === 'refused' ? 1 : 0),
      warned: b.warned + (c.kind === 'warned' ? 1 : 0),
      mainWrites: b.mainWrites + (c.kind === 'main' ? 1 : 0),
      noted,
    },
  }
}

// ------------------------------------------------------------------------------------------------ $ helpers
// `$` may only be handed to a function declared at the top of this file, and `$.env.get` takes string literals.

async function standDown($: Dollar): Promise<boolean> {
  const all = await $.env.get('DOJO_OFF')
  const mine = await $.env.get('DOJO_LANES_OFF')
  return isOn(all) || isOn(mine)
}

async function sessionCwd($: Dollar): Promise<string | undefined> {
  try {
    const cwd = await $.session.cwd()
    return typeof cwd === 'string' && cwd !== '' ? cwd : undefined
  } catch {
    return undefined
  }
}

async function liveAgents($: Dollar): Promise<Awaited<ReturnType<Dollar['agent']['list']>> | undefined> {
  try {
    const list = await $.agent.list()
    return Array.isArray(list) ? list : undefined
  } catch {
    return undefined
  }
}

// Settle what the engine's agent list says is over, and what it no longer lists (reconcileBoard). A list that cannot be
// read changes nothing.
async function reconcile($: Dollar): Promise<void> {
  const live = await liveAgents($)
  if (live === undefined) return
  const status = new Map<string, string>()
  for (const info of live) status.set(info.id, String(info.status))
  const now = await $.clock.now()
  const seen = await read($, board)
  if (reconcileBoard(seen, status, now) === seen) return
  await update($, board, b => reconcileBoard(b, status, now))
}

async function adopt($: Dollar, id: string): Promise<Seed> {
  const live = await liveAgents($)
  const info = live?.find(a => a.id === id)
  if (info === undefined) return { id, label: `agent ${id.slice(0, 8)}`, type: '', canWrite: true, adopted: true }
  const type = typeof info.type === 'string' ? info.type : ''
  return { id, label: pickLabel(info.name, info.description, type) || `agent ${id.slice(0, 8)}`, type, canWrite: !isReadOnlyType(type), adopted: true, listed: true }
}

async function findContract($: Dollar, paths: readonly string[]): Promise<string | undefined> {
  const cwd = await sessionCwd($)
  for (const one of paths) {
    const abs = one.startsWith('/') ? normalizePath(one) : cwd !== undefined ? normalizePath(one, cwd) : one
    try {
      if (await $.fs.exists(abs)) return abs
    } catch {
      // try the next one
    }
  }
  return undefined
}

// A write by the main loop is never refused. It is noted, once per path, when a running agent holds the path.
async function mainLoopWrite($: Dollar, path: string, now: number, mode: Mode): Promise<void> {
  if (mode === 'off') return
  let b = await read($, board)
  let lane = activeLane(b, path)
  if (lane === undefined || (agentOf(b, lane.agentId)?.status ?? 'settled') === 'settled') return
  // The board says that agent still runs; ask the engine before telling the person.
  await reconcile($)
  b = await read($, board)
  lane = activeLane(b, path)
  const holder = lane === undefined ? undefined : agentOf(b, lane.agentId)
  if (holder === undefined || holder.status === 'settled') return
  const contest: Contest = { at: now, path, label: 'main', holderId: holder.id, holderLabel: holder.label, kind: 'main' }
  const seen = { first: true }
  await update($, board, cur => {
    const r = recordContest(cur, contest, `main|${path}`)
    seen.first = r.first
    return r.board
  })
  if (seen.first) $.ui.log(`main loop wrote ${path} while it is in ${holder.label}'s lane`)
}

// A subagent's write: claim the path (or find who holds it) BEFORE the tool runs. Returns the refusal, if any.
async function agentWrite($: Dollar, id: string, path: string, now: number, mode: Mode): Promise<string | undefined> {
  const b0 = await read($, board)
  const known = agentOf(b0, id)
  const lane0 = activeLane(b0, path)
  // the common case: it already owns the path and nothing changes
  if (known !== undefined && known.status === 'running' && lane0 !== undefined && lane0.agentId === id) return undefined

  const seed: Seed = known !== undefined ? { id, label: known.label, type: known.type, canWrite: known.canWrite } : await adopt($, id)
  let outcome = { kind: 'claimed' } as Outcome
  await update($, board, b => {
    const r = claimPath(b, seed, path, now)
    outcome = r.outcome
    return r.board
  })
  if (outcome.kind === 'held') {
    // Held by an agent the board thinks runs. If the engine says it is over, the lane is free.
    await reconcile($)
    await update($, board, b => {
      const r = claimPath(b, seed, path, now)
      outcome = r.outcome
      return r.board
    })
  }
  if (outcome.kind !== 'held' || mode === 'off') return undefined

  const holder = outcome.holder
  const lock = mode === 'lock'
  const contest: Contest = { at: now, path, label: seed.label, holderId: holder.id, holderLabel: holder.label, kind: lock ? 'refused' : 'warned' }
  const seen = { first: true }
  await update($, board, b => {
    const r = recordContest(b, contest, lock ? undefined : `warn|${path}|${id}`)
    seen.first = r.first
    return r.board
  })
  if (lock) {
    $.ui.log(`refused ${seed.label} writing ${path} (in ${holder.label}'s lane)`)
    return denyText(path, holder.label, now - outcome.since)
  }
  if (seen.first) $.ui.log(`${seed.label} wrote ${path} while it is in ${holder.label}'s lane (warn mode)`)
  return undefined
}

async function guardWrite($: Dollar, e: WriteCall, mode: Mode): Promise<string | undefined> {
  const raw = pathOf(e)
  if (raw === undefined) return undefined
  const path = normalizePath(raw, raw.startsWith('/') ? undefined : await sessionCwd($))
  const now = await $.clock.now()
  if (e.agentId === undefined) {
    await mainLoopWrite($, path, now, mode)
    return undefined
  }
  return agentWrite($, e.agentId, path, now, mode)
}

// A subagent's turn ended: note it, and ask the engine in RECHECK_MS whether the agent is really done.
async function endTurn($: Dollar, id: string, how: string): Promise<void> {
  const now = await $.clock.now()
  await update($, board, b => turnEnded(b, id, how, now))
  $.clock.after(RECHECK_MS, () => {
    void recheck($, id, now).catch(() => undefined)
  })
}

// Parked (the list still shows it waiting, running or pending) or settled; an unreadable list settles it, as before.
async function recheck($: Dollar, id: string, endedAt: number): Promise<void> {
  const live = await liveAgents($)
  const listed = live?.find(a => a.id === id)
  const status = listed === undefined ? undefined : String(listed.status)
  const now = await $.clock.now()
  const seen = await read($, board)
  if (finishRecheck(seen, id, endedAt, status, now) === seen) return
  await update($, board, b => finishRecheck(b, id, endedAt, status, now))
}

type SpawnPlan = { note?: string; nudgeable: boolean }

// Before the spawn: settle what the engine says is over, look for a contract, decide whether to add the note.
async function planSpawn($: Dollar, e: SpawnView, attach: boolean, paths: readonly string[]): Promise<SpawnPlan> {
  const eligible = e.workflow === undefined && e.fork !== true && e.subagentType !== 'fork'
  if (!eligible) return { nudgeable: false }
  await reconcile($)
  const b = await read($, board)
  const writers = b.agents.filter(a => a.status === 'running' && a.canWrite).length
  const canWrite = !isReadOnlyType(e.subagentType ?? '')
  const contract = await findContract($, paths)
  const wanted = attach && (contract !== undefined || (canWrite && writers >= 1))
  const plan: SpawnPlan = { nudgeable: contract === undefined }
  if (wanted && !e.prompt.includes(MARK)) plan.note = noteText(contract)
  return plan
}

function seedOfSpawn(e: SpawnView, id: string): Seed {
  const type = typeof e.subagentType === 'string' ? e.subagentType : ''
  const seed: Seed = { id, label: pickLabel(e.name, e.description, type) || `agent ${id.slice(0, 8)}`, type, canWrite: !isReadOnlyType(type), fromSpawn: true }
  if (e.workflow !== undefined) seed.workflow = true
  return seed
}

// After the spawn: remember the agent. Returns the number of writing agents in flight when the no-contract nudge is due
// (once per wave; a wave ends when no subagent is running), else 0.
async function recordSpawn($: Dollar, seed: Seed, nudgeable: boolean): Promise<number> {
  const now = await $.clock.now()
  const out = { writers: 0 }
  await update($, board, b => {
    // its turn.complete may have come in before this record: then it is over already and stays over
    const gone = endedOf(b).find(x => x.id === seed.id && now - x.at <= ENDED_MS)
    const prior = b.agents.filter(a => a.status === 'running' && a.id !== seed.id)
    const wave = prior.length === 0 ? false : b.waveToasted
    const others = prior.filter(a => a.canWrite).length
    const nudge = gone === undefined && nudgeable && seed.canWrite && others >= 1 && !wave
    out.writers = nudge ? others + 1 : 0
    let next = upsert(b, seed, now, false)
    if (gone !== undefined) next = settleMany(next, new Map([[seed.id, gone.how]]), gone.at)
    return { ...next, ended: endedOf(next).filter(x => x.id !== seed.id), waveToasted: wave || nudge }
  })
  return out.writers
}

async function lanesText($: Dollar, mode: Mode): Promise<string> {
  if (await standDown($)) return 'Stood down (DOJO_OFF or DOJO_LANES_OFF is set); lanes are not tracked.'
  await reconcile($)
  const b = await read($, board)
  const running = b.agents.filter(a => a.status === 'running')
  const parked = b.agents.filter(a => a.status === 'parked')
  if (b.lanes.length === 0) {
    return `No subagent has written anything yet.${running.length > 0 ? ` (${running.length} running)` : ''}`
  }
  const now = await $.clock.now()
  const cwd = await sessionCwd($)
  const held = b.lanes.filter(l => l.releasedAt === undefined).length
  const lines = [
    `${b.agents.length} agent${b.agents.length === 1 ? '' : 's'} (${running.length} running${parked.length > 0 ? `, ${parked.length} parked` : ''}) · ${held} file${held === 1 ? '' : 's'} held · mode ${mode}`,
  ]
  const listed = b.agents.slice(-25)
  if (listed.length < b.agents.length) lines.push(`  (${b.agents.length - listed.length} earlier agents not shown)`)
  for (const a of listed) {
    const files: string[] = []
    for (const l of b.lanes) {
      if (l.agentId === a.id && !files.includes(l.path)) files.push(l.path)
    }
    const shown = files.slice(0, 4).map(p => short(p, cwd))
    const more = files.length > shown.length ? ` +${files.length - shown.length} more` : ''
    lines.push(`  ${a.label} · ${a.status} · ${files.length > 0 ? shown.join(', ') + more : 'no writes'}`)
  }
  const total = b.refused + b.warned + b.mainWrites
  if (total === 0) {
    lines.push('contested: none')
  } else {
    lines.push(`contested: ${total} (${b.refused} refused, ${b.warned} allowed in warn mode, ${b.mainWrites} by the main loop) — last ${Math.min(5, b.contested.length)}:`)
    for (const c of b.contested.slice(-5)) {
      const what = c.kind === 'main' ? 'main loop wrote' : `${c.label} wanted`
      const verdict = c.kind === 'refused' ? 'refused' : c.kind === 'warned' ? 'allowed (warn)' : 'allowed'
      lines.push(`  ${ago(now - c.at)} · ${what} ${short(c.path, cwd)} (held by ${c.holderLabel}) · ${verdict}`)
    }
  }
  return lines.join('\n')
}

// ------------------------------------------------------------------------------------------------ hooks

export const register: Register = (on, options) => {
  const mode = asMode(options.mode)
  const attachContract = asFlag(options.attach_contract, true)
  const contractPaths = asPaths(options.contract_paths)

  on('session.start', async ($, e, next) => {
    try {
      await $.command.register({
        name: 'lanes',
        description: 'Which running agent holds which files, and what was refused',
        immediate: true,
      })
    } catch {
      // the command is a convenience
    }
    return next(e)
  }).catch(($, e, next) => next(e))

  on('command.run', { command: ['lanes', 'dojo-lanes:lanes'] }, async $ => {
    try {
      return { text: await lanesText($, mode) }
    } catch {
      return { text: 'Could not read the lanes.' }
    }
  }).catch(() => ({ text: 'Could not read the lanes.' }))

  // The lane claim. It judges before `next`, so the tool never runs for a refused write.
  on('tool.call', async ($, e, next) => {
    if (!WRITE_TOOLS.has(String(e.tool))) return next(e)
    let deny: string | undefined
    try {
      if (!(await standDown($))) deny = await guardWrite($, e as unknown as WriteCall, mode)
    } catch {
      // a coordination aid: a failure here never blocks a write
    }
    if (deny !== undefined) return { deny }
    return next(e)
  }).catch(($, e, next) => next(e))

  on('agent.spawn', async ($, e, next) => {
    let plan: SpawnPlan | undefined
    try {
      if (!(await standDown($))) plan = await planSpawn($, e, attachContract, contractPaths)
    } catch {
      plan = undefined
    }
    const r = await next(plan?.note !== undefined ? { ...e, prompt: `${e.prompt}\n\n${plan.note}` } : e)
    if (plan !== undefined && r.deny === undefined && r.agentId !== undefined) {
      try {
        const writers = await recordSpawn($, seedOfSpawn(e, r.agentId), plan.nudgeable)
        if (writers > 0) {
          $.ui.toast(
            `${writers} writing agents in flight and no contract file (Dojo rule 4). Lanes hold first-writer ownership; /lanes shows who holds what.`,
          )
        }
      } catch {
        // best effort
      }
    }
    return r
  }).catch(($, e, next) => next(e))

  on('turn.complete', async ($, e, next) => {
    const r = await next(e)
    if (e.agentId !== undefined) {
      try {
        if (!(await standDown($))) await endTurn($, e.agentId, e.reason)
      } catch {
        // best effort
      }
    }
    return r
  }).catch(($, e, next) => next(e))

  // A /clear or an exit ends the conversation the agents belonged to.
  on('session.end', async ($, e, next) => {
    try {
      await update($, board, () => EMPTY)
    } catch {
      // best effort
    }
    return next(e)
  }).catch(($, e, next) => next(e))
}
