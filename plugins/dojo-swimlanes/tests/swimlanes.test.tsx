import { expect, mock, test } from 'claude-code/testing'

import type { LaneAgent } from '../types'
import { buildLanesSvg, esc, niceStep, stripOf, ticksOf, viewOf, wavesOf } from '../hooks/model'

// Mod kit tests. The hooks a test registers with `on` sit beneath the plugin and stand for the engine.

const T0 = 1_000_000

type Listed = { id: string; status: string; description: string; type: string }
type World = { listed: Listed[]; clock: ReturnType<typeof mock.clock>; stateDown: boolean }

function world(on: any, env: Record<string, string> = {}): World {
  const w: World = { listed: [], clock: mock.clock(on, { now: T0 }), stateDown: false }
  let ids = 0
  mock.env(on, env)
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('command.register', (_$: any, e: any) => ({ value: { command: e.name } }))
  on('agent.spawn', (_$: any, e: any) => {
    const agentId = `ag-${++ids}`
    w.listed.push({ id: agentId, status: 'running', description: e.description, type: e.subagentType })
    return { model: e.model ?? 'claude-haiku-4-5', agentId }
  })
  on('agent.list', () => ({ value: w.listed.map(one => ({ ...one })) }))
  on('tool.call', (_$: any, e: any) => {
    const command = String(e.command ?? '')
    if (e.tool === 'Bash' && command.startsWith('rm')) return { deny: 'rm is not allowed here' }
    if (e.tool === 'Grep') return { result: {}, text: 'pattern is invalid', isError: true }
    return { result: {}, text: 'ok' }
  })
  on('turn.complete', (_$: any, e: any) => {
    const listed = w.listed.find(one => one.id === e.agentId)
    if (listed) listed.status = 'completed'
    return { text: e.answer }
  })
  on('session.start', (_$: any, e: any) => ({ cwd: e.cwd }))
  // Stands for a state store that fails once a test says so.
  on('state.set', (_$: any, e: any, next: any) => {
    if (w.stateDown) throw new Error('state is down')
    return next(e)
  })
  return w
}

const start = ($: any) => $.session.start({ source: 'startup', cwd: '/work/demo', surface: 'terminal', isInteractive: true })
const spawn = ($: any, description: string) => $.agent.spawn({ prompt: `Build ${description}`, description, subagentType: 'general-purpose' })
const call = ($: any, agentId: string, tool: string, extra: Record<string, unknown> = {}) => $.tool.call({ tool, agentId, ...extra } as any)
let turns = 0
const complete = ($: any, agentId: string, answer: string, extra: Record<string, unknown> = {}) =>
  $.turn.complete({ answer, durationMs: 1, isAborted: false, turnId: `t${++turns}`, reason: 'answer', agentId, ...extra })
const swim = async ($: any, args = 'text'): Promise<string> => (await $.command.run({ command: 'swimlanes', args })).text

const PANE = {
  title: 'Swimlanes',
  isFocused: true,
  bodyColumns: 100,
  placement: 'dock' as const,
  scroll: { offset: 0, bodyRows: 30 },
  view: {},
}

function agent(over: Partial<LaneAgent>): LaneAgent {
  return { id: 'x', n: 1, label: 'a', type: 't', spawnedAt: 0, status: 'returned', endedAt: 1000, calls: [], ...over }
}

test('spawn, calls and complete build a lane per agent', async ($, on) => {
  const w = world(on)
  await start($)
  await spawn($, 'Draft the notes')
  await spawn($, 'Check the links')
  await call($, 'ag-1', 'Read', { file_path: '/work/demo/notes.md' })
  await w.clock.advance(4000)
  await call($, 'ag-1', 'Edit', { file_path: '/work/demo/notes.md' })
  await call($, 'ag-2', 'Bash', { command: 'ls -la\nsecond line' })
  await w.clock.advance(5000)
  await complete($, 'ag-1', 'Done.')
  const text = await swim($)
  expect(text).not.toMatch(/^dojo-swimlanes/)
  expect(text).toMatch(/^Wave 1 · 2 agents · 1 running · 1 done · 9s/)
  expect(text).toMatch(/#1 Draft the notes +haiku 4\.5 +[▮·]+ +returned/)
  expect(text).toMatch(/#2 Check the links +haiku 4\.5 +.*running/)
  expect(text).toContain('▮')
})

test('a refused call is a deny mark whose title holds the deny text', async ($, on) => {
  world(on)
  await start($)
  await spawn($, 'cleaner')
  await call($, 'ag-1', 'Bash', { command: 'rm -rf /work/demo/tmp' })
  await call($, 'ag-1', 'Grep', { pattern: 'a(' })
  const ui = await $.ui.mount({ plugin: 'dojo-swimlanes', surface: 'desktop', component: 'Pane', requestId: 'dojo-swimlanes', props: PANE })
  const svg = await ui.find({ type: 'Svg' })
  expect(svg).toBeDefined()
  const source = String(svg?.props.source)
  // The agent is still live: a plain image, since a reloading interactive frame blinked on the desktop.
  expect(svg?.props.isInteractive).toBe(false)
  expect(source).toMatch(/<title>#1 Bash rm -rf \/work\/demo\/tmp · [^<]*\nrm is not allowed here<\/title>/)
  expect(source).toContain('pattern is invalid')
  expect(source).toContain('fill="#e76f51"')
  expect(source).toContain('✗')
  expect(String(svg?.props.alt)).toMatch(/2 refused or failed/)
  await ui.unmount()
})

test('after the recheck a parked agent is waiting and a finished one is done', async ($, on) => {
  const w = world(on)
  await start($)
  await spawn($, 'parked')
  await spawn($, 'finished')
  await complete($, 'ag-1', 'turn one')
  await complete($, 'ag-2', 'all done')
  // The engine still holds the first (background work of its own).
  const parked = w.listed.find(one => one.id === 'ag-1')
  if (parked) parked.status = 'waiting'
  await w.clock.advance(3000)
  const text = await swim($)
  expect(text).toMatch(/^Wave 1 · 2 agents · 1 waiting · 1 done/)
  expect(text).toMatch(/#1 parked .*┄.* waiting/)
  expect(text).toMatch(/#2 finished .* returned/)
})

test('the default view is the latest wave and /swimlanes all shows every agent', async ($, on) => {
  const w = world(on)
  await start($)
  await spawn($, 'first')
  await complete($, 'ag-1', 'ok')
  await w.clock.advance(10000)
  await spawn($, 'second')
  await spawn($, 'third')
  const latest = await swim($)
  expect(latest).toMatch(/^Wave 2 · 2 agents/)
  expect(latest).not.toContain('#1 first')
  expect(await swim($, '')).toBe('2 agents in view')
  expect(await swim($, 'all')).toBe('3 agents in view')
  expect(await swim($)).toMatch(/^All waves · 3 agents/)
  expect(await swim($, 'all')).toBe('2 agents in view')
  // The same split from the pure function: a live agent keeps its wave open.
  const waves = wavesOf([agent({ n: 1, spawnedAt: 0, endedAt: 100 }), agent({ n: 2, spawnedAt: 50, endedAt: 200 }), agent({ n: 3, spawnedAt: 500, endedAt: 900 })])
  expect(waves.map(one => one.length)).toEqual([2, 1])
  expect(viewOf([agent({ n: 1, status: 'waiting', spawnedAt: 0 }), agent({ n: 2, spawnedAt: 9999 })], false).agents).toHaveLength(2)
})

test('time ticks are nice steps with at most eight on the axis', () => {
  expect(niceStep(3000)).toBe(1000)
  expect(niceStep(9000)).toBe(2000)
  expect(niceStep(30000)).toBe(5000)
  expect(niceStep(60000)).toBe(10000)
  expect(niceStep(100000)).toBe(15000)
  expect(niceStep(240000)).toBe(30000)
  expect(niceStep(600000)).toBe(120000)
  for (const span of [5000, 20000, 45000, 90000, 300000, 900000]) {
    const count = ticksOf(span).length
    expect(count).toBeGreaterThanOrEqual(4)
    expect(count).toBeLessThanOrEqual(9)
  }
})

test('a label with < & and quotes is escaped in the SVG', () => {
  expect(esc(`a<b & "c"`)).toBe('a&lt;b &amp; &quot;c&quot;')
  const bad = agent({ n: 1, label: `x<script>&"y"`, spawnedAt: 0, endedAt: 5000, calls: [{ id: 'c', tool: 'Read', kind: 'read', t0: 100, t1: 900, target: `<img "&">` }] })
  const svg = buildLanesSvg({ agents: [bad], waveNo: 1, isAll: false }, 6000, 80)
  expect(svg).not.toContain('<script>')
  expect(svg).not.toContain('<img')
  expect(svg).toContain('x&lt;script&gt;&amp;&quot;y&quot;')
  expect(svg).toContain('&lt;img &quot;&amp;&quot;&gt;')
  expect(svg.startsWith('<svg ')).toBe(true)
  expect(svg.length).toBeLessThan(131072)
})

test('the terminal strip has one glyph per bucket: call, refusal, idle, waiting', () => {
  const calls = [
    { id: 'a', tool: 'Read', kind: 'read' as const, t0: 0, t1: 900 },
    { id: 'b', tool: 'Bash', kind: 'bash' as const, t0: 3000, t1: 3100, deny: 'no' },
  ]
  const done = agent({ spawnedAt: 0, endedAt: 8000, calls })
  expect(stripOf(done, 0, 8000, 8000, 8)).toBe('▮··✗····')
  const parked = agent({ spawnedAt: 0, endedAt: 2000, status: 'waiting', calls: [] })
  expect(stripOf(parked, 0, 6000, 6000, 6)).toBe('··┄┄┄┄')
})

test('the terminal pane draws rows, the desktop pane draws the SVG', async ($, on) => {
  const w = world(on)
  await start($)
  await spawn($, 'Draft the notes')
  await call($, 'ag-1', 'Read', { file_path: '/work/demo/a.md' })
  await w.clock.advance(2000)
  const term = await $.ui.mount({ plugin: 'dojo-swimlanes', surface: 'terminal', component: 'Pane', requestId: 'dojo-swimlanes', props: PANE })
  expect(await term.find({ type: 'Text', text: /#1 Draft the notes .*▮/ })).toBeDefined()
  expect(await term.find({ type: 'Svg' })).toBeUndefined()
  expect(await term.find({ type: 'Button', key: 'all' })).toBeDefined()
  await term.unmount()
  const desk = await $.ui.mount({ plugin: 'dojo-swimlanes', surface: 'desktop', component: 'Pane', requestId: 'dojo-swimlanes', props: PANE })
  const svg = await desk.find({ type: 'Svg' })
  expect(String(svg?.props.source)).toContain('>now<')
  expect(String(svg?.props.source)).toContain('height="92"')
  await desk.unmount()
})

test('the command answers one line, or says nothing has run', async ($, on) => {
  world(on)
  await start($)
  expect(await swim($, '')).toBe('No subagent has run yet')
  expect(await swim($)).toBe('No subagent has run yet')
  await spawn($, 'one')
  expect(await swim($, '')).toBe('1 agents in view')
  expect((await $.command.run({ command: 'dojo-swimlanes:swimlanes', args: '' } as any)).text).toBe('1 agents in view')
})

test('a bookkeeping failure never refuses a tool call', async ($, on) => {
  const w = world(on)
  await start($)
  await spawn($, 'one')
  w.stateDown = true
  const ran = await call($, 'ag-1', 'Read', { file_path: '/work/demo/a.md' })
  expect(ran.deny).toBeUndefined()
  expect(ran.text).toBe('ok')
})

test('DOJO_SWIMLANES_OFF turns the mod into a pass-through', async ($, on) => {
  world(on, { DOJO_SWIMLANES_OFF: '1' })
  await start($)
  await spawn($, 'one')
  const ran = await call($, 'ag-1', 'Read', { file_path: '/work/demo/a.md' })
  expect(ran.text).toBe('ok')
  expect(await swim($, 'text')).toBe('No subagent has run yet')
})

// Seen live on the desktop (2.1.295): an interactive Svg is a sandboxed frame that reloads on every new source,
// so a chart redrawn each second blinked. Live lanes draw a plain image; a settled wave draws interactive.
test('the desktop chart is a plain image while lanes are live and interactive once the wave settles', async ($, on) => {
  const w = world(on)
  await start($)
  await spawn($, 'Draft the notes')
  await call($, 'ag-1', 'Read', { file_path: '/work/demo/a.md' })
  const live = await $.ui.mount({ plugin: 'dojo-swimlanes', surface: 'desktop', component: 'Pane', requestId: 'dojo-swimlanes', props: PANE })
  expect((await live.find({ type: 'Svg' }))?.props.isInteractive).toBe(false)
  await live.unmount()
  await complete($, 'ag-1', 'done')
  await w.clock.advance(3000)
  const settled = await $.ui.mount({ plugin: 'dojo-swimlanes', surface: 'desktop', component: 'Pane', requestId: 'dojo-swimlanes', props: PANE })
  expect((await settled.find({ type: 'Svg' }))?.props.isInteractive).toBe(true)
  await settled.unmount()
})

test('the enabled option off turns the mod into a pass-through, as the kill switch does', { options: { enabled: false } }, async ($, on) => {
  world(on)
  await start($)
  await spawn($, 'one')
  const ran = await call($, 'ag-1', 'Read', { file_path: '/work/demo/a.md' })
  expect(ran.text).toBe('ok')
  expect(await swim($, 'text')).toBe('No subagent has run yet')
})
