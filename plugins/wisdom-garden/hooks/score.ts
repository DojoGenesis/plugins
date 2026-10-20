import type { GardenCard, GardenMetric, GardenRead, GardenSession, GardenVerdict, GardenWeek } from '../types'

// The pure half of the /garden-score mod: classify a memory read, parse frontmatter and git output, and turn the
// logs into one weekly card. No `$` in here, so every rule can be tested with plain values.

export const DAY_MS = 86400000
export const WEEK_MS = 7 * DAY_MS
export const BASE_WEEKS = 4
export const KEEP_MS = 120 * DAY_MS
export const KEEP_READS = 20000
export const KEEP_SESSIONS = 2000
export const KEEP_WEEKS = 104
export const VERDICT_WEEKS = 4

// A recurrence note: the words a seed or feedback file uses when a known failure happened again. A proxy for
// "repeat mistakes", and the card says so.
export const RECURRENCE = /\b(fired again|happened again|recurred|recurrence|again today|second time|third time|twice|same (?:mistake|failure|bug) again)\b/i

const MEMORY_FILE = /^(seed|feedback|reference|project)_[^/\\]*\.md$/i

/** What a path read through the Read tool counts as: a memory file, a skill, or nothing. */
export function classifyPath(path: string): { id: string; kind: GardenRead['kind'] } | undefined {
  const parts = path.split(/[\\/]+/).filter(Boolean)
  const base = parts[parts.length - 1] ?? ''
  if (base === 'SKILL.md' && parts.length >= 2) return { id: `skill:${parts[parts.length - 2]}`, kind: 'skill' }
  const m = MEMORY_FILE.exec(base)
  if (!m) return undefined
  return { id: base.replace(/\.md$/i, ''), kind: (m[1] ?? '').toLowerCase() as GardenRead['kind'] }
}

export type Front = {
  name?: string
  updated?: string
  verified?: string
  validUntil?: string
  supersedes: string[]
  supersededBy?: string
}

const unquote = (v: string): string => v.trim().replace(/^["']|["']$/g, '').trim()

function listOf(v: string): string[] {
  const t = v.trim()
  if (t === '') return []
  const inner = t.startsWith('[') && t.endsWith(']') ? t.slice(1, -1) : t
  return inner.split(',').map(unquote).filter(Boolean)
}

/**
 * Reads the frontmatter fields the score needs, at the top level or nested one level (under `metadata:`); the
 * top level wins, as memory-lint's typed edges read them (scripts/README-memory-lint.md, "Typed edges"). Lists are
 * inline `[a, b]`, a single scalar, or a YAML block list. Dates: `verified`, `as_of`, `updated`, `valid_until`.
 */
export function parseFront(text: string): Front {
  const top: Record<string, string> = {}
  const nested: Record<string, string> = {}
  const lists: { top: string[] | undefined; nested: string[] | undefined } = { top: undefined, nested: undefined }
  const lines = text.split(/\r?\n/)
  if (lines[0]?.trim() !== '---') return { supersedes: [] }
  let listKey: string | undefined
  let listTop = true
  for (const raw of lines.slice(1, 200)) {
    if (raw.trim() === '---') break
    const item = /^\s*-\s+(.+)$/.exec(raw)
    if (item && listKey === 'supersedes') {
      const into = listTop ? 'top' : 'nested'
      lists[into] = [...(lists[into] ?? []), unquote(item[1] ?? '')]
      continue
    }
    const kv = /^(\s*)([A-Za-z_]+):\s*(.*)$/.exec(raw)
    if (!kv) continue
    const isTop = (kv[1] ?? '') === ''
    const key = (kv[2] ?? '').toLowerCase()
    const val = kv[3] ?? ''
    listKey = val.trim() === '' ? key : undefined
    listTop = isTop
    if (key === 'supersedes') {
      if (val.trim() !== '') lists[isTop ? 'top' : 'nested'] = listOf(val)
      continue
    }
    const into = isTop ? top : nested
    if (!(key in into)) into[key] = unquote(val)
  }
  const pick = (key: string): string | undefined => {
    const v = top[key] ?? nested[key]
    return v === undefined || v === '' ? undefined : v
  }
  return {
    name: top.name || undefined,
    updated: pick('updated'),
    verified: pick('verified') ?? pick('as_of'),
    validUntil: pick('valid_until'),
    supersedes: lists.top ?? lists.nested ?? [],
    supersededBy: pick('superseded_by'),
  }
}

/** A `YYYY-MM-DD` (or longer ISO) date as epoch ms at UTC midnight; undefined when unreadable. */
export function dayOf(value: string | undefined): number | undefined {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value ?? '')
  if (!m) return undefined
  const t = Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
  return Number.isFinite(t) ? t : undefined
}

/**
 * Why a memory file was stale at the moment it was read: `expired` (its `valid_until` has passed), `superseded`
 * (it names a `superseded_by`), `old` (its `verified`, else `updated`, is more than `staleDays` old). A file with
 * none of these dates is never called stale: age is not guessed from the file's mtime, which a checkout resets.
 */
export function staleFlags(front: Front, now: number, staleDays: number): string[] {
  const flags: string[] = []
  const until = dayOf(front.validUntil)
  if (until !== undefined && now > until + DAY_MS) flags.push('expired')
  if (front.supersededBy) flags.push('superseded')
  const seen = dayOf(front.verified) ?? dayOf(front.updated)
  if (staleDays > 0 && seen !== undefined && now - seen > staleDays * DAY_MS) flags.push('old')
  return flags
}

/** `git log --format=@@%ct -p --unified=0`: counts added lines matching RECURRENCE, by commit time. */
export function recurrenceTimes(log: string): number[] {
  const times: number[] = []
  let t: number | undefined
  for (const line of log.split('\n')) {
    if (line.startsWith('@@') && /^@@\d+$/.test(line.trim())) {
      t = Number(line.trim().slice(2)) * 1000
      continue
    }
    if (t === undefined || !line.startsWith('+') || line.startsWith('+++')) continue
    if (RECURRENCE.test(line)) times.push(t)
  }
  return times
}

/** `git log --diff-filter=A --name-only --format=@@%ct`: each added path with its commit time. */
export function addedFiles(log: string): { path: string; t: number }[] {
  const out: { path: string; t: number }[] = []
  let t: number | undefined
  for (const raw of log.split('\n')) {
    const line = raw.trim()
    if (line === '') continue
    if (/^@@\d+$/.test(line)) {
      t = Number(line.slice(2)) * 1000
      continue
    }
    if (t !== undefined) out.push({ path: line, t })
  }
  return out
}

/** The newest `compression_log_YYYY-MM-DD_*.md` in a listing, as epoch ms; the date comes from the name. */
export function newestCompression(names: readonly string[]): number | undefined {
  let best: number | undefined
  for (const name of names) {
    const m = /^compression_log_(\d{4}-\d{2}-\d{2})/.exec(name)
    const t = m ? dayOf(m[1]) : undefined
    if (t !== undefined && (best === undefined || t > best)) best = t
  }
  return best
}

export type RitualCounts = { offered: number; accepted: number; declined: number }

/**
 * The drift ritual hook's ledger rows (`ritual: YYYY-MM-DD HH:MM offered|accepted|declined ...`, written to
 * ~/.claude/convergence-ledger.md) inside [from, to). The stamp is local time; read as UTC it is off by the zone at
 * most, which a weekly count can carry.
 */
export function ritualCounts(text: string, from: number, to: number): RitualCounts {
  const out: RitualCounts = { offered: 0, accepted: 0, declined: 0 }
  for (const line of text.split(/\r?\n/)) {
    const m = /^ritual:\s+(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?\s+(offered|accepted|declined)\b/.exec(line)
    if (!m) continue
    const t = Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]), Number(m[4] ?? 0), Number(m[5] ?? 0))
    if (t >= from && t < to) out[m[6] as keyof RitualCounts] += 1
  }
  return out
}

export function median(values: readonly number[]): number | undefined {
  if (values.length === 0) return undefined
  const s = [...values].sort((a, b) => a - b)
  const mid = Math.floor(s.length / 2)
  const hi = s[mid] ?? 0
  return s.length % 2 === 1 ? hi : ((s[mid - 1] ?? hi) + hi) / 2
}

const inWin = (t: number, from: number, to: number): boolean => t >= from && t < to

/** Everything the card is built from, gathered by the hooks module. */
export type ScoreInput = {
  now: number
  reads: readonly GardenRead[]
  sessions: readonly GardenSession[]
  /** Commit times of recurrence notes; undefined when git could not be read. */
  recurrences?: readonly number[]
  /** Added seed and skill paths with commit times; undefined when git could not be read. */
  added?: readonly { path: string; t: number }[]
  /** Ids (file names without `.md`, and `name:` slugs) another file `supersedes`, or that name a `superseded_by`. */
  superseded: ReadonlySet<string>
  /** The newest compression log's date; undefined when there is none or the folder is missing. */
  lastCompression?: number
  activeSeeds?: number
  memoryRoot?: string
  /** The drift ritual ledger's text, when there is one. */
  ritualLedger?: string
  notes: string[]
}

function metric(key: string, label: string, better: GardenMetric['better'], week: number | undefined, base: number | undefined, unit: string, note?: string): GardenMetric {
  return { key, label, better, week: week ?? null, base: base ?? null, unit, note }
}

/** Builds this week's card: the window is [now - 7 days, now), the baseline the four weeks before it, averaged. */
export function computeCard(input: ScoreInput): GardenCard {
  const { now } = input
  // The week includes this very moment, so a read logged a moment ago counts.
  const end = now + 1
  const wFrom = now - WEEK_MS
  const bFrom = now - (BASE_WEEKS + 1) * WEEK_MS
  const perWeek = (times: readonly number[]): [number, number] => [
    times.filter(t => inWin(t, wFrom, end)).length,
    times.filter(t => inWin(t, bFrom, wFrom)).length / BASE_WEEKS,
  ]

  const metrics: GardenMetric[] = []

  // 1. Fewer repeat mistakes (proxy).
  if (input.recurrences) {
    const [w, b] = perWeek(input.recurrences)
    metrics.push(metric('repeats', 'Recurrence notes added to seed and feedback files', 'lower', w, b, 'notes',
      'Proxy: lines that say a known failure happened again. Not a transcript scan.'))
  } else {
    metrics.push(metric('repeats', 'Recurrence notes added to seed and feedback files', 'lower', undefined, undefined, 'notes', 'git could not be read'))
  }

  // 2. Faster, cheaper work.
  const sWeek = input.sessions.filter(s => inWin(s.t, wFrom, end))
  const sBase = input.sessions.filter(s => inWin(s.t, bFrom, wFrom))
  const usd = (list: readonly GardenSession[]) => median(list.map(s => s.usd).filter((v): v is number => typeof v === 'number'))
  metrics.push(metric('cost', 'Median cost per session', 'lower', usd(sWeek), usd(sBase), 'USD',
    'List-price estimate from the session ledger; tasks are not matched by kind yet.'))
  metrics.push(metric('turns', 'Median turns per session', 'lower', median(sWeek.map(s => s.turns)), median(sBase.map(s => s.turns)), 'turns'))

  // 3. New capability.
  if (input.added) {
    const seeds = input.added.filter(a => /(^|\/)seed_[^/]*\.md$/i.test(a.path)).map(a => a.t)
    const skills = input.added.filter(a => /(^|\/)SKILL\.md$/.test(a.path)).map(a => a.t)
    const [sw, sb] = perWeek(seeds)
    const [kw, kb] = perWeek(skills)
    metrics.push(metric('newSeeds', 'New seeds', 'higher', sw, sb, 'seeds'))
    metrics.push(metric('newSkills', 'New skills', 'higher', kw, kb, 'skills'))
  } else {
    metrics.push(metric('newSeeds', 'New seeds', 'higher', undefined, undefined, 'seeds', 'git could not be read'))
    metrics.push(metric('newSkills', 'New skills', 'higher', undefined, undefined, 'skills', 'git could not be read'))
  }
  const rWeek = input.reads.filter(r => inWin(r.t, wFrom, end))
  const rBase = input.reads.filter(r => inWin(r.t, bFrom, wFrom))
  const distinct = (list: readonly GardenRead[]) => new Set(list.map(r => r.id)).size
  const baseDistinct = rBase.length === 0 ? undefined : [0, 1, 2, 3]
    .map(i => distinct(rBase.filter(r => inWin(r.t, wFrom - (i + 1) * WEEK_MS, wFrom - i * WEEK_MS))))
    .reduce((a, b) => a + b, 0) / BASE_WEEKS
  metrics.push(metric('reused', 'Distinct seeds, memories and skills used', 'higher', distinct(rWeek), baseDistinct, 'items',
    'Counted from Read and Skill calls since the mod was installed.'))

  // 4. Stale-memory harm (control).
  const isStale = (r: GardenRead) => (r.stale?.length ?? 0) > 0 || input.superseded.has(r.id) || (r.name !== undefined && input.superseded.has(r.name))
  const staleWeek = rWeek.filter(isStale)
  const staleBase = rBase.filter(isStale)
  metrics.push(metric('stale', 'Reads of stale or superseded memory', 'lower', staleWeek.length, rBase.length === 0 ? undefined : staleBase.length / BASE_WEEKS, 'reads',
    'Stale: past valid_until, superseded, or verified/updated over the age limit.'))

  // 5. Harvest cadence.
  const last = input.lastCompression
  const sinceSessions = last === undefined ? undefined : input.sessions.filter(s => s.t >= last + DAY_MS).length
  const cadence = {
    lastCompression: last ?? null,
    days: last === undefined ? null : Math.floor((now - last) / DAY_MS),
    sessionsSince: sinceSessions ?? null,
    ritual: input.ritualLedger === undefined ? null : ritualCounts(input.ritualLedger, wFrom, end),
  }

  const staleIds = [...new Set(staleWeek.map(r => r.id))].slice(0, 12)
  return {
    at: now,
    from: wFrom,
    memoryRoot: input.memoryRoot ?? null,
    activeSeeds: input.activeSeeds ?? null,
    metrics,
    cadence,
    staleIds,
    sessions: sWeek.length,
    reads: rWeek.length,
    notes: input.notes,
  }
}

export function weekOf(card: GardenCard): GardenWeek {
  const values: Record<string, number | null> = {}
  for (const m of card.metrics) values[m.key] = m.week
  return { at: card.at, activeSeeds: card.activeSeeds, values }
}

/**
 * The compounding reading, per metric, once there are VERDICT_WEEKS weekly rows. The change per week in the
 * newer half is compared with the older half, signed so that positive is "better": rising gains read
 * `compounding`, falling gains `saturating`, about the same `linear`, and a worsening newer half `not improving`.
 * The bars (1.25x and 0.75x) are fixed here so the reading cannot be tuned after the fact.
 */
export const RISE_BAR = 1.25
export const FALL_BAR = 0.75

export function verdicts(weeks: readonly GardenWeek[], card: GardenCard): GardenVerdict[] {
  if (weeks.length < VERDICT_WEEKS) return []
  const rows = [...weeks].sort((a, b) => a.at - b.at)
  const out: GardenVerdict[] = []
  for (const m of card.metrics) {
    const series = rows.map(r => r.values[m.key]).filter((v): v is number => typeof v === 'number')
    if (series.length < VERDICT_WEEKS) {
      out.push({ key: m.key, label: m.label, reading: 'too few weeks' })
      continue
    }
    const sign = m.better === 'higher' ? 1 : -1
    const half = Math.floor(series.length / 2)
    const gain = (list: number[]) => (list.length < 2 ? 0 : (sign * ((list[list.length - 1] ?? 0) - (list[0] ?? 0))) / (list.length - 1))
    const older = gain(series.slice(0, half + 1))
    const newer = gain(series.slice(half))
    let reading: GardenVerdict['reading']
    if (newer < 0) reading = 'not improving'
    else if (older <= 0) reading = newer > 0 ? 'compounding' : 'flat'
    else if (newer >= older * RISE_BAR) reading = 'compounding'
    else if (newer <= older * FALL_BAR) reading = 'saturating'
    else reading = 'linear'
    out.push({ key: m.key, label: m.label, reading })
  }
  return out
}

export function fmt(value: number | null, unit: string): string {
  if (value === null) return 'n/a'
  if (unit === 'USD') return `$${value.toFixed(2)}`
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

/** One plain-text form of the card, for the command's answer where no pane is placed, and for the toast. */
export function cardText(card: GardenCard, weeks: readonly GardenWeek[]): string {
  const lines: string[] = []
  lines.push(`Garden score, week ending ${new Date(card.at).toISOString().slice(0, 10)} (vs the 4 weeks before)`)
  for (const m of card.metrics) lines.push(`  ${m.label}: ${fmt(m.week, m.unit)} this week, ${fmt(m.base, m.unit)} a week before${trend(m)}`)
  const c = card.cadence
  lines.push(c.days === null
    ? '  Harvest cadence: no compression log found'
    : `  Harvest cadence: last compression log ${c.days} days ago, ${c.sessionsSince ?? 'n/a'} sessions since`)
  if (c.ritual) lines.push(`  Ritual offers this week: ${ritualLine(c.ritual)}`)
  const v = verdicts(weeks, card)
  if (v.length === 0) lines.push(`  Compounding reading: needs ${Math.max(0, VERDICT_WEEKS - weeks.length)} more weekly rows`)
  else lines.push('  Compounding reading: ' + v.map(x => `${x.key} ${x.reading}`).join(', '))
  for (const n of card.notes) lines.push(`  Note: ${n}`)
  return lines.join('\n')
}

export function ritualLine(r: RitualCounts): string {
  return `${r.offered} offered, ${r.accepted} accepted, ${r.declined} declined`
}

/** `better`, `worse` or `same` for one metric, as a short suffix; nothing when either side is unknown. */
export function direction(m: GardenMetric): 'better' | 'worse' | 'same' | undefined {
  if (m.week === null || m.base === null) return undefined
  if (m.week === m.base) return 'same'
  const up = m.week > m.base
  return (m.better === 'higher') === up ? 'better' : 'worse'
}

function trend(m: GardenMetric): string {
  const d = direction(m)
  return d === undefined ? '' : ` (${d})`
}
