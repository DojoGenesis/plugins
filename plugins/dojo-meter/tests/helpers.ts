import { mock } from 'claude-code/testing'

// Shared setup for the kit tests. The hooks a test registers with `on` sit beneath the plugin and stand for
// the engine: a stand-in model that answers each step with the usage the test planned, a store in memory
// (spied, so tests can read what was written), a mocked clock and environment, and a toast recorder.

export const PROPS = {
  hasSurvey: false,
  isWorking: false,
  maxRows: 6,
  bodyColumns: 100,
  scroll: { offset: 0, bodyRows: 6 },
  view: {},
}

export type Counts = {
  input?: number
  output?: number
  read?: number
  write?: number
}

export type World = {
  plan: { usage: unknown }
  toasts: string[]
  kv: Map<string, unknown>
  storeSets: { key: string; value: unknown }[]
  deleted: string[]
  clock: ReturnType<typeof mock.clock>
}

export type WorldOptions = {
  env?: Record<string, string>
  now?: number
  window?: number
  failStoreSet?: boolean
  failUsage?: boolean
  entries?: Record<string, unknown>
  stepError?: string
}

// Local noon of a calendar date, so the local date key does not depend on the machine's zone.
export const localNoon = (year: number, month: number, day: number): number => new Date(year, month - 1, day, 12).getTime()

export function world(on: any, options: WorldOptions = {}): World {
  const w: World = {
    plan: { usage: null },
    toasts: [],
    kv: new Map<string, unknown>(Object.entries(options.entries ?? {})),
    storeSets: [],
    deleted: [],
    clock: mock.clock(on, { now: options.now ?? localNoon(2026, 10, 2) }),
  }
  mock.env(on, options.env ?? {})
  on('ui.toast', (_$: any, e: any) => {
    w.toasts.push(e.text)
    return { value: undefined }
  })
  on('store.get', (_$: any, e: any) => ({ value: w.kv.get(e.key) }))
  on('store.set', (_$: any, e: any) => {
    if (options.failStoreSet) throw new Error('store unavailable')
    w.storeSets.push({ key: e.key, value: e.value })
    w.kv.set(e.key, e.value)
    return { value: undefined }
  })
  on('store.keys', () => ({ value: [...w.kv.keys()] }))
  on('store.delete', (_$: any, e: any) => {
    w.deleted.push(e.key)
    w.kv.delete(e.key)
    return { value: undefined }
  })
  on('session.usage', () => {
    if (options.failUsage) throw new Error('usage unavailable')
    return {
      value: {
        startedAt: 0,
        context: { window: options.window ?? 1000000, tokens: 0, percent: 0 },
        rateLimits: [],
      },
    }
  })
  // The stand-in model: one step answers with the usage the test planned (or throws when asked to).
  on('turn.step', async function* (_$: any, e: any) {
    if (options.stepError) throw new Error(options.stepError)
    const usage = w.plan.usage
    yield { kind: 'stop', stopReason: 'end_turn', usage }
    return { turnId: e.turnId, index: e.index, answer: '', toolUses: [], stopReason: 'end_turn', usage }
  })
  on('turn.complete', (_$: any, e: any) => ({ text: e.answer, usage: e.usage }))
  // What the engine draws when the plugin steps aside: an empty row.
  on('ui.render', () => ({ type: 'Box', props: {}, children: [] }))
  return w
}

export const usageOf = (model: string, counts: Counts) => ({
  model,
  input_tokens: counts.input ?? 0,
  output_tokens: counts.output ?? 0,
  cache_read_input_tokens: counts.read ?? 0,
  cache_creation_input_tokens: counts.write ?? 0,
})

// One model request, as the engine raises it: the stand-in answers with `usage` (null = a step with none).
// Resolves the chunks the caller received. The caller-side `result` is not populated by the kit, so a test
// shows the plugin left the step alone by what reached the caller: the chunks, and no throw.
export async function step($: any, w: World, usage: unknown, agentId?: string): Promise<any[]> {
  w.plan.usage = usage
  const model = typeof usage === 'object' && usage !== null ? String((usage as any).model ?? 'x') : 'x'
  const stream = $.turn.step({ turnId: 't1', index: 0, model, messageCount: 1, ...(agentId ? { agentId } : {}) })
  const chunks: any[] = []
  for await (const chunk of stream) chunks.push(chunk)
  return chunks
}

export async function complete($: any, agentId?: string): Promise<any> {
  return $.turn.complete({
    answer: 'done',
    durationMs: 1,
    isAborted: false,
    turnId: 't1',
    reason: 'answer',
    ...(agentId ? { agentId } : {}),
  })
}

// What the band shows right now ('' when it draws nothing), read from a mounted AbovePrompt.
export async function bandText($: any, surface: 'terminal' | 'desktop' = 'terminal', props: any = PROPS): Promise<string> {
  const ui = await $.ui.mount({ plugin: 'dojo-meter', surface, component: 'AbovePrompt', props })
  const found = await ui.find({ type: 'Text', text: /meter/ })
  await ui.unmount()
  return found?.text ?? ''
}

// The band command, raised the way the engine raises it. `$` is typed loosely here: the kit's own input type
// asks for the origin and presentation the engine stamps, which a test has no use for.
export async function runBand($: any, args: string): Promise<{ text?: string }> {
  return $.command.run({ command: 'dojo-meter:band', args })
}
