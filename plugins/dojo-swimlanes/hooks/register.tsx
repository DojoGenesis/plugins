import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Call, LaneAgent, LaneStatus, Timeline } from '../types'
import { MAX_AGENTS, MAX_CALLS, MAX_DENY, buildLanesSvg, clip, headerLine, isLive, kindOf, svgAlt, targetOf, termRows, textForm, viewOf } from './model'

// dojo-swimlanes mod (early access). A subagent fan-out as a timeline: one lane per agent, time left to right, a
// mark per tool call. /swimlanes opens the pane: an interactive SVG where the surface has Svg, rows of text where
// it has not. It only watches: it never blocks a call and never writes the status line.

const PANE = 'dojo-swimlanes'
const TICK_MS = 1000
// After a turn ends, how soon the engine's task list is asked whether the agent is done or parked.
const RECHECK_MS = 2500
const HELD = new Set(['running', 'waiting', 'pending'])

const timelineAtom = atom({ plugin: 'dojo-swimlanes', key: 'timeline' } as const, { agents: [], nextN: 1 } as Timeline)
const tickAtom = atom({ plugin: 'dojo-swimlanes', key: 'tick' } as const, 0)
const allAtom = atom({ plugin: 'dojo-swimlanes', key: 'isAll' } as const, false)

const isOn = (value: string | undefined): boolean => typeof value === 'string' && ['1', 'true', 'yes', 'on'].includes(value.trim().toLowerCase())

// The names `$.env.get` may read must be string literals, so each is spelled out here.
async function standDown($: EngineInterface): Promise<boolean> {
  if (!isEnabled) return true
  return isOn(await $.env.get('DOJO_OFF')) || isOn(await $.env.get('DOJO_SWIMLANES_OFF'))
}

// The redraw timer, one per registration (a hot reload drops it with the module).
type Timer = { handle?: { cancel: () => void } }

const fresh = (id: string, n: number, now: number): LaneAgent => ({
  id,
  n,
  label: `agent ${id.slice(0, 8)}`,
  type: 'unknown',
  spawnedAt: now,
  status: 'running',
  calls: [],
})

// Applies `change` to the agent `id`, adding a stranger (an agent the mod never saw spawn) when it is unknown.
function withAgent(tl: Timeline, id: string, now: number, change: (one: LaneAgent) => LaneAgent): Timeline {
  const known = tl.agents.some(one => one.id === id)
  const base = known ? tl : { agents: [...tl.agents, fresh(id, tl.nextN, now)].slice(-MAX_AGENTS), nextN: tl.nextN + 1 }
  return { ...base, agents: base.agents.map(one => (one.id === id ? change(one) : one)) }
}

// While any agent is live, bump the tick every second; stop the timer when none is.
async function pulse($: EngineInterface, timer: Timer): Promise<void> {
  const tl = await read($, timelineAtom)
  if (!tl.agents.some(isLive)) {
    timer.handle?.cancel()
    timer.handle = undefined
    return
  }
  await update($, tickAtom, n => n + 1)
}

function ensureTimer($: EngineInterface, timer: Timer): void {
  if (timer.handle !== undefined) return
  timer.handle = $.clock.every(TICK_MS, () => void pulse($, timer))
}

// Tells a parked agent from a finished one: the engine still holds a parked agent.
async function recheck($: EngineInterface, timer: Timer, id: string): Promise<void> {
  let listed
  try {
    listed = await $.agent.list()
  } catch {
    return
  }
  const info = listed.find(one => one.id === id)
  if (info === undefined || !HELD.has(info.status)) return
  await update($, timelineAtom, tl => ({
    ...tl,
    agents: tl.agents.map(one => (one.id === id && !isLive(one) ? { ...one, status: 'waiting' as const } : one)),
  }))
  ensureTimer($, timer)
}

async function openPane($: EngineInterface): Promise<boolean> {
  const { isPlaced } = await $.ui.open({ id: PANE, title: 'Swimlanes', focus: true })
  return isPlaced
}

// The `enabled` option (userConfig): false turns the mod into a pass-through, as the kill switches do.
let isEnabled = true

function asFlag(value: unknown, fallback: boolean): boolean {
  if (typeof value === 'boolean') return value
  if (typeof value === 'string') {
    const text = value.trim().toLowerCase()
    if (['false', '0', 'no', 'off'].includes(text)) return false
    if (['true', '1', 'yes', 'on'].includes(text)) return true
  }
  return fallback
}

export const register: Register = (on, options) => {
  isEnabled = asFlag(options.enabled, true)
  let isOff = false
  const timer: Timer = {}

  on('session.start', async ($, e, next) => {
    isOff = await standDown($)
    if (!isOff) {
      await $.command.register({
        name: 'swimlanes',
        description: 'The subagent fan-out as a timeline: one lane per agent, a mark per tool call. Opens the Swimlanes pane.',
        argumentHint: '[text|all]',
        immediate: true,
      })
    }
    return next(e)
  })

  on('agent.spawn', async ($, e, next) => {
    const started = await next(e)
    const id = started.agentId
    if (isOff || id === undefined) return started
    const now = await $.clock.now()
    const info = {
      label: clip(e.name ?? (e.description || e.subagentType), 40),
      type: e.subagentType,
      model: started.model,
    }
    await update($, timelineAtom, tl => {
      // Its first call, or even its end, may have landed before this continuation ran: fill the facts in.
      if (tl.agents.some(one => one.id === id)) return { ...tl, agents: tl.agents.map(one => (one.id === id ? { ...one, ...info } : one)) }
      const agent: LaneAgent = { id, n: tl.nextN, ...info, spawnedAt: now, status: 'running', calls: [] }
      return { agents: [...tl.agents, agent].slice(-MAX_AGENTS), nextN: tl.nextN + 1 }
    })
    ensureTimer($, timer)
    return started
  }).catch(($, e, next) => next(e)) // bookkeeping only: never stand between a spawn and its agent

  on('tool.call', async ($, e, next) => {
    const id = e.agentId
    if (isOff || id === undefined) return next(e)
    const tool = String(e.tool)
    const t0 = await $.clock.now()
    const callId = e.tool_use_id || `${tool}@${t0}`
    const call: Call = { id: callId, tool, kind: kindOf(tool), t0, target: targetOf(e) }
    await update($, timelineAtom, tl =>
      withAgent(tl, id, t0, one => {
        // A settled agent that calls a tool again was resumed.
        const awake = one.status === 'running' ? one : { ...one, status: 'running' as const, endedAt: undefined }
        return { ...awake, calls: [...awake.calls, call].slice(-MAX_CALLS) }
      }),
    )
    ensureTimer($, timer)
    let ran: Awaited<ReturnType<typeof next>> | undefined
    let failure: unknown
    try {
      ran = await next(e)
      return ran
    } catch (error) {
      failure = error
      throw error
    } finally {
      const t1 = await $.clock.now()
      let deny: string | undefined
      if (ran !== undefined && ran.deny !== undefined) deny = ran.deny
      else if (ran !== undefined && ran.isError === true) deny = ran.text ?? 'the call errored'
      else if (failure !== undefined) deny = failure instanceof Error ? failure.message : String(failure)
      const ok = deny === undefined
      await update($, timelineAtom, tl => ({
        ...tl,
        agents: tl.agents.map(one =>
          one.id !== id
            ? one
            : {
                ...one,
                calls: one.calls.map(c => (c.id === callId ? { ...c, t1, ok, deny: deny === undefined ? undefined : clip(deny, MAX_DENY) } : c)),
              },
        ),
      }))
    }
  }).catch(($, e, next) => next(e)) // bookkeeping only: a failure here never refuses the call

  on('turn.complete', async ($, e, next) => {
    const id = e.agentId
    if (!isOff && id !== undefined) {
      try {
        const now = await $.clock.now()
        const answer = e.answer.trim()
        const isAborted = e.isAborted || e.reason === 'aborted'
        const status: LaneStatus = isAborted ? 'aborted' : e.reason === 'answer' && answer !== '' ? 'returned' : 'failed'
        await update($, timelineAtom, tl => withAgent(tl, id, now, one => ({ ...one, status, endedAt: now })))
        // A turn's end may be a park: ask the engine shortly whether it is done or still holds the agent.
        $.clock.after(RECHECK_MS, () => void recheck($, timer, id))
      } catch {
        // bookkeeping only
      }
    }
    return next(e)
  })

  on('command.run', { command: ['swimlanes', 'dojo-swimlanes:swimlanes'] }, async ($, e) => {
    const arg = e.args.trim().toLowerCase()
    let isAll = await read($, allAtom)
    if (arg === 'all') {
      isAll = !isAll
      await update($, allAtom, () => isAll)
    }
    const tl = await read($, timelineAtom)
    const now = await $.clock.now()
    const view = viewOf(tl.agents, isAll)
    if (arg === 'text') return { text: textForm(view, now, 72) }
    const placed = await openPane($)
    if (tl.agents.length === 0) return { text: 'No subagent has run yet' }
    if (!placed) return { text: textForm(view, now, 72) }
    return { text: `${view.agents.length} agents in view` }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const tl = await read($, timelineAtom)
    await read($, tickAtom)
    const isAll = await read($, allAtom)
    const now = await $.clock.now()
    const view = viewOf(tl.agents, isAll)
    const els = $.ui.resolve(e)
    const { Box, Text, Button } = els
    const toggle = () => update($, allAtom, v => !v)
    const toggleButton = (
      <Button key="all" autoFocus onPress={toggle}>
        {isAll ? 'Latest wave only' : 'Show all agents'}
      </Button>
    )
    if (view.agents.length === 0) {
      return (
        <Box flexDirection="column">
          <Text dimColor>No subagent has run yet.</Text>
          {toggleButton}
        </Box>
      )
    }
    const head = headerLine(view, now)
    if (e.surface !== 'terminal' && 'Svg' in els) {
      const { Svg } = els
      // Seen live on the desktop: an interactive Svg is a sandboxed frame, and a new source each second reloads
      // it, so the pane blinked once a second. While any lane is live the chart is a plain image the surface
      // swaps in place; once the wave settles it stops changing and becomes interactive, tooltips included.
      const isSettled = !view.agents.some(isLive)
      return (
        <Box flexDirection="column">
          <Text bold>{head}</Text>
          <Svg source={buildLanesSvg(view, now, e.props.bodyColumns)} alt={svgAlt(view, now)} isInteractive={isSettled} />
          {toggleButton}
        </Box>
      )
    }
    const { rows, axis } = termRows(view, now, Math.max(30, e.props.bodyColumns - 2))
    return (
      <Box flexDirection="column">
        <Text bold>{head}</Text>
        {rows.map(row => (
          <Text>{`${row.head}  ${row.strip}  ${row.tail}`}</Text>
        ))}
        <Text dimColor>{axis}</Text>
        {toggleButton}
      </Box>
    )
  })
}
