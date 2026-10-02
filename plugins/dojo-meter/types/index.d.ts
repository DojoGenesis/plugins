// Types for the dojo-meter mod. Self-contained: it imports nothing and names no engine member.

/** One ledger row: the four usage counts for one loop (main, a subagent or a workflow agent) and one model. */
export type MeterLedgerRow = {
  loop: string
  model: string
  input: number
  output: number
  cacheRead: number
  cacheWrite: number
  requests: number
}

/** The session ledger as the mod keeps it: rows in insertion order. */
export type MeterLedger = MeterLedgerRow[]

/** What the band draws, already formatted; the band fits it to the width at draw time. */
export type MeterBand = {
  /** `opus $<x> · sonnet $<y>`: only tiers that have a priced request. Empty when nothing is priced. */
  tiers: string
  /** `$<x>`, `$<x> (partial)` when a model without a price was used, or `unpriced` when no request had a price. */
  total: string
  /** `<n>k (<p>%)`, or null before the first main-thread request. */
  ctx: string | null
  /** `<p>%`, or null when there is no input-side traffic. */
  cache: string | null
  /** `$<x>`, `$<x> (partial)` or `unpriced`: today's stored total plus this session's unflushed share, or null before the first flush. */
  today: string | null
}

declare module 'claude-code' {
  interface PluginState {
    'dojo-meter': {
      band: MeterBand | null
      hidden: boolean
    }
  }
}
