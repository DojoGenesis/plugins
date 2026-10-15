import { expect, mock, test } from 'claude-code/testing'

import { parseRefusal } from '../hooks/model'

const STAGING =
  "PreToolUse:Bash hook error: dojo-gates: staging — `git add -A`, `git add --all`, `git add .` (and `git stage`, its synonym) stage everything in the tree, including files you didn't mean to ship. Stage explicit paths (`git add path/a path/b`), check `git status`, then commit. To allow it on purpose, set DOJO_GATES_SKIP=staging in the environment Claude Code starts with (or under env in settings.json)."
const LANES =
  "dojo-lanes: /work/demo/lanes-demo/target.txt is in Lanes holder's lane (claimed 8s ago). Two agents writing one file clobber each other (Dojo rule 4). Don't write it: put the change you need in your report so the orchestrator applies it after Lanes holder returns."
const REWRITE =
  'dojo-gates: pushed-rewrite — a forced push here would drop commits the remote already has (its branch is not an ancestor of what you\'re pushing). Fetch and integrate first, or ask the person before overwriting a remote branch. To allow it on purpose, set DOJO_GATES_SKIP=pushed-rewrite in the environment Claude Code starts with (or under env in settings.json).'
const SECRET =
  'dojo-gates: secret-print — `env` on its own lists every variable, secrets included. Name the one you need (`printenv PATH`). To allow it on purpose, set DOJO_GATES_SKIP=secret-print in the environment Claude Code starts with (or under env in settings.json).'
const TOKEN =
  'dojo-gates: token-url — this command carries a token in its arguments, which lands in shell history, .git/config and the transcript. Pass it by reference instead: a credential helper, `gh auth`, or an SSH remote. To allow it on purpose, set DOJO_GATES_SKIP=token-url in the environment Claude Code starts with (or under env in settings.json).'
const TIMEOUT =
  "dojo-gates: mac-timeout — `timeout` isn't installed on macOS, so this would fail before your command ran. Use `gtimeout` (it is installed) with the same arguments. To allow it on purpose, set DOJO_GATES_SKIP=mac-timeout in the environment Claude Code starts with (or under env in settings.json)."
const BIGREAD =
  "dojo-gates: big-read — app.log is 900 KB, and reading all of it puts the whole file in context. Search first (`grep -n 'pattern' <path>`), then Read with `offset` and `limit` around the lines you need. To allow it on purpose, set DOJO_GATES_SKIP=big-read in the environment Claude Code starts with (or under env in settings.json)."

const SURFACES = ['terminal', 'desktop', 'vscode', 'mobile'] as const

// What the engine answers beneath the mod: env, session start, command registration, and a plain row.
const beneath = (on: any, env: Record<string, string> = {}) => {
  mock.env(on, env)
  on('session.start', (_$: any, e: any) => ({ cwd: e.cwd }))
  on('command.register', (_$: any, e: any) => ({ value: { command: e.name } }))
  on('ui.render', () => ({ type: 'Text', props: {}, children: ['beneath'] }))
}
const result = (text: string, extra: Record<string, unknown> = {}) => ({
  tool_use_id: 'tu-1',
  tool: 'Bash',
  output: text,
  isErrored: true,
  ...extra,
})
const mountResult = ($: any, surface: string, props: any) =>
  $.ui.mount({ plugin: 'dojo-fixcards', surface, component: 'ToolResult', props, requestId: props.tool_use_id })
const started = ($: any) => $.session.start({ source: 'startup', cwd: '/w', surface: 'terminal', isInteractive: true })

test('staging parses to mod, rule, fixes and allow', () => {
  const r = parseRefusal(STAGING)!
  expect(r.mod).toBe('dojo-gates')
  expect(r.rule).toBe('staging')
  expect(r.fixes).toEqual(['git add path/a path/b', 'git status'])
  expect(r.allow).toBe('DOJO_GATES_SKIP=staging')
  expect(r.reason).toContain("files you didn't mean to ship")
  expect(r.reason).not.toContain('Stage explicit')
  expect(r.raw).toBe(STAGING)
})

test('lanes parses to the file and the holder', () => {
  const r = parseRefusal(LANES)!
  expect(r.mod).toBe('dojo-lanes')
  expect(r.rule).toBe(null)
  expect(r.path).toEqual({ file: '/work/demo/lanes-demo/target.txt', holder: 'Lanes holder', claimed: '8s' })
  expect(r.reason).toContain('Dojo rule 4')
  expect(r.allow).toBe(null)
})

test('the other gates guards parse with their rule, fixes and allow', () => {
  const rewrite = parseRefusal(REWRITE)!
  expect([rewrite.rule, rewrite.fixes, rewrite.allow]).toEqual(['pushed-rewrite', [], 'DOJO_GATES_SKIP=pushed-rewrite'])
  expect(rewrite.advice).toContain('Fetch and integrate first')
  const secret = parseRefusal(SECRET)!
  expect([secret.rule, secret.fixes, secret.allow]).toEqual(['secret-print', ['printenv PATH'], 'DOJO_GATES_SKIP=secret-print'])
  expect(secret.reason).toContain('lists every variable')
  const token = parseRefusal(TOKEN)!
  expect([token.rule, token.fixes, token.allow]).toEqual(['token-url', ['gh auth'], 'DOJO_GATES_SKIP=token-url'])
  const timeout = parseRefusal(TIMEOUT)!
  expect([timeout.rule, timeout.fixes]).toEqual(['mac-timeout', ['gtimeout']])
  const big = parseRefusal(BIGREAD)!
  expect([big.rule, big.fixes, big.allow]).toEqual(['big-read', ["grep -n 'pattern' <path>", 'offset', 'limit'], 'DOJO_GATES_SKIP=big-read'])
})

test('text with no dojo guard parses to null; an unknown future guard keeps mod and reason', () => {
  expect(parseRefusal('Error: file not found')).toBe(null)
  expect(parseRefusal('')).toBe(null)
  const odd = parseRefusal('dojo-newguard: something odd happened here')!
  expect(odd.mod).toBe('dojo-newguard')
  expect(odd.rule).toBe(null)
  expect(odd.reason).toBe('something odd happened here')
  expect(odd.fixes).toEqual([])
})

test('a refusal draws the card on every surface: header, fix code, allow code', async ($, on) => {
  beneath(on)
  await started($)
  for (const surface of SURFACES) {
    const ui = await mountResult($, surface, result(STAGING))
    expect(await ui.find({ type: 'Text', text: /Blocked by dojo-gates/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /staging/ })).toBeDefined()
    expect(await ui.find({ type: 'Code', text: 'git add path/a path/b' })).toBeDefined()
    expect(await ui.find({ type: 'Code', text: 'git status' })).toBeDefined()
    expect(await ui.find({ type: 'Code', text: 'DOJO_GATES_SKIP=staging' })).toBeDefined()
    expect(await ui.find({ type: 'Code', text: 'git add -A' })).toBeUndefined()
    await ui.unmount()
  }
})

test('the lanes card names the holder and the file', async ($, on) => {
  beneath(on)
  await started($)
  const ui = await mountResult($, 'desktop', result(LANES))
  expect(await ui.find({ type: 'Text', text: /Blocked by dojo-lanes/ })).toBeDefined()
  expect(await ui.find({ type: 'Code', text: '/work/demo/lanes-demo/target.txt' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /Held by Lanes holder/ })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /applies it after Lanes holder returns/ })).toBeDefined()
  await ui.unmount()
})

test('a non-dojo error and a successful row pass through untouched', async ($, on) => {
  beneath(on)
  await started($)
  const plain = await mountResult($, 'terminal', result('Error: exit code 1'))
  expect(await plain.find({ type: 'Text', text: 'beneath' })).toBeDefined()
  expect(await plain.find({ type: 'Text', text: /Blocked by/ })).toBeUndefined()
  const ok = await mountResult($, 'terminal', result(STAGING, { tool_use_id: 'tu-2', isErrored: false }))
  expect(await ok.find({ type: 'Text', text: 'beneath' })).toBeDefined()
  expect(await ok.find({ type: 'Text', text: /Blocked by/ })).toBeUndefined()
})

test('/fixcards off lets rows pass through, on draws them again', async ($, on) => {
  beneath(on)
  await started($)
  expect((await $.command.run({ command: 'fixcards', args: '' } as any)).text).toBe('on · 0 cards drawn this session')
  expect((await $.command.run({ command: 'fixcards', args: 'off' } as any)).text).toBe('off · 0 cards drawn this session')
  const off = await mountResult($, 'desktop', result(STAGING))
  expect(await off.find({ type: 'Text', text: 'beneath' })).toBeDefined()
  expect(await off.find({ type: 'Text', text: /Blocked by/ })).toBeUndefined()
  await off.unmount()
  expect((await $.command.run({ command: 'dojo-fixcards:fixcards', args: 'on' } as any)).text).toMatch(/^on ·/)
  const back = await mountResult($, 'desktop', result(STAGING, { tool_use_id: 'tu-3' }))
  expect(await back.find({ type: 'Text', text: /Blocked by dojo-gates/ })).toBeDefined()
})

test('the drawn counter counts each refused call once at tool.call time', async ($, on) => {
  beneath(on)
  on('tool.call', (_$: any, e: any) =>
    e.tool_use_id === 'ok-1' ? { result: {}, text: 'fine' } : { isError: true, result: STAGING, text: STAGING },
  )
  await started($)
  const call = (id: string) => $.tool.call({ tool: 'Bash', command: 'git add -A', tool_use_id: id } as any)
  await call('r-1')
  await call('r-1')
  await call('r-2')
  await call('ok-1')
  expect((await $.command.run({ command: 'fixcards', args: 'status' } as any)).text).toBe('on · 2 cards drawn this session')
})

test('DOJO_FIXCARDS_OFF turns the mod into a pass-through', async ($, on) => {
  beneath(on, { DOJO_FIXCARDS_OFF: '1' })
  await started($)
  const ui = await mountResult($, 'terminal', result(STAGING))
  expect(await ui.find({ type: 'Text', text: 'beneath' })).toBeDefined()
})

// Seen live (2.1.295): reads and shell commands fold into one group line, so a refused call there has no
// ToolResult block. The mod unfolds such a group and the refused ToolUse row draws the card under itself.
const groupCall = (text: string, extra: Record<string, unknown> = {}) => ({
  tool_use_id: 'tu-g1',
  tool: 'Read',
  input: { file_path: '/work/demo/build.log' },
  isRunning: false,
  isErrored: true,
  isInterrupted: false,
  output: text,
  ...extra,
})
const mountGroup = ($: any, surface: string, calls: any[]) =>
  $.ui.mount({ plugin: 'dojo-fixcards', surface, component: 'ToolGroup', props: { calls, isActive: false, isExpanded: false }, requestId: 'g-1' })
const mountUse = ($: any, surface: string, call: any) =>
  $.ui.mount({ plugin: 'dojo-fixcards', surface, component: 'ToolUse', props: call, requestId: call.tool_use_id })

test('a group holding a dojo refusal is unfolded; a group without one stays folded', async ($, on) => {
  const seen: boolean[] = []
  on('ui.render', { component: 'ToolGroup' }, (_$: any, e: any) => {
    seen.push(e.props.isExpanded)
    return { type: 'Text', props: {}, children: ['group'] }
  })
  beneath(on)
  await started($)
  const refused = await mountGroup($, 'desktop', [groupCall(BIGREAD), groupCall('', { tool_use_id: 'tu-g2', isErrored: false })])
  await refused.unmount()
  const plain = await mountGroup($, 'desktop', [groupCall('Error: exit code 1', { tool_use_id: 'tu-g3' })])
  await plain.unmount()
  expect(seen).toEqual([true, false])
})

test('the refused row of an unfolded group keeps its own row and draws the card under it', async ($, on) => {
  beneath(on)
  await started($)
  const group = await mountGroup($, 'terminal', [groupCall(BIGREAD)])
  await group.unmount()
  for (const surface of SURFACES) {
    const row = await mountUse($, surface, groupCall(BIGREAD))
    expect(await row.find({ type: 'Text', text: 'beneath' })).toBeDefined()
    expect(await row.find({ type: 'Text', text: /Blocked by dojo-gates/ })).toBeDefined()
    expect(await row.find({ type: 'Code', text: 'DOJO_GATES_SKIP=big-read' })).toBeDefined()
    await row.unmount()
  }
})

test('a standalone refused ToolUse row is left to its ToolResult block: no second card', async ($, on) => {
  beneath(on)
  await started($)
  const row = await mountUse($, 'desktop', groupCall(STAGING, { tool_use_id: 'tu-standalone', tool: 'Bash' }))
  expect(await row.find({ type: 'Text', text: /Blocked by/ })).toBeUndefined()
  expect(await row.find({ type: 'Text', text: 'beneath' })).toBeDefined()
  await row.unmount()
})

test('the enabled option off turns the mod into a pass-through, as the kill switch does', { options: { enabled: false } }, async ($, on) => {
  beneath(on)
  await started($)
  const ui = await mountResult($, 'terminal', result(STAGING))
  expect(await ui.find({ type: 'Text', text: 'beneath' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: /Blocked by/ })).toBeUndefined()
})
