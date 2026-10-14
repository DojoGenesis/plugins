// The state contract of dojo-lanes: one value, `board`, kept by the host for the session. It is plain JSON,
// so it survives a hot reload of the module, and it is the only thing /lanes reads.

/** One agent the mod has seen: spawned through `agent.spawn`, or adopted the first time it wrote. */
export type LaneAgent = {
  id: string
  /** `name ?? description ?? subagentType` of the spawn. */
  label: string
  /** The spawn's `subagentType`; '' when the agent was adopted without one. */
  type: string
  /** False for the read-only types (Explore, Plan, :scout, :reviewer, :judge, :researcher ...). */
  canWrite: boolean
  /**
   * `parked`: its turn ended but the engine's list still shows it alive (waiting on background work, say), so it keeps
   * its lanes: it may wake and write again.
   */
  status: 'running' | 'parked' | 'settled'
  startedAt: number
  /** A turn.complete was seen at this time and the 2.5 s recheck has not decided yet. Cleared by its next write. */
  endedAt?: number
  /** When the recheck parked it. */
  parkedAt?: number
  settledAt?: number
  /** How it ended: a turn.complete reason, the engine's status for it, or why the mod let it go. */
  how?: string
  /** Spawned by a workflow script: never settled by its absence from the engine's agent list. */
  workflow?: boolean
  /** First seen when it wrote, not at its spawn. */
  adopted?: boolean
  /** The engine's agent list has named it at least once. An adopted agent is settled by absence only after that. */
  listed?: boolean
}

/** A turn.complete that arrived for an agent the board did not know yet (its spawn is still being recorded). */
export type Ended = {
  id: string
  at: number
  how: string
}

/** One claim: `agentId` was the first writer of `path`. Kept after release, marked by `releasedAt`. */
export type Lane = {
  path: string
  agentId: string
  claimedAt: number
  releasedAt?: number
}

/** A write that met another running agent's lane. */
export type Contest = {
  at: number
  path: string
  /** Who wanted to write; `main` for the main loop. */
  label: string
  holderId: string
  holderLabel: string
  /** `refused` (lock), `warned` (warn, allowed), `main` (main loop, always allowed). */
  kind: 'refused' | 'warned' | 'main'
}

export type Board = {
  agents: LaneAgent[]
  lanes: Lane[]
  /** The most recent contested attempts, oldest first. */
  contested: Contest[]
  refused: number
  warned: number
  mainWrites: number
  /** Keys of the once-only log lines already shown. */
  noted: string[]
  /** The no-contract nudge was already toasted in the current wave. */
  waveToasted: boolean
  /** Recent turn.completes of agents not on the board yet, so a spawn recorded late stays settled. */
  ended: Ended[]
}

declare module 'claude-code' {
  interface PluginState {
    'dojo-lanes': { board: Board }
  }
}
