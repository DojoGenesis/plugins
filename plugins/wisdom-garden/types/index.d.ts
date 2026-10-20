// Types for the wisdom-garden mod (/garden-score). Self-contained: it imports nothing and names no engine member.

/** One read of a memory file or a skill, as the reuse log keeps it. */
export type GardenRead = {
  /** The file name without `.md` (`seed_zero-overlap`), or `skill:<name>`. */
  id: string
  kind: 'seed' | 'feedback' | 'reference' | 'project' | 'skill'
  /** The file's `name:` slug, when it has one. */
  name?: string
  /** When it was read, epoch ms. */
  t: number
  /** The session that read it. */
  s: string
  /** Why it was stale at that moment: `expired`, `superseded`, `old`. Absent when it was not. */
  stale?: string[]
}

/** One session's totals, kept up to date at each main-thread turn. */
export type GardenSession = {
  s: string
  /** When the session first finished a turn, epoch ms. */
  t: number
  /** The session's cost so far as /cost totals it, when the host keeps one. */
  usd?: number
  turns: number
}

export type GardenMetric = {
  key: string
  label: string
  better: 'higher' | 'lower'
  /** This week's figure, or null when it could not be measured. */
  week: number | null
  /** The weekly average over the four weeks before, or null. */
  base: number | null
  unit: string
  note?: string
}

export type GardenCadence = {
  /** The newest compression log's date, epoch ms, or null. */
  lastCompression: number | null
  days: number | null
  sessionsSince: number | null
  /** The drift ritual hook's offers and answers this week, from ~/.claude/convergence-ledger.md; null without one. */
  ritual: { offered: number; accepted: number; declined: number } | null
}

/** The weekly card the pane draws. */
export type GardenCard = {
  at: number
  from: number
  memoryRoot: string | null
  activeSeeds: number | null
  metrics: GardenMetric[]
  cadence: GardenCadence
  /** Up to 12 ids of stale memories read this week. */
  staleIds: string[]
  sessions: number
  reads: number
  notes: string[]
}

/** One saved week: the figures the compounding reading is drawn from. */
export type GardenWeek = {
  at: number
  activeSeeds: number | null
  values: Record<string, number | null>
}

export type GardenVerdict = {
  key: string
  label: string
  reading: 'compounding' | 'linear' | 'saturating' | 'not improving' | 'flat' | 'too few weeks'
}

declare module 'claude-code' {
  interface PluginState {
    'wisdom-garden': {
      card: GardenCard | null
      weeks: GardenWeek[]
      busy: boolean
    }
  }
}
