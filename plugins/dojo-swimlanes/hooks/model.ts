import type { Call, CallKind, LaneAgent, LaneStatus } from '../types'

// Pure logic for dojo-swimlanes: no `$`. Classification, waves, the header line, the SVG string and the text form.

export const MAX_AGENTS = 16
export const MAX_CALLS = 200
export const MAX_DENY = 200
export const MAX_TARGET = 80

export const COLORS = {
  bg: '#0f2a3d',
  panel: '#143847',
  grid: '#4a6a7a',
  ink: '#e9eff3',
  soft: '#bccdd8',
  cloud: '#94a3b8',
  read: '#86b0cc',
  write: '#ffd166',
  bash: '#7fb88c',
  agent: '#e8b04a',
  deny: '#e76f51',
} as const

const FONT = 'JetBrains Mono, SFMono-Regular, Menlo, monospace'
const SVG_LIMIT = 120000

export function clip(text: string, max: number): string {
  const flat = text.replace(/\s+/g, ' ').trim()
  return flat.length <= max ? flat : `${flat.slice(0, Math.max(0, max - 1))}…`
}

// Text for an XML attribute or element body. Characters XML 1.0 forbids are dropped.
export function esc(text: string): string {
  return text
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export function kindOf(tool: string): CallKind {
  if (['Read', 'Grep', 'Glob'].includes(tool)) return 'read'
  if (['Write', 'Edit', 'MultiEdit', 'NotebookEdit'].includes(tool)) return 'write'
  if (tool === 'Bash') return 'bash'
  if (['Agent', 'Task', 'SendMessage'].includes(tool)) return 'agent'
  return 'other'
}

// The file, the pattern or the first line of the command, from a tool call's input.
export function targetOf(input: unknown): string | undefined {
  if (typeof input !== 'object' || input === null) return undefined
  const bag = input as Record<string, unknown>
  for (const key of ['file_path', 'notebook_path', 'pattern', 'command', 'url', 'path', 'description']) {
    const value = bag[key]
    if (typeof value === 'string' && value.trim() !== '') {
      const first = (value.split('\n')[0] ?? '').trim()
      return clip(first, MAX_TARGET)
    }
  }
  return undefined
}

export function shortModel(model: string | undefined): string {
  if (model === undefined || model === '') return ''
  return model
    .replace(/^claude-/, '')
    .replace(/-\d{8}$/, '')
    .replace(/-(\d+)-(\d+)$/, ' $1.$2')
    .replace(/-/g, ' ')
}

export function fmtDuration(ms: number): string {
  const total = Math.max(0, Math.round(ms / 100) / 10)
  if (total < 10) return `${total.toFixed(1)}s`
  const secs = Math.round(total)
  if (secs < 60) return `${secs}s`
  const minutes = Math.floor(secs / 60)
  const rest = secs % 60
  if (minutes < 60) return rest === 0 ? `${minutes}m` : `${minutes}m ${rest}s`
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`
}

export const isLive = (agent: LaneAgent): boolean => agent.status === 'running' || agent.status === 'waiting'

// The agents spawned since the last moment no agent was live, grouped oldest wave first.
export function wavesOf(agents: readonly LaneAgent[]): LaneAgent[][] {
  const sorted = [...agents].sort((a, b) => a.spawnedAt - b.spawnedAt || a.n - b.n)
  const waves: LaneAgent[][] = []
  let maxEnd = -Infinity
  for (const agent of sorted) {
    const current = waves[waves.length - 1]
    if (current === undefined || agent.spawnedAt > maxEnd) waves.push([agent])
    else current.push(agent)
    maxEnd = Math.max(maxEnd, isLive(agent) ? Infinity : (agent.endedAt ?? agent.spawnedAt))
  }
  return waves
}

export type View = { agents: LaneAgent[]; waveNo: number; isAll: boolean }

export function viewOf(agents: readonly LaneAgent[], isAll: boolean): View {
  const waves = wavesOf(agents)
  if (isAll) return { agents: [...agents].sort((a, b) => a.n - b.n), waveNo: waves.length, isAll }
  return { agents: waves[waves.length - 1] ?? [], waveNo: waves.length, isAll }
}

const plural = (n: number, word: string): string => `${n} ${word}${n === 1 ? '' : 's'}`

export function spanOf(agents: readonly LaneAgent[], now: number): { start: number; end: number } {
  if (agents.length === 0) return { start: now, end: now }
  let start = Infinity
  let end = -Infinity
  for (const agent of agents) {
    start = Math.min(start, agent.spawnedAt)
    end = Math.max(end, isLive(agent) ? now : (agent.endedAt ?? agent.spawnedAt))
    for (const call of agent.calls) end = Math.max(end, call.t1 ?? call.t0)
  }
  return { start, end: Math.max(end, start) }
}

export function headerLine(view: View, now: number): string {
  const { agents } = view
  const count = (status: LaneStatus) => agents.filter(one => one.status === status).length
  const parts = [view.isAll ? 'All waves' : `Wave ${view.waveNo}`, plural(agents.length, 'agent')]
  const running = count('running')
  const waiting = count('waiting')
  const done = count('returned')
  const failed = count('failed')
  const aborted = count('aborted')
  if (running > 0) parts.push(`${running} running`)
  if (waiting > 0) parts.push(`${waiting} waiting`)
  if (done > 0) parts.push(`${done} done`)
  if (failed > 0) parts.push(`${failed} failed`)
  if (aborted > 0) parts.push(`${aborted} aborted`)
  const span = spanOf(agents, now)
  parts.push(fmtDuration(span.end - span.start).replace(/(\d)\.\d+s$/, '$1s'))
  return parts.join(' · ')
}

// ------------------------------------------------------------------------------------------------ time axis

const STEPS_S = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600]

// The smallest nice step that puts no more than 8 ticks on the span.
export function niceStep(spanMs: number): number {
  for (const step of STEPS_S) if (Math.floor(spanMs / (step * 1000)) <= 8) return step * 1000
  return 600000
}

export function tickLabel(ms: number): string {
  const secs = Math.round(ms / 1000)
  if (secs < 60) return `${secs}s`
  const minutes = Math.floor(secs / 60)
  const rest = secs % 60
  return rest === 0 ? `${minutes}m` : `${minutes}m${rest}s`
}

export function ticksOf(spanMs: number): number[] {
  const step = niceStep(spanMs)
  const out: number[] = []
  for (let t = 0; t <= spanMs; t += step) out.push(t)
  return out
}

// ------------------------------------------------------------------------------------------------ SVG

export function callTitle(agent: LaneAgent, call: Call, now: number): string {
  const dur = fmtDuration((call.t1 ?? now) - call.t0)
  const head = `#${agent.n} ${call.tool}${call.target ? ` ${call.target}` : ''} · ${dur}`
  return call.deny ? `${head}\n${call.deny}` : head
}

const kindColor = (kind: CallKind): string => COLORS[kind === 'other' ? 'cloud' : kind]

export function svgSize(bodyColumns: number, lanes: number): { width: number; height: number } {
  return { width: Math.max(480, bodyColumns * 8), height: 28 * lanes + 64 }
}

function buildSvg(view: View, now: number, bodyColumns: number, perLane: number): string {
  const { agents } = view
  const { width, height } = svgSize(bodyColumns, agents.length)
  const labelW = 172
  const px0 = labelW + 8
  const px1 = width - 22
  const pw = Math.max(40, px1 - px0)
  const span = spanOf(agents, now)
  const dur = Math.max(1000, span.end - span.start)
  const x = (t: number): number => px0 + (Math.min(Math.max(t, span.start), span.start + dur) - span.start) / dur * pw
  const f = (n: number): string => (Math.round(n * 10) / 10).toString()
  const anyLive = agents.some(isLive)
  const top = 32
  const out: string[] = []
  out.push(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" font-family="${FONT}">`,
    `<rect width="${width}" height="${height}" fill="${COLORS.bg}"/>`,
  )
  // time axis and grid
  for (const t of ticksOf(dur)) {
    const gx = f(x(span.start + t))
    out.push(
      `<line x1="${gx}" y1="22" x2="${gx}" y2="${top + 28 * agents.length}" stroke="${COLORS.grid}" stroke-opacity="0.35"/>`,
      `<text x="${gx}" y="15" font-size="10" fill="${COLORS.soft}" text-anchor="middle">${esc(tickLabel(t))}</text>`,
    )
  }
  agents.forEach((agent, i) => {
    const y = top + 28 * i
    const label = clip(`#${agent.n} ${agent.label}`, 22)
    const model = shortModel(agent.model)
    out.push(
      `<g><title>${esc(`#${agent.n} ${agent.label} · ${agent.type} · ${agent.status}`)}</title>`,
      `<text x="8" y="${y + 12}" font-size="11" fill="${COLORS.ink}">${esc(label)}</text>`,
      `<text x="8" y="${y + 23}" font-size="9" fill="${COLORS.soft}">${esc(clip(model, 26))}</text></g>`,
      `<line x1="0" y1="${y + 28}" x2="${width}" y2="${y + 28}" stroke="${COLORS.grid}" stroke-opacity="0.2"/>`,
    )
    const live = isLive(agent)
    const settledEnd = agent.endedAt ?? agent.spawnedAt
    const bandEnd = agent.status === 'running' ? now : settledEnd
    const bx0 = x(agent.spawnedAt)
    const bx1 = Math.max(bx0 + 3, x(bandEnd))
    out.push(`<rect x="${f(bx0)}" y="${y + 4}" width="${f(bx1 - bx0)}" height="20" rx="3" fill="${COLORS.panel}" stroke="${COLORS.grid}" stroke-opacity="0.5"/>`)
    if (agent.status === 'waiting') {
      const tx1 = Math.max(bx1 + 3, x(now))
      out.push(`<line x1="${f(bx1)}" y1="${y + 14}" x2="${f(tx1)}" y2="${y + 14}" stroke="${COLORS.agent}" stroke-width="2" stroke-dasharray="4 3"><title>${esc(`#${agent.n} waiting`)}</title></line>`)
    }
    for (const call of agent.calls.slice(-perLane)) {
      const cx0 = x(call.t0)
      const cx1 = x(call.t1 ?? (live ? now : call.t0))
      const title = `<title>${esc(callTitle(agent, call, now))}</title>`
      if (call.deny !== undefined) {
        out.push(`<g>${title}<text x="${f(cx0 + 1)}" y="${y + 19}" font-size="13" font-weight="bold" fill="${COLORS.deny}">✗</text></g>`)
      } else {
        out.push(`<rect x="${f(cx0)}" y="${y + 8}" width="${f(Math.max(3, cx1 - cx0))}" height="12" rx="1" fill="${kindColor(call.kind)}">${title}</rect>`)
      }
    }
    if (!live) {
      const glyph = agent.status === 'returned' ? '✓' : agent.status === 'failed' ? '✗' : '■'
      const color = agent.status === 'returned' ? COLORS.bash : agent.status === 'failed' ? COLORS.deny : COLORS.cloud
      out.push(`<text x="${f(bx1 + 4)}" y="${y + 19}" font-size="12" fill="${color}"><title>${esc(`#${agent.n} ${agent.status}`)}</title>${glyph}</text>`)
    }
  })
  if (anyLive) {
    const nx = f(x(now))
    out.push(
      `<line x1="${nx}" y1="22" x2="${nx}" y2="${top + 28 * agents.length}" stroke="${COLORS.ink}" stroke-width="1.5" stroke-dasharray="3 3"/>`,
      `<text x="${nx}" y="29" font-size="9" fill="${COLORS.ink}" text-anchor="middle">now</text>`,
    )
  }
  // legend
  const ly = height - 14
  const items: [string, string][] = [
    ['read', COLORS.read],
    ['write', COLORS.write],
    ['bash', COLORS.bash],
    ['agent', COLORS.agent],
    ['other', COLORS.cloud],
  ]
  let lx = 8
  for (const [name, color] of items) {
    out.push(`<rect x="${lx}" y="${ly - 9}" width="10" height="10" rx="1" fill="${color}"/>`, `<text x="${lx + 14}" y="${ly}" font-size="10" fill="${COLORS.soft}">${name}</text>`)
    lx += 22 + name.length * 6.2
  }
  out.push(`<text x="${f(lx)}" y="${ly}" font-size="12" font-weight="bold" fill="${COLORS.deny}">✗</text><text x="${f(lx + 12)}" y="${ly}" font-size="10" fill="${COLORS.soft}">refused or failed</text>`)
  lx += 22 + 'refused or failed'.length * 6.2
  out.push(`<line x1="${f(lx)}" y1="${ly - 4}" x2="${f(lx + 18)}" y2="${ly - 4}" stroke="${COLORS.agent}" stroke-width="2" stroke-dasharray="4 3"/><text x="${f(lx + 24)}" y="${ly}" font-size="10" fill="${COLORS.soft}">waiting</text>`)
  if (perLane < MAX_CALLS && agents.some(one => one.calls.length > perLane)) {
    out.push(`<text x="${width - 8}" y="${ly}" font-size="9" fill="${COLORS.cloud}" text-anchor="end">last ${perLane} calls per lane</text>`)
  }
  out.push('</svg>')
  return out.join('')
}

// The drawing as one string, kept under the element's size limit by showing fewer calls per lane when it must.
export function buildLanesSvg(view: View, now: number, bodyColumns: number): string {
  let perLane = MAX_CALLS
  let svg = buildSvg(view, now, bodyColumns, perLane)
  while (svg.length > SVG_LIMIT && perLane > 4) {
    perLane = Math.floor(perLane * 0.6)
    svg = buildSvg(view, now, bodyColumns, perLane)
  }
  return svg
}

export function svgAlt(view: View, now: number): string {
  const refused = view.agents.reduce((sum, a) => sum + a.calls.filter(c => c.deny !== undefined).length, 0)
  const calls = view.agents.reduce((sum, a) => sum + a.calls.length, 0)
  return `Swimlanes. ${headerLine(view, now)}. ${plural(calls, 'tool call')}, ${refused} refused or failed.`
}

// ------------------------------------------------------------------------------------------------ terminal

// One glyph per time bucket: ▮ a call ran, ✗ a refused or failed call, · idle, ┄ waiting, a space outside the agent's life.
export function stripOf(agent: LaneAgent, start: number, end: number, now: number, buckets: number): string {
  const n = Math.max(1, buckets)
  const bw = Math.max(1, (end - start) / n)
  const live = isLive(agent)
  const lifeEnd = agent.status === 'running' ? now : (agent.endedAt ?? agent.spawnedAt)
  let out = ''
  for (let i = 0; i < n; i++) {
    const bs = start + i * bw
    const be = bs + bw
    const inLife = be > agent.spawnedAt && bs <= Math.max(lifeEnd, agent.spawnedAt)
    const isTail = agent.status === 'waiting' && be > lifeEnd && bs <= now
    let glyph = ' '
    const hits = agent.calls.filter(c => c.t0 < be && (c.t1 ?? (live ? now : c.t0)) >= bs)
    if (hits.some(c => c.deny !== undefined && c.t0 >= bs && c.t0 < be)) glyph = '✗'
    else if (hits.length > 0) glyph = '▮'
    else if (isTail) glyph = '┄'
    else if (inLife) glyph = '·'
    out += glyph
  }
  return out
}

export type TermRow = { head: string; strip: string; tail: string }

export function termRows(view: View, now: number, bodyColumns: number): { rows: TermRow[]; axis: string } {
  const { agents } = view
  const span = spanOf(agents, now)
  const dur = Math.max(1000, span.end - span.start)
  const labels = agents.map(a => clip(`#${a.n} ${a.label}`, 24))
  const models = agents.map(a => clip(shortModel(a.model), 14))
  const tails = agents.map(a => `${a.status} ${fmtDuration((isLive(a) && a.status === 'running' ? now : (a.endedAt ?? now)) - a.spawnedAt).replace(/(\d)\.\d+s$/, '$1s')}`)
  const lw = Math.max(0, ...labels.map(s => s.length))
  const mw = Math.max(0, ...models.map(s => s.length))
  const tw = Math.max(0, ...tails.map(s => s.length))
  const buckets = Math.max(8, bodyColumns - lw - mw - tw - 6)
  const rows = agents.map((agent, i) => ({
    head: `${(labels[i] ?? '').padEnd(lw)}  ${(models[i] ?? '').padEnd(mw)}`,
    strip: stripOf(agent, span.start, span.start + dur, now, buckets),
    tail: tails[i] ?? '',
  }))
  const end = fmtDuration(dur)
  const gap = Math.max(1, buckets - 2 - end.length)
  const axis = `${' '.repeat(lw + mw + 4)}0s${' '.repeat(gap)}${end}`
  return { rows, axis }
}

export function textForm(view: View, now: number, bodyColumns: number): string {
  if (view.agents.length === 0) return 'No subagent has run yet'
  const { rows, axis } = termRows(view, now, bodyColumns)
  return [headerLine(view, now), ...rows.map(r => `${r.head}  ${r.strip}  ${r.tail}`), axis].join('\n')
}
