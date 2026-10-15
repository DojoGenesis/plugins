import { expect, mock, test } from 'claude-code/testing'

import type { FleetAgent } from '../types'
import { findAgent, fitCols, isWriterBrief, nudgeText, parseSteer, rowParts, stallOf } from '../hooks/model'

// Mod kit tests. The hooks a test registers with `on` sit beneath the plugin and stand for the engine: a spawner
// that hands out agent ids, a tool runner, a message bus that records what was sent, a mocked clock and env.

const MIN = 60000
const T0 = 1_000_000

type Listed = { id: string; status: string; description: string; type: string }

type World = {
  // The engine's task list as `$.agent.list()` answers it: every spawned agent, running, unless a test changes it.
  listed: Listed[]
  toasts: string[]
  logs: string[]
  sent: { to: unknown; text: string }[]
  stops: string[]
  clock: ReturnType<typeof mock.clock>
}

function world(on: any, env: Record<string, string> = {}): World {
  const w: World = { listed: [], toasts: [], logs: [], sent: [], stops: [], clock: mock.clock(on, { now: T0 }) }
  let ids = 0
  mock.env(on, env)
  on('ui.toast', (_$: any, e: any) => {
    w.toasts.push(String(e.text))
    return { value: undefined }
  })
  on('ui.log', (_$: any, e: any) => {
    w.logs.push(String(e.text))
    return { value: undefined }
  })
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('command.register', (_$: any, e: any) => ({ value: { command: e.name } }))
  on('session.send', (_$: any, e: any) => {
    w.sent.push({ to: e.to, text: e.text })
    return { isDelivered: true }
  })
  on('agent.spawn', (_$: any, e: any) => {
    const agentId = `ag-${++ids}`
    if (e.workflow === undefined) w.listed.push({ id: agentId, status: 'running', description: e.description, type: e.subagentType })
    return { model: e.model ?? 'claude-sonnet-5-5', agentId }
  })
  on('agent.list', () => ({ value: w.listed.map(one => ({ ...one })) }))
  on('tool.call', (_$: any, e: any) => {
    if (e.tool === 'TaskStop') w.stops.push(e.task_id)
    return { result: {}, text: 'ok' }
  })
  // The engine marks a subagent done once its turn ends (a test that parks one sets it back to 'waiting').
  on('turn.complete', (_$: any, e: any) => {
    const listed = w.listed.find(one => one.id === e.agentId)
    if (listed) listed.status = 'completed'
    return { text: e.answer }
  })
  on('session.start', (_$: any, e: any) => ({ cwd: e.cwd }))
  // What another plugin (dojo-meter's band) or the engine draws beneath: the fleet band must keep it.
  on('ui.render', () => ({ type: 'Text', props: {}, children: ['beneath'] }))
  return w
}

const start = ($: any) => $.session.start({ source: 'startup', cwd: '/w', surface: 'terminal', isInteractive: true })
const spawn = ($: any, description: string, subagentType = 'general-purpose') =>
  $.agent.spawn({ prompt: `Build ${description}. Owned files: src/${description}.ts`, description, subagentType })
const call = ($: any, agentId: string, tool: string, extra: Record<string, unknown> = {}) =>
  $.tool.call({ tool, agentId, ...extra } as any)
let turns = 0
const complete = ($: any, agentId: string, answer: string, extra: Record<string, unknown> = {}) =>
  $.turn.complete({ answer, durationMs: 1, isAborted: false, turnId: `t${++turns}`, reason: 'answer', agentId, ...extra })
// Raised the way the engine raises a command; `$` loose: the kit's input asks for the origin and presentation the
// engine stamps, which a test has no use for.
const steer = ($: any, args: string): Promise<{ text: string }> => $.command.run({ command: 'steer', args })
const fleet = async ($: any): Promise<string> => (await $.command.run({ command: 'fleet', args: 'list' })).text

const BAND = {
  hasSurvey: false,
  isWorking: true,
  maxRows: 8,
  bodyColumns: 100,
  scroll: { offset: 0, bodyRows: 8 },
  view: {},
}
const PANE = {
  title: 'Fleet',
  isFocused: true,
  bodyColumns: 80,
  placement: 'dock' as const,
  scroll: { offset: 0, bodyRows: 30 },
  view: {},
}

// ------------------------------------------------------------------------------------------------ tracking

test('spawned agents, their work and their ends show in /fleet', async ($, on) => {
  world(on)
  await start($)
  await spawn($, 'api')
  await spawn($, 'web')
  await call($, 'ag-1', 'Edit', { file_path: '/w/src/api.ts', old_string: 'a', new_string: 'b' })
  await call($, 'ag-2', 'Read', { file_path: '/w/src/web.ts' })
  await complete($, 'ag-2', 'Done: web wired, tests green.')
  const text = await fleet($)
  // The engine heads a command's output with the plugin's name: the answer must not repeat it.
  expect(text).not.toMatch(/^dojo-fleet/)
  expect(text).toMatch(/^1 running · 1 returned/)
  expect(text).toMatch(/#1 +api +sonnet 5\.5 +\S+ +1 tool · 1 write +last Edit/)
  expect(text).toMatch(/#2 +web .* returned$/m)
})

test('an aborted, an empty and an errored end each count as not returned', async ($, on) => {
  world(on)
  await start($)
  await spawn($, 'a')
  await spawn($, 'b')
  await spawn($, 'c')
  await complete($, 'ag-1', '', {})
  await complete($, 'ag-2', 'partial', { reason: 'aborted', isAborted: true })
  await complete($, 'ag-3', 'x', { reason: 'error' })
  const text = await fleet($)
  expect(text).toContain('0 running')
  expect(text).toContain('3 failed')
  expect(text).toContain('returned an empty answer')
  expect(text).toContain('interrupted')
  expect(text).toContain('ended on an API error')
})

test('a settled agent that calls a tool again is running again (resumed)', async ($, on) => {
  const w = world(on)
  await start($)
  await spawn($, 'api')
  await complete($, 'ag-1', 'stopped early', { reason: 'aborted', isAborted: true })
  // Resumed (a SendMessage after a stop): the engine lists it running again.
  const resumed = w.listed.find(one => one.id === 'ag-1')
  if (resumed) resumed.status = 'running'
  await call($, 'ag-1', 'Read', { file_path: '/w/a' })
  expect(await fleet($)).toContain('1 running')
})

test('a loop the mod never saw spawn is still listed', async ($, on) => {
  world(on)
  await start($)
  await call($, 'zz-older-agent', 'Read', { file_path: '/w/a' })
  expect(await fleet($)).toMatch(/#1 +agent zz-older/)
})

test('the engine task list settles an agent killed or dropped without an end', async ($, on) => {
  const w = world(on)
  await start($)
  await spawn($, 'killed one')
  await spawn($, 'dropped one')
  await spawn($, 'still busy')
  const killed = w.listed.find(one => one.id === 'ag-1')
  if (killed) killed.status = 'killed'
  w.listed = w.listed.filter(one => one.id !== 'ag-2')
  await w.clock.advance(30000)
  let text = await fleet($)
  expect(text).toMatch(/#1 +killed one .* stopped \(killed\)/)
  // Gone from the list for under a minute: still running.
  expect(text).toMatch(/#2 +dropped one/)
  expect(text).toContain('2 running')
  await w.clock.advance(45000)
  text = await fleet($)
  expect(text).toMatch(/#2 +dropped one .* no longer in the engine's task list/)
  expect(text).toContain('1 running')
})

test('a workflow agent is never settled for being absent from the task list', async ($, on) => {
  const w = world(on)
  await start($)
  await $.agent.spawn({ prompt: 'p', description: 'wf step', subagentType: 'general-purpose', workflow: { runId: 'wf_1', agentIndex: 1 } } as any)
  await w.clock.advance(5 * MIN)
  expect(await fleet($)).toContain('1 running')
})

test('an end that lands before the spawn record keeps the agent settled, with its spawn facts', async ($, on) => {
  const w = world(on)
  await start($)
  await complete($, 'ag-1', 'Done fast.')
  await spawn($, 'quick')
  // By now the engine calls it done.
  const done = w.listed.find(one => one.id === 'ag-1')
  if (done) done.status = 'completed'
  const text = await fleet($)
  expect(text).toContain('0 running')
  expect(text).toMatch(/#1 +quick +sonnet 5\.5 .* returned/)
})

test('/fleet with a placed pane answers one line; /fleet list answers the table', async ($, on) => {
  world(on)
  await start($)
  await spawn($, 'api')
  const short = (await $.command.run({ command: 'fleet', args: '' } as any)).text
  expect(short).toBe('1 running. The Fleet pane is open: pick a row to steer, nudge or stop it. /fleet list prints the list.')
  expect(await fleet($)).toMatch(/^1 running\n  ● #1 +api/)
})

test('a turn that ends while the engine still holds the agent reads waiting, then returned when it is done', async ($, on) => {
  const w = world(on)
  await start($)
  await spawn($, 'parked')
  await call($, 'ag-1', 'Bash', { command: 'sleep 150; ls' })
  await complete($, 'ag-1', 'Started the long command in the background; waiting for it.')
  const held = w.listed.find(one => one.id === 'ag-1')
  if (held) held.status = 'waiting'
  await w.clock.advance(3000)
  let text = await fleet($)
  expect(text).toMatch(/^0 running · 1 waiting/)
  expect(text).toMatch(/◐ #1 +parked .* waiting on its own background work/)
  // It wakes, works, and ends for real.
  await call($, 'ag-1', 'Read', { file_path: '/w/out.txt' })
  expect(await fleet($)).toMatch(/^1 running/)
  await complete($, 'ag-1', 'Done: the command printed 3 files.')
  await w.clock.advance(3000)
  text = await fleet($)
  expect(text).toMatch(/^0 running · 1 returned/)
  expect(text).toMatch(/✓ #1 +parked .* returned/)
})

test('an ordinary end the engine marks completed stays returned (no false waiting)', async ($, on) => {
  const w = world(on)
  await start($)
  await spawn($, 'quick')
  await complete($, 'ag-1', 'All done.')
  await w.clock.advance(20000)
  expect(await fleet($)).toMatch(/^0 running · 1 returned/)
})

test('a parked agent keeps a chip in the band', async ($, on) => {
  const w = world(on)
  await start($)
  await spawn($, 'parked')
  await complete($, 'ag-1', 'waiting on a shell')
  const held = w.listed.find(one => one.id === 'ag-1')
  if (held) held.status = 'waiting'
  await w.clock.advance(3000)
  const ui = await $.ui.mount({ plugin: 'dojo-fleet', surface: 'terminal', component: 'AbovePrompt', props: BAND })
  expect(await ui.find({ type: 'Text', text: /◐ #1 parked .* waiting/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /0 running · 1 waiting/ })).toBeDefined()
  await ui.unmount()
})

test('the classic fallback name /dojo-fleet:fleet is answered by the mod too', async ($, on) => {
  world(on)
  await start($)
  const text = (await $.command.run({ command: 'dojo-fleet:fleet', args: 'list' } as any)).text
  expect(text).toBe('No subagent has run in this session yet.')
})

// ------------------------------------------------------------------------------------------------ steering

test('/steer sends the message into the named agent\'s loop', async ($, on) => {
  const w = world(on)
  await start($)
  await spawn($, 'api')
  await spawn($, 'web')
  const out = await steer($, '#2 stop after this file and report')
  expect(w.sent).toEqual([{ to: 'ag-2', text: 'stop after this file and report' }])
  expect(out.text).toMatch(/^Steered #2 web/)
  expect(w.logs.some(line => line.startsWith('Steered #2 web'))).toBe(true)
})

test('/steer by name, and its usage and unknown-agent answers', async ($, on) => {
  const w = world(on)
  await start($)
  await spawn($, 'api-builder')
  await steer($, 'api use the contract')
  expect(w.sent[0]).toEqual({ to: 'ag-1', text: 'use the contract' })
  expect((await steer($, '')).text).toContain('Running: #1 api-builder')
  expect((await steer($, '#9 hi')).text).toContain('No agent matches "#9"')
  expect((await steer($, '#1')).text).toContain('What should #1')
})

// ------------------------------------------------------------------------------------------------ stalls

test('a stall toasts once; a nudge sends constraints; a second stall says build inline', { options: { stall_minutes: 10 } }, async ($, on) => {
  const w = world(on)
  await start($)
  await spawn($, 'api')
  await w.clock.advance(11 * MIN)
  expect(w.toasts).toHaveLength(1)
  expect(w.toasts[0]).toMatch(/#1 api looks stalled \(no tool call in 1\dm/)
  await w.clock.advance(3 * MIN)
  expect(w.toasts).toHaveLength(1)

  for (const surface of ['terminal'] as const) {
    const ui = await $.ui.mount({ plugin: 'dojo-fleet', surface, component: 'Pane', requestId: 'dojo-fleet', props: PANE })
    await ui.press({ key: 'row:ag-1' })
    expect(await ui.find({ type: 'Text', text: /looks stalled/ })).toBeDefined()
    await ui.press({ key: 'nudge' })
    await ui.unmount()
  }
  expect(w.sent).toHaveLength(1)
  expect(w.sent[0]?.text).toMatch(/dojo-fleet check-in for #1 api: .* make your next tool call a Write or Edit/)

  // It wakes up and writes, which clears the stall; then it goes quiet again.
  await call($, 'ag-1', 'Edit', { file_path: '/w/src/api.ts', old_string: 'a', new_string: 'b' })
  await w.clock.advance(1 * MIN)
  await w.clock.advance(11 * MIN)
  expect(w.toasts).toHaveLength(2)
  expect(w.toasts[1]).toMatch(/stalled again after a nudge .* build the track inline/)
})

test('stall_minutes 0 turns stall checks off', { options: { stall_minutes: 0 } }, async ($, on) => {
  const w = world(on)
  await start($)
  await spawn($, 'api')
  await w.clock.advance(120 * MIN)
  expect(w.toasts).toEqual([])
  expect(await fleet($)).not.toContain('stalled')
})

test('DOJO_FLEET_STALL_MINUTES overrides the option', { options: { stall_minutes: 10 } }, async ($, on) => {
  const w = world(on, { DOJO_FLEET_STALL_MINUTES: '1' })
  await start($)
  await spawn($, 'api')
  await w.clock.advance(75000)
  expect(w.toasts).toHaveLength(1)
  expect(w.toasts[0]).toMatch(/#1 api looks stalled/)
})

const agent = (over: Partial<FleetAgent>): FleetAgent => ({
  id: 'a',
  n: 1,
  label: 'a',
  type: 'general-purpose',
  model: 'sonnet',
  isWriter: true,
  brief: '',
  spawnedAt: 0,
  status: 'running',
  tools: 0,
  reads: 0,
  writes: 0,
  errors: 0,
  inFlight: [],
  stalls: 0,
  nudges: 0,
  steers: 0,
  ...over,
})

test('stallOf: busy readers, hung tools, dry writers and waiting parents', async () => {
  const limit = 10 * MIN
  const reader = agent({ isWriter: false, lastToolAt: 9 * MIN })
  expect(stallOf(reader, [reader], 12 * MIN, limit)).toBeUndefined()
  const writer = agent({ lastToolAt: 11 * MIN })
  expect(stallOf(writer, [writer], 12 * MIN, limit)).toMatch(/nothing written in 12m/)
  const hung = agent({ isWriter: false, inFlight: [{ id: 'x', tool: 'Bash', since: 1 * MIN }], lastToolAt: 1 * MIN })
  expect(stallOf(hung, [hung], 12 * MIN, limit)).toMatch(/Bash has not returned in 11m/)
  const parent = agent({ id: 'p' })
  const child = agent({ id: 'c', parentId: 'p' })
  expect(stallOf(parent, [parent, child], 30 * MIN, limit)).toBeUndefined()
  expect(stallOf(agent({ status: 'returned' }), [], 30 * MIN, limit)).toBeUndefined()
})

test('isWriterBrief: builders write, readers and read-only briefs do not', async () => {
  expect(isWriterBrief('general-purpose', 'Implement the parser in src/parse.ts and run the tests.')).toBe(true)
  expect(isWriterBrief('general-purpose', 'Read big.d.ts and report the count. Write nothing.')).toBe(false)
  expect(isWriterBrief('general-purpose', 'Find every caller of fetchUser and report file:line.')).toBe(false)
  expect(isWriterBrief('Explore', 'Fix the bug in a.ts')).toBe(false)
  expect(isWriterBrief('dojo-protocol:builder', 'Edit src/a.ts per the contract.')).toBe(true)
})

test('a reader is nudged to report, a builder to write', async () => {
  const reader = agent({ isWriter: false, label: 'reader' })
  const builder = agent({ isWriter: true, label: 'builder' })
  expect(nudgeText(reader, 'no tool call in 11m')).toMatch(/stop and report what you have so far/)
  expect(nudgeText(reader, 'no tool call in 11m')).not.toMatch(/Write or Edit/)
  expect(nudgeText(builder, 'nothing written in 11m')).toMatch(/Write or Edit of a file you own/)
})

test('findAgent and parseSteer', async () => {
  const list = [agent({ id: 'x1', n: 1, label: 'api builder' }), agent({ id: 'x2', n: 2, label: 'web' })]
  expect(findAgent(list, '#2')?.id).toBe('x2')
  expect(findAgent(list, '1')?.id).toBe('x1')
  expect(findAgent(list, 'API')?.id).toBe('x1')
  expect(findAgent(list, 'x2')?.id).toBe('x2')
  expect(findAgent(list, '#7')).toBeUndefined()
  expect(parseSteer('  #3   go on  ')).toEqual({ ref: '#3', text: 'go on' })
  expect(parseSteer('#3')).toEqual({ ref: '#3', text: '' })
})

// ------------------------------------------------------------------------------------------------ stop

test('Stop runs TaskStop on the agent, and its aborted end still reads stopped', async ($, on) => {
  const w = world(on)
  await start($)
  await spawn($, 'api')
  const ui = await $.ui.mount({ plugin: 'dojo-fleet', surface: 'desktop', component: 'Pane', requestId: 'dojo-fleet', props: PANE })
  await ui.press({ key: 'row:ag-1' })
  await ui.press({ key: 'stop' })
  await ui.unmount()
  expect(w.stops).toEqual(['ag-1'])
  await complete($, 'ag-1', '', { reason: 'aborted', isAborted: true })
  const text = await fleet($)
  expect(text).toContain('1 stopped')
  expect(text).toContain('stopped from the fleet')
})

// ------------------------------------------------------------------------------------------------ band

test('the band shows only while agents run, and Hide hides it until the next fan-out', async ($, on) => {
  world(on)
  await start($)
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'dojo-fleet', surface, component: 'AbovePrompt', props: BAND })
    expect(await ui.find({ type: 'Text', text: /^fleet$/ })).toBeUndefined()
    await ui.unmount()
  }
  await spawn($, 'api')
  await spawn($, 'web')
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'dojo-fleet', surface, component: 'AbovePrompt', props: BAND })
    expect(await ui.find({ type: 'Text', text: /^fleet$/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /2 running/ })).toBeDefined()
    expect(await ui.find({ type: 'Button', key: 'open' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'beneath' })).toBeDefined()
    await ui.unmount()
  }
  const ui = await $.ui.mount({ plugin: 'dojo-fleet', surface: 'terminal', component: 'AbovePrompt', props: BAND })
  await ui.press({ key: 'hide' })
  expect(await ui.find({ type: 'Text', text: /^fleet$/ })).toBeUndefined()
  await ui.unmount()
  await complete($, 'ag-1', 'ok')
  await complete($, 'ag-2', 'ok')
  await spawn($, 'next wave')
  const again = await $.ui.mount({ plugin: 'dojo-fleet', surface: 'terminal', component: 'AbovePrompt', props: BAND })
  expect(await again.find({ type: 'Text', text: /1 running/ })).toBeDefined()
  await again.unmount()
})

test('with an agent\'s transcript open, the band shows its fleet row and actions, not a second message box', async ($, on) => {
  const w = world(on)
  await start($)
  await spawn($, 'api')
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({
      plugin: 'dojo-fleet',
      surface,
      component: 'AbovePrompt',
      props: { ...BAND, view: { agentId: 'ag-1' } },
    })
    expect(await ui.find({ type: 'Text', text: /#1 api/ })).toBeDefined()
    // The engine's own prompt messages the agent in this view.
    expect(await ui.find({ type: 'Input' })).toBeUndefined()
    expect(await ui.find({ type: 'Button', key: 'nudge' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'beneath' })).toBeDefined()
    await ui.unmount()
  }
  const ui = await $.ui.mount({ plugin: 'dojo-fleet', surface: 'terminal', component: 'AbovePrompt', props: { ...BAND, view: { agentId: 'ag-1' } } })
  await ui.press({ key: 'stop' })
  await ui.unmount()
  expect(w.stops).toEqual(['ag-1'])
})

test('a waiting agent in view offers Stop but no Nudge', async ($, on) => {
  const w = world(on)
  await start($)
  await spawn($, 'parked')
  await complete($, 'ag-1', 'waiting on a shell')
  const held = w.listed.find(one => one.id === 'ag-1')
  if (held) held.status = 'waiting'
  await w.clock.advance(3000)
  const ui = await $.ui.mount({ plugin: 'dojo-fleet', surface: 'terminal', component: 'AbovePrompt', props: { ...BAND, view: { agentId: 'ag-1' } } })
  expect(await ui.find({ type: 'Button', key: 'nudge' })).toBeUndefined()
  expect(await ui.find({ type: 'Button', key: 'stop' })).toBeDefined()
  await ui.unmount()
})

// ------------------------------------------------------------------------------------------------ kill switch

test('DOJO_FLEET_OFF stands the mod down', async ($, on) => {
  const w = world(on, { DOJO_FLEET_OFF: '1' })
  await start($)
  await spawn($, 'api')
  const ui = await $.ui.mount({ plugin: 'dojo-fleet', surface: 'terminal', component: 'AbovePrompt', props: BAND })
  expect(await ui.find({ type: 'Text', text: /^fleet$/ })).toBeUndefined()
  await ui.unmount()
  await w.clock.advance(60 * MIN)
  expect(w.toasts).toEqual([])
})

// ------------------------------------------------------------------------------------------------ narrow pane

// The 2026-10-14 field test: at about 60 columns the pane's fixed-width boxes shrank with the row and short cells
// wrapped ("haiku / 5.5", "25 / s"). The columns are now sized to the pane, and model and age are never wrapped.
const rowsFor = (...over: Partial<FleetAgent>[]) =>
  over.map((o, i) => rowParts(agent({ id: `a${i}`, n: i + 1, model: 'claude-haiku-5-5', ...o }), T0 + 25_000, undefined))
const rowWidth = (c: ReturnType<typeof fitCols>, tail: number) =>
  2 + c.id + c.label + c.model + c.age + c.work + (c.work > 0 ? 5 : 4) + tail

test('fitCols: a wide pane keeps every column at its natural width', async () => {
  const parts = rowsFor({ label: 'api-builder', spawnedAt: T0, tools: 12, writes: 3 })
  const cols = fitCols(parts, 120)
  expect(cols).toEqual({ id: 2, label: 11, model: 9, age: 3, work: 19 })
})

test('fitCols: at 58 cells the row fits, the label gives way, and model and age stay whole', async () => {
  const parts = rowsFor(
    { label: 'api-builder', spawnedAt: T0, tools: 12, writes: 3 },
    { label: 'database-migration-author', spawnedAt: T0 - 65_000, tools: 3, writes: 1 },
  )
  const cols = fitCols(parts, 58)
  expect(cols.model).toBe('haiku 5.5'.length) // never shortened while anything else can give
  expect(cols.age).toBeGreaterThanOrEqual('1m30s'.length)
  expect(rowWidth(cols, 12)).toBeLessThanOrEqual(58)
  expect(cols.label).toBeGreaterThanOrEqual(6)
})

test('fitCols: a very narrow pane drops the work column, then truncates; no column reaches zero', async () => {
  const parts = rowsFor({ label: 'database-migration-author', spawnedAt: T0 - 3_700_000, tools: 120, writes: 30 })
  const cols = fitCols(parts, 40)
  expect(cols.work).toBe(0)
  expect(cols.id).toBeGreaterThan(0)
  expect(cols.label).toBeGreaterThanOrEqual(6)
  expect(cols.model).toBeGreaterThanOrEqual(5)
  expect(cols.age).toBeGreaterThanOrEqual(3)
  expect(rowWidth(cols, 12)).toBeLessThanOrEqual(40)
  const tiny = fitCols(parts, 5) // nothing fits: every column keeps its floor and the tail truncates
  expect(tiny.label).toBe(6)
  expect(tiny.model).toBe(5)
  expect(tiny.age).toBe(3)
})

test('the pane at 60 columns never wraps a model or an age cell: both are fixed-width and truncate', async ($, on) => {
  const w = world(on)
  await start($)
  await $.agent.spawn({ prompt: 'Build api. Owned files: src/api.ts', description: 'api', subagentType: 'general-purpose', model: 'claude-haiku-5-5' })
  await w.clock.advance(25_000)
  const props = { ...PANE, bodyColumns: 60 }
  const ui = await $.ui.mount({ plugin: 'dojo-fleet', surface: 'terminal', component: 'Pane', requestId: 'dojo-fleet', props })
  const model = await ui.find({ type: 'Text', text: 'haiku 5.5' })
  const age = await ui.find({ type: 'Text', text: '25s' })
  expect(model).toBeDefined()
  expect(age).toBeDefined()
  expect((model as any).props.wrap).toBe('truncate-end')
  expect((age as any).props.wrap).toBe('truncate-end')
  await ui.unmount()
})
