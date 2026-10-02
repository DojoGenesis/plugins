import { PRICING } from './pricing'
import type { MeterBand } from '../types'

// Pure functions for the dojo-meter mod: no engine calls, so the arithmetic is testable on its own.
//
// Money is kept as integer "units" of 1e-10 USD so round-number cases are exact:
//   units = tokens x (price per million x 100) x (multiplier x 100)    and    USD = units / 1e10
// The mod sees one flat cache-write count per request (no 5-minute / 1-hour split), so it prices every
// write at the 5-minute multiplier. The cost report reads the split and can read higher.

export type Row = {
  loop: string
  model: string // normalized id
  input: number
  output: number
  cacheRead: number
  cacheWrite: number
  requests: number
}
export type Ledger = Map<string, Row>
export type TierName = 'opus' | 'sonnet' | 'haiku' | 'fable' | 'other'
export type Estimate = {
  byTier: Partial<Record<TierName, number>> // units, tiers that had a priced request
  total: number // units, priced requests only
  unpricedTokens: number
  // False when no priced token backs the figure and an unpriced model is in the ledger (even one with no usable
  // counts): the figure is then 'unpriced', never a bare $0.00. Same rule as cost.py Bucket.value.
  hasPriced: boolean
}

export const TIER_ORDER: readonly TierName[] = ['opus', 'sonnet', 'haiku', 'fable', 'other']
export const UNITS_PER_USD = 1e10

const MAX_MODEL_LENGTH = 200

// Same rules as scripts/cost.py normalize_model; tests/model_vectors.json drives both.
export function normalizeModel(raw: unknown): string {
  if (typeof raw !== 'string') return ''
  let text = raw.trim().toLowerCase()
  if (text === '' || text.length > MAX_MODEL_LENGTH) return ''
  text = text.replace(/\[[^\]]*\]/g, '')
  text = text.replace(/^(?:[a-z0-9_-]+[./])+(?=claude-)/, '')
  text = text.replace(/@\d{8}$/, '')
  text = text.replace(/-v\d+(?::\d+)?$/, '')
  text = text.replace(/-\d{8}$/, '')
  return text.trim()
}

export function tierOf(normalized: string): TierName {
  for (const tier of TIER_ORDER) {
    if (tier !== 'other' && normalized.includes(tier)) return tier
  }
  return 'other'
}

export type Price = { input: number; output: number; cache_read: number }

// The pricing.json key an id is priced as, or undefined (unpriced). An id is priced only when it IS a known id, or a
// known id plus one known variant decoration ("-fast" or "-latest"; the date, bracket and provider tags are already
// gone after normalizeModel). It is never priced by resemblance: a newer version number (claude-opus-5-6,
// claude-opus-5-50), an unknown suffix ("-preview") or junk after a known id stays unpriced. Same rule as
// scripts/cost.py price_key; tests/model_vectors.json drives both.
const hasKey = (key: string): boolean => Object.prototype.hasOwnProperty.call(PRICING.models, key)
const VARIANT = /-(?:fast|latest)$/

export function priceKeyFor(normalized: string): string | undefined {
  if (hasKey(normalized)) return normalized
  const base = normalized.replace(VARIANT, '')
  if (base !== normalized && hasKey(base)) return base
  return undefined
}

export function priceFor(normalized: string): Price | undefined {
  const key = priceKeyFor(normalized)
  return key === undefined ? undefined : PRICING.models[key]
}

const scaled = (price: number): number => Math.round(price * 100)

export function count(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : 0
}

// Adds one request's usage to the ledger. Returns the request's input-side size (input + cache read +
// cache creation), the context the model was shown, or undefined when there was no usable usage.
export function addUsage(ledger: Ledger, loop: string, usage: unknown): number | undefined {
  if (typeof usage !== 'object' || usage === null) return undefined
  const u = usage as Record<string, unknown>
  const model = normalizeModel(u.model)
  const key = `${loop}\u0000${model}`
  const row: Row = ledger.get(key) ?? { loop, model, input: 0, output: 0, cacheRead: 0, cacheWrite: 0, requests: 0 }
  const input = count(u.input_tokens)
  const cacheRead = count(u.cache_read_input_tokens)
  const cacheWrite = count(u.cache_creation_input_tokens)
  row.input += input
  row.output += count(u.output_tokens)
  row.cacheRead += cacheRead
  row.cacheWrite += cacheWrite
  row.requests += 1
  ledger.set(key, row)
  return input + cacheRead + cacheWrite
}

export function estimateUsd(ledger: Ledger): Estimate {
  const byTier: Partial<Record<TierName, number>> = {}
  let total = 0
  let unpricedTokens = 0
  let unpricedRows = 0
  let pricedTokens = 0
  const writeMultiplier = Math.round(PRICING.cache_write_5m_multiplier * 100)
  for (const row of ledger.values()) {
    const tokens = row.input + row.output + row.cacheRead + row.cacheWrite
    const price = priceFor(row.model)
    if (price === undefined) {
      unpricedTokens += tokens
      unpricedRows += 1
      continue
    }
    const input = scaled(price.input)
    const units =
      row.input * input * 100 +
      row.output * scaled(price.output) * 100 +
      row.cacheRead * scaled(price.cache_read) * 100 +
      row.cacheWrite * input * writeMultiplier
    const tier = tierOf(row.model)
    byTier[tier] = (byTier[tier] ?? 0) + units
    total += units
    pricedTokens += tokens
  }
  const hasPriced = !(pricedTokens === 0 && unpricedRows > 0)
  return { byTier: hasPriced ? byTier : {}, total, unpricedTokens, hasPriced }
}

// Cache-read share of input-side tokens: read / (input + write + read), or undefined with no traffic.
export function cacheShare(ledger: Ledger): number | undefined {
  let read = 0
  let side = 0
  for (const row of ledger.values()) {
    read += row.cacheRead
    side += row.input + row.cacheWrite + row.cacheRead
  }
  return side > 0 ? read / side : undefined
}

export function formatTokens(n: number): string {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (n >= 1e4) return `${Math.round(n / 1e3)}k`
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}k`
  return String(Math.round(n))
}

export function formatUsd(units: number): string {
  if (units > 0 && units < 1e8) return '<$0.01'
  return `$${(Math.round(units / 1e8) / 100).toFixed(2)}`
}

export function formatBudget(usd: number): string {
  return Number.isInteger(usd) ? `$${usd}` : `$${usd.toFixed(2)}`
}

export function percentText(fraction: number): string {
  return `${Math.round(fraction * 100)}%`
}

// The local calendar date of a time in milliseconds, as YYYY-MM-DD. It matches the report's local midnight.
export function dayKey(ms: number): string {
  const date = new Date(ms)
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

export type BandInput = {
  ledger: Ledger
  ctxTokens?: number
  ctxWindow?: number
  todayBaseUnits?: number // today's stored total, units, as of the last flush
  todayUnpricedTokens?: number // today's stored count of tokens that had no price, as of the last flush
  flushedUnits: number // the part of this session's total already inside todayBaseUnits
}

// The band's content, or null while the ledger holds nothing to show.
export function buildBand(input: BandInput): MeterBand | null {
  if (input.ledger.size === 0) return null
  const estimate = estimateUsd(input.ledger)
  const tiers = TIER_ORDER.filter(tier => estimate.byTier[tier] !== undefined)
    .map(tier => `${tier} ${formatUsd(estimate.byTier[tier] ?? 0)}`)
    .join(' · ')
  let total = estimate.hasPriced ? formatUsd(estimate.total) : 'unpriced'
  if (estimate.hasPriced && estimate.unpricedTokens > 0) total += ' (partial)'
  let ctx: string | null = null
  if (input.ctxTokens !== undefined) {
    ctx = formatTokens(input.ctxTokens)
    if (input.ctxWindow !== undefined && input.ctxWindow > 0) {
      ctx += ` (${percentText(input.ctxTokens / input.ctxWindow)})`
    }
  }
  const share = cacheShare(input.ledger)
  let today: string | null = null
  if (input.todayBaseUnits !== undefined) {
    const units = input.todayBaseUnits + Math.max(0, estimate.total - input.flushedUnits)
    const hasUnpriced = (input.todayUnpricedTokens ?? 0) > 0 || estimate.unpricedTokens > 0
    // Unpriced spend is never shown as $0: with no priced dollars the figure reads 'unpriced', otherwise '(partial)'.
    today = hasUnpriced ? (units > 0 ? `${formatUsd(units)} (partial)` : 'unpriced') : formatUsd(units)
  }
  return { tiers, total, ctx, cache: share === undefined ? null : percentText(share), today }
}

// One line that fits `columns`, dropping the least important parts first: today, cache, the tier split, ctx.
export function fitBand(band: MeterBand, columns: number): string {
  const money = band.tiers === '' ? `≈ ${band.total}` : `${band.tiers} ≈ ${band.total}`
  const withParts = (parts: (string | null)[]): string => ['meter  ' + money, ...parts.filter(p => p !== null)].join('  |  ')
  const ctx = band.ctx === null ? null : `ctx ${band.ctx}`
  const cache = band.cache === null ? null : `cache ${band.cache}`
  const today = band.today === null ? null : `today ${band.today}`
  const short = `meter  ≈ ${band.total}`
  const candidates = [
    withParts([ctx, cache, today]),
    withParts([ctx, cache]),
    withParts([ctx]),
    [short, ctx].filter(p => p !== null).join('  |  '),
    short,
  ]
  for (const candidate of candidates) {
    if (candidate.length <= columns) return candidate
  }
  const last = candidates[candidates.length - 1] ?? short
  return columns > 1 ? last.slice(0, columns - 1) + '…' : last.slice(0, Math.max(columns, 0))
}
