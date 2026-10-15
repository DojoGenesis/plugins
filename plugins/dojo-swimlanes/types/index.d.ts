// dojo-swimlanes' state contract: what the pane draws from, held by the host for the session.

export type LaneStatus = 'running' | 'waiting' | 'returned' | 'failed' | 'aborted'

export type CallKind = 'read' | 'write' | 'bash' | 'agent' | 'other'

// One tool call of one subagent.
export type Call = {
  id: string
  tool: string
  kind: CallKind
  t0: number
  // Absent while the call runs.
  t1?: number
  ok?: boolean
  // Why the call was refused or errored (at most 200 characters).
  deny?: string
  // The file, pattern or first line of the command (at most 80 characters).
  target?: string
}

export type LaneAgent = {
  // The agent's loop id.
  id: string
  // Its number in this session, from 1, in spawn order.
  n: number
  label: string
  type: string
  model?: string
  spawnedAt: number
  // When its last turn ended; a waiting agent keeps it (the dashed tail starts there).
  endedAt?: number
  status: LaneStatus
  calls: Call[]
}

export type Timeline = { agents: LaneAgent[]; nextN: number }

declare module 'claude-code' {
  interface PluginState {
    'dojo-swimlanes': {
      timeline: Timeline
      // Bumped by the clock while agents are live, so the drawing redraws.
      tick: number
      // Show every kept agent instead of the latest wave.
      isAll: boolean
    }
  }
}
