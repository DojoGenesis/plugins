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
  // Across several waves the wall-clock span is mostly idle time (the chart folds it), so say how many waves.
  if (view.isAll && view.waveNo > 1) {
    parts.push(plural(view.waveNo, 'wave'))
  } else {
    const span = spanOf(agents, now)
    parts.push(fmtDuration(span.end - span.start).replace(/(\d)\.\d+s$/, '$1s'))
  }
  return parts.join(' · ')
}

// ------------------------------------------------------------------------------------------------ detail rows

export type Tone = 'claude' | 'warning' | 'success' | 'error' | 'subtle'
export type DetailRow = { id: string; glyph: string; tone: Tone; title: string; facts: string }

// One line per agent in view, for the native text under the chart: the numbers read at the surface's own type size
// and stay crisp, where the chart's are drawn inside an image.
export function detailRows(view: View, now: number): DetailRow[] {
  return view.agents.map(agent => {
    const writes = agent.calls.filter(call => call.kind === 'write' && call.deny === undefined && call.ok !== false).length
    const refused = agent.calls.filter(call => call.deny !== undefined).length
    const end = isLive(agent) ? now : (agent.endedAt ?? agent.spawnedAt)
    const look: Record<LaneStatus, [string, Tone]> = {
      running: ['●', 'claude'],
      waiting: ['◐', 'warning'],
      returned: ['✓', 'success'],
      failed: ['✗', 'error'],
      aborted: ['■', 'subtle'],
    }
    const [glyph, tone] = look[agent.status]
    const facts = [
      shortModel(agent.model),
      agent.status,
      fmtDuration(Math.max(0, end - agent.spawnedAt)).replace(/(\d)\.\d+s$/, '$1s'),
      plural(agent.calls.length, 'tool call'),
      writes > 0 ? plural(writes, 'write') : '',
      refused > 0 ? `${refused} refused or failed` : '',
    ].filter(part => part !== '')
    return { id: agent.id, glyph, tone, title: `#${agent.n} ${agent.label}`, facts: facts.join(' · ') }
  })
}

// ------------------------------------------------------------------------------------------------ time axis

// Seen live: the steps stopped at 10m, so a 12-hour span drew some seventy overlapping labels. They run to a day
// now, and past that the step grows in whole days, so no span puts more than `maxTicks` labels on the axis.
const STEPS_S = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 10800, 21600, 43200, 86400]

// The smallest nice step that puts no more than `maxTicks` ticks on the span.
export function niceStep(spanMs: number, maxTicks = 8): number {
  const most = Math.max(1, maxTicks)
  for (const step of STEPS_S) if (Math.floor(spanMs / (step * 1000)) <= most) return step * 1000
  return Math.ceil(spanMs / most / 86400000) * 86400000
}

export function tickLabel(ms: number): string {
  const secs = Math.round(ms / 1000)
  if (secs < 60) return `${secs}s`
  if (secs < 3600) {
    const minutes = Math.floor(secs / 60)
    const rest = secs % 60
    return rest === 0 ? `${minutes}m` : `${minutes}m${rest}s`
  }
  const hours = Math.floor(secs / 3600)
  const minutes = Math.floor((secs % 3600) / 60)
  return minutes === 0 ? `${hours}h` : `${hours}h${minutes}m`
}

export function ticksOf(spanMs: number, maxTicks = 8): number[] {
  const step = niceStep(spanMs, maxTicks)
  const out: number[] = []
  for (let t = 0; t <= spanMs; t += step) out.push(t)
  return out
}

// ------------------------------------------------------------------------------------------------ busy segments

// Idle stretches longer than this, when no agent in view is alive, are drawn as a fixed-width break instead of to
// scale. Seen live: "All waves" over half a day left each wave a sliver at either end of a 12-hour axis.
export const GAP_MIN_MS = 20000
export const BREAK_PX = 36

export type Segment = { t0: number; t1: number }

// The busy stretches of the view, in time order: the union of each agent's life (to now while it is alive), with
// stretches closer than GAP_MIN_MS merged. The gaps between them are what the drawing folds.
export function segmentsOf(agents: readonly LaneAgent[], now: number): Segment[] {
  const lives = agents
    .map(agent => {
      let end = isLive(agent) ? now : (agent.endedAt ?? agent.spawnedAt)
      for (const call of agent.calls) end = Math.max(end, call.t1 ?? call.t0)
      return { t0: agent.spawnedAt, t1: Math.max(end, agent.spawnedAt) }
    })
    .sort((a, b) => a.t0 - b.t0)
  const out: Segment[] = []
  for (const life of lives) {
    const last = out[out.length - 1]
    if (last !== undefined && life.t0 - last.t1 <= GAP_MIN_MS) last.t1 = Math.max(last.t1, life.t1)
    else out.push({ ...life })
  }
  return out
}

// A time-to-x map over the busy segments: each segment gets width in proportion to its length, each gap between
// two segments a fixed BREAK_PX. A time inside a gap lands in the middle of its break.
export type Scale = { x: (t: number) => number; segs: { seg: Segment; x0: number; x1: number }[]; breaks: { gap: Segment; x0: number; x1: number }[] }

export function scaleOf(segs: readonly Segment[], px0: number, px1: number): Scale {
  const list = segs.length > 0 ? segs : [{ t0: 0, t1: 1000 }]
  const lengths = list.map(seg => Math.max(1000, seg.t1 - seg.t0))
  const total = lengths.reduce((a, b) => a + b, 0)
  const room = Math.max(40, px1 - px0 - BREAK_PX * (list.length - 1))
  const placed: Scale['segs'] = []
  const breaks: Scale['breaks'] = []
  let cursor = px0
  list.forEach((seg, i) => {
    if (i > 0) {
      const prev = list[i - 1] as Segment
      breaks.push({ gap: { t0: prev.t1, t1: seg.t0 }, x0: cursor, x1: cursor + BREAK_PX })
      cursor += BREAK_PX
    }
    const width = ((lengths[i] as number) / total) * room
    placed.push({ seg, x0: cursor, x1: cursor + width })
    cursor += width
  })
  const x = (t: number): number => {
    for (let i = 0; i < placed.length; i++) {
      const one = placed[i] as Scale['segs'][number]
      if (t < one.seg.t0) {
        // Inside the gap before this segment: the middle of that break (before the first: its left edge).
        const gap = breaks[i - 1]
        return gap === undefined ? one.x0 : (gap.x0 + gap.x1) / 2
      }
      if (t <= one.seg.t1 || i === placed.length - 1) {
        const len = Math.max(1000, one.seg.t1 - one.seg.t0)
        return one.x0 + ((Math.min(t, one.seg.t0 + len) - one.seg.t0) / len) * (one.x1 - one.x0)
      }
    }
    return px1
  }
  return { x, segs: placed, breaks }
}

// The largest unit only, rounded, for a gap label that must fit its break: "+12h", "+2m", "+29s". The exact
// length is the break's tooltip.
export function compactGap(ms: number): string {
  const secs = Math.round(ms / 1000)
  if (secs >= 86400) return `+${Math.round(secs / 86400)}d`
  if (secs >= 3600) return `+${Math.round(secs / 3600)}h`
  if (secs >= 60) return `+${Math.round(secs / 60)}m`
  return `+${secs}s`
}

export type AxisLabel = { x: number; text: string; kind: 'gap' | 'tick' }

const labelHalf = (text: string): number => text.length * 3.7 + 5

// Axis labels that do not overlap, in drawing order: every gap label first, then each segment's ticks.
export function axisLabels(scale: Scale): AxisLabel[] {
  const wanted: AxisLabel[] = []
  for (const { gap, x0, x1 } of scale.breaks) wanted.push({ x: (x0 + x1) / 2, text: compactGap(gap.t1 - gap.t0), kind: 'gap' })
  for (const { seg, x0, x1 } of scale.segs) {
    const len = Math.max(1000, seg.t1 - seg.t0)
    for (const t of ticksOf(len, Math.floor((x1 - x0) / 64))) {
      wanted.push({ x: x0 + (t / len) * (x1 - x0), text: tickLabel(t), kind: 'tick' })
    }
  }
  const placed: AxisLabel[] = []
  for (const one of wanted) {
    const clash = placed.some(other => Math.abs(other.x - one.x) < labelHalf(other.text) + labelHalf(one.text))
    if (!clash) placed.push(one)
  }
  return placed
}

// ------------------------------------------------------------------------------------------------ SVG

export function callTitle(agent: LaneAgent, call: Call, now: number): string {
  const dur = fmtDuration((call.t1 ?? now) - call.t0)
  const head = `#${agent.n} ${call.tool}${call.target ? ` ${call.target}` : ''} · ${dur}`
  return call.deny ? `${head}\n${call.deny}` : head
}

const kindColor = (kind: CallKind): string => COLORS[kind === 'other' ? 'cloud' : kind]

// The drawing's size in CSS pixels. The pane hands the Svg this width and height explicitly: seen live, a desktop
// with no `width` drew the image at its own pixel size in device pixels, half size on a 2x screen.
export function svgSize(bodyColumns: number, lanes: number): { width: number; height: number } {
  const width = Math.max(480, bodyColumns * 8)
  return { width, height: LANE_H * lanes + 56 + LEGEND_ROW * legendRows(width) }
}

const LEGEND_ROW = 20

// The legend's rows at this width: all seven items need about 600px on one line.
export function legendRows(width: number): number {
  return width < 620 ? 2 : 1
}

// Seen live: at 30px lanes and 10-12px type the chart read poorly in a docked desktop pane. Lanes are 38px now and
// the type a size or two larger; the exact numbers live in the native table under the chart.
const LANE_H = 38

function buildSvg(view: View, now: number, bodyColumns: number, perLane: number): string {
  const { agents } = view
  const { width, height } = svgSize(bodyColumns, agents.length)
  // The label column takes about a third of the drawing, so a narrow pane keeps room for the lanes.
  const labelW = Math.round(Math.min(220, Math.max(150, width * 0.34)))
  const labelChars = Math.max(10, Math.floor((labelW - 14) / 8.6))
  const px0 = labelW + 8
  const px1 = width - 22
  const scale = scaleOf(segmentsOf(agents, now), px0, px1)
  const x = scale.x
  const f = (n: number): string => (Math.round(n * 10) / 10).toString()
  const anyLive = agents.some(isLive)
  const top = 38
  const bottom = top + LANE_H * agents.length
  const out: string[] = []
  out.push(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" font-family="${FONT}">`,
    `<rect width="${width}" height="${height}" fill="${COLORS.bg}"/>`,
  )
  // Folded idle gaps: a dashed band; the exact length is its tooltip.
  for (const { gap, x0, x1 } of scale.breaks) {
    const full = `+${fmtDuration(gap.t1 - gap.t0).replace(/(\d)\.\d+s$/, '$1s')}`
    out.push(
      `<rect x="${f(x0 + 4)}" y="24" width="${f(x1 - x0 - 8)}" height="${f(bottom - 24)}" fill="${COLORS.bg}" stroke="${COLORS.grid}" stroke-opacity="0.6" stroke-dasharray="2 3"><title>${esc(`${full} with no agent running (folded)`)}</title></rect>`,
    )
  }
  // Axis labels. Seen live: six waves in one pane put every segment's ticks and every gap label on top of each
  // other. Candidates are placed best first (gap labels, then each segment's ticks), and one that would overlap a
  // placed label is dropped with its grid line.
  for (const label of axisLabels(scale)) {
    const gx = f(label.x)
    if (label.kind === 'tick') out.push(`<line x1="${gx}" y1="24" x2="${gx}" y2="${bottom}" stroke="${COLORS.grid}" stroke-opacity="0.35"/>`)
    out.push(`<text x="${gx}" y="18" font-size="${label.kind === 'gap' ? 12 : 12}" fill="${label.kind === 'gap' ? COLORS.agent : COLORS.soft}" text-anchor="middle">${esc(label.text)}</text>`)
  }
  agents.forEach((agent, i) => {
    const y = top + LANE_H * i
    const label = clip(`#${agent.n} ${agent.label}`, labelChars)
    const model = shortModel(agent.model)
    out.push(
      `<g><title>${esc(`#${agent.n} ${agent.label} · ${agent.type} · ${agent.status}`)}</title>`,
      `<text x="8" y="${y + 17}" font-size="14" font-weight="600" fill="${COLORS.ink}">${esc(label)}</text>`,
      `<text x="8" y="${y + 31}" font-size="12" fill="${COLORS.soft}">${esc(clip(model, labelChars))}</text></g>`,
      `<line x1="0" y1="${y + LANE_H}" x2="${width}" y2="${y + LANE_H}" stroke="${COLORS.grid}" stroke-opacity="0.2"/>`,
    )
    const live = isLive(agent)
    const settledEnd = agent.endedAt ?? agent.spawnedAt
    const bandEnd = agent.status === 'running' ? now : settledEnd
    const bx0 = x(agent.spawnedAt)
    const bx1 = Math.max(bx0 + 3, x(bandEnd))
    out.push(`<rect x="${f(bx0)}" y="${y + 5}" width="${f(bx1 - bx0)}" height="28" rx="4" fill="${COLORS.panel}" stroke="${COLORS.grid}" stroke-opacity="0.5"/>`)
    if (agent.status === 'waiting') {
      const tx1 = Math.max(bx1 + 3, x(now))
      out.push(`<line x1="${f(bx1)}" y1="${y + 19}" x2="${f(tx1)}" y2="${y + 19}" stroke="${COLORS.agent}" stroke-width="2" stroke-dasharray="4 3"><title>${esc(`#${agent.n} waiting`)}</title></line>`)
    }
    for (const call of agent.calls.slice(-perLane)) {
      const cx0 = x(call.t0)
      const cx1 = x(call.t1 ?? (live ? now : call.t0))
      const title = `<title>${esc(callTitle(agent, call, now))}</title>`
      if (call.deny !== undefined) {
        out.push(`<g>${title}<text x="${f(cx0 + 1)}" y="${y + 25}" font-size="17" font-weight="bold" fill="${COLORS.deny}">✗</text></g>`)
      } else {
        out.push(`<rect x="${f(cx0)}" y="${y + 10}" width="${f(Math.max(4, cx1 - cx0))}" height="18" rx="2" fill="${kindColor(call.kind)}">${title}</rect>`)
      }
    }
    if (!live) {
      const glyph = agent.status === 'returned' ? '✓' : agent.status === 'failed' ? '✗' : '■'
      const color = agent.status === 'returned' ? COLORS.bash : agent.status === 'failed' ? COLORS.deny : COLORS.cloud
      out.push(`<text x="${f(bx1 + 5)}" y="${y + 25}" font-size="16" fill="${color}"><title>${esc(`#${agent.n} ${agent.status}`)}</title>${glyph}</text>`)
    }
  })
  if (anyLive) {
    const nx = f(x(now))
    out.push(
      `<line x1="${nx}" y1="24" x2="${nx}" y2="${bottom}" stroke="${COLORS.ink}" stroke-width="1.5" stroke-dasharray="3 3"/>`,
      `<text x="${nx}" y="34" font-size="11" fill="${COLORS.ink}" text-anchor="middle">now</text>`,
    )
  }
  // legend, wrapped onto a second row when the drawing is too narrow for one (legendRows decides the height)
  const swatch = (color: string) => (lx: number, ly: number) => `<rect x="${f(lx)}" y="${ly - 10}" width="11" height="11" rx="2" fill="${color}"/>`
  const items: { name: string; mark: (lx: number, ly: number) => string; markW: number }[] = [
    { name: 'read', mark: swatch(COLORS.read), markW: 15 },
    { name: 'write', mark: swatch(COLORS.write), markW: 15 },
    { name: 'bash', mark: swatch(COLORS.bash), markW: 15 },
    { name: 'agent', mark: swatch(COLORS.agent), markW: 15 },
    { name: 'other', mark: swatch(COLORS.cloud), markW: 15 },
    { name: 'refused or failed', mark: (lx, ly) => `<text x="${f(lx)}" y="${ly}" font-size="14" font-weight="bold" fill="${COLORS.deny}">✗</text>`, markW: 14 },
    { name: 'waiting', mark: (lx, ly) => `<line x1="${f(lx)}" y1="${ly - 4}" x2="${f(lx + 18)}" y2="${ly - 4}" stroke="${COLORS.agent}" stroke-width="2" stroke-dasharray="4 3"/>`, markW: 24 },
  ]
  const rows = legendRows(width)
  let ly = height - 16 - LEGEND_ROW * (rows - 1)
  let lx = 8
  for (const item of items) {
    const w = item.markW + item.name.length * 7.3 + 12
    if (lx + w > width - 8 && lx > 8) {
      ly += LEGEND_ROW
      lx = 8
    }
    out.push(item.mark(lx, ly), `<text x="${f(lx + item.markW)}" y="${ly}" font-size="12" fill="${COLORS.soft}">${item.name}</text>`)
    lx += w
  }
  if (perLane < MAX_CALLS && agents.some(one => one.calls.length > perLane)) {
    out.push(`<text x="${width - 8}" y="${height - 16}" font-size="11" fill="${COLORS.cloud}" text-anchor="end">last ${perLane} calls per lane</text>`)
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
