// dojo-tally keeps its ledger in $.state so a hot reload does not lose the waves: plain objects and arrays only.

export type TallyOutcome = 'running' | 'returned' | 'failed' | 'silent' | 'unchecked'

export type TallyAgent = {
  /** Stable number within the session, in spawn order (#1, #2, ...): what /refute takes. */
  no: number
  /** The agent's id: the `agentId` its loop's events carry. */
  id: string
  /** `name ?? description ?? subagentType` of the spawn. */
  label: string
  /** The agent type it was spawned as. */
  type: string
  /** What it runs on, as `agent.spawn` answered. */
  model: string
  /** The wave it belongs to (TallyWave.id). */
  wave: number
  /** True for an agent a workflow script started. */
  isWorkflow: boolean
  /** Clock time (ms) at spawn. */
  startedAt: number
  /** Clock time (ms) of its last tool call; the spawn time before any. */
  lastCallAt: number
  /**
   * Tool calls attempted, by kind. A denied or failed call still counts; `errors` counts those. `reads` is every call
   * that is not a write, bookkeeping aside (so an mcp__ tool counts as looking at something).
   */
  reads: number
  writes: number
  bash: number
  total: number
  errors: number
  /**
   * Its outcome. While `isSettled` is false and `hasEnded` is true this is the provisional one, recorded at its last
   * turn.complete and not yet reported; before any end it is 'running'.
   */
  outcome: TallyOutcome
  /** Why it is not `returned`; '' otherwise. Provisional like `outcome` until it settles. */
  reason: string
  /** Clock time (ms) it first settled; 0 until then. Its life is `settledAt - startedAt`. */
  settledAt: number
  /** True once a turn.complete was recorded for it. It settles only after a recheck finds it really done. */
  hasEnded: boolean
  /** True when a recheck found it ended a turn but still alive (status waiting, running or pending): waiting on its own background work. */
  isParked: boolean
  /** True once it ended for good: the recheck found it done, or reconcile found it gone. */
  isSettled: boolean
  /** True when the mod inferred the end (no turn.complete was seen); a real end that turns up later corrects it. */
  isReconciled: boolean
}

export type TallyWave = {
  id: number
  /** Clock time (ms) the first member spawned. */
  openedAt: number
  /** Clock time (ms) the last member settled; 0 while the wave is open. */
  settledAt: number
  /** The members' `no`, in spawn order. */
  nos: number[]
}

export type TallyJudge = {
  /** The judge's agentId. */
  id: string
  /** The `no` of the agent whose report it is judging. */
  no: number
  label: string
  type: string
  /** True once a turn.complete was recorded; the verdict is posted only when a recheck finds the judge really done. */
  hasEnded: boolean
  isParked: boolean
  /** The last turn's end, recorded: `reason` as turn.complete spells it, whether it was interrupted, its answer (clipped). */
  endReason: string
  endAborted: boolean
  endAnswer: string
}

export type TallyState = {
  agents: TallyAgent[]
  /** The last five waves, oldest first. */
  waves: TallyWave[]
  /** Judges /refute started that have not returned yet. */
  judges: TallyJudge[]
  /** The next agent number. */
  nextNo: number
  /** The next wave id. */
  nextWave: number
  /** The id of the open wave; 0 when none is open. */
  open: number
}

declare module 'claude-code' {
  interface PluginState {
    'dojo-tally': {
      ledger: TallyState
      /** Settled agents' answers (clipped to 8000 characters), by agent `no`; kept apart so tool calls do not rewrite them. */
      answers: Record<string, string>
    }
  }
}
