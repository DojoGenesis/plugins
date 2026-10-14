import { expect, mock, test } from 'claude-code/testing'

// Mod kit tests. The kit stands the engine beneath the plugin: hooks the test registers with `on` sit below it.
// The engine stand-ins here: agent.spawn hands out ids a1, a2, ...; tool.call answers ok; turn.complete echoes.
// The kit holds session.append itself (mock.session reads the rows back), and the clock (mock.clock).

type Ui = { toast: string[]; log: string[] }

function watchUi(on: any): Ui {
  const ui: Ui = { toast: [], log: [] }
  on('ui.toast', (_$: any, e: any) => { ui.toast.push(String(e.text)); return { value: undefined } as any })
  on('ui.log', (_$: any, e: any) => { ui.log.push(String(e.text)); return { value: undefined } as any })
  return ui
}

type Spawned = { subagentType: string; model?: string; description: string; prompt: string }

// The agents the engine starts: a1, a2, ... Types in `deny` are refused, as a type that is not installed is. A test
// raising $.agent.spawn reaches this stand-in with the input spelled as the engine spells it; a plugin's own
// $.agent.spawn reaches it with the Agent tool's spelling (`subagent_type`) and wants the tool's result back, so the
// stand-in answers both. Every other tool answers ok (or an error for the command 'fail').
function spawner(on: any, deny: string[] = []): Spawned[] {
  let n = 0
  const seen: Spawned[] = []
  on('agent.spawn', (_$: any, e: any) => {
    const type = e.subagentType ?? e.subagent_type
    seen.push({ subagentType: type, model: e.model, description: e.description, prompt: e.prompt })
    if (deny.includes(type)) return { deny: `agent type ${type} is not installed` }
    const agentId = `a${++n}`
    if (e.tool === 'Agent') return { model: e.model, agentId, result: { agentId, content: [] }, text: 'started' } as any
    return { model: e.model ?? 'inherit', agentId }
  })
  on('tool.call', (_$: any, e: any) => {
    if (e.command === 'fail') return { result: undefined as any, text: 'Exit code 1', isError: true as const }
    return { result: { stdout: 'ok', stderr: '' } as any, text: 'ok' }
  })
  return seen
}

function standIn(on: any) {
  on('turn.complete', (_$: any, e: any) => ({ text: e.answer, usage: e.usage }))
  on('session.start', (_$: any, e: any) => ({ cwd: e.cwd }))
  on('command.register', (_$: any, e: any) => ({ value: { command: e.name } }) as any)
}

// A turn.complete is recorded, not reported: the mod reads the engine's roster RECHECK ms later and settles the agent
// only if the roster says it is done. `complete` is a turn that ends and lets the recheck run (the roster is unreadable
// in a test that registers none, which settles it); `endTurn` is a turn that ends and leaves the clock where it is.
const RECHECK = 2500
let theClock: ReturnType<typeof mock.clock> | undefined
function tick(on: any, options: { now?: number } = {}) {
  theClock = mock.clock(on, options)
  return theClock
}

let turn = 0
const endTurn = ($: any, answer: string, extra: Record<string, unknown> = {}) =>
  $.turn.complete({ answer, durationMs: 1500, isAborted: false, turnId: `t${++turn}`, reason: 'answer', ...extra })
const complete = async ($: any, answer: string, extra: Record<string, unknown> = {}) => {
  const r = await endTurn($, answer, extra)
  if (theClock !== undefined) await theClock.advance(RECHECK)
  return r
}
const spawn = ($: any, description: string, extra: Record<string, unknown> = {}) =>
  $.agent.spawn({ prompt: `do ${description}`, description, subagentType: 'general-purpose', ...extra })
const call = ($: any, agentId: string | undefined, tool: string, extra: Record<string, unknown> = {}) =>
  $.tool.call({ tool, agentId, ...extra } as any)
const read = ($: any, agentId: string) => call($, agentId, 'Read', { file_path: '/work/a.ts' })
const bash = ($: any, agentId: string, command = 'pytest -q') => call($, agentId, 'Bash', { command })
const start = ($: any) => $.session.start({ source: 'startup', cwd: '/work', surface: 'terminal', isInteractive: true })
const run = ($: any, command: string, args = '') => $.command.run({ command, args })

// /tally pads its columns with runs of spaces; most assertions care about the cells, not the padding
const flat = (text: string): string => text.replace(/ {2,}/g, ' ')

const texts = (sess: { appended: () => readonly any[] }): string[] =>
  sess.appended().map(r => r.message.content.map((b: any) => b.text ?? '').join(''))

// ----------------------------------------------------------------------------------------------- a wave settles

test('three agents: returned, silent and failed; the last settle appends one meta row and toasts once', async ($, on) => {
  mock.env(on, {})
  tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  await spawn($, 'audit routes')
  await spawn($, 'audit schema', { subagentType: 'dojo-protocol:reviewer' })
  await spawn($, 'audit config')
  await read($, 'a1')
  await read($, 'a1')
  await complete($, 'Found 2 defects: routes.ts:12 and routes.ts:40.', { agentId: 'a1' })
  await complete($, 'No defects found.', { agentId: 'a2' })
  expect(ui.toast.length).toBe(0)
  expect(texts(sess).length).toBe(0)
  await complete($, '', { agentId: 'a3', isAborted: true, reason: 'aborted' })

  expect(ui.toast.length).toBe(1)
  expect(ui.toast[0]).toBe('wave settled — dispatched 3 · returned 1 · failed 1 · silent 1 · unchecked 0')
  const rows = texts(sess)
  expect(rows.length).toBe(1)
  const row = rows[0] as string
  expect(row).toMatch('[dojo-tally] Fan-out settled: dispatched 3 · returned 1 · failed 1 · silent 1 · unchecked 0')
  expect(row).toMatch('#2 audit schema (dojo-protocol:reviewer): silent — clean verdict after reading nothing (rule 9)')
  expect(row).toMatch('#3 audit config (general-purpose): failed — it was interrupted before it answered')
  expect(row).not.toMatch('#1 audit routes')
  expect(row).toMatch('Treat each report as a claim until a check backs it (Dojo rules 5, 6, 9). The person can send one to a judge with /refute <n>.')
  // a meta row for the model: a user-role row on the main conversation, no agent
  const stored = sess.appended()[0] as any
  expect(stored.message.type).toBe('user')
  expect(stored.agentId).toBe(undefined)
})

test('a clean verdict after reading something is returned, not silent', async ($, on) => {
  mock.env(on, {})
  tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  await spawn($, 'review a')
  await spawn($, 'review b')
  await call($, 'a1', 'Grep', { pattern: 'x' })
  await complete($, 'No defects found.', { agentId: 'a1' })
  await complete($, 'No defects found.', { agentId: 'a2' })
  expect(ui.toast[0]).toMatch('returned 1 · failed 0 · silent 1 · unchecked 0')
  expect(texts(sess)[0]).toMatch('#2 review b')
  expect(texts(sess)[0]).not.toMatch('#1 review a')
})

test('a failed agent says why: error, refusal, empty answer', async ($, on) => {
  mock.env(on, {})
  tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await spawn($, 'three')
  await complete($, '', { agentId: 'a1', reason: 'error' })
  await complete($, '', { agentId: 'a2', reason: 'refusal', refusal: { reason: 'policy' } })
  await complete($, '   \n', { agentId: 'a3' })
  const row = texts(sess)[0] as string
  expect(row).toMatch('failed 3')
  expect(row).toMatch('#1 one (general-purpose): failed — its turn ended in an error')
  expect(row).toMatch('#2 two (general-purpose): failed — the model refused')
  expect(row).toMatch('#3 three (general-purpose): failed — it returned an empty answer')
})

test('"Tests pass." with no Bash is unchecked; with a Bash call it is returned', async ($, on) => {
  mock.env(on, {})
  tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  await spawn($, 'builder one')
  await spawn($, 'builder two')
  await call($, 'a1', 'Edit', { file_path: '/work/a.ts', old_string: 'a', new_string: 'b' })
  await call($, 'a2', 'Edit', { file_path: '/work/b.ts', old_string: 'a', new_string: 'b' })
  await bash($, 'a2')
  await complete($, 'Done. Tests pass.', { agentId: 'a1' })
  await complete($, 'Done. Tests pass.', { agentId: 'a2' })
  expect(ui.toast[0]).toMatch('returned 1 · failed 0 · silent 0 · unchecked 1')
  const row = texts(sess)[0] as string
  expect(row).toMatch('#1 builder one (general-purpose): unchecked — claims a check it never ran (rule 5)')
  expect(row).not.toMatch('#2 builder two')
})

test('other check claims count as unchecked; a negated claim does not', async ($, on) => {
  mock.env(on, {})
  tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  await spawn($, 'a')
  await spawn($, 'b')
  await spawn($, 'c')
  await spawn($, 'd')
  await complete($, 'The build passed and I verified the output.', { agentId: 'a1' })
  await complete($, 'Lint is clean (exit 0).', { agentId: 'a2' })
  await complete($, 'I could not verify this against a running server; it is unverified.', { agentId: 'a3' })
  await complete($, 'Changed two files, ran nothing.', { agentId: 'a4' })
  const row = texts(sess)[0] as string
  expect(row).toMatch('returned 2 · failed 0 · silent 0 · unchecked 2')
  expect(row).toMatch('#1 a (general-purpose): unchecked')
  expect(row).toMatch('#2 b (general-purpose): unchecked')
  expect(row).not.toMatch('#3 c')
})

test('denied and errored calls still count as attempted', async ($, on) => {
  mock.env(on, {})
  tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  await start($)
  await spawn($, 'checker')
  await spawn($, 'other')
  await bash($, 'a1', 'fail')
  await call($, 'a1', 'Read', { file_path: '/work/a.ts' })
  await call($, 'a1', 'Write', { file_path: '/work/o.txt', content: 'x' })
  await call($, undefined, 'Read', { file_path: '/work/main.ts' }) // the main loop is nobody's
  const out = (await run($, 'tally')).text as string
  // Bash is a read for the silent test but shows once, as bash: 1 Bash + 1 Read + 1 Write
  expect(flat(out)).toMatch('#1 checker general-purpose inherit running 1 read · 1 write · 1 bash')
  expect(flat(out)).toMatch('#2 other general-purpose inherit running 0 reads · 0 writes · 0 bash')
  // a bash that failed is a read of the world that was attempted: "No defects found." after it is not silent
  await complete($, 'No defects found.', { agentId: 'a1' })
  await complete($, 'ok', { agentId: 'a2' })
  expect(texts(sess)[0]).toMatch('returned 2')
})

// ----------------------------------------------------------------------------------------------- when nothing is said

test('a single-agent wave appends nothing and toasts nothing', async ($, on) => {
  mock.env(on, {})
  tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  await spawn($, 'lonely')
  await complete($, 'No defects found.', { agentId: 'a1' })
  expect(ui.toast.length).toBe(0)
  expect(sess.appended().length).toBe(0)
})

test('min_wave raises the bar', { options: { min_wave: 3 } }, async ($, on) => {
  mock.env(on, {})
  tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await complete($, 'ok', { agentId: 'a1' })
  await complete($, 'ok', { agentId: 'a2' })
  expect(ui.toast.length).toBe(0)
  expect(sess.appended().length).toBe(0)
  await spawn($, 'three')
  await spawn($, 'four')
  await spawn($, 'five')
  await complete($, 'ok', { agentId: 'a3' })
  await complete($, 'ok', { agentId: 'a4' })
  await complete($, 'ok', { agentId: 'a5' })
  expect(ui.toast.length).toBe(1)
  expect(sess.appended().length).toBe(1)
})

test('settle_note false toasts but appends nothing', { options: { settle_note: false } }, async ($, on) => {
  mock.env(on, {})
  tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await complete($, 'ok', { agentId: 'a1' })
  await complete($, '', { agentId: 'a2', reason: 'error' })
  expect(ui.toast.length).toBe(1)
  expect(ui.toast[0]).toMatch('returned 1 · failed 1')
  expect(sess.appended().length).toBe(0)
})

test('a refused append goes to the log instead and breaks nothing', async ($, on) => {
  mock.env(on, {})
  tick(on, { now: 1000 })
  standIn(on)
  spawner(on)
  on('session.append', (_$: any) => ({ deny: 'the session is read-only' }) as any)
  const ui = watchUi(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await complete($, 'ok', { agentId: 'a1' })
  await complete($, '', { agentId: 'a2', reason: 'error' })
  expect(ui.toast.length).toBe(1)
  expect(ui.log.length).toBe(1)
  expect(ui.log[0]).toMatch('dojo-tally')
  expect(ui.log[0]).toMatch('[dojo-tally] Fan-out settled: dispatched 2')
})

test('DOJO_TALLY_OFF stands down: nothing tracked, appended or toasted', async ($, on) => {
  mock.env(on, { DOJO_TALLY_OFF: '1' })
  tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  await start($)
  await spawn($, 'one')
  await spawn($, 'two')
  await complete($, '', { agentId: 'a1', reason: 'error' })
  await complete($, 'No defects found.', { agentId: 'a2' })
  expect(ui.toast.length).toBe(0)
  expect(sess.appended().length).toBe(0)
  expect(((await run($, 'tally')).text as string)).toMatch('off')
})

test('DOJO_OFF stands down too', async ($, on) => {
  mock.env(on, { DOJO_OFF: 'true' })
  tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await complete($, '', { agentId: 'a1', reason: 'error' })
  await complete($, '', { agentId: 'a2', reason: 'error' })
  expect(ui.toast.length).toBe(0)
  expect(sess.appended().length).toBe(0)
})

// ----------------------------------------------------------------------------------------------- waves

test('a settled wave closes; the next spawn opens a new one; only the last five are kept', async ($, on) => {
  mock.env(on, {})
  tick(on, { now: 1000 })
  mock.session(on)
  standIn(on)
  spawner(on)
  await start($)
  for (let i = 1; i <= 6; i++) {
    await spawn($, `solo ${i}`)
    await complete($, 'ok', { agentId: `a${i}` })
  }
  const out = (await run($, 'tally')).text as string
  expect(out).toMatch('5 agents in 5 waves')
  expect(out).not.toMatch('solo 1')
  expect(flat(out)).toMatch('#2 solo 2')
  expect(flat(out)).toMatch('#6 solo 6')
})

test('a spawn while the wave is open joins it: nested spawns, workflow agents; judges and teammates do not', async ($, on) => {
  mock.env(on, {})
  tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  await start($)
  await spawn($, 'parent')
  await spawn($, 'child', { parentAgentId: 'a1' } as any)
  await spawn($, 'flow step', { workflow: { runId: 'wf_1', agentIndex: 1 } } as any)
  await spawn($, 'mate', { isTeammate: true } as any)
  const mid = (await run($, 'tally')).text as string
  expect(mid).toMatch('3 agents in 1 wave')
  expect(mid).toMatch('Open wave 1 (live): dispatched 3 · settled 0 · running 3')
  expect(mid).not.toMatch('mate')
  await complete($, 'ok', { agentId: 'a1' })
  await complete($, 'ok', { agentId: 'a2' })
  expect(ui.toast.length).toBe(0)
  await complete($, 'ok', { agentId: 'a3' })
  expect(ui.toast[0]).toMatch('dispatched 3 · returned 3')
  expect(sess.appended().length).toBe(1)
})

test('an agent the mod never saw spawn (a1 settles, w-9 unknown) is not counted', async ($, on) => {
  mock.env(on, {})
  tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await complete($, 'ok', { agentId: 'w-9' })
  await call($, 'w-9', 'Read', { file_path: '/x' })
  await complete($, 'ok', { agentId: 'a1' })
  expect(ui.toast.length).toBe(0)
  expect(sess.appended().length).toBe(0)
})

test('an agent that answers twice is judged on its first turn', async ($, on) => {
  mock.env(on, {})
  tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await complete($, 'ok', { agentId: 'a1' })
  await complete($, '', { agentId: 'a1', reason: 'error' })
  await complete($, 'ok', { agentId: 'a2' })
  expect(texts(sess).length).toBe(1)
  expect(texts(sess)[0]).toMatch('returned 2 · failed 0')
})

// ----------------------------------------------------------------------------------------------- /tally

test('/tally lists the open wave live and the settled waves, with outcome, counts and duration', async ($, on) => {
  mock.env(on, {})
  const clock = tick(on, { now: 10_000 })
  mock.session(on)
  standIn(on)
  spawner(on)
  await start($)
  expect(((await run($, 'tally')).text as string)).toBe('No fan-out yet.')

  await spawn($, 'audit routes', { subagentType: 'dojo-protocol:reviewer', model: 'sonnet' })
  await spawn($, 'audit schema')
  await read($, 'a1')
  await bash($, 'a1')
  await complete($, 'Found a defect at routes.ts:12.', { agentId: 'a1', durationMs: 12_300 })
  await complete($, 'No defects found.', { agentId: 'a2', durationMs: 800 })
  await clock.advance(5000)
  await spawn($, 'fix it')
  await call($, 'a3', 'Edit', { file_path: '/work/a.ts', old_string: 'a', new_string: 'b' })
  await clock.advance(7000)

  const out = (await run($, 'tally')).text as string
  expect(out).toMatch('3 agents in 2 waves')
  // newest first: the open wave is live
  expect(out.indexOf('Open wave 2 (live)')).toBeLessThan(out.indexOf('Wave 1 (settled)'))
  expect(out).toMatch('Open wave 2 (live): dispatched 1 · settled 0 · running 1')
  // life is spawn to settle (or to now): the turn's own durationMs (12.3s, 0.8s) is not what is shown
  expect(flat(out)).toMatch('#3 fix it general-purpose inherit running 0 reads · 1 write · 0 bash 7s')
  expect(out).toMatch('Wave 1 (settled): dispatched 2 · returned 1 · failed 0 · silent 1 · unchecked 0')
  expect(flat(out)).toMatch('#1 audit routes dojo-protocol:reviewer sonnet returned 1 read · 0 writes · 1 bash 3s')
  expect(flat(out)).toMatch('#2 audit schema general-purpose inherit silent 0 reads · 0 writes · 0 bash 5s')
  expect(out).toMatch('clean verdict after reading nothing (rule 9)')
})

// ----------------------------------------------------------------------------------------------- /refute

async function settledPair($: any, on: any) {
  mock.env(on, {})
  tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  await start($)
  await spawn($, 'audit routes', { subagentType: 'dojo-protocol:reviewer' })
  await spawn($, 'audit schema')
  await read($, 'a1')
  await complete($, 'Defect: routes.ts:12 returns 200 on a failed auth check.', { agentId: 'a1' })
  await complete($, 'Schema is fine. Tests pass.', { agentId: 'a2' })
  return sess
}

test('/refute 2 spawns the judge with the report, and the verdict lands when it returns', async ($, on) => {
  const seen = spawner(on)
  const ui = watchUi(on)
  const sess = await settledPair($, on)
  expect(sess.appended().length).toBe(1) // the settle note
  const spawnsBefore = seen.length

  const r = await run($, 'refute', '2')
  expect(seen.length).toBe(spawnsBefore + 1)
  const judge = seen[seen.length - 1] as Spawned
  expect(judge.subagentType).toBe('dojo-protocol:judge')
  expect(judge.model).toBe('opus')
  expect(judge.description).toBe('refute #2')
  expect(judge.prompt).toMatch('Refute or confirm the claims in this subagent report.')
  expect(judge.prompt).toMatch('confirmed | refuted | unverified')
  expect(judge.prompt).toMatch('Report from audit schema (general-purpose):\nSchema is fine. Tests pass.')
  expect(r.text).toBe("sent #2 audit schema's report to dojo-protocol:judge (opus). The verdict lands in the conversation when it returns.")
  expect(sess.appended().length).toBe(1) // nothing yet

  // the judge is a3: it did not join a wave and its return settles nothing
  const toastsBefore = ui.toast.length
  await complete($, '#2 claim "Tests pass": unverified. I ran pytest -q: 3 failed (tests/test_schema.py:9).', { agentId: 'a3' })
  expect(sess.appended().length).toBe(2)
  const verdict = texts(sess)[1] as string
  expect(verdict).toMatch('[dojo-tally] Judge verdict on #2 audit schema:\n#2 claim "Tests pass": unverified.')
  expect(ui.toast.length).toBe(toastsBefore + 1)
  expect(ui.toast[ui.toast.length - 1]).toMatch('judge verdict on #2 audit schema')

  // a second return from the same judge id says nothing more
  await complete($, 'again', { agentId: 'a3' })
  expect(sess.appended().length).toBe(2)
  const tally = (await run($, 'tally')).text as string
  expect(tally).toMatch('2 agents in 1 wave')
})

test('/refute falls back to general-purpose when the judge type is refused', async ($, on) => {
  const seen = spawner(on, ['dojo-protocol:judge'])
  watchUi(on)
  const sess = await settledPair($, on)
  const before = seen.length
  const r = await run($, 'refute', '1')
  expect(seen.slice(before).map(s => s.subagentType)).toEqual(['dojo-protocol:judge', 'general-purpose'])
  expect((seen[seen.length - 1] as Spawned).prompt).toMatch('Report from audit routes (dojo-protocol:reviewer):\nDefect: routes.ts:12')
  expect(r.text).toMatch("sent #1 audit routes's report to general-purpose (opus)")
  await complete($, 'Confirmed: routes.ts:12 returns 200 (I read it).', { agentId: 'a3' })
  expect(texts(sess)[1]).toMatch('Judge verdict on #1 audit routes:\nConfirmed')
})

test('/refute says so when no judge can be started', async ($, on) => {
  const deny: string[] = []
  const seen = spawner(on, deny)
  watchUi(on)
  await settledPair($, on)
  deny.push('dojo-protocol:judge', 'general-purpose')
  const spawns = seen.length
  const r = (await run($, 'refute', '1')).text as string
  expect(seen.length).toBe(spawns + 2)
  expect(r).toMatch('could not start a judge for #1 audit routes')
  expect(r).toMatch('is not installed')
})

test('judge_model sonnet is honoured', { options: { judge_model: 'sonnet' } }, async ($, on) => {
  const seen = spawner(on)
  watchUi(on)
  await settledPair($, on)
  const r = await run($, 'refute', '#1')
  expect((seen[seen.length - 1] as Spawned).model).toBe('sonnet')
  expect(r.text).toMatch('dojo-protocol:judge (sonnet)')
})

test('/refute finds an agent by label or by agentId', async ($, on) => {
  const seen = spawner(on)
  watchUi(on)
  await settledPair($, on)
  await run($, 'refute', 'audit routes')
  expect((seen[seen.length - 1] as Spawned).description).toBe('refute #1')
  await run($, 'refute', 'a2')
  expect((seen[seen.length - 1] as Spawned).description).toBe('refute #2')
  await run($, 'refute', 'SCHEMA')
  expect((seen[seen.length - 1] as Spawned).description).toBe('refute #2')
})

test('/refute with no target, an unknown one or a running one lists what it can take', async ($, on) => {
  const seen = spawner(on)
  watchUi(on)
  await settledPair($, on)
  await spawn($, 'still going') // a4, wave 2, running
  const spawns = seen.length

  const none = (await run($, 'refute', '')).text as string
  expect(none).toMatch('usage /refute <agent #>')
  expect(none).toMatch('#1 audit routes (dojo-protocol:reviewer) — returned')
  expect(none).toMatch('#2 audit schema (general-purpose) — unchecked')

  const unknown = (await run($, 'refute', '9')).text as string
  expect(unknown).toMatch('no agent matches "9"')
  expect(unknown).toMatch('#1 audit routes')

  const running = (await run($, 'refute', '3')).text as string
  expect(running).toMatch('#3 still going is still running')
  expect(seen.length).toBe(spawns)
})

test('a judge that returns nothing is reported as no verdict, not as a pass', async ($, on) => {
  spawner(on)
  watchUi(on)
  const sess = await settledPair($, on)
  await run($, 'refute', '2')
  await complete($, '', { agentId: 'a3', reason: 'error' })
  const row = texts(sess)[1] as string
  expect(row).toMatch('The judge on #2 audit schema returned no verdict')
  expect(row).toMatch('unrefuted, not confirmed')
})

test('a report that came back empty has nothing to refute', async ($, on) => {
  const seen = spawner(on)
  watchUi(on)
  mock.env(on, {})
  tick(on, { now: 1000 })
  mock.session(on)
  standIn(on)
  await start($)
  await spawn($, 'one')
  await spawn($, 'two')
  await complete($, '', { agentId: 'a1', reason: 'error' })
  await complete($, 'ok', { agentId: 'a2' })
  const spawns = seen.length
  const r = (await run($, 'refute', '1')).text as string
  expect(r).toMatch('returned no report')
  expect(seen.length).toBe(spawns)
})

test('a long report is clipped to 8000 characters for the judge, a long verdict to 6000 in the conversation', async ($, on) => {
  const seen = spawner(on)
  watchUi(on)
  mock.env(on, {})
  tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  await start($)
  await spawn($, 'one')
  await spawn($, 'two')
  await complete($, 'ok', { agentId: 'a1' })
  await complete($, 'x'.repeat(9000), { agentId: 'a2' })
  await run($, 'refute', '2')
  const prompt = (seen[seen.length - 1] as Spawned).prompt
  expect(prompt).toMatch('x'.repeat(7999) + '…')
  expect(prompt).not.toMatch('x'.repeat(8000))
  await complete($, 'y'.repeat(7000), { agentId: 'a3' })
  const row = texts(sess)[1] as string
  expect(row).toMatch('y'.repeat(5999) + '…')
  expect(row).not.toMatch('y'.repeat(6000))
})

test('each wave gets its own note, and an agent that fell out of the last five waves cannot be refuted', async ($, on) => {
  const seen = spawner(on)
  watchUi(on)
  mock.env(on, {})
  tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  await start($)
  let id = 0
  for (let wave = 1; wave <= 6; wave++) {
    await spawn($, `w${wave} first`)
    await spawn($, `w${wave} second`)
    await complete($, `report ${wave}a`, { agentId: `a${++id}` })
    await complete($, `report ${wave}b`, { agentId: `a${++id}` })
  }
  expect(sess.appended().length).toBe(6)
  const spawns = seen.length
  const gone = (await run($, 'refute', '1')).text as string
  expect(gone).toMatch('#1 is no longer kept (only the last 5 waves are)')
  expect(seen.length).toBe(spawns)
  // the newest wave is still there, with its reports
  await run($, 'refute', '12')
  expect((seen[seen.length - 1] as Spawned).prompt).toMatch('Report from w6 second (general-purpose):\nreport 6b')
})

test('command answers carry no "dojo-tally: " prefix: the engine adds the plugin name itself', async ($, on) => {
  const deny: string[] = []
  spawner(on, deny)
  watchUi(on)
  mock.env(on, {})
  tick(on, { now: 1000 })
  mock.session(on)
  standIn(on)
  await start($)
  const answers: string[] = []
  const ask = async (command: string, args = '') => answers.push((await run($, command, args)).text as string)
  await ask('tally') // empty
  await ask('refute') // usage
  await spawn($, 'one')
  await spawn($, 'two')
  await ask('tally') // open wave
  await ask('refute', '1') // still running
  await complete($, '', { agentId: 'a1', reason: 'error' })
  await complete($, 'ok', { agentId: 'a2' })
  await ask('tally') // settled
  await ask('refute', '1') // no report
  await ask('refute', 'nobody') // unknown
  await ask('refute', '2') // sent
  deny.push('dojo-protocol:judge', 'general-purpose')
  await ask('refute', '2') // no judge can start
  expect(answers.length).toBe(9)
  for (const text of answers) {
    expect(text.length > 0).toBe(true)
    expect(text.startsWith('dojo-tally')).toBe(false)
  }
  // the toast, the log line and the meta rows keep the prefix
})

// ----------------------------------------------------------------------------------------------- reconcile

type Listed = { id: string; status: string }

// agent.list: the engine's roster, as a test sets it. A test that registers none gets a rejected list, which the mod
// reads as "no roster, no change".
function roster(on: any, listed: Listed[]) {
  on('agent.list', () => ({ value: listed.map(l => ({ id: l.id, description: l.id, type: 'general-purpose', status: l.status })) }) as any)
}

const MIN = 60_000

test('a member that is killed never sends turn.complete: reconcile settles the wave, one toast and one meta row', async ($, on) => {
  mock.env(on, {})
  const clock = tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  const listed: Listed[] = [{ id: 'a3', status: 'running' }]
  roster(on, listed)
  await start($)
  await spawn($, 'one')
  await spawn($, 'two')
  await spawn($, 'three')
  await complete($, 'ok', { agentId: 'a1' })
  await complete($, 'ok', { agentId: 'a2' })
  await clock.advance(30_000)
  expect(ui.toast.length).toBe(0) // still running: nothing settles
  expect(sess.appended().length).toBe(0)

  listed[0] = { id: 'a3', status: 'killed' }
  await clock.advance(15_000)
  expect(ui.toast.length).toBe(1)
  expect(ui.toast[0]).toBe('wave settled — dispatched 3 · returned 2 · failed 1 · silent 0 · unchecked 0')
  expect(texts(sess).length).toBe(1)
  expect(texts(sess)[0]).toMatch('#3 three (general-purpose): failed — stopped (killed)')

  await clock.advance(MIN) // later ticks and a /tally say nothing more
  await run($, 'tally')
  expect(ui.toast.length).toBe(1)
  expect(texts(sess).length).toBe(1)
  expect(((await run($, 'tally')).text as string)).toMatch('Wave 1 (settled)')
})

test('/tally reconciles too, without waiting for the timer', async ($, on) => {
  mock.env(on, {})
  tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  roster(on, [{ id: 'a2', status: 'killed' }])
  await start($)
  await spawn($, 'one')
  await spawn($, 'two')
  await complete($, 'ok', { agentId: 'a1' })
  const out = (await run($, 'tally')).text as string
  expect(out).toMatch('Wave 1 (settled): dispatched 2 · returned 1 · failed 1')
  expect(out).toMatch('stopped (killed)')
  expect(ui.toast.length).toBe(1)
  expect(sess.appended().length).toBe(1)
})

test('reconcile reasons: completed, failed and killed in the roster; absent from it for 60 seconds, not before', async ($, on) => {
  mock.env(on, {})
  const clock = tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  roster(on, [
    { id: 'a2', status: 'completed' },
    { id: 'a3', status: 'failed' },
    { id: 'a4', status: 'killed' },
    // a5 is not listed at all
  ])
  await start($)
  for (const label of ['one', 'two', 'three', 'four', 'five']) await spawn($, label)
  await complete($, 'ok', { agentId: 'a1' })
  await clock.advance(30_000)
  expect(ui.toast.length).toBe(0) // a5 is not listed, but it was spawned only 30 seconds ago
  await clock.advance(30_000)
  expect(ui.toast.length).toBe(1)
  const row = texts(sess)[0] as string
  expect(row).toMatch('dispatched 5 · returned 1 · failed 4')
  expect(row).toMatch('#2 two (general-purpose): failed — ended without a final answer')
  expect(row).toMatch('#3 three (general-purpose): failed — its task failed')
  expect(row).toMatch('#4 four (general-purpose): failed — stopped (killed)')
  expect(row).toMatch("#5 five (general-purpose): failed — no longer in the engine's task list")
})

test('a workflow member is never settled by absence; a long quiet settles it as "no end seen"', async ($, on) => {
  mock.env(on, {})
  const clock = tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  roster(on, []) // the engine lists no workflow agents
  await start($)
  await spawn($, 'flow step', { workflow: { runId: 'wf_1', agentIndex: 1 } } as any)
  await spawn($, 'plain')
  await complete($, 'ok', { agentId: 'a2' })
  await clock.advance(10 * MIN)
  expect(ui.toast.length).toBe(0)
  expect(flat((await run($, 'tally')).text as string)).toMatch('#1 flow step general-purpose inherit running')

  await clock.advance(15 * MIN) // 25 minutes in; the agent is still at work
  await call($, 'a1', 'Read', { file_path: '/work/a.ts' })
  await clock.advance(6 * MIN) // 31 minutes in, but only 6 quiet minutes
  expect(ui.toast.length).toBe(0)
  await clock.advance(5 * MIN) // 36 minutes in, 11 quiet minutes
  expect(ui.toast.length).toBe(1)
  expect(texts(sess)[0]).toMatch('#1 flow step (general-purpose): failed — no end seen')
  expect(sess.appended().length).toBe(1)
})

test('an agent reconcile wrote off that then answers is corrected, and the model is told', async ($, on) => {
  mock.env(on, {})
  const clock = tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  roster(on, [{ id: 'a2', status: 'completed' }]) // the engine marked it done a moment before its turn.complete
  await start($)
  await spawn($, 'one')
  await spawn($, 'two')
  await read($, 'a2')
  await complete($, 'ok', { agentId: 'a1' })
  await clock.advance(15_000)
  expect(ui.toast.length).toBe(1)
  expect(texts(sess)[0]).toMatch('returned 1 · failed 1')

  await complete($, 'Found a defect at x.ts:3.', { agentId: 'a2' })
  expect(ui.toast.length).toBe(1) // one toast per wave
  expect(texts(sess).length).toBe(2)
  expect(texts(sess)[1]).toMatch('[dojo-tally] Correction: #2 two (general-purpose) did end after the fan-out was reported: returned.')
  expect(texts(sess)[1]).toMatch('dispatched 2 · returned 2 · failed 0')
  expect(flat((await run($, 'tally')).text as string)).toMatch('#2 two general-purpose inherit returned 1 read · 0 writes · 0 bash')
  await complete($, 'again', { agentId: 'a2' }) // and a third end changes nothing
  expect(texts(sess).length).toBe(2)
})

test('reconcile with no roster to read changes nothing', async ($, on) => {
  mock.env(on, {})
  const clock = tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  on('agent.list', () => { throw new Error('roster unavailable') })
  await start($)
  await spawn($, 'one')
  await spawn($, 'two')
  await complete($, 'ok', { agentId: 'a1' })
  await clock.advance(5 * MIN)
  expect(ui.toast.length).toBe(0)
  expect(sess.appended().length).toBe(0)
})

test('reconcile does nothing under the kill switch', async ($, on) => {
  mock.env(on, { DOJO_TALLY_OFF: 'yes' })
  const clock = tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  roster(on, [{ id: 'a1', status: 'killed' }, { id: 'a2', status: 'killed' }])
  await start($)
  await spawn($, 'one')
  await spawn($, 'two')
  await clock.advance(5 * MIN)
  expect(ui.toast.length).toBe(0)
  expect(sess.appended().length).toBe(0)
})

// ----------------------------------------------------------------------------------------------- reviewer findings

test('/refute <digits> that names a pruned agent says it is no longer kept, even when a label contains the digits', async ($, on) => {
  const seen = spawner(on)
  watchUi(on)
  mock.env(on, {})
  tick(on, { now: 1000 })
  mock.session(on)
  standIn(on)
  await start($)
  for (let i = 1; i <= 7; i++) {
    await spawn($, i === 7 ? 'report 2 of 7' : `solo ${i}`)
    await complete($, 'ok', { agentId: `a${i}` })
  }
  const spawns = seen.length
  const pruned = (await run($, 'refute', '2')).text as string
  expect(pruned).toMatch('#2 is no longer kept (only the last 5 waves are)')
  expect(((await run($, 'refute', '#1')).text as string)).toMatch('#1 is no longer kept')
  expect(seen.length).toBe(spawns) // nothing was sent to a judge
  // a number nobody has been given yet is a different answer; a label still finds its agent
  expect(((await run($, 'refute', '8')).text as string)).toMatch('no agent matches "8"')
  await run($, 'refute', 'report 2')
  expect((seen[seen.length - 1] as Spawned).description).toBe('refute #7')
})

test('a judge whose end arrives before its spawn resolves still posts its verdict', async ($, on) => {
  mock.env(on, {})
  tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  const ui = watchUi(on)
  let n = 0
  on('agent.spawn', async (_h: any, e: any) => {
    const agentId = `a${++n}`
    if (e.tool === 'Agent') {
      // the judge is quick: it ends inside the call that starts it
      await $.turn.complete({ answer: 'refuted: routes.ts:12 does return 401.', durationMs: 5, isAborted: false, turnId: 'early', reason: 'answer', agentId })
      return { model: e.model, agentId, result: { agentId, content: [] }, text: 'started' } as any
    }
    return { model: e.model ?? 'inherit', agentId }
  })
  on('tool.call', () => ({ result: { stdout: 'ok', stderr: '' } as any, text: 'ok' }))
  await start($)
  await spawn($, 'audit routes')
  await spawn($, 'audit schema')
  await complete($, 'Defect: routes.ts:12 returns 200.', { agentId: 'a1' })
  await complete($, 'ok', { agentId: 'a2' })
  expect(sess.appended().length).toBe(1)
  const r = (await run($, 'refute', '1')).text as string
  expect(r).toMatch("sent #1 audit routes's report")
  await theClock?.advance(RECHECK)
  expect(sess.appended().length).toBe(2)
  expect(texts(sess)[1]).toMatch('[dojo-tally] Judge verdict on #1 audit routes:\nrefuted: routes.ts:12 does return 401.')
  expect(ui.toast[ui.toast.length - 1]).toMatch('judge verdict on #1 audit routes')
})

test('a member whose end arrives before its spawn resolves is still counted, and the wave settles', async ($, on) => {
  mock.env(on, {})
  tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  const ui = watchUi(on)
  let n = 0
  on('agent.spawn', async (_h: any, e: any) => {
    const agentId = `a${++n}`
    if (e.description === 'fast') {
      await $.turn.complete({ answer: 'Defect at f.ts:1.', durationMs: 5, isAborted: false, turnId: 'early', reason: 'answer', agentId })
    }
    return { model: e.model ?? 'inherit', agentId }
  })
  on('tool.call', () => ({ result: { stdout: 'ok', stderr: '' } as any, text: 'ok' }))
  await spawn($, 'slow')
  await spawn($, 'fast')
  expect(ui.toast.length).toBe(0)
  await complete($, 'Defect at s.ts:2.', { agentId: 'a1' })
  expect(ui.toast.length).toBe(1)
  expect(ui.toast[0]).toMatch('dispatched 2 · returned 2')
  expect(sess.appended().length).toBe(1)
})

test('a reviewer that used only an mcp__ tool and says "no defects found" is not silent; one that used nothing is', async ($, on) => {
  mock.env(on, {})
  tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  await start($)
  await spawn($, 'mcp reviewer')
  await spawn($, 'todo reviewer')
  await spawn($, 'idle reviewer')
  await spawn($, 'skill reviewer')
  await call($, 'a1', 'mcp__docs__search', { query: 'auth' })
  await call($, 'a2', 'TodoWrite', { todos: [] })
  await call($, 'a4', 'Skill', { skill: 'review' })
  for (const id of ['a1', 'a2', 'a3', 'a4']) await complete($, 'No defects found.', { agentId: id })
  expect(ui.toast[0]).toMatch('returned 2 · failed 0 · silent 2')
  const row = texts(sess)[0] as string
  expect(row).toMatch('#2 todo reviewer (general-purpose): silent')
  expect(row).toMatch('#3 idle reviewer (general-purpose): silent')
  expect(row).not.toMatch('#1 mcp reviewer')
  expect(row).not.toMatch('#4 skill reviewer')
  const out = (await run($, 'tally')).text as string
  expect(flat(out)).toMatch('#1 mcp reviewer general-purpose inherit returned 1 read · 0 writes · 0 bash')
  expect(flat(out)).toMatch('#2 todo reviewer general-purpose inherit silent 0 reads · 0 writes · 0 bash')
})

// ----------------------------------------------------------------------------------------------- parked: a turn is not an end

// A Bash moved to a background shell ends a turn with an interim answer, and the agent stays alive (roster status
// `waiting`) until the work finishes and it wakes for another turn.

test('a member that ends a turn but is still alive is parked: nothing settles, and the second answer is the one that counts', async ($, on) => {
  mock.env(on, {})
  const clock = tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  const seen = spawner(on)
  const ui = watchUi(on)
  const listed: Listed[] = [{ id: 'a2', status: 'waiting' }]
  roster(on, listed) // a1 is not listed: it is done and gone
  await start($)
  await spawn($, 'one')
  await spawn($, 'two')
  await read($, 'a1')
  await complete($, 'Found a defect at x.ts:3.', { agentId: 'a1' })
  await endTurn($, 'I started the review in the background; no defects found yet.', { agentId: 'a2' })
  await clock.advance(RECHECK)
  expect(ui.toast.length).toBe(0)
  expect(sess.appended().length).toBe(0)
  const parked = (await run($, 'tally')).text as string
  expect(parked).toMatch('Open wave 1 (live): dispatched 2 · settled 1 · running 0 · waiting 1')
  expect(flat(parked)).toMatch('#2 two general-purpose inherit waiting')
  expect(parked).toMatch('waiting on its own background work')
  expect(flat(parked)).not.toMatch('#2 two general-purpose inherit silent')
  await clock.advance(30_000) // the timer sees it alive too
  expect(ui.toast.length).toBe(0)
  expect(sess.appended().length).toBe(0)
  expect(((await run($, 'refute', '2')).text as string)).toMatch('#2 two is waiting on its own background work')

  // it wakes, works, ends again with the real answer, and the engine marks it completed
  await read($, 'a2')
  await bash($, 'a2')
  listed[0] = { id: 'a2', status: 'completed' }
  await endTurn($, 'Defect: routes.ts:12 returns 200.', { agentId: 'a2' })
  await clock.advance(RECHECK)
  expect(ui.toast.length).toBe(1)
  expect(ui.toast[0]).toBe('wave settled — dispatched 2 · returned 2 · failed 0 · silent 0 · unchecked 0')
  expect(sess.appended().length).toBe(1)
  await clock.advance(MIN) // and nothing more
  expect(ui.toast.length).toBe(1)
  expect(sess.appended().length).toBe(1)
  // the report on file is the second answer, not the interim one
  await run($, 'refute', '2')
  const prompt = (seen[seen.length - 1] as Spawned).prompt
  expect(prompt).toMatch('Defect: routes.ts:12 returns 200.')
  expect(prompt).not.toMatch('started the review in the background')
})

test('a roster that cannot be read at the recheck settles the agent with what it recorded', async ($, on) => {
  mock.env(on, {})
  tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  on('agent.list', () => { throw new Error('roster unavailable') })
  await start($)
  await spawn($, 'one')
  await spawn($, 'two')
  await complete($, 'ok', { agentId: 'a1' })
  expect(ui.toast.length).toBe(0)
  await complete($, 'No defects found.', { agentId: 'a2' })
  expect(ui.toast.length).toBe(1)
  expect(ui.toast[0]).toMatch('returned 1 · failed 0 · silent 1')
  expect(sess.appended().length).toBe(1)
})

test('a roster that says the agent completed settles it at the recheck, not before', async ($, on) => {
  mock.env(on, {})
  const clock = tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  roster(on, [{ id: 'a1', status: 'completed' }, { id: 'a2', status: 'completed' }])
  await start($)
  await spawn($, 'one')
  await spawn($, 'two')
  await endTurn($, 'ok', { agentId: 'a1' })
  await endTurn($, 'ok', { agentId: 'a2' })
  expect(ui.toast.length).toBe(0) // recorded, not reported
  await clock.advance(RECHECK - 1)
  expect(ui.toast.length).toBe(0)
  await clock.advance(1)
  expect(ui.toast.length).toBe(1)
  expect(sess.appended().length).toBe(1)
})

test('a parked member that the timer later sees completed settles via reconcile, with the answer it recorded', async ($, on) => {
  mock.env(on, {})
  const clock = tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  const seen = spawner(on)
  const ui = watchUi(on)
  const listed: Listed[] = [{ id: 'a2', status: 'running' }] // the engine has not flipped it yet at the recheck
  roster(on, listed)
  await start($)
  await spawn($, 'one')
  await spawn($, 'two')
  await complete($, 'ok', { agentId: 'a1' })
  await endTurn($, 'The build passed.', { agentId: 'a2' })
  await clock.advance(RECHECK)
  expect(ui.toast.length).toBe(0)
  expect(flat((await run($, 'tally')).text as string)).toMatch('#2 two general-purpose inherit waiting')

  listed[0] = { id: 'a2', status: 'completed' }
  await clock.advance(15_000)
  expect(ui.toast.length).toBe(1)
  expect(ui.toast[0]).toMatch('dispatched 2 · returned 1 · failed 0 · silent 0 · unchecked 1') // "The build passed" claims a check, ran no command
  expect(texts(sess)[0]).toMatch('#2 two (general-purpose): unchecked')
  await run($, 'refute', '2')
  expect((seen[seen.length - 1] as Spawned).prompt).toMatch('Report from two (general-purpose):\nThe build passed.')
})

test('a parked member that is then killed is failed, not reported as the interim answer it gave', async ($, on) => {
  mock.env(on, {})
  const clock = tick(on, { now: 1000 })
  const sess = mock.session(on)
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  const listed: Listed[] = [{ id: 'a2', status: 'waiting' }]
  roster(on, listed)
  await start($)
  await spawn($, 'one')
  await spawn($, 'two')
  await complete($, 'ok', { agentId: 'a1' })
  await endTurn($, 'Started in the background.', { agentId: 'a2' })
  await clock.advance(RECHECK)
  expect(ui.toast.length).toBe(0)
  listed[0] = { id: 'a2', status: 'killed' }
  await clock.advance(15_000)
  expect(ui.toast.length).toBe(1)
  expect(texts(sess)[0]).toMatch('returned 1 · failed 1')
  expect(texts(sess)[0]).toMatch('#2 two (general-purpose): failed — stopped (killed)')
})

test('a judge that parks posts its verdict only when it is really done, and the last answer is the one posted', async ($, on) => {
  const listed: Listed[] = []
  roster(on, listed)
  const seen = spawner(on)
  const ui = watchUi(on)
  const sess = await settledPair($, on)
  expect(seen.length).toBe(2)
  await run($, 'refute', '2') // the judge is a3
  listed.push({ id: 'a3', status: 'waiting' })
  await endTurn($, 'Started the checks in the background; waiting.', { agentId: 'a3' })
  await theClock?.advance(RECHECK)
  expect(sess.appended().length).toBe(1) // only the settle note: no verdict yet
  const toasts = ui.toast.length
  await theClock?.advance(MIN)
  expect(sess.appended().length).toBe(1)

  listed[0] = { id: 'a3', status: 'completed' }
  await endTurn($, 'Refuted: "Tests pass" is unverified (pytest -q: 3 failed).', { agentId: 'a3' })
  await theClock?.advance(RECHECK)
  expect(sess.appended().length).toBe(2)
  expect(texts(sess)[1]).toMatch('[dojo-tally] Judge verdict on #2 audit schema:\nRefuted: "Tests pass" is unverified')
  expect(texts(sess)[1]).not.toMatch('Started the checks')
  expect(ui.toast.length).toBe(toasts + 1)
  await theClock?.advance(MIN)
  expect(sess.appended().length).toBe(2) // posted once
})

test('a judge that is parked and then killed reports no verdict', async ($, on) => {
  const listed: Listed[] = []
  roster(on, listed)
  spawner(on)
  watchUi(on)
  const sess = await settledPair($, on)
  await run($, 'refute', '2')
  listed.push({ id: 'a3', status: 'waiting' })
  await endTurn($, 'Started the checks in the background; waiting.', { agentId: 'a3' })
  await theClock?.advance(RECHECK)
  listed[0] = { id: 'a3', status: 'killed' }
  await theClock?.advance(15_000)
  expect(sess.appended().length).toBe(2)
  expect(texts(sess)[1]).toMatch('The judge on #2 audit schema returned no verdict (stopped (killed))')
  expect(texts(sess)[1]).toMatch('unrefuted, not confirmed')
})

// ----------------------------------------------------------------------------------------------- the table

test('/tally rows are an aligned table: wall-clock life, spelled-out work, a short model', async ($, on) => {
  mock.env(on, {})
  const clock = tick(on, { now: 1000 })
  mock.session(on)
  standIn(on)
  spawner(on)
  watchUi(on)
  await start($)
  await spawn($, 'notes writer', { model: 'claude-haiku-5-5' })
  await spawn($, 'reviewer', { subagentType: 'Explore', model: 'claude-haiku-5-5' })
  for (let i = 0; i < 7; i++) await read($, 'a1')
  await call($, 'a1', 'Write', { file_path: '/work/notes.md', content: 'x' })
  await bash($, 'a1')
  await bash($, 'a1')
  await read($, 'a2')
  await clock.advance(1500)
  await complete($, 'Reviewed a.ts: one nit at line 3.', { agentId: 'a2', durationMs: 9 }) // settles 4s after the spawn
  await clock.advance(141_500)
  await complete($, 'Wrote the notes.', { agentId: 'a1', durationMs: 31_000 }) // the last turn was short; the life was 2m28s

  const out = (await run($, 'tally')).text as string
  expect(out).toBe(
    [
      '2 agents in 1 wave',
      'Wave 1 (settled): dispatched 2 · returned 2 · failed 0 · silent 0 · unchecked 0',
      '  #1  notes writer  general-purpose  haiku 5.5  returned  7 reads · 1 write · 2 bash  2m28s',
      '  #2  reviewer      Explore          haiku 5.5  returned  1 read · 0 writes · 0 bash     4s',
      "/refute <n> sends a settled agent's report to a judge.",
    ].join('\n'),
  )
  expect(out).not.toMatch('r/w/b')
})

test('/tally columns line up across waves, long labels are cut, models are shortened, sub-lines hang under the label', async ($, on) => {
  mock.env(on, {})
  const clock = tick(on, { now: 1000 })
  mock.session(on)
  standIn(on)
  spawner(on)
  watchUi(on)
  const listed: Listed[] = [{ id: 'a2', status: 'waiting' }]
  roster(on, listed)
  await start($)
  await spawn($, 'a very long label that keeps going and going', { model: 'claude-sonnet-5-5' })
  await complete($, '', { agentId: 'a1', reason: 'error' })
  await spawn($, 'b', { model: 'some-model-id-that-is-long' })
  await endTurn($, 'Started in the background.', { agentId: 'a2' })
  await clock.advance(RECHECK)
  const lines = ((await run($, 'tally')).text as string).split('\n')
  const rows = lines.filter(l => /^ {2}#\d/.test(l))
  expect(rows.length).toBe(2)
  const [open, settled] = rows as [string, string] // newest wave first
  expect(flat(open)).toMatch('#2 b general-purpose some-model-id-th waiting 0 reads · 0 writes · 0 bash')
  expect(flat(settled)).toMatch('#1 a very long label that… general-purpose sonnet 5.5 failed 0 reads · 0 writes · 0 bash')
  expect(settled).not.toMatch('label that …') // the cut does not leave a space before the ellipsis
  // every column starts in the same place in both rows, and the rows are as wide as each other
  expect(open.length).toBe(settled.length)
  for (const cell of ['general-purpose', '0 reads']) expect(open.indexOf(cell)).toBe(settled.indexOf(cell))
  expect(open.indexOf('waiting') - open.indexOf('some-model-id-th')).toBe(settled.indexOf('failed') - settled.indexOf('sonnet 5.5'))
  const reason = lines.find(l => l.includes('its turn ended in an error'))
  expect(reason?.startsWith(' '.repeat(2 + 2 + 2) + 'its turn')).toBe(true)
  const waitingLine = lines.find(l => l.includes('waiting on its own background work'))
  expect(waitingLine?.startsWith(' '.repeat(2 + 2 + 2) + 'waiting on')).toBe(true)
})

test('the classic fallback name /dojo-tally:tally is answered by the mod too', async ($, on) => {
  mock.env(on, {})
  tick(on, { now: 10_000 })
  mock.session(on)
  standIn(on)
  spawner(on)
  await start($)
  expect(((await run($, 'dojo-tally:tally')).text as string)).toBe('No fan-out yet.')
})
