import type { FleetAgent } from '../types'

// Pure logic of dojo-fleet: no `$`, so the tests and the hooks read the same rules.

// Agent types not expected to write files (the four orchestration mods share this list).
const READ_ONLY_TYPES = new Set([
  'Explore',
  'Plan',
  'claude-code-guide',
  'statusline-setup',
  'dojo-protocol:scout',
  'dojo-protocol:reviewer',
  'dojo-protocol:judge',
])
const READ_ONLY_SUFFIX = /:(scout|reviewer|judge|researcher)$/

export const WRITE_TOOLS = new Set(['Edit', 'Write', 'NotebookEdit', 'MultiEdit'])
export const READ_TOOLS = new Set(['Read', 'Grep', 'Glob', 'Bash', 'WebFetch', 'WebSearch', 'NotebookRead', 'LSP'])

// Still in play: running, or parked on background work of its own.
export const isLive = (agent: FleetAgent): boolean => agent.status === 'running' || agent.status === 'waiting'

export const isWriterType = (type: string): boolean => !READ_ONLY_TYPES.has(type) && !READ_ONLY_SUFFIX.test(type)

// A brief that rules writing out, and the verbs of one that asks for it.
const NO_WRITE = /\b(write nothing|writes? no files?|do not (write|edit|modify|change)|don'?t (write|edit|modify|change)|read[- ]only|no (writes|edits))\b/i
const WRITE_VERB = /\b(edit|write|implement|fix|create|add|refactor|update|build|patch|append|rename|delete|remove|migrate|scaffold)\b/i

// Whether the stall check should expect files written: a type that can write AND a brief that asks it to. A
// general-purpose agent sent to read and report is not a builder; one that does write becomes one (tool.call).
export function isWriterBrief(type: string, prompt: string): boolean {
  if (!isWriterType(type) || NO_WRITE.test(prompt)) return false
  return WRITE_VERB.test(prompt)
}

export const clip = (text: string, max: number): string => {
  const flat = text.replace(/\s+/g, ' ').trim()
  return flat.length <= max ? flat : `${flat.slice(0, max - 1)}…`
}

export function fmtDuration(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m${String(s % 60).padStart(2, '0')}s`
  return `${Math.floor(m / 60)}h${String(m % 60).padStart(2, '0')}m`
}

// Why a running agent looks stalled, or undefined. Progress is judged by what the agent does (tool calls,
// files written), never by what it says. An agent waiting on running children of its own is not stalled.
export function stallOf(agent: FleetAgent, all: readonly FleetAgent[], now: number, limitMs: number): string | undefined {
  if (agent.status !== 'running' || limitMs <= 0) return undefined
  if (all.some(other => other.parentId === agent.id && isLive(other))) return undefined
  const hung = agent.inFlight.reduce<{ tool: string; since: number } | undefined>(
    (oldest, call) => (oldest === undefined || call.since < oldest.since ? call : oldest),
    undefined,
  )
  if (hung !== undefined && now - hung.since >= limitMs) return `${hung.tool} has not returned in ${fmtDuration(now - hung.since)}`
  const quiet = now - (agent.lastToolAt ?? agent.spawnedAt)
  if (hung === undefined && quiet >= limitMs) return `no tool call in ${fmtDuration(quiet)}`
  if (agent.isWriter) {
    const dry = now - (agent.lastWriteAt ?? agent.spawnedAt)
    if (dry >= limitMs) return agent.writes === 0 ? `nothing written in ${fmtDuration(dry)}` : `no write in ${fmtDuration(dry)}`
  }
  return undefined
}

export type FleetCounts = { running: number; waiting: number; stalled: number; returned: number; failed: number; stopped: number }

export function countsOf(agents: readonly FleetAgent[], now: number, limitMs: number): FleetCounts {
  const counts: FleetCounts = { running: 0, waiting: 0, stalled: 0, returned: 0, failed: 0, stopped: 0 }
  for (const agent of agents) {
    if (agent.status === 'running') {
      counts.running += 1
      if (stallOf(agent, agents, now, limitMs) !== undefined) counts.stalled += 1
    } else if (agent.status === 'waiting') counts.waiting += 1
    else if (agent.status === 'returned') counts.returned += 1
    else if (agent.status === 'stopped') counts.stopped += 1
    else counts.failed += 1
  }
  return counts
}

export function countsText(c: FleetCounts): string {
  const parts = [`${c.running} running`]
  if (c.stalled > 0) parts.push(`${c.stalled} stalled`)
  if (c.waiting > 0) parts.push(`${c.waiting} waiting`)
  if (c.returned > 0) parts.push(`${c.returned} returned`)
  if (c.failed > 0) parts.push(`${c.failed} failed`)
  if (c.stopped > 0) parts.push(`${c.stopped} stopped`)
  return parts.join(' · ')
}

// `#3`, `3`, an agent id, or the start of a label (case-insensitive); the newest match wins.
export function findAgent(agents: readonly FleetAgent[], ref: string): FleetAgent | undefined {
  const want = ref.trim().replace(/^#/, '')
  if (want === '') return undefined
  if (/^\d+$/.test(want)) return agents.find(agent => agent.n === Number(want))
  const byId = agents.find(agent => agent.id === want)
  if (byId !== undefined) return byId
  const lower = want.toLowerCase()
  return [...agents].reverse().find(agent => agent.label.toLowerCase().startsWith(lower))
}

// Split `/steer <agent> <message>`: the first word names the agent.
export function parseSteer(args: string): { ref: string; text: string } {
  const trimmed = args.trim()
  const space = trimmed.search(/\s/)
  return space < 0 ? { ref: trimmed, text: '' } : { ref: trimmed.slice(0, space), text: trimmed.slice(space + 1).trim() }
}

export function glyphOf(agent: FleetAgent, stalled: boolean): string {
  if (agent.status === 'running') return stalled ? '▲' : '●'
  if (agent.status === 'waiting') return '◐'
  if (agent.status === 'returned') return '✓'
  if (agent.status === 'stopped') return '■'
  if (agent.status === 'aborted') return '○'
  return '✗'
}

// The resume-with-constraints message: it unwedges a stalled agent once; a second stall means the track is
// built inline instead.
export function nudgeText(agent: FleetAgent, reason: string): string {
  const head = `dojo-fleet check-in for #${agent.n} ${agent.label}: from outside you look stalled (${reason}).`
  if (!agent.isWriter) {
    return [
      head,
      'From here: if a command hangs or something blocks you, stop and report what you have so far, and what blocks you;',
      'otherwise finish the reading you need and return your result soon. Never run anything that blocks.',
    ].join(' ')
  }
  return [
    head,
    'From here: make your next tool call a Write or Edit of a file you own, within your next few calls;',
    'work in small write → build → test cycles; never run anything that blocks (servers, watch modes, GUI binaries);',
    'if a command hangs, stop it and report instead of waiting. If something blocks you, say what and return now.',
  ].join(' ')
}

export const plural = (n: number, word: string): string => `${n} ${word}${n === 1 ? '' : 's'}`

// `claude-haiku-5-5` reads as `haiku 5.5`; any other id is kept, cut to 16 characters.
export function shortModel(model: string): string {
  const m = /^(?:claude-)?([a-z]+)-(\d+)-(\d+)/.exec(model)
  if (m !== null) return `${m[1]} ${m[2]}.${m[3]}`
  return model.length > 16 ? `${model.slice(0, 15)}…` : model
}

// One agent's row, field by field, so a list can align them in columns.
export type RowParts = { id: string; label: string; model: string; age: string; work: string; tail: string }

export function rowParts(agent: FleetAgent, now: number, stalled: string | undefined): RowParts {
  const work = agent.isWriter ? `${plural(agent.tools, 'tool')} · ${plural(agent.writes, 'write')}` : plural(agent.tools, 'tool')
  const tail =
    agent.status === 'running'
      ? (stalled ?? (agent.lastTool ? `last ${agent.lastTool}` : 'starting'))
      : agent.status === 'waiting'
        ? 'waiting on its own background work'
        : (agent.reason ?? agent.status)
  return {
    id: `#${agent.n}`,
    label: agent.label,
    model: shortModel(agent.model),
    age: fmtDuration((agent.endedAt ?? now) - agent.spawnedAt),
    work,
    tail,
  }
}

// Column widths of the pane's rows, in character cells.
export type Cols = { id: number; label: number; model: number; age: number; work: number }

// The widest each column grows, and the least the pane keeps for the tail (a stall reason, the last tool).
const COL_CAPS: Cols = { id: 6, label: 24, model: 16, age: 7, work: 22 }
const ROW_CHROME = 2 // the glyph and the space before the id, drawn inside the id Button
const MIN_TAIL = 12

// Column widths that fit `available` cells. A pane row is: [glyph id] label model age work tail, one gap between
// each. Left alone the fixed boxes shrink together once the row is wider than the pane, and a short cell such as
// "haiku 5.5" or "25s" wraps. So the columns are sized to the pane here, the tail takes whatever is left, and a
// narrow pane gives up, in order: label width down to 10, the work column, label width down to 6, then model and
// age width (their text is truncated, never wrapped). A work width of 0 means the column is not drawn, and the
// label takes its room back. Wide panes get each column's natural width, so nothing changes for them.
export function fitCols(parts: readonly RowParts[], available: number): Cols {
  const natural = (pick: (p: RowParts) => string, cap: number) => Math.min(cap, Math.max(1, ...parts.map(p => pick(p).length)))
  const cols: Cols = {
    id: natural(p => p.id, COL_CAPS.id),
    label: natural(p => p.label, COL_CAPS.label),
    model: natural(p => p.model, COL_CAPS.model),
    age: natural(p => p.age, COL_CAPS.age),
    work: natural(p => p.work, COL_CAPS.work),
  }
  const drawn = () => (cols.work > 0 ? 5 : 4) + ROW_CHROME + cols.id + cols.label + cols.model + cols.age + cols.work + MIN_TAIL
  const trim = (key: 'label' | 'model' | 'age', floor: number) => {
    const over = drawn() - available
    if (over > 0 && cols[key] > floor) cols[key] -= Math.min(over, cols[key] - floor)
  }
  const labelWidth = cols.label
  trim('label', 10)
  if (drawn() > available) {
    cols.work = 0
    cols.label = labelWidth // the work column's room goes back to the name
    trim('label', 6)
  }
  trim('model', 5)
  trim('age', 3)
  return cols
}

export function rowText(agent: FleetAgent, now: number, stalled: string | undefined): string {
  const p = rowParts(agent, now, stalled)
  return `${p.id} ${p.label} · ${p.model} · ${p.age} · ${p.work} · ${p.tail}`
}

// Rows padded to shared column widths (a terminal draws them as a table); the label column is capped at 24.
// `pad` is the fill: a drawn tree collapses runs of plain spaces, so the pane pads with no-break spaces.
export function alignRows(rows: readonly RowParts[], pad = ' '): string[] {
  const w = (pick: (p: RowParts) => string, cap = 64) => Math.min(cap, Math.max(0, ...rows.map(p => pick(p).length)))
  const id = w(p => p.id)
  const label = w(p => p.label, 24)
  const model = w(p => p.model)
  const age = w(p => p.age)
  const work = w(p => p.work)
  return rows.map(p =>
    [
      p.id.padEnd(id, pad),
      clip(p.label, label).padEnd(label, pad),
      p.model.padEnd(model, pad),
      p.age.padStart(age, pad),
      p.work.padEnd(work, pad),
      p.tail,
    ].join(pad + pad),
  )
}

// The band's chip for one running agent: number, name, age, what it is doing (or why it looks stalled), writes.
export function chipText(agent: FleetAgent, now: number, stalled: string | undefined): string {
  const doing = agent.status === 'waiting' ? 'waiting' : (stalled ?? agent.lastTool ?? 'starting')
  const writes = agent.isWriter && agent.writes > 0 ? ` ✎${agent.writes}` : ''
  return `#${agent.n} ${clip(agent.label, 18)} ${fmtDuration(now - agent.spawnedAt)} ${doing}${writes}`
}

// The /fleet answer: one line per agent, running first, newest first within each group. No `dojo-fleet:` lead:
// the engine already heads a plugin command's output with the plugin's name.
export function summaryLines(agents: readonly FleetAgent[], now: number, limitMs: number): string[] {
  if (agents.length === 0) return ['No subagent has run in this session yet.']
  const order = (agent: FleetAgent) => (isLive(agent) ? 0 : 1)
  const sorted = [...agents].sort((a, b) => order(a) - order(b) || b.n - a.n)
  const counts = countsOf(agents, now, limitMs)
  const stalls = sorted.map(agent => stallOf(agent, agents, now, limitMs))
  const rows = alignRows(sorted.map((agent, i) => rowParts(agent, now, stalls[i])))
  return [countsText(counts), ...sorted.map((agent, i) => `  ${glyphOf(agent, stalls[i] !== undefined)} ${rows[i]}`)]
}
