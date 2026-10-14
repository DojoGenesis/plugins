// dojo-fleet's state contract: what the pane and the band draw from, held by the host for the session.

// `waiting`: it ended a turn, but the engine still holds it (parked on background work of its own); it wakes for
// another turn when that work finishes.
export type FleetStatus = 'running' | 'waiting' | 'returned' | 'failed' | 'aborted' | 'stopped'

// One tool call an agent has started and not yet seen return.
export type FleetCall = { id: string; tool: string; since: number }

export type FleetAgent = {
  // The agent's loop id (agent.spawn's agentId, every later event's agentId).
  id: string
  // Its number in this session, from 1, in spawn order: what /steer and the pane call it.
  n: number
  label: string
  type: string
  model: string
  parentId?: string
  // The workflow run that started it, when a workflow script's agent() did.
  runId?: string
  // Seen in `$.agent.list()` at least once: only such an agent (or one whose spawn the mod saw) may be settled
  // for having left the list.
  wasListed?: boolean
  // Expected to write files (not a read-only type): the stall check watches its writes.
  isWriter: boolean
  // The first words of its brief, for the detail view.
  brief: string
  spawnedAt: number
  endedAt?: number
  status: FleetStatus
  reason?: string
  // The first words of its answer once it settled.
  answer?: string
  tools: number
  reads: number
  writes: number
  errors: number
  lastTool?: string
  lastToolAt?: number
  lastWriteAt?: number
  inFlight: FleetCall[]
  // When the stall check last fired for it (one toast per stall).
  stallNoticedAt?: number
  stalls: number
  nudges: number
  steers: number
}

declare module 'claude-code' {
  interface PluginState {
    'dojo-fleet': {
      agents: FleetAgent[]
      // Bumped by the clock while agents run, so elapsed times and stall flags redraw.
      tick: number
      // The agent the pane's detail view shows.
      selected: string | null
      isBandHidden: boolean
    }
  }
}
