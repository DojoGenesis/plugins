import { expect, mock, test } from 'claude-code/testing'
import { CASES } from './cases'

// Mod kit tests. The kit puts the engine beneath the plugin: hooks the test registers with `on` stand for it.
// The classic Stop hook is not run here (the unittest suite covers it); these tests cover the mod, and run the
// shared case table (cases.json, the same one the Python tests run) through the mod's hooks.

type Ui = { status: string[]; toast: string[] }

function watchUi(on: any): Ui {
  const ui: Ui = { status: [], toast: [] }
  on('ui.status', (_$: any, e: any) => { ui.status.push(String(e.text)); return { value: undefined } as any })
  on('ui.toast', (_$: any, e: any) => { ui.toast.push(String(e.text)); return { value: undefined } as any })
  return ui
}

// The engine stand-in for tool.call: answers with `reply(e)`, and counts what reached the bottom.
function engine(on: any, reply: (e: any) => any) {
  const seen: any[] = []
  on('tool.call', (_$: any, e: any) => {
    seen.push(e)
    return reply(e)
  })
  return seen
}

const ok = (text: string) => ({ result: { stdout: text, stderr: '' } as any, text })
const failed = (text: string) => ({ result: undefined as any, text, isError: true as const })

function standIn(on: any) {
  on('turn.start', (_$: any, e: any) => ({ turnId: e.turnId }))
  on('turn.complete', (_$: any, e: any) => ({ text: e.answer, usage: e.usage }))
}

let turn = 0
const complete = ($: any, answer: string, extra: Record<string, unknown> = {}) =>
  $.turn.complete({ answer, durationMs: 1, isAborted: false, turnId: `t${++turn}`, reason: 'answer', ...extra })
const start = ($: any, text = 'do the thing') => $.turn.start({ text, turnId: `t${++turn}` })
const bash = ($: any, command: string, extra: Record<string, unknown> = {}) => $.tool.call({ tool: 'Bash', command, ...extra } as any)
const spawn = ($: any, prompt: string) => $.agent.spawn({ prompt })
const edit = ($: any) => $.tool.call({ tool: 'Edit', file_path: '/work/app/x.txt', old_string: 'a', new_string: 'b' } as any)

const last = (ui: Ui) => ui.status.length === 0 ? '' : (ui.status[ui.status.length - 1] as string)

// ----------------------------------------------------------------------------------------------- the ledger

test('a claim with no check this turn shows UNVERIFIED in the status line and a toast', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  engine(on, () => ok('ok'))
  const ui = watchUi(on)
  await start($)
  await edit($)
  await complete($, 'Fixed and deployed.')
  expect(last(ui)).toMatch('UNVERIFIED')
  expect(last(ui)).toMatch('dojo-verify')
  expect(ui.toast.length).toBe(1)
  expect(ui.toast[0]).toMatch('UNVERIFIED')
})

test('a passing Bash check before the claim means no UNVERIFIED', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  const seen = engine(on, () => ok('12 passed in 0.4s'))
  const ui = watchUi(on)
  await start($)
  await bash($, 'pytest -q')
  await complete($, 'Fixed. The tests pass.')
  expect(seen.length).toBe(1)
  expect(ui.status.join('|')).not.toMatch('UNVERIFIED')
  expect(ui.toast.length).toBe(0)
})

test('a Bash result that is an error does not count as a check', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  engine(on, (e: any) => (e.tool === 'Bash' ? failed('Exit code 1\nFAILED tests/test_a.py') : ok('ok')))
  const ui = watchUi(on)
  await start($)
  await edit($)
  await bash($, 'pytest -q')
  await complete($, 'All tests pass.')
  expect(last(ui)).toMatch('UNVERIFIED')
})

test('a command that only looks like a check does not count', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  engine(on, () => ok('a.js'))
  const ui = watchUi(on)
  await start($)
  await edit($)
  await bash($, 'ls build')
  await complete($, 'Verified.')
  expect(last(ui)).toMatch('UNVERIFIED')
})

test('a check that exits 0 while its output shows failures does not count', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  engine(on, () => ok('2 failed, 5 passed'))
  const ui = watchUi(on)
  await start($)
  await edit($)
  await bash($, 'pytest | tail -3')
  await complete($, 'Tests pass.')
  expect(last(ui)).toMatch('UNVERIFIED')
})

test('a session with no change in it is never judged, strong words included', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  engine(on, () => ok('done'))
  const ui = watchUi(on)
  for (const text of ['Done.', 'Fixed and deployed.', 'It returns the fixed point of the map.', 'Your site is deployed on Pages.']) {
    await start($)
    await complete($, text)
  }
  await start($)
  await bash($, 'git status')
  await complete($, 'All tests pass.')
  expect(ui.status.join('|')).not.toMatch('UNVERIFIED')
  expect(ui.toast.length).toBe(0)
  await start($)
  await edit($)
  await complete($, 'Done.')
  expect(last(ui)).toMatch('UNVERIFIED')
})

test('a check after the last change backs the claim; a change after the check re-opens it', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  engine(on, () => ok('3 passed'))
  const ui = watchUi(on)
  await start($)
  await edit($)
  await bash($, 'pytest -q')
  await complete($, 'Fixed.')
  expect(ui.status.join('|')).not.toMatch('UNVERIFIED')
  await start($)
  await edit($)
  await complete($, 'Fixed.')
  expect(last(ui)).toMatch('UNVERIFIED')
})

test('the ledger is the session\'s: a check in an earlier prompt still backs a later claim', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  engine(on, () => ok('3 passed'))
  const ui = watchUi(on)
  await start($, 'first')
  await edit($)
  await bash($, 'pytest -q')
  await complete($, 'Done, tests pass.')
  await start($, 'second')
  await complete($, 'Fixed.')
  expect(ui.status.join('|')).not.toMatch('UNVERIFIED')
  expect(ui.toast.length).toBe(0)
})

test('dispatching an agent is not a change the mod can see: not judged', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  engine(on, () => ok('started'))
  const ui = watchUi(on)
  await start($)
  await $.tool.call({ tool: 'Agent', prompt: 'do it' } as any)
  await complete($, 'Fixed and deployed.')
  expect(ui.status.join('|')).not.toMatch('UNVERIFIED')
})

test('a Bash command that writes a file is a change; one that only reads is not', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  let output = ''
  engine(on, () => ok(output))
  const ui = watchUi(on)
  await start($)
  await bash($, 'git status')
  await complete($, 'Fixed.')
  expect(ui.status.join('|')).not.toMatch('UNVERIFIED')
  for (const cmd of ["sed -i '' s/a/b/ f.py", 'echo 5 > retries.txt', 'git checkout -- f.py', 'npm install', 'cat > f.py <<EOF\nx\nEOF']) {
    await start($)
    await bash($, 'pytest -q')
    await bash($, cmd)
    await complete($, 'Fixed.')
    expect(last(ui)).toMatch('UNVERIFIED')
  }
})

test('incidental words do not switch detection off, and a disclosure excuses only its own sentence', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  engine(on, () => ok('ok'))
  const ui = watchUi(on)
  for (const text of [
    "I didn't run into any issues. Fixed and deployed.",
    'Fixed the bug where unverified users could log in. All tests pass.',
    'No tests were broken by this change. Everything is green.',
    'Here is the plan:\n```\nstep\nAll tests pass.',
  ]) {
    const before = ui.status.length
    await start($)
    await edit($)
    await complete($, text)
    expect(ui.status.slice(before).join('|')).toMatch('UNVERIFIED')
  }
  for (const text of [
    "Fixed and deployed. I couldn't verify it in production.",
    'Root cause: the loader never checked the file size. Fixed it with a guard.',
    'No regressions and all tests pass.',
    'The test suite passes.',
  ]) {
    const before = ui.status.length
    await start($)
    await edit($)
    await complete($, text)
    expect(ui.status.slice(before).join('|')).toMatch('UNVERIFIED')
  }
  for (const text of ["Fixed and deployed, but I couldn't verify it in production.", 'Fixed the typo (unverified).', 'Fixed the typo; not tested.']) {
    const before = ui.status.length
    await start($)
    await edit($)
    await complete($, text)
    expect(ui.status.slice(before).join('|')).not.toMatch('UNVERIFIED')
  }
})

test('masked idioms and non-checks do not count; a package-manager tool run does', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  let output = ''
  engine(on, () => ok(output))
  const ui = watchUi(on)
  const cases: Array<[string, string, boolean]> = [
    ['pytest -q >/dev/null 2>&1 && echo ok || echo broken', 'broken', false],
    ['pytest > out.log 2>&1; echo done', 'done', false],
    ['pytest --version', 'pytest 8.0.0', false],
    ['pnpm tsc --noEmit', '', true],
    ['yarn jest', 'Tests: 5 passed', true],
    ['pytest && echo ok || exit 1', '1 passed\nok', true],
  ]
  for (const [cmd, out, evidence] of cases) {
    output = out
    const before = ui.status.length
    await start($)
    await edit($)
    await bash($, cmd)
    await complete($, 'Fixed.')
    const unverified = ui.status.slice(before).join('|').includes('UNVERIFIED')
    expect(`${cmd} -> ${!unverified}`).toBe(`${cmd} -> ${evidence}`)
  }
})

test('negated, disclosed, quoted and conditional claims are not flagged', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  engine(on, () => ok('clean'))
  const ui = watchUi(on)
  for (const text of [
    'This is not verified.',
    'The migration is unverified.',
    'Fixed the typo (unverified).',
    'If the tests pass, merge it.',
    'Is it fixed?',
    '```\nAll tests passed\n```',
  ]) {
    await start($)
    await edit($)
    await complete($, text)
  }
  expect(ui.status.join('|')).not.toMatch('UNVERIFIED')
  expect(ui.toast.length).toBe(0)
})

test('a turn that ends in an abort or an error is not judged', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  engine(on, () => ok('ok'))
  const ui = watchUi(on)
  await start($)
  await edit($)
  await complete($, 'Fixed.', { reason: 'aborted', isAborted: true })
  expect(ui.status.join('|')).not.toMatch('UNVERIFIED')
})

test('a continuation turn keeps the ledger; a new human prompt clears the flag', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  engine(on, () => ok('3 passed'))
  const ui = watchUi(on)
  await start($, 'first')
  await edit($)
  await bash($, 'pytest')
  await start($, '') // continuation (a background wake): same ledger
  await complete($, 'Fixed.')
  expect(ui.status.join('|')).not.toMatch('UNVERIFIED')
  await start($, 'second') // a change since the last check
  await edit($)
  await complete($, 'Fixed.')
  expect(last(ui)).toMatch('UNVERIFIED')
  await start($, 'third')
  expect(last(ui)).toBe('undefined') // the flag is cleared when the next prompt starts
})

// ----------------------------------------------------------------------------------------------- options

test('toast_unverified false: status still shows, no toast', { options: { toast_unverified: false } }, async ($, on) => {
  mock.env(on, {})
  standIn(on)
  engine(on, () => ok('ok'))
  const ui = watchUi(on)
  await start($)
  await edit($)
  await complete($, 'Fixed.')
  expect(last(ui)).toMatch('UNVERIFIED')
  expect(ui.toast.length).toBe(0)
})

test('show_status false: no status line at all, toast still shows', { options: { show_status: false } }, async ($, on) => {
  mock.env(on, {})
  standIn(on)
  engine(on, () => ok('ok'))
  const ui = watchUi(on)
  await start($)
  await edit($)
  await complete($, 'Fixed.')
  expect(ui.status.length).toBe(0)
  expect(ui.toast.length).toBe(1)
})

test('mode off makes the mod inert', { options: { mode: 'off' } }, async ($, on) => {
  mock.env(on, {})
  standIn(on)
  engine(on, () => ok('ok'))
  const ui = watchUi(on)
  await start($)
  await edit($)
  await complete($, 'Fixed.')
  expect(ui.status.length).toBe(0)
  expect(ui.toast.length).toBe(0)
})

test('DOJO_OFF=1 makes the mod inert', async ($, on) => {
  mock.env(on, { DOJO_OFF: '1' })
  standIn(on)
  engine(on, () => ok('ok'))
  const ui = watchUi(on)
  await start($)
  await edit($)
  await complete($, 'Fixed.')
  expect(ui.status.length).toBe(0)
  expect(ui.toast.length).toBe(0)
})

test('DOJO_VERIFY_OFF=1 makes the mod inert; DOJO_VERIFY_OFF=0 does not', async ($, on) => {
  mock.env(on, { DOJO_VERIFY_OFF: '1' })
  standIn(on)
  engine(on, () => ok('ok'))
  const ui = watchUi(on)
  await start($)
  await edit($)
  await complete($, 'Fixed.')
  expect(ui.status.length).toBe(0)
})

test('DOJO_VERIFY_OFF=0 does not turn it off', async ($, on) => {
  mock.env(on, { DOJO_VERIFY_OFF: '0', DOJO_OFF: '0' })
  standIn(on)
  engine(on, () => ok('ok'))
  const ui = watchUi(on)
  await start($)
  await edit($)
  await complete($, 'Fixed.')
  expect(last(ui)).toMatch('UNVERIFIED')
})

// ----------------------------------------------------------------------------------------------- pass-through

test('one tool call reaches the engine once, and the result comes back untouched', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  const seen = engine(on, () => ok('1 passed'))
  watchUi(on)
  const r: any = await bash($, 'pytest')
  expect(seen.length).toBe(1)
  expect(r.text).toBe('1 passed')
})

test('a failure in the plugin after next ran never re-runs the tool', async ($, on) => {
  standIn(on)
  // The environment read fails inside the plugin, after next has already run the tool. The call must reach the
  // engine exactly once: a catch that called next again would run the command a second time.
  on('env.get', () => { throw new Error('environment unavailable') })
  const seen = engine(on, () => ok('1 passed'))
  watchUi(on)
  const r: any = await bash($, 'pytest')
  expect(seen.length).toBe(1)
  expect(r.text).toBe('1 passed')
})

test('a failure in the plugin after a spawn never starts a second agent', async ($, on) => {
  standIn(on)
  on('env.get', () => { throw new Error('environment unavailable') })
  const seen = spawner(on)
  watchUi(on)
  const r: any = await spawn($, 'one')
  expect(seen.length).toBe(1)
  expect(r.agentId).toBe('a1')
})

test('turn.complete reaches the hooks beneath and passes usage through', async ($, on) => {
  mock.env(on, {})
  const usage = { model: 'm', input_tokens: 1, output_tokens: 2, cache_read_input_tokens: 3, cache_creation_input_tokens: 4 }
  let reached = 0
  on('turn.complete', (_$: any, e: any) => { reached++; return { text: e.answer, usage: e.usage } })
  watchUi(on)
  const r: any = await complete($, 'ok', { usage })
  expect(reached).toBe(1)
  expect(r.usage?.model).toBe('m')
  expect(r.text).toBe('ok')
})

// ----------------------------------------------------------------------------------------------- agents

function spawner(on: any) {
  let n = 0
  const seen: any[] = []
  on('agent.spawn', (_$: any, e: any) => {
    seen.push(e)
    return { model: e.model ?? 'inherit', agentId: `a${++n}` }
  })
  return seen
}

test('three spawns: dispatched 3, two answers and an empty one: returned 2, failed 1', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  const seen = spawner(on)
  const ui = watchUi(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await spawn($, 'three')
  expect(seen.length).toBe(3) // each spawn reached the engine once
  expect(last(ui)).toMatch('dispatched 3 / returned 0 / failed 0 (3 outstanding)')
  await complete($, 'ok', { agentId: 'a1' })
  await complete($, 'ok', { agentId: 'a2' })
  await complete($, '', { agentId: 'a3' })
  expect(last(ui)).toMatch('dispatched 3 / returned 2 / failed 1')
  expect(last(ui)).not.toMatch('outstanding')
})

test('an agent still running shows as outstanding, not failed', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await complete($, 'ok', { agentId: 'a1' })
  expect(last(ui)).toMatch('dispatched 2 / returned 1 / failed 0 (1 outstanding)')
})

test('a turn that ends in error counts as failed; a second answer does not double-count', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await complete($, '', { agentId: 'a1', reason: 'error' })
  await complete($, 'ok', { agentId: 'a2' })
  await complete($, 'ok again', { agentId: 'a2' })
  expect(last(ui)).toMatch('dispatched 2 / returned 1 / failed 1')
})

test('an agent id that was never spawned (a workflow agent) does not raise the returned count', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  await spawn($, 'one')
  await complete($, 'ok', { agentId: 'w-9' })
  expect(last(ui)).toMatch('dispatched 1 / returned 0 / failed 0 (1 outstanding)')
})

test('a subagent claim does not raise UNVERIFIED', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  await spawn($, 'one')
  await complete($, 'Fixed and deployed. All tests pass.', { agentId: 'a1' })
  expect(ui.status.join('|')).not.toMatch('UNVERIFIED')
  expect(ui.toast.length).toBe(0)
})

test('the status line is one string: UNVERIFIED and the tally together', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  spawner(on)
  engine(on, () => ok('ok'))
  const ui = watchUi(on)
  await start($)
  await edit($)
  await spawn($, 'one')
  await complete($, 'Fixed.')
  expect(last(ui)).toMatch('UNVERIFIED')
  expect(last(ui)).toMatch('dispatched 1 / returned 0 / failed 0')
})

test('settled agents drop out of the count at the next human prompt; running ones carry over', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  await spawn($, 'one')
  await spawn($, 'two')
  await complete($, 'ok', { agentId: 'a1' })
  await start($, 'next prompt')
  expect(last(ui)).toMatch('dispatched 1 / returned 0 / failed 0 (1 outstanding)')
  await complete($, 'ok', { agentId: 'a2' })
  expect(last(ui)).toMatch('dispatched 1 / returned 1 / failed 0')
  await start($, 'and another')
  expect(last(ui)).toBe('undefined')
})

test('the agent tally survives a new human prompt', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  spawner(on)
  const ui = watchUi(on)
  await spawn($, 'one')
  await start($, 'next prompt')
  expect(last(ui)).toMatch('dispatched 1')
})

// ----------------------------------------------------------------------------------------------- shared case table

test('the claim table: every case agrees with the classic hook (a session with a change)', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  engine(on, () => ok('clean'))
  const ui = watchUi(on)
  await start($)
  await edit($) // the ledger stays mutated and unchecked for every row below
  const wrong: string[] = []
  for (const c of CASES.claims) {
    if (!c.mutated) continue
    const before = ui.status.length
    await start($)
    await complete($, c.text)
    const flagged = ui.status.slice(before).join('|').includes('UNVERIFIED')
    if (flagged !== c.claim) wrong.push(`${JSON.stringify(c.text)} expected claim=${c.claim}`)
  }
  expect(wrong).toEqual([])
})

test('the claim table: a session with no change is never judged', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  engine(on, () => ok('clean'))
  const ui = watchUi(on)
  for (const c of CASES.claims) {
    if (c.mutated) continue
    await start($)
    await complete($, c.text)
  }
  await start($)
  await bash($, 'git status')
  expect(ui.status.join('|')).not.toMatch('UNVERIFIED')
  expect(ui.toast.length).toBe(0)
})

test('the command table: every case agrees with the classic hook', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  let output = ''
  engine(on, () => ok(output))
  const ui = watchUi(on)
  const wrong: string[] = []
  for (const c of CASES.commands) {
    output = c.output
    const before = ui.status.length
    await start($)
    await edit($)
    await bash($, c.cmd)
    await complete($, 'Fixed.')
    const unverified = ui.status.slice(before).join('|').includes('UNVERIFIED')
    if (unverified === c.evidence) wrong.push(`${JSON.stringify(c.cmd)} expected evidence=${c.evidence}`)
  }
  expect(wrong).toEqual([])
})

test('the mutation table: every command agrees with the classic hook', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  let output = ''
  engine(on, () => ok(output))
  const ui = watchUi(on)
  const wrong: string[] = []
  for (const c of CASES.mutations as Array<{ cmd: string; mutates: boolean }>) {
    const before = ui.status.length
    await start($)
    await edit($)
    output = '3 passed'
    await bash($, 'pytest -q')
    output = ''
    await bash($, c.cmd)
    await complete($, 'All tests pass.')
    const flagged = ui.status.slice(before).join('|').includes('UNVERIFIED')
    if (flagged !== c.mutates) wrong.push(`${JSON.stringify(c.cmd)} expected mutates=${c.mutates}`)
  }
  expect(wrong).toEqual([])
})

test('a scratch file in the temp directory is not a change, in any edit tool', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  engine(on, () => ok('3 passed'))
  const ui = watchUi(on)
  await start($)
  await edit($)
  await bash($, 'pytest -q')
  await $.tool.call({ tool: 'Write', file_path: '/tmp/notes.md', content: 'x' } as any)
  await $.tool.call({ tool: 'NotebookEdit', notebook_path: '/private/var/folders/ab/T/n.ipynb' } as any)
  await complete($, 'All tests pass.')
  expect(ui.status.join('|')).not.toMatch('UNVERIFIED')
})

test('no message can make the claim patterns slow', async ($, on) => {
  mock.env(on, {})
  standIn(on)
  engine(on, () => ok('ok'))
  watchUi(on)
  await start($)
  await edit($)
  const messages = ['tests' + ' '.repeat(100000), 'all the ' + 'full '.repeat(20000), 'a. '.repeat(40000), 'tests '.repeat(20000), 'I never '.repeat(20000)]
  for (const text of messages) {
    const t0 = Date.now()
    await complete($, text)
    expect(Date.now() - t0 < 500).toBe(true)
  }
})

// One test per row: the ledger is the session's, so every row needs a fresh mod.
for (const row of CASES.sequences as Array<{ name: string; steps: string[][]; text: string; flagged: boolean }>) {
  test(`session table: ${row.name}`, async ($, on) => {
    mock.env(on, {})
    standIn(on)
    let output = ''
    let failing = false
    engine(on, () => (failing ? failed(output) : ok(output)))
    const ui = watchUi(on)
    await start($)
    for (const step of row.steps) {
      const kind = step[0]
      if (kind === 'edit') {
        await edit($)
      } else if (kind === 'run' || kind === 'fail') {
        failing = kind === 'fail'
        output = step[2] as string
        await bash($, step[1] as string)
      } else if (kind === 'scratch') {
        await $.tool.call({ tool: 'Write', file_path: '/tmp/notes.md', content: 'x' } as any)
      } else if (kind === 'read') {
        await $.tool.call({ tool: 'Read', file_path: '/tmp/x' } as any)
      } else if (kind === 'agent') {
        await $.tool.call({ tool: 'Agent', prompt: 'do it' } as any)
      } else {
        throw new Error(`unknown step ${String(kind)}`)
      }
    }
    const before = ui.status.length
    await complete($, row.text)
    expect(ui.status.slice(before).join('|').includes('UNVERIFIED')).toBe(row.flagged)
  })
}
