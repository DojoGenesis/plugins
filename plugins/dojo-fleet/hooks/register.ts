import { atom, read, update } from 'claude-code'
import type { AgentInfo, EngineInterface, Register } from 'claude-code'

import type { FleetAgent, FleetStatus } from '../types'
import { renderAgentBar, renderChips, renderPane, renderPaneCards } from './views'
import type { CardsView, Chip, FleetActions, PaneCard, PaneView, Tone } from './views'
import {
  READ_TOOLS,
  WRITE_TOOLS,
  chipText,
  clip,
  countsOf,
  countsText,
  findAgent,
  fitCols,
  fmtDuration,
  glyphOf,
  isLive,
  isWriterBrief,
  nudgeText,
  parseSteer,
  plural,
  rowParts,
  rowText,
  shortModel,
  stallOf,
  summaryLines,
} from './model'

// dojo-fleet mod (early access). The fan-out made visible and steerable:
//  - a pane (/fleet) listing every subagent of the session, live: status, model, age, work done, stall reason;
//    pick one to steer it (a message into its running loop), nudge it, or stop it;
//  - a band above the prompt while agents run, which turns into the steering bar of the agent whose transcript
//    is open; it wraps whatever is drawn beneath it (dojo-meter's band), never replaces it;
//  - a stall tripwire: progress is judged by tool calls and files written, never by what an agent says; a stall
//    raises one toast; a nudge sends resume-with-constraints once; a second stall says build the track inline.
// It never writes the status line (dojo-router and dojo-verify own it) and never blocks a call.

const PANE = 'dojo-fleet'
const TICK_MS = 15000
const MAX_AGENTS = 200
// How long a non-workflow agent may be missing from `$.agent.list()` before it counts as ended.
const VANISH_MS = 60000
// After a turn ends, how soon the engine's task list is asked whether the agent is done or parked.
const RECHECK_MS = 2500
// Engine statuses that mean the agent is still held: a turn that ended there was not its last.
const HELD = new Set(['running', 'waiting', 'pending'])

const AGENTS = { plugin: 'dojo-fleet', key: 'agents' } as const
const agentsAtom = atom(AGENTS, [])
const tickAtom = atom({ plugin: 'dojo-fleet', key: 'tick' } as const, 0)
const selectedAtom = atom({ plugin: 'dojo-fleet', key: 'selected' } as const, null)
const hiddenAtom = atom({ plugin: 'dojo-fleet', key: 'isBandHidden' } as const, false)

type Settings = { limitMs: number; showBand: boolean; stallToast: boolean; autoOpen: boolean }

const isOn = (value: string | undefined): boolean =>
  typeof value === 'string' && ['1', 'true', 'yes'].includes(value.trim().toLowerCase())

function asFlag(value: unknown, fallback: boolean): boolean {
  if (typeof value === 'boolean') return value
  if (typeof value === 'string') {
    const text = value.trim().toLowerCase()
    if (['false', '0', 'no', 'off'].includes(text)) return false
    if (['true', '1', 'yes', 'on'].includes(text)) return true
  }
  return fallback
}

function asMinutes(value: unknown, fallback: number): number {
  const n = typeof value === 'number' ? value : typeof value === 'string' ? Number(value.trim()) : NaN
  return Number.isFinite(n) && n >= 0 ? n : fallback
}

// The names `$.env.get` may read must be string literals, so each is spelled out here.
async function standDown($: EngineInterface): Promise<boolean> {
  return isOn(await $.env.get('DOJO_OFF')) || isOn(await $.env.get('DOJO_FLEET_OFF'))
}

const settle = (agent: FleetAgent, status: FleetStatus, now: number, reason: string | undefined): FleetAgent => ({
  ...agent,
  status,
  reason,
  endedAt: now,
  inFlight: [],
  stallNoticedAt: undefined,
})

// A loop the mod never saw spawn (it started before the mod loaded): listed so it is not invisible.
function stranger(id: string, n: number, now: number): FleetAgent {
  return {
    id,
    n,
    label: `agent ${id.slice(0, 8)}`,
    type: 'unknown',
    model: '?',
    isWriter: true,
    brief: '',
    spawnedAt: now,
    status: 'running',
    tools: 0,
    reads: 0,
    writes: 0,
    errors: 0,
    inFlight: [],
    stalls: 0,
    nudges: 0,
    steers: 0,
  }
}

const nextNumber = (list: readonly FleetAgent[]): number => list.reduce((top, agent) => Math.max(top, agent.n), 0) + 1

async function agentsOf($: EngineInterface): Promise<FleetAgent[]> {
  return read($, agentsAtom)
}

// Brings the board in line with the engine's own task list: an agent killed or dropped without a turn.complete
// would otherwise sit 'running' forever. A turn.complete that arrives later still wins (it settles again).
// A workflow agent is never listed, so it is never settled for being absent.
async function reconcile($: EngineInterface): Promise<void> {
  let listed: AgentInfo[]
  try {
    listed = await $.agent.list()
  } catch {
    return
  }
  const byId = new Map(listed.map(info => [info.id, info]))
  const now = await $.clock.now()
  await update($, agentsAtom, list =>
    list.map(agent => {
      const info = byId.get(agent.id)
      const one = info !== undefined && agent.wasListed !== true ? { ...agent, wasListed: true } : agent
      if (one.status === 'stopped') return one
      if (!isLive(one)) {
        // Its turn ended, but the engine still holds it: parked on work of its own, it wakes for another turn.
        return info !== undefined && HELD.has(info.status) ? { ...one, status: 'waiting' as const, endedAt: undefined, reason: undefined } : one
      }
      if (info !== undefined) {
        if (info.status === 'killed') return settle(one, 'stopped', now, 'stopped (killed)')
        if (info.status === 'failed') return settle(one, 'failed', now, 'failed (task list)')
        if (info.status === 'completed') {
          // A parked agent the engine now calls done keeps the answer of its last turn.
          return one.status === 'waiting' ? { ...settle(one, 'returned', now, undefined), answer: one.answer } : settle(one, 'returned', now, 'ended; no final answer seen')
        }
        return one
      }
      const canVanish = one.runId === undefined && (one.wasListed === true || one.type !== 'unknown')
      return canVanish && now - one.spawnedAt >= VANISH_MS ? settle(one, 'failed', now, "no longer in the engine's task list") : one
    }),
  )
}

// Opens with the keyboard in it: arrows walk the rows, Enter picks one, Esc goes back to the prompt.
async function openPane($: EngineInterface): Promise<boolean> {
  const { isPlaced } = await $.ui.open({ id: PANE, title: 'Fleet', focus: true })
  return isPlaced
}

// Sends `message` into the agent's loop. Answers a plain sentence (a command's output is already headed with the
// plugin's name); the transcript line it logs carries the `dojo-fleet:` lead.
async function steer($: EngineInterface, id: string, message: string): Promise<string> {
  const text = message.trim()
  const agent = (await agentsOf($)).find(one => one.id === id)
  if (agent === undefined) return 'That agent is no longer listed.'
  if (text === '') return `Nothing to send to #${agent.n}.`
  const sent = await $.session.send({ to: { agentId: id }, text })
  if (!sent.isDelivered) {
    const line = `Could not reach #${agent.n} ${agent.label}: ${sent.reason}`
    $.ui.log(line)
    return line
  }
  await update($, agentsAtom, list => list.map(one => (one.id === id ? { ...one, steers: one.steers + 1 } : one)))
  const line = `Steered #${agent.n} ${agent.label}: "${clip(text, 160)}"`
  $.ui.log(line)
  return line
}

async function nudge($: EngineInterface, id: string, limitMs: number): Promise<void> {
  const agents = await agentsOf($)
  const agent = agents.find(one => one.id === id)
  if (agent === undefined || agent.status !== 'running') return
  const reason = stallOf(agent, agents, await $.clock.now(), limitMs) ?? 'a check-in asked by the person'
  const sent = await $.session.send({ to: { agentId: id }, text: nudgeText(agent, reason) })
  if (!sent.isDelivered) {
    $.ui.log(`could not nudge #${agent.n} ${agent.label}: ${sent.reason}`)
    return
  }
  await update($, agentsAtom, list => list.map(one => (one.id === id ? { ...one, nudges: one.nudges + 1 } : one)))
  $.ui.log(`nudged #${agent.n} ${agent.label} (${reason}). If it stalls again, stop it and build the track inline.`)
}

async function stop($: EngineInterface, id: string): Promise<void> {
  const agent = (await agentsOf($)).find(one => one.id === id)
  if (agent === undefined || !isLive(agent)) return
  const ran = await $.tool.call({ tool: 'TaskStop', task_id: id })
  if (ran.deny !== undefined || ran.isError === true) {
    $.ui.log(`could not stop #${agent.n} ${agent.label}: ${ran.deny ?? ran.text ?? 'TaskStop failed'}`)
    return
  }
  const now = await $.clock.now()
  await update($, agentsAtom, list => list.map(one => (one.id === id ? settle(one, 'stopped', now, 'stopped from the fleet') : one)))
  $.ui.log(`stopped #${agent.n} ${agent.label}.`)
}

// Every TICK_MS while agents run: move the clock the drawings read, and raise one toast per new stall.
async function tick($: EngineInterface, settings: Settings): Promise<void> {
  // Reconcile while anything is in play, and for two minutes after the last end (a turn's end may be a park).
  const before = await agentsOf($)
  const clockNow = await $.clock.now()
  const recent = before.some(agent => agent.endedAt !== undefined && clockNow - agent.endedAt < 120000)
  if (!before.some(isLive) && !recent) return
  await reconcile($)
  const agents = await agentsOf($)
  const now = await $.clock.now()
  await update($, tickAtom, () => now)
  const fresh: { agent: FleetAgent; reason: string }[] = []
  const cleared = new Set<string>()
  for (const agent of agents) {
    const reason = stallOf(agent, agents, now, settings.limitMs)
    if (reason !== undefined && agent.stallNoticedAt === undefined) fresh.push({ agent, reason })
    if (reason === undefined && agent.stallNoticedAt !== undefined) cleared.add(agent.id)
  }
  if (fresh.length === 0 && cleared.size === 0) return
  const noticed = new Set(fresh.map(one => one.agent.id))
  await update($, agentsAtom, list =>
    list.map(one => {
      if (noticed.has(one.id)) return { ...one, stallNoticedAt: now, stalls: one.stalls + 1 }
      if (cleared.has(one.id)) return { ...one, stallNoticedAt: undefined }
      return one
    }),
  )
  const first = fresh[0]
  if (first === undefined || !settings.stallToast) return
  const again = first.agent.nudges > 0
  const more = fresh.length > 1 ? ` (+${fresh.length - 1} more)` : ''
  $.ui.toast(
    again
      ? `#${first.agent.n} ${first.agent.label} stalled again after a nudge (${first.reason})${more}. Stop it and build the track inline.`
      : `#${first.agent.n} ${first.agent.label} looks stalled (${first.reason})${more}. /fleet to nudge, steer or stop it.`,
  )
}

function colorOf(agent: FleetAgent, stalled: boolean): Tone {
  if (agent.status === 'running') return stalled ? 'warning' : 'claude'
  if (agent.status === 'waiting') return 'suggestion'
  if (agent.status === 'returned') return 'success'
  if (agent.status === 'failed') return 'error'
  return 'subtle'
}

function thresholdText(limitMs: number): string {
  const minutes = limitMs / 60000
  return limitMs > 0 ? `stall after ${Number.isInteger(minutes) ? `${minutes}m` : fmtDuration(limitMs)}` : 'stall checks off'
}

// One agent as a desktop card: who, its state in its colour, what it is doing now, and the actions it takes.
function cardOf(agent: FleetAgent, now: number, stall: string | undefined, isSelected: boolean): PaneCard {
  const isStalled = stall !== undefined
  const work = agent.isWriter || agent.writes > 0 ? `${plural(agent.tools, 'tool')} · ${plural(agent.writes, 'write')}` : plural(agent.tools, 'tool')
  const current = agent.inFlight[agent.inFlight.length - 1]
  const doing =
    agent.status === 'running'
      ? current !== undefined
        ? `now ${current.tool} · ${fmtDuration(Math.max(0, now - current.since))}`
        : agent.lastTool !== undefined
          ? `last ${agent.lastTool}`
          : 'starting'
      : agent.status === 'waiting'
        ? 'waiting on its own background work'
        : undefined
  return {
    id: agent.id,
    n: agent.n,
    glyph: glyphOf(agent, isStalled),
    tone: colorOf(agent, isStalled),
    title: `#${agent.n} ${agent.label}`,
    status: isStalled ? 'stalled' : agent.reason !== undefined && !isLive(agent) ? `${agent.status} (${agent.reason})` : agent.status,
    meta: `${shortModel(agent.model)} · ${fmtDuration((agent.endedAt ?? now) - agent.spawnedAt)} · ${work}`,
    doing,
    stallLine: isStalled ? `looks stalled: ${stall}` : undefined,
    answer: agent.answer !== undefined && !isLive(agent) ? clip(agent.answer.replace(/\s+/g, ' '), 160) : undefined,
    isSelected,
    canSteer: isLive(agent),
    canNudge: agent.status === 'running',
    canStop: isLive(agent),
  }
}

// Every action a drawing offers, bound to one `$`: views.tsx draws, these act. Top level, because `$` may only be
// handed to a function declared at the top of the module.
function actionsFor($: EngineInterface, limitMs: number): FleetActions {
  return {
    select: id => update($, selectedAtom, () => id),
    steer: (id, text) => void steer($, id, text),
    nudge: id => nudge($, id, limitMs),
    stop: id => stop($, id),
    close: () => update($, selectedAtom, () => null),
    open: () => openPane($),
    hide: () => update($, hiddenAtom, () => true),
  }
}

export const register: Register = (on, options) => {
  const settings: Settings = {
    limitMs: asMinutes(options.stall_minutes, 10) * 60000,
    showBand: asFlag(options.show_band, true),
    stallToast: asFlag(options.stall_toast, true),
    autoOpen: asFlag(options.auto_open, true),
  }
  let isOff = false
  let timer: { cancel: () => void } | undefined
  // Whether this wave has already opened the pane by itself (auto_open); a new wave starts it over.
  let isAutoOpened = false

  on('session.start', async ($, e, next) => {
    isOff = await standDown($)
    // DOJO_FLEET_STALL_MINUTES overrides the option, for hosts with no settings to hold it (headless, SDK, tests).
    const override = await $.env.get('DOJO_FLEET_STALL_MINUTES')
    if (override !== undefined && override.trim() !== '') settings.limitMs = asMinutes(override, settings.limitMs / 60000) * 60000
    if (!isOff) {
      await $.command.register({
        name: 'fleet',
        description: 'Every subagent of this session: status, model, work done, stalls. Opens the Fleet pane.',
        argumentHint: '[list]',
        immediate: true,
      })
      await $.command.register({
        name: 'steer',
        description: 'Send a message into a running subagent (by #number or name).',
        argumentHint: '<#n|name> <message>',
        immediate: true,
      })
      timer?.cancel()
      timer = $.clock.every(TICK_MS, () => void tick($, settings))
    }
    return next(e)
  })

  on('agent.spawn', async ($, e, next) => {
    const started = await next(e)
    const id = started.agentId
    if (isOff || id === undefined) return started
    const now = await $.clock.now()
    let isNewWave = false
    const info = {
      label: clip(e.name ?? (e.description || e.subagentType), 40),
      type: e.subagentType,
      model: started.model,
      parentId: e.parentAgentId,
      runId: e.workflow?.runId,
      isWriter: isWriterBrief(e.subagentType, e.prompt),
      brief: clip(e.prompt, 400),
    }
    await update($, agentsAtom, list => {
      // Its first tool call, or even its end, may have landed before this continuation ran: fill the facts in and
      // keep what was counted (and a settled status: no resurrection).
      if (list.some(one => one.id === id)) return list.map(one => (one.id === id ? { ...one, ...info } : one))
      isNewWave = !list.some(isLive)
      const agent: FleetAgent = {
        id,
        n: nextNumber(list),
        ...info,
        spawnedAt: now,
        status: 'running',
        tools: 0,
        reads: 0,
        writes: 0,
        errors: 0,
        inFlight: [],
        stalls: 0,
        nudges: 0,
        steers: 0,
      }
      return [...list, agent].slice(-MAX_AGENTS)
    })
    if (isNewWave) {
      await update($, hiddenAtom, () => false)
      isAutoOpened = false
    }
    // A fan-out (two agents alive at once) opens the pane, once per wave, without taking the keyboard. Seen live:
    // the pane went unseen unless /fleet was typed. The engine places an unasked pane only where there is room
    // (a docked pane, or a terminal at least 144 columns wide) and otherwise holds it until the person opens it.
    if (settings.autoOpen && !isAutoOpened && (await read($, agentsAtom)).filter(isLive).length >= 2) {
      isAutoOpened = true
      await $.ui.open({ id: PANE, title: 'Fleet' }).catch(() => undefined)
    }
    return started
  }).catch(($, e, next) => next(e)) // bookkeeping only: never stand between a spawn and its agent

  on('tool.call', async ($, e, next) => {
    const id = e.agentId
    if (isOff || id === undefined) return next(e)
    const tool = String(e.tool)
    const startedAt = await $.clock.now()
    const callId = e.tool_use_id || `${tool}@${startedAt}`
    await update($, agentsAtom, list => {
      const known = list.some(one => one.id === id)
      const all = known ? list : [...list, stranger(id, nextNumber(list), startedAt)]
      return all.map(one => {
        if (one.id !== id) return one
        // A settled agent that calls a tool again was resumed (SendMessage after a stop, a teammate waking).
        const awake = one.status === 'running' ? one : { ...one, status: 'running' as const, endedAt: undefined, reason: undefined }
        return {
          ...awake,
          tools: awake.tools + 1,
          lastTool: tool,
          lastToolAt: startedAt,
          inFlight: [...awake.inFlight, { id: callId, tool, since: startedAt }].slice(-20),
        }
      })
    })
    let ran: Awaited<ReturnType<typeof next>> | undefined
    try {
      ran = await next(e)
      return ran
    } finally {
      const endedAt = await $.clock.now()
      const isOk = ran !== undefined && ran.deny === undefined && ran.isError !== true
      const isWrite = isOk && WRITE_TOOLS.has(tool)
      await update($, agentsAtom, list =>
        list.map(one =>
          one.id !== id
            ? one
            : {
                ...one,
                inFlight: one.inFlight.filter(call => call.id !== callId),
                lastToolAt: endedAt,
                // An agent that writes is a writer, whatever its brief said.
                isWriter: one.isWriter || isWrite,
                reads: one.reads + (READ_TOOLS.has(tool) ? 1 : 0),
                writes: one.writes + (isWrite ? 1 : 0),
                lastWriteAt: isWrite ? endedAt : one.lastWriteAt,
                errors: one.errors + (isOk ? 0 : 1),
              },
        ),
      )
    }
  }).catch(($, e, next) => next(e)) // bookkeeping only: a failure here never refuses the call

  on('turn.complete', async ($, e, next) => {
    const id = e.agentId
    if (!isOff && id !== undefined) {
      const now = await $.clock.now()
      const answer = e.answer.trim()
      const isAborted = e.isAborted || e.reason === 'aborted'
      const status: FleetStatus = isAborted ? 'aborted' : e.reason === 'answer' && answer !== '' ? 'returned' : 'failed'
      const reason =
        status === 'returned'
          ? undefined
          : isAborted
            ? 'interrupted'
            : e.reason === 'refusal'
              ? 'refused'
              : e.reason === 'error'
                ? 'ended on an API error'
                : 'returned an empty answer'
      await update($, agentsAtom, list =>
        // An end that beat the spawn record: keep it, the spawn fills the facts in later.
        (list.some(one => one.id === id) ? list : [...list, stranger(id, nextNumber(list), now)]).map(one => {
          if (one.id !== id) return one
          // A stop from the fleet ends the turn as aborted: keep saying it was stopped.
          if (one.status === 'stopped' && isAborted) return one
          return { ...settle(one, status, now, reason), answer: answer === '' ? undefined : clip(answer, 400) }
        }),
      )
      // A turn's end may be a park: ask the engine shortly whether it is done or still holds the agent.
      $.clock.after(RECHECK_MS, () => void reconcile($))
    }
    return next(e)
  })

  // `/fleet` opens the pane and says one line (the pane holds the list); `/fleet list`, or a surface that placed
  // no pane, answers the whole list as text.
  on('command.run', { command: ['fleet', 'dojo-fleet:fleet'] }, async ($, e) => {
    await reconcile($)
    const now = await $.clock.now()
    const agents = await agentsOf($)
    const lines = summaryLines(agents, now, settings.limitMs)
    if (e.args.trim().toLowerCase() === 'list') return { text: lines.join('\n') }
    // The engine's own task list, raw: what the board is reconciled against.
    if (e.args.trim().toLowerCase() === 'engine') {
      const listed = await $.agent.list().catch(() => [] as AgentInfo[])
      if (listed.length === 0) return { text: 'The engine lists no agents right now.' }
      return { text: listed.map(one => `${one.id.slice(0, 12)}  ${one.status.padEnd(9)} ${one.type}  ${one.description}`).join('\n') }
    }
    const isPlaced = await openPane($)
    if (!isPlaced) return { text: lines.join('\n') }
    const head = agents.length === 0 ? 'No subagent yet' : countsText(countsOf(agents, now, settings.limitMs))
    return { text: `${head}. The Fleet pane is open: pick a row to steer, nudge or stop it. /fleet list prints the list.` }
  })

  on('command.run', { command: 'steer' }, async ($, e) => {
    const { ref, text } = parseSteer(e.args)
    const agents = await agentsOf($)
    const running = agents.filter(one => one.status === 'running')
    const list = running.length === 0 ? 'none running' : running.map(one => `#${one.n} ${one.label}`).join(', ')
    if (ref === '') return { text: `Usage: /steer <#n|name> <message>. Running: ${list}.` }
    const agent = findAgent(agents, ref)
    if (agent === undefined) return { text: `No agent matches "${ref}". Running: ${list}.` }
    if (text === '') return { text: `What should #${agent.n} ${agent.label} hear? /steer ${ref} <message>` }
    return { text: await steer($, agent.id, text) }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const agents = await read($, agentsAtom)
    await read($, tickAtom)
    const selectedId = await read($, selectedAtom)
    const now = await $.clock.now()
    const width = Math.max(20, e.props.bodyColumns - 2)
    const room = Math.max(3, (e.viewport?.rows ?? 24) - (selectedId === null ? 6 : 16))
    const counts = countsOf(agents, now, settings.limitMs)
    // Most urgent first: stalled, running, waiting, then the settled.
    const stalls = new Map(agents.map(agent => [agent.id, stallOf(agent, agents, now, settings.limitMs)]))
    const order = (agent: FleetAgent) =>
      stalls.get(agent.id) !== undefined ? 0 : agent.status === 'running' ? 1 : agent.status === 'waiting' ? 2 : 3
    const sorted = [...agents].sort((a, b) => order(a) - order(b) || b.n - a.n)
    // Surfaces with proportional type draw a card per agent (seen live: the terminal's fixed-width columns read
    // raggedly in the desktop app, and the actions waited behind a pick-a-row step). The terminal keeps its rows.
    if (e.surface !== 'terminal') {
      const fits = Math.max(2, Math.floor((e.viewport?.rows ?? 40) / 6))
      const cards = sorted.slice(0, fits)
      const view: CardsView = {
        title: agents.length === 0 ? 'Fleet' : `Fleet — ${countsText(counts)}`,
        threshold: thresholdText(settings.limitMs),
        isEmpty: agents.length === 0,
        cards: cards.map(agent => cardOf(agent, now, stalls.get(agent.id), agent.id === selectedId)),
        more: sorted.length - cards.length,
      }
      return renderPaneCards($.ui.resolve(e), view, actionsFor($, settings.limitMs))
    }
    const shown = sorted.slice(0, room)
    const parts = shown.map(agent => rowParts(agent, now, stalls.get(agent.id)))
    const selected = agents.find(one => one.id === selectedId)
    const stall = selected === undefined ? undefined : stalls.get(selected.id)
    const isTripped = selected !== undefined && selected.nudges > 0 && selected.stalls >= 2 && stall !== undefined
    const minutes = settings.limitMs / 60000
    const view: PaneView = {
      title: agents.length === 0 ? 'Fleet' : `Fleet — ${countsText(counts)}`,
      threshold: settings.limitMs > 0 ? `stall after ${Number.isInteger(minutes) ? `${minutes}m` : fmtDuration(settings.limitMs)}` : 'stall checks off',
      isEmpty: agents.length === 0,
      rows: shown.map((agent, i) => {
        const isStalled = stalls.get(agent.id) !== undefined
        return {
          id: agent.id,
          glyph: glyphOf(agent, isStalled),
          tone: colorOf(agent, isStalled),
          parts: parts[i] ?? rowParts(agent, now, undefined),
          isPlain: agent.status === 'running' && !isStalled,
          isSelected: agent.id === selectedId,
          isFirst: i === 0,
        }
      }),
      cols: fitCols(parts, width),
      more: sorted.length - shown.length,
      detail:
        selected === undefined
          ? undefined
          : {
              id: selected.id,
              n: selected.n,
              title: `#${selected.n} ${selected.label}`,
              facts: `${selected.type} · ${shortModel(selected.model)} · ${selected.status}${selected.reason ? ` (${selected.reason})` : ''} · ${fmtDuration((selected.endedAt ?? now) - selected.spawnedAt)}`,
              stallLine:
                stall === undefined
                  ? undefined
                  : isTripped
                    ? `stalled again after a nudge (${stall}): stop it and build this track inline`
                    : `looks stalled: ${stall}`,
              stats: `${plural(selected.tools, 'tool')} · ${plural(selected.reads, 'read')} · ${plural(selected.writes, 'write')} · ${plural(selected.errors, 'error')} · steered ${selected.steers} · nudged ${selected.nudges}`,
              brief: selected.brief === '' ? undefined : clip(selected.brief, width * 2),
              answer:
                selected.answer === undefined
                  ? undefined
                  : `${selected.status === 'waiting' ? 'last turn' : 'answer'}  ${clip(selected.answer, width * 2)}`,
              canSteer: isLive(selected),
              canNudge: selected.status === 'running',
              canStop: isLive(selected),
            },
    }
    return renderPane($.ui.resolve(e), view, actionsFor($, settings.limitMs))
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (isOff || !settings.showBand || e.props.hasSurvey) return next(e)
    const agents = await read($, agentsAtom)
    await read($, tickAtom)
    const isHidden = await read($, hiddenAtom)
    const viewing = e.props.view.agentId === undefined ? undefined : agents.find(one => one.id === e.props.view.agentId)
    if (viewing === undefined && (!agents.some(isLive) || isHidden)) return next(e)

    const now = await $.clock.now()
    const width = Math.max(20, e.props.bodyColumns)
    const below = await next(e)

    if (viewing !== undefined) {
      const reason = stallOf(viewing, agents, now, settings.limitMs)
      const bar = {
        id: viewing.id,
        glyph: glyphOf(viewing, reason !== undefined),
        tone: colorOf(viewing, reason !== undefined),
        text: clip(rowText(viewing, now, reason), Math.max(20, width - 34)),
        canNudge: viewing.status === 'running',
        canStop: isLive(viewing),
      }
      return renderAgentBar($.ui.resolve(e), bar, actionsFor($, settings.limitMs), below)
    }

    // One chip per agent in play, stalled ones first, as many as fit beside the counts and the two buttons.
    const counts = countsOf(agents, now, settings.limitMs)
    const live = agents
      .filter(isLive)
      .map(one => ({ one, stall: stallOf(one, agents, now, settings.limitMs) }))
      .sort((a, b) => Number(b.stall !== undefined) - Number(a.stall !== undefined) || a.one.n - b.one.n)
    const tally = countsText(counts)
    let budget = width - 'fleet'.length - tally.length - '[ Open ] [ Hide ]'.length - 8
    const chips: Chip[] = []
    for (const { one, stall } of live) {
      const text = `${glyphOf(one, stall !== undefined)} ${chipText(one, now, stall)}`
      if (text.length + 2 > budget) break
      budget -= text.length + 2
      chips.push({ id: one.id, tone: colorOf(one, stall !== undefined), text })
    }
    return renderChips($.ui.resolve(e), chips, live.length - chips.length, tally, actionsFor($, settings.limitMs), below)
  })
}
