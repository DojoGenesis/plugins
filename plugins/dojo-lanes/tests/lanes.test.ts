import { expect, mock, test } from 'claude-code/testing'

// Mod kit tests. The kit puts the engine beneath the plugin: hooks the test registers with `on` stand for it. The
// world below answers what the mod asks of `$` (the session's directory, whether a file exists, the agent list) and
// records what reaches the bottom: the tool calls that got through, the spawns, the log lines and the toasts. An op's
// stand-in answers `{ value }`; a spawn's answers `{ model, agentId }`.

type Info = { id: string; description: string; type: string; status: string; name?: string }

type World = {
  files: Set<string>
  live: Info[]
  log: string[]
  toast: string[]
  reached: any[]
  spawned: any[]
  registered: any[]
  sets: any[]
  clock: any
  denySpawn: boolean
  listFails: boolean
  /** Raised inside the spawn stand-in, before it answers: what happens while the engine starts the agent. */
  duringSpawn?: ($: any, agentId: string) => Promise<unknown>
}

const void_ = { value: undefined } as any

function world(on: any, opts: { env?: Record<string, string>; cwd?: string; clock?: boolean } = {}): World {
  const w: World = { files: new Set(), live: [], log: [], toast: [], reached: [], spawned: [], registered: [], sets: [], clock: undefined, denySpawn: false, listFails: false }
  mock.env(on, opts.env ?? {})
  if (opts.clock !== false) w.clock = mock.clock(on, { now: 1_000_000 })
  on('session.cwd', () => ({ value: opts.cwd ?? '/work' }))
  on('fs.exists', (_$: any, e: any) => ({ value: w.files.has(e.path) }))
  on('agent.list', () => {
    if (w.listFails) throw new Error('list unavailable')
    return { value: w.live }
  })
  on('ui.log', (_$: any, e: any) => { w.log.push(String(e.text)); return void_ })
  on('ui.toast', (_$: any, e: any) => { w.toast.push(String(e.text)); return void_ })
  on('command.register', (_$: any, e: any) => { w.registered.push(e); return { value: { command: e.name } } as any })
  on('tool.call', (_$: any, e: any) => { w.reached.push(e); return { result: {} as any, text: 'ok' } as any })
  let n = 0
  on('agent.spawn', async (_$: any, e: any) => {
    w.spawned.push(e)
    if (w.denySpawn) return { deny: 'no more agents' }
    const agentId = `a${++n}`
    if (w.duringSpawn !== undefined) await w.duringSpawn(_$, agentId)
    return { model: e.model ?? 'inherit', agentId }
  })
  on('turn.complete', (_$: any, e: any) => ({ text: e.answer, usage: e.usage }))
  on('session.start', (_$: any, e: any) => ({ cwd: e.cwd }))
  on('session.end', (_$: any, e: any) => ({ sessionId: e.sessionId }) as any)
  // the kit answers the session state beneath the plugins; this only watches what the mod writes
  on('state.set', (_$: any, e: any, next: any) => {
    w.sets.push(e)
    return next(e)
  })
  return w
}

let turn = 0
const write = ($: any, path: string, agentId?: string, extra: Record<string, unknown> = {}) =>
  $.tool.call({ tool: 'Write', file_path: path, content: 'x', ...(agentId === undefined ? {} : { agentId }), ...extra } as any)
const spawn = ($: any, description: string, extra: Record<string, unknown> = {}) =>
  $.agent.spawn({ prompt: `do ${description}`, description, subagentType: 'general-purpose', ...extra } as any)
const finish = ($: any, agentId: string | undefined, extra: Record<string, unknown> = {}) =>
  $.turn.complete({ answer: 'done', durationMs: 1, isAborted: false, turnId: `t${++turn}`, reason: 'answer', ...(agentId === undefined ? {} : { agentId }), ...extra })
// A turn ends, and the mod's recheck 2.5 s later reads the engine's list: an agent it does not list (the default here) or
// lists as completed is over, and its lanes are released.
const done = async ($: any, w: World, agentId: string) => {
  await finish($, agentId)
  await w.clock.advance(2500)
}
const lanes = async ($: any): Promise<string> => {
  const text: string = ((await $.command.run({ command: 'lanes', args: '' } as any)) as any).text
  // the engine prefixes a plugin command's output with the plugin's name: the answer must not carry it twice
  expect(text.startsWith('dojo-lanes')).toBe(false)
  return text
}
const denied = (r: any): string | undefined => (typeof r.deny === 'string' ? r.deny : undefined)

// ----------------------------------------------------------------------------------------------- the lock

test('a second running agent writing the holder\'s file is refused with the holder\'s label; another file passes', async ($, on) => {
  const w = world(on)
  await spawn($, 'scout-one')
  await spawn($, 'builder-two')
  const first = await write($, '/work/src/a.ts', 'a1')
  expect(denied(first)).toBe(undefined)
  const second = await write($, '/work/src/a.ts', 'a2')
  const why = denied(second)
  expect(why).toMatch('dojo-lanes: /work/src/a.ts is in scout-one\'s lane')
  expect(why).toMatch('claimed 0s ago')
  expect(why).toMatch('Dojo rule 4')
  expect(why).toMatch('put the change you need in your report so the orchestrator applies it after scout-one returns')
  // the tool never ran for the refused write
  expect(w.reached.length).toBe(1)
  expect(w.log.length).toBe(1)
  expect(w.log[0]).toMatch('refused builder-two writing /work/src/a.ts')
  // a different file is the second agent's own
  expect(denied(await write($, '/work/src/b.ts', 'a2'))).toBe(undefined)
  expect(w.reached.length).toBe(2)
  // and the holder may keep writing what it holds
  expect(denied(await write($, '/work/src/a.ts', 'a1'))).toBe(undefined)
  expect(w.reached.length).toBe(3)
})

test('the age in the refusal follows the clock', async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await write($, '/work/a.ts', 'a1')
  await w.clock.advance(42_000)
  expect(denied(await write($, '/work/a.ts', 'a2'))).toMatch('claimed 42s ago')
})

test('after the holder\'s turn.complete the other agent can claim the file', async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await write($, '/work/a.ts', 'a1')
  expect(denied(await write($, '/work/a.ts', 'a2'))).toMatch('one')
  await done($, w, 'a1')
  expect(denied(await write($, '/work/a.ts', 'a2'))).toBe(undefined)
  expect(w.reached.length).toBe(2)
  // the file is a2's now: a third running agent meets a2's lane
  await spawn($, 'three')
  expect(denied(await write($, '/work/a.ts', 'a3'))).toMatch('two\'s lane')
})

test('an agent the engine lists as killed, failed or completed holds nothing, with no turn.complete seen', async ($, on) => {
  const w = world(on)
  for (const status of ['killed', 'failed', 'completed']) {
    await spawn($, `holder-${status}`)
    await spawn($, `taker-${status}`)
  }
  // ids are a1..a6: holders are odd, takers even
  await write($, '/work/killed.ts', 'a1')
  await write($, '/work/failed.ts', 'a3')
  await write($, '/work/completed.ts', 'a5')
  expect(denied(await write($, '/work/killed.ts', 'a2'))).toMatch('holder-killed')
  w.live = [
    { id: 'a1', description: 'holder-killed', type: 'general-purpose', status: 'killed' },
    { id: 'a3', description: 'holder-failed', type: 'general-purpose', status: 'failed' },
    { id: 'a5', description: 'holder-completed', type: 'general-purpose', status: 'completed' },
  ]
  expect(denied(await write($, '/work/killed.ts', 'a2'))).toBe(undefined)
  expect(denied(await write($, '/work/failed.ts', 'a4'))).toBe(undefined)
  expect(denied(await write($, '/work/completed.ts', 'a6'))).toBe(undefined)
})

test('an agent the engine lists as running is still the holder', async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  await spawn($, 'two')
  w.live = [{ id: 'a1', description: 'one', type: 'general-purpose', status: 'running' }]
  await write($, '/work/a.ts', 'a1')
  expect(denied(await write($, '/work/a.ts', 'a2'))).toMatch('one\'s lane')
})

test('two near-simultaneous writes to one file: one wins, one is refused', async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  await spawn($, 'two')
  const [x, y] = await Promise.all([write($, '/work/race.ts', 'a1'), write($, '/work/race.ts', 'a2')])
  const verdicts = [denied(x), denied(y)]
  expect(verdicts.filter(v => v === undefined).length).toBe(1)
  expect(verdicts.filter(v => v !== undefined).length).toBe(1)
  expect(w.reached.length).toBe(1)
})

test('paths are compared after light normalization and a relative path is read against the session directory', async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await write($, '/work/src/./a.ts', 'a1')
  expect(denied(await write($, '/work//src/a.ts', 'a2'))).toMatch('/work/src/a.ts is in one')
  expect(denied(await write($, '/work/src/lib/../a.ts', 'a2'))).toMatch('one\'s lane')
  expect(denied(await write($, 'src/a.ts', 'a2'))).toMatch('one\'s lane')
  expect(denied(await write($, 'src/other.ts', 'a2'))).toBe(undefined)
  expect(w.reached.length).toBe(2)
})

test('NotebookEdit is keyed by notebook_path; Edit and MultiEdit are lanes too; reads are not', async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await $.tool.call({ tool: 'NotebookEdit', notebook_path: '/work/n.ipynb', new_source: 'x', agentId: 'a1' } as any)
  const nb = await $.tool.call({ tool: 'NotebookEdit', notebook_path: '/work/n.ipynb', new_source: 'y', agentId: 'a2' } as any)
  expect(denied(nb)).toMatch('/work/n.ipynb is in one\'s lane')
  await $.tool.call({ tool: 'Edit', file_path: '/work/e.ts', old_string: 'a', new_string: 'b', agentId: 'a1' } as any)
  expect(denied(await $.tool.call({ tool: 'Edit', file_path: '/work/e.ts', old_string: 'b', new_string: 'c', agentId: 'a2' } as any))).toMatch('one\'s lane')
  await $.tool.call({ tool: 'MultiEdit', file_path: '/work/m.ts', edits: [], agentId: 'a1' } as any)
  expect(denied(await $.tool.call({ tool: 'MultiEdit', file_path: '/work/m.ts', edits: [], agentId: 'a2' } as any))).toMatch('one\'s lane')
  // a read of a held file is nobody's business
  const before = w.reached.length
  expect(denied(await $.tool.call({ tool: 'Read', file_path: '/work/e.ts', agentId: 'a2' } as any))).toBe(undefined)
  expect(denied(await $.tool.call({ tool: 'Bash', command: 'ls', agentId: 'a2' } as any))).toBe(undefined)
  expect(w.reached.length).toBe(before + 2)
})

test('an agent the mod never saw spawn is adopted from the engine\'s list the first time it writes', async ($, on) => {
  const w = world(on)
  w.live = [{ id: 'x9', description: 'ghost writer', type: 'general-purpose', status: 'running' }]
  await spawn($, 'real')
  await write($, '/work/a.ts', 'x9')
  expect(denied(await write($, '/work/a.ts', 'a1'))).toMatch('ghost writer\'s lane')
  // one the list does not know either still holds its file, under a generic label
  await write($, '/work/b.ts', 'zz-unlisted-77')
  expect(denied(await write($, '/work/b.ts', 'a1'))).toMatch('agent zz-unlis')
})

test('an agent that wrote after it settled (a continued one) is running again and holds its lane', async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await write($, '/work/a.ts', 'a1')
  await done($, w, 'a1')
  expect(denied(await write($, '/work/a.ts', 'a1'))).toBe(undefined)
  expect(denied(await write($, '/work/a.ts', 'a2'))).toMatch('one\'s lane')
  expect(w.reached.length).toBe(2)
})

test('a turn.complete from the main loop settles nobody', async ($, on) => {
  world(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await write($, '/work/a.ts', 'a1')
  await finish($, undefined)
  expect(denied(await write($, '/work/a.ts', 'a2'))).toMatch('one\'s lane')
})

// ----------------------------------------------------------------------------------------------- reconcile by absence

test('a holder that was killed and dropped from the engine\'s list for 60 s no longer holds its file', async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await write($, '/work/a.ts', 'a1')
  // killed with no turn.complete, and the list no longer names it (nor anyone: a2 is not listed either)
  w.live = []
  await w.clock.advance(59_000)
  expect(denied(await write($, '/work/a.ts', 'a2'))).toMatch('one\'s lane')
  await w.clock.advance(2_000)
  expect(denied(await write($, '/work/a.ts', 'a2'))).toBe(undefined)
  const board = w.sets.filter(s => s.key === 'board').pop().value
  const one = board.agents.find((a: any) => a.id === 'a1')
  expect(one.status).toBe('settled')
  expect(one.how).toBe('no longer in the engine\'s task list')
  // a1's lane was released, a2 holds the file now
  expect(board.lanes.find((l: any) => l.agentId === 'a1').releasedAt !== undefined).toBe(true)
  expect(board.lanes.find((l: any) => l.agentId === 'a2' && l.releasedAt === undefined).path).toBe('/work/a.ts')
})

test('an agent the engine still lists as running is not let go by age', async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await write($, '/work/a.ts', 'a1')
  w.live = [{ id: 'a1', description: 'one', type: 'general-purpose', status: 'running' }]
  await w.clock.advance(10 * 60_000)
  expect(denied(await write($, '/work/a.ts', 'a2'))).toMatch('one\'s lane')
})

test('a workflow holder absent from the list is not released by absence', async ($, on) => {
  const w = world(on)
  await spawn($, 'wf worker', { workflow: { runId: 'wf_1', agentIndex: 1 } })
  await spawn($, 'two')
  await write($, '/work/a.ts', 'a1')
  w.live = []
  await w.clock.advance(30 * 60_000)
  expect(denied(await write($, '/work/a.ts', 'a2'))).toMatch('wf worker\'s lane')
  expect(await lanes($)).toMatch('wf worker · running · a.ts')
  // it is released the ordinary way: its turn.complete
  await done($, w, 'a1')
  expect(denied(await write($, '/work/a.ts', 'a2'))).toBe(undefined)
})

test('an agent first seen at a write is let go by absence only once the list has named it', async ($, on) => {
  const w = world(on)
  await spawn($, 'real')
  // never listed: its label is generic, and absence says nothing about it
  await write($, '/work/b.ts', 'zz-unlisted-77')
  w.live = []
  await w.clock.advance(10 * 60_000)
  expect(denied(await write($, '/work/b.ts', 'a1'))).toMatch('agent zz-unlis')
  // named by the list at its first write: from then on, absence counts
  w.live = [{ id: 'x9', description: 'ghost writer', type: 'general-purpose', status: 'running' }]
  await write($, '/work/c.ts', 'x9')
  expect(denied(await write($, '/work/c.ts', 'a1'))).toMatch('ghost writer\'s lane')
  w.live = []
  await w.clock.advance(61_000)
  expect(denied(await write($, '/work/c.ts', 'a1'))).toBe(undefined)
  // and one the list names only later is marked then
  await write($, '/work/d.ts', 'zz-late-1')
  w.live = [{ id: 'zz-late-1', description: 'late one', type: 'general-purpose', status: 'running' }]
  await lanes($)
  w.live = []
  await w.clock.advance(61_000)
  expect(denied(await write($, '/work/d.ts', 'a1'))).toBe(undefined)
})

test('an unreadable agent list changes nothing', async ($, on) => {
  const w = world(on)
  w.listFails = true
  await spawn($, 'one')
  await spawn($, 'two')
  await write($, '/work/a.ts', 'a1')
  await w.clock.advance(10 * 60_000)
  expect(denied(await write($, '/work/a.ts', 'a2'))).toMatch('one\'s lane')
})

test('a turn.complete that lands before the spawn is recorded leaves the agent settled', async ($, on) => {
  const w = world(on)
  // the agent finishes while the engine is still answering the spawn
  w.duringSpawn = (_$, agentId) => finish($, agentId)
  await spawn($, 'quick')
  w.duringSpawn = undefined
  const board = w.sets.filter(s => s.key === 'board').pop().value
  const quick = board.agents.find((a: any) => a.id === 'a1')
  expect(quick.status).toBe('settled')
  expect(quick.how).toBe('answer')
  expect(quick.label).toBe('quick')
  expect(board.ended.length).toBe(0)
  // it holds nothing, and it is not counted as in flight: the next writer is alone
  await spawn($, 'next')
  expect(w.toast.length).toBe(0)
  await write($, '/work/a.ts', 'a2')
  expect(await lanes($)).toMatch('quick · settled · no writes')
})

test('a spawn recorded after the agent already settled does not bring it back', async ($, on) => {
  const w = world(on)
  await write($, '/work/a.ts', 'a1')
  await done($, w, 'a1')
  // the spawn of a1 is only now recorded (its first write was seen before, and adopted)
  await spawn($, 'late record')
  const board = w.sets.filter(s => s.key === 'board').pop().value
  const a1 = board.agents.find((a: any) => a.id === 'a1')
  expect(a1.status).toBe('settled')
  expect(a1.label).toBe('late record')
  expect(a1.adopted).toBe(undefined)
})

// ----------------------------------------------------------------------------------------------- parked agents

const info = (id: string, description: string, status: string): Info => ({ id, description, type: 'general-purpose', status })

test('a turn that ends while the engine lists the agent as waiting parks it: it keeps its lanes until the list says it is done', async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await write($, '/work/a.ts', 'a1')
  // its Bash moved to a background shell: the turn ends, the agent lives on
  w.live = [info('a1', 'one', 'waiting'), info('a2', 'two', 'running')]
  await finish($, 'a1')
  // not released at the turn's end, nor by the recheck
  expect(denied(await write($, '/work/a.ts', 'a2'))).toMatch('one\'s lane')
  await w.clock.advance(2500)
  expect(denied(await write($, '/work/a.ts', 'a2'))).toMatch('one\'s lane')
  const text = await lanes($)
  expect(text).toMatch('one · parked · a.ts')
  expect(text.split('\n')[0]).toMatch('(1 running, 1 parked)')
  // waiting for as long as it likes: still its file
  await w.clock.advance(30 * 60_000)
  expect(denied(await write($, '/work/a.ts', 'a2'))).toMatch('one\'s lane')
  // the list now says it is over: the next conflict releases the lane
  w.live = [info('a1', 'one', 'completed'), info('a2', 'two', 'running')]
  expect(denied(await write($, '/work/a.ts', 'a2'))).toBe(undefined)
  expect(await lanes($)).toMatch('one · settled · a.ts')
})

test('a parked agent that wakes and writes is running again and still holds its lane', async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await write($, '/work/a.ts', 'a1')
  w.live = [info('a1', 'one', 'waiting'), info('a2', 'two', 'running')]
  await finish($, 'a1')
  await w.clock.advance(2500)
  expect(await lanes($)).toMatch('one · parked')
  expect(denied(await write($, '/work/a.ts', 'a1'))).toBe(undefined)
  expect(await lanes($)).toMatch('one · running · a.ts')
  expect(denied(await write($, '/work/a.ts', 'a2'))).toMatch('one\'s lane')
  // it can take a new file as well
  expect(denied(await write($, '/work/b.ts', 'a1'))).toBe(undefined)
  expect(denied(await write($, '/work/b.ts', 'a2'))).toMatch('one\'s lane')
})

test('an agent that writes again before the recheck is not parked or released by it', async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await write($, '/work/a.ts', 'a1')
  await finish($, 'a1')
  await w.clock.advance(1000)
  await write($, '/work/b.ts', 'a1')
  // the recheck finds the list without it (which would release a finished agent): it must leave this one alone
  await w.clock.advance(1500)
  expect(await lanes($)).toMatch('one · running · a.ts, b.ts')
  expect(denied(await write($, '/work/a.ts', 'a2'))).toMatch('one\'s lane')
})

test('waiting, running and pending park an agent; completed, failed, killed, idle and absent release it', async ($, on) => {
  const w = world(on)
  const cases: Array<[string, boolean]> = [
    ['waiting', true], ['running', true], ['pending', true],
    ['completed', false], ['failed', false], ['killed', false], ['idle', false], ['absent', false],
  ]
  const live: Info[] = []
  for (const [i, [status]] of cases.entries()) {
    await spawn($, `holder-${status}`)
    await spawn($, `taker-${status}`)
    const holder = `a${2 * i + 1}`
    const taker = `a${2 * i + 2}`
    await write($, `/work/${status}.ts`, holder)
    live.push(info(taker, `taker-${status}`, 'running'))
    if (status !== 'absent') live.push(info(holder, `holder-${status}`, status))
  }
  w.live = live
  for (const [i] of cases.entries()) await finish($, `a${2 * i + 1}`)
  await w.clock.advance(2500)
  for (const [i, [status, parked]] of cases.entries()) {
    const verdict = denied(await write($, `/work/${status}.ts`, `a${2 * i + 2}`))
    if (parked) expect(verdict).toMatch(`holder-${status}\'s lane`)
    else expect(verdict).toBe(undefined)
  }
})

test('an unreadable agent list at the recheck releases the agent, as an ordinary end does', async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await write($, '/work/a.ts', 'a1')
  w.listFails = true
  await finish($, 'a1')
  expect(denied(await write($, '/work/a.ts', 'a2'))).toMatch('one\'s lane')
  await w.clock.advance(2500)
  expect(denied(await write($, '/work/a.ts', 'a2'))).toBe(undefined)
})

test('a parked agent the list stops naming is let go after 60 s; a parked workflow agent never is', async ($, on) => {
  const w = world(on)
  await spawn($, 'plain')
  await spawn($, 'wf worker', { workflow: { runId: 'wf_1', agentIndex: 1 } })
  await spawn($, 'taker')
  await write($, '/work/p.ts', 'a1')
  await write($, '/work/w.ts', 'a2')
  w.live = [info('a1', 'plain', 'waiting'), info('a2', 'wf worker', 'waiting'), info('a3', 'taker', 'running')]
  await finish($, 'a1')
  await finish($, 'a2')
  await w.clock.advance(2500)
  expect(await lanes($)).toMatch('(1 running, 2 parked)')
  // the engine forgets both
  w.live = [info('a3', 'taker', 'running')]
  await w.clock.advance(59_000)
  expect(denied(await write($, '/work/p.ts', 'a3'))).toMatch('plain\'s lane')
  await w.clock.advance(2_000)
  expect(denied(await write($, '/work/p.ts', 'a3'))).toBe(undefined)
  await w.clock.advance(30 * 60_000)
  expect(denied(await write($, '/work/w.ts', 'a3'))).toMatch('wf worker\'s lane')
})

// ----------------------------------------------------------------------------------------------- modes

test('mode warn: the second write passes and is logged once per path and agent', { options: { mode: 'warn' } }, async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await spawn($, 'three')
  await write($, '/work/a.ts', 'a1')
  expect(denied(await write($, '/work/a.ts', 'a2'))).toBe(undefined)
  expect(denied(await write($, '/work/a.ts', 'a2'))).toBe(undefined)
  expect(w.reached.length).toBe(3)
  expect(w.log.length).toBe(1)
  expect(w.log[0]).toMatch('two wrote /work/a.ts while it is in one\'s lane')
  // another agent is another pair; another path is another pair
  expect(denied(await write($, '/work/a.ts', 'a3'))).toBe(undefined)
  await write($, '/work/b.ts', 'a1')
  expect(denied(await write($, '/work/b.ts', 'a2'))).toBe(undefined)
  expect(w.log.length).toBe(3)
  // the holder keeps the lane
  expect(await lanes($)).toMatch('allowed in warn mode')
})

test('mode off: nothing is refused or logged, and the claims are still on record for /lanes', { options: { mode: 'off' } }, async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await write($, '/work/a.ts', 'a1')
  expect(denied(await write($, '/work/a.ts', 'a2'))).toBe(undefined)
  expect(w.reached.length).toBe(2)
  expect(w.log.length).toBe(0)
  expect(await lanes($)).toMatch('one · running · a.ts')
})

test('the main loop writing a path a running agent holds is allowed and logged once per path', async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  await write($, '/work/a.ts', 'a1')
  expect(denied(await write($, '/work/a.ts'))).toBe(undefined)
  expect(denied(await write($, '/work/a.ts'))).toBe(undefined)
  expect(w.reached.length).toBe(3)
  expect(w.log).toEqual(['main loop wrote /work/a.ts while it is in one\'s lane'])
  // a path nobody holds, and a path whose holder is done, say nothing
  await write($, '/work/free.ts')
  await done($, w, 'a1')
  await write($, '/work/a.ts')
  expect(w.log.length).toBe(1)
  expect(await lanes($)).toMatch('2 by the main loop')
  expect(await lanes($)).toMatch('main loop wrote a.ts (held by one) · allowed')
})

test('the main loop is never refused even in lock mode, and never claims', async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  await write($, '/work/m.ts')
  // the main loop's write took no lane: the agent may have the file
  expect(denied(await write($, '/work/m.ts', 'a1'))).toBe(undefined)
  expect(w.reached.length).toBe(2)
})

test('session.start registers /lanes as an immediate command', async ($, on) => {
  const w = world(on)
  await $.session.start({ source: 'startup', cwd: '/work', surface: 'terminal', isInteractive: true } as any)
  expect(w.registered.length).toBe(1)
  expect(w.registered[0].name).toBe('lanes')
  expect(w.registered[0].immediate).toBe(true)
  expect(String(w.registered[0].description).length > 10).toBe(true)
})

test('a /clear ends the conversation the agents belonged to: the board starts over', async ($, on) => {
  world(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await write($, '/work/a.ts', 'a1')
  expect(await lanes($)).toMatch('one · running · a.ts')
  await $.session.end({ reason: 'clear', sessionId: 's1' } as any)
  expect(await lanes($)).toBe('No subagent has written anything yet.')
  // and a new agent takes the file at once
  await spawn($, 'three')
  expect(denied(await write($, '/work/a.ts', 'a3'))).toBe(undefined)
})

// ----------------------------------------------------------------------------------------------- the contract

test('a spawn gets a note naming CONTRACT.md when it exists, and the original prompt stays first', async ($, on) => {
  const w = world(on)
  w.files.add('/work/CONTRACT.md')
  await spawn($, 'lone builder')
  const prompt: string = w.spawned[0].prompt
  expect(prompt.startsWith('do lone builder\n\n')).toBe(true)
  expect(prompt).toMatch('dojo-lanes: shared decisions for this fan-out are frozen in /work/CONTRACT.md')
  expect(prompt).toMatch('read it before you write')
  expect(prompt).toMatch('Files you write first become your lane')
  expect(prompt).toMatch('a file another running agent holds will be refused')
  expect(prompt).toMatch('report')
  expect(w.toast.length).toBe(0)
})

test('contract paths are tried in order, relative ones under the session directory', async ($, on) => {
  const w = world(on, { cwd: '/repo' })
  w.files.add('/repo/.dojo/dag-contract.md')
  w.files.add('/repo/.parallel-tracks/manifest.json')
  await spawn($, 'one')
  expect(w.spawned[0].prompt).toMatch('/repo/.dojo/dag-contract.md')
  expect(w.spawned[0].prompt).not.toMatch('manifest.json')
})

test('contract_paths is configurable', { options: { contract_paths: 'docs/PLAN.md, /abs/decisions.md' } }, async ($, on) => {
  const w = world(on)
  w.files.add('/work/CONTRACT.md')
  w.files.add('/abs/decisions.md')
  await spawn($, 'one')
  expect(w.spawned[0].prompt).toMatch('/abs/decisions.md')
  expect(w.spawned[0].prompt).not.toMatch('CONTRACT.md')
})

test('attach_contract false leaves the prompt alone', { options: { attach_contract: false } }, async ($, on) => {
  const w = world(on)
  w.files.add('/work/CONTRACT.md')
  await spawn($, 'one')
  await spawn($, 'two')
  expect(w.spawned.map(s => s.prompt)).toEqual(['do one', 'do two'])
})

test('a workflow agent\'s prompt and a fork\'s are left alone; both still hold lanes', async ($, on) => {
  const w = world(on)
  w.files.add('/work/CONTRACT.md')
  await spawn($, 'wf worker', { workflow: { runId: 'wf_1', agentIndex: 1 } })
  await spawn($, 'forked', { fork: true, subagentType: 'fork' })
  expect(w.spawned[0].prompt).toBe('do wf worker')
  expect(w.spawned[1].prompt).toBe('do forked')
  await write($, '/work/a.ts', 'a1')
  expect(denied(await write($, '/work/a.ts', 'a2'))).toMatch('wf worker\'s lane')
})

test('with no contract file, a lone writer is left alone and the next concurrent one gets the note', async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  expect(w.spawned[0].prompt).toBe('do one')
  await spawn($, 'two')
  expect(w.spawned[1].prompt).toMatch('dojo-lanes: other agents are writing in parallel with you')
  expect(w.spawned[1].prompt).not.toMatch('frozen in')
})

test('a read-only agent alongside a writer needs no note and does not count as a writer', async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  await spawn($, 'looker', { subagentType: 'Explore' })
  await spawn($, 'reviewer', { subagentType: 'dojo-protocol:reviewer' })
  await spawn($, 'researcher', { subagentType: 'some-plugin:researcher' })
  expect(w.spawned.slice(1).map(s => s.prompt)).toEqual(['do looker', 'do reviewer', 'do researcher'])
  // one writer is still the only writer: the next writer is the second
  await spawn($, 'two')
  expect(w.spawned[4].prompt).toMatch('other agents are writing in parallel')
  expect(w.toast.length).toBe(1)
  expect(w.toast[0]).toMatch('2 writing agents in flight')
})

// ----------------------------------------------------------------------------------------------- the nudge

test('the rule-4 nudge fires once per wave, and a new wave starts when nothing runs', async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  expect(w.toast.length).toBe(0)
  await spawn($, 'two')
  expect(w.toast).toEqual([
    '2 writing agents in flight and no contract file (Dojo rule 4). Lanes hold first-writer ownership; /lanes shows who holds what.',
  ])
  await spawn($, 'three')
  expect(w.toast.length).toBe(1)
  // the wave ends when the last agent returns
  await done($, w, 'a1')
  await done($, w, 'a2')
  await done($, w, 'a3')
  await spawn($, 'four')
  expect(w.toast.length).toBe(1)
  await spawn($, 'five')
  expect(w.toast.length).toBe(2)
  expect(w.toast[1]).toMatch('2 writing agents in flight')
})

test('no nudge when a contract file exists', async ($, on) => {
  const w = world(on)
  w.files.add('/work/CONTRACT.md')
  await spawn($, 'one')
  await spawn($, 'two')
  await spawn($, 'three')
  expect(w.toast.length).toBe(0)
})

test('a refused spawn is not tracked and does not nudge', async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  w.denySpawn = true
  const r: any = await spawn($, 'two')
  expect(r.deny).toBe('no more agents')
  expect(w.toast.length).toBe(0)
  expect(await lanes($)).toMatch('No subagent has written anything yet. (1 running)')
})

// ----------------------------------------------------------------------------------------------- /lanes

test('/lanes says so when nothing has been written', async ($, on) => {
  world(on)
  expect(await lanes($)).toBe('No subagent has written anything yet.')
  await spawn($, 'one')
  await spawn($, 'two')
  expect(await lanes($)).toMatch('No subagent has written anything yet.')
})

test('/lanes lists each agent with its files, then what was contested', async ($, on) => {
  const w = world(on)
  await spawn($, 'scout-one')
  await spawn($, 'builder-two')
  await spawn($, 'quiet-three')
  await write($, '/work/src/a.ts', 'a1')
  await write($, '/work/src/b.ts', 'a1')
  await write($, '/work/docs/c.md', 'a2')
  await w.clock.advance(5_000)
  await write($, '/work/src/a.ts', 'a2')
  await w.clock.advance(7_000)
  const text = await lanes($)
  const lines = text.split('\n')
  expect(lines[0]).toBe('3 agents (3 running) · 3 files held · mode lock')
  expect(lines).toContain('  scout-one · running · src/a.ts, src/b.ts')
  expect(lines).toContain('  builder-two · running · docs/c.md')
  expect(lines).toContain('  quiet-three · running · no writes')
  expect(text).toMatch('contested: 1 (1 refused, 0 allowed in warn mode, 0 by the main loop) — last 1:')
  expect(text).toMatch('7s ago · builder-two wanted src/a.ts (held by scout-one) · refused')
  // the holder returns: it is settled and its files are listed as its own history
  await done($, w, 'a1')
  const after = await lanes($)
  expect(after).toMatch('  scout-one · settled · src/a.ts, src/b.ts')
  expect(after).toMatch('(2 running)')
  expect(after).toMatch('· 1 file held')
})

test('/lanes shows the last five contested attempts only', async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await write($, '/work/a.ts', 'a1')
  for (let i = 0; i < 7; i++) {
    await w.clock.advance(1_000)
    await write($, '/work/a.ts', 'a2')
  }
  const text = await lanes($)
  expect(text).toMatch('contested: 7 (7 refused')
  expect(text).toMatch('last 5:')
  expect(text.split('\n').filter(l => l.includes('wanted a.ts')).length).toBe(5)
})

test('the board is plain JSON in the session state, under the declared key', async ($, on) => {
  const w = world(on)
  await spawn($, 'one')
  await write($, '/work/a.ts', 'a1')
  const mine = w.sets.filter(s => s.plugin === 'dojo-lanes' && s.key === 'board')
  expect(mine.length > 0).toBe(true)
  const b = mine[mine.length - 1].value
  expect(b.lanes.length).toBe(1)
  expect(b.lanes[0].path).toBe('/work/a.ts')
  expect(b.lanes[0].agentId).toBe('a1')
  expect(b.agents[0].label).toBe('one')
  expect(JSON.parse(JSON.stringify(b))).toEqual(b)
})

// ----------------------------------------------------------------------------------------------- stand-down and failure

test('DOJO_LANES_OFF=1 passes everything: no refusal, no note, no nudge, no log', async ($, on) => {
  const w = world(on, { env: { DOJO_LANES_OFF: '1' } })
  w.files.add('/work/CONTRACT.md')
  await spawn($, 'one')
  await spawn($, 'two')
  expect(w.spawned.map(s => s.prompt)).toEqual(['do one', 'do two'])
  await write($, '/work/a.ts', 'a1')
  expect(denied(await write($, '/work/a.ts', 'a2'))).toBe(undefined)
  expect(denied(await write($, '/work/a.ts'))).toBe(undefined)
  expect(w.reached.length).toBe(3)
  expect(w.log.length).toBe(0)
  expect(w.toast.length).toBe(0)
  expect(await lanes($)).toMatch('Stood down')
})

test('DOJO_OFF=true stands down too; a 0 does not', async ($, on) => {
  const w = world(on, { env: { DOJO_OFF: 'true', DOJO_LANES_OFF: '0' } })
  await spawn($, 'one')
  await spawn($, 'two')
  await write($, '/work/a.ts', 'a1')
  expect(denied(await write($, '/work/a.ts', 'a2'))).toBe(undefined)
  expect(w.reached.length).toBe(2)
})

test('DOJO_LANES_OFF=0 and DOJO_OFF=no leave the mod on', async ($, on) => {
  world(on, { env: { DOJO_LANES_OFF: '0', DOJO_OFF: 'no' } })
  await spawn($, 'one')
  await spawn($, 'two')
  await write($, '/work/a.ts', 'a1')
  expect(denied(await write($, '/work/a.ts', 'a2'))).toMatch('one\'s lane')
})

test('the guard fails open: with the clock gone the write still goes through', async ($, on) => {
  const w = world(on, { clock: false })
  on('clock.now', () => { throw new Error('clock unavailable') })
  await spawn($, 'one')
  await spawn($, 'two')
  await write($, '/work/a.ts', 'a1')
  const r = await write($, '/work/a.ts', 'a2')
  expect(denied(r)).toBe(undefined)
  expect(w.reached.length).toBe(2)
})

test('a failure in the plugin after a spawn never starts a second agent', async ($, on) => {
  const w = world(on, { clock: false })
  // recording the agent needs the clock; the spawn has already happened by then
  on('clock.now', () => { throw new Error('clock unavailable') })
  const r: any = await spawn($, 'one')
  expect(w.spawned.length).toBe(1)
  expect(r.agentId).toBe('a1')
  expect(w.toast.length).toBe(0)
})

test('the classic fallback name /dojo-lanes:lanes is answered by the mod too', async ($, on) => {
  world(on)
  const text: string = ((await $.command.run({ command: 'dojo-lanes:lanes', args: '' } as any)) as any).text
  expect(text).toBe('No subagent has written anything yet.')
})
