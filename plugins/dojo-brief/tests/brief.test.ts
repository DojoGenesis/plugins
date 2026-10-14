import { expect, mock, test } from 'claude-code/testing'

// The kit stands the engine beneath the plugin: hooks the test registers with `on` sit below it. The test's own
// tool.call hook plays the engine's Agent tool and counts what reached it; its ui.log hook collects the dim lines.

type Seen = { description?: string; subagent_type?: string; prompt?: string }

function engine(on: any): Seen[] {
  const seen: Seen[] = []
  on('tool.call', (_$: any, e: any) => {
    seen.push({ description: e.description, subagent_type: e.subagent_type, prompt: e.prompt })
    return { result: { agentId: `a${seen.length}`, content: [] } as any, text: 'ok' } as any
  })
  return seen
}

function watchLog(on: any): string[] {
  const lines: string[] = []
  on('ui.log', (_$: any, e: any) => {
    lines.push(String(e.text))
    return { value: undefined } as any
  })
  return lines
}

// The ui.log hook runs after the call that raised it; a turn of the loop lets it land.
const flush = async () => {
  for (let i = 0; i < 10; i++) await Promise.resolve()
}

const dispatch = ($: any, extra: Record<string, unknown> = {}) =>
  $.tool.call({ tool: 'Agent', description: 'fix retry test', prompt: COMPLETE, ...extra } as any)

// A brief with all six fields in it: goal, owned files, facts, done-check, return shape, rules.
const COMPLETE = [
  'Goal: fix the flaky retry test in the sync worker so it stops failing on CI.',
  'Owned files: src/sync/retry.ts and src/sync/retry.test.ts only. Everything else is read-only.',
  'Facts: the backoff is computed at src/sync/retry.ts:42; the test sleeps for real time at src/sync/retry.test.ts:17.',
  'Done-check: run `pnpm test src/sync` and show the output; pass means exit 0.',
  'Return: files changed, commands run with exit codes, anything unfinished.',
  'Rules: read before editing; no git add or commit.',
].join('\n\n')

// Names files, but says nothing about how done is judged or what to send back.
const PARTIAL =
  'Please change how the slug helper in src/util/slug.ts treats accented letters. At the moment it strips them, ' +
  'which makes titles such as "Café" collapse into "caf". Keep the letters, lowercase them, and leave the rest of ' +
  'the function alone. The only place that calls it is src/site/posts.ts, which should not need to change.'

const THIN = 'fix the retry bug'

// ------------------------------------------------------------------------------- a complete brief

for (const mode of ['notice', 'sendback', 'off']) {
  test(`a complete brief passes in ${mode} mode with no log`, { options: { mode } }, async ($, on) => {
    mock.env(on, {})
    const seen = engine(on)
    const log = watchLog(on)
    const r = await dispatch($)
    await flush()
    expect(seen.length).toBe(1)
    expect(seen[0]?.prompt).toBe(COMPLETE)
    expect((r as any).deny).toBe(undefined)
    expect(log).toEqual([])
  })
}

// ------------------------------------------------------------------------------------ notice mode

test('notice: a thin brief passes and one dim line names what is missing', async ($, on) => {
  mock.env(on, {})
  const seen = engine(on)
  const log = watchLog(on)
  const r = await dispatch($, { prompt: THIN, description: 'Fix Retry Bug' })
  await flush()
  expect(seen.length).toBe(1)
  expect(seen[0]?.prompt).toBe(THIN)
  expect((r as any).deny).toBe(undefined)
  expect(log.length).toBe(1)
  expect(log[0]).toMatch("'Fix Retry Bug' brief is missing: ")
  expect(log[0]).toMatch('detail (under 200 chars)')
  expect(log[0]).toMatch('owned files')
  expect(log[0]).toMatch('done-check')
  expect(log[0]).toMatch('return shape')
  expect(log[0]).toMatch('(dojo-protocol:delegate)')
})

test('notice is the default mode', async ($, on) => {
  mock.env(on, {})
  engine(on)
  const log = watchLog(on)
  await dispatch($, { prompt: THIN })
  await flush()
  expect(log.length).toBe(1)
})

test('notice: only the fields that are missing are named', async ($, on) => {
  mock.env(on, {})
  engine(on)
  const log = watchLog(on)
  await dispatch($, { prompt: PARTIAL, description: 'slug accents' })
  await flush()
  expect(log.length).toBe(1)
  expect(log[0]).toMatch('done-check')
  expect(log[0]).toMatch('return shape')
  expect(log[0]).not.toMatch('owned files')
  expect(log[0]).not.toMatch('detail')
})

test('notice: min_chars moves the line between thin and not thin', { options: { min_chars: 20 } }, async ($, on) => {
  mock.env(on, {})
  engine(on)
  const log = watchLog(on)
  await dispatch($, { prompt: 'Edit src/a.ts. Return a diff. Run the build.', description: 'tiny' })
  await flush()
  expect(log).toEqual([])
})

// ---------------------------------------------------------------------------------- sendback mode

test('sendback: refuses the first thin dispatch with the field list, passes the second with the same description', { options: { mode: 'sendback' } }, async ($, on) => {
  mock.env(on, {})
  const seen = engine(on)
  const log = watchLog(on)
  const first: any = await dispatch($, { prompt: THIN, description: 'Fix Retry Bug' })
  expect(typeof first.deny).toBe('string')
  expect(first.deny).toMatch('dojo-brief: this brief is missing detail (under 200 chars), owned files, done-check, return shape.')
  expect(first.deny).toMatch('Goal, Owned files, Done-check, Facts (path:line), Return shape, Rules carried (dojo-protocol:delegate)')
  expect(first.deny).toMatch('a second dispatch with the same description goes through')
  expect(seen.length).toBe(0)

  // the same description, spelled with other case and spaces around it, is the same description
  const second: any = await dispatch($, { prompt: THIN, description: '  fix retry bug ' })
  expect(second.deny).toBe(undefined)
  expect(seen.length).toBe(1)
  await flush()
  expect(log.some(line => line.includes('still missing'))).toBe(true)
})

test('sendback: a different description is sent back on its own', { options: { mode: 'sendback' } }, async ($, on) => {
  mock.env(on, {})
  const seen = engine(on)
  watchLog(on)
  const a: any = await dispatch($, { prompt: THIN, description: 'first job' })
  const b: any = await dispatch($, { prompt: THIN, description: 'second job' })
  const c: any = await dispatch($, { prompt: THIN, description: 'first job' })
  expect(typeof a.deny).toBe('string')
  expect(typeof b.deny).toBe('string')
  expect(c.deny).toBe(undefined)
  expect(seen.length).toBe(1)
})

test('sendback: a rewritten, complete brief goes through at once and is never sent back', { options: { mode: 'sendback' } }, async ($, on) => {
  mock.env(on, {})
  const seen = engine(on)
  await dispatch($, { prompt: THIN, description: 'job' })
  const r: any = await dispatch($, { prompt: COMPLETE, description: 'job' })
  expect(r.deny).toBe(undefined)
  expect(seen.length).toBe(1)
})

test('sendback: a fork is never sent back', { options: { mode: 'sendback' } }, async ($, on) => {
  mock.env(on, {})
  const seen = engine(on)
  const r: any = await dispatch($, { prompt: 'carry on', subagent_type: 'fork', description: 'side thread' })
  expect(r.deny).toBe(undefined)
  expect(seen.length).toBe(1)
})

// ----------------------------------------------------------------------------------------- off mode

test('off: a thin brief passes with no log', { options: { mode: 'off' } }, async ($, on) => {
  mock.env(on, {})
  const seen = engine(on)
  const log = watchLog(on)
  await dispatch($, { prompt: THIN })
  await flush()
  expect(seen.length).toBe(1)
  expect(log).toEqual([])
})

// ------------------------------------------------------------------------------------- read-only types

test('an Explore brief without a done-check is not flagged for done-check', async ($, on) => {
  mock.env(on, {})
  engine(on)
  const log = watchLog(on)
  await dispatch($, { prompt: PARTIAL, subagent_type: 'Explore', description: 'slug survey' })
  await flush()
  expect(log.length).toBe(1)
  expect(log[0]).toMatch('return shape')
  expect(log[0]).not.toMatch('done-check')
  // the same brief to a builder is flagged for it
  await dispatch($, { prompt: PARTIAL, subagent_type: 'general-purpose', description: 'slug build' })
  await flush()
  expect(log.length).toBe(2)
  expect(log[1]).toMatch('done-check')
})

test('an Explore brief that names files and what to send back is complete', async ($, on) => {
  mock.env(on, {})
  engine(on)
  const log = watchLog(on)
  await dispatch($, { prompt: PARTIAL + ' Reply with the file:line of each call site.', subagent_type: 'Explore' })
  await dispatch($, { prompt: PARTIAL + ' Reply with the file:line of each call site.', subagent_type: 'dojo-protocol:scout' })
  await dispatch($, { prompt: PARTIAL + ' Reply with the file:line of each call site.', subagent_type: 'vendor:researcher' })
  await flush()
  expect(log).toEqual([])
})

// ----------------------------------------------------------------------------------- what counts as a field

test('files: a path, a bare file name, a backticked path or scoping words count; "and/or" and URLs do not', async ($, on) => {
  mock.env(on, {})
  engine(on)
  const log = watchLog(on)
  const pad = ' Reply with the result. Verify it with the build.'
  const named = [
    'Update src/lib/format.ts so dates are padded.',
    'Update register.ts so dates are padded.',
    'Update `hooks/dir` so dates are padded.',
    'Update ./scripts/run-it so dates are padded.',
    'Update the formatter. Files: the formatter module only.',
    'Update the formatter. Owned files are listed in the contract.',
    'Update everything under the lib directory so dates are padded.',
  ]
  for (const text of named) await dispatch($, { prompt: text + pad, description: text.slice(0, 20), subagent_type: 'general-purpose' })
  await flush()
  const filesMissing = (line: string) => line.includes('owned files')
  expect(log.filter(filesMissing)).toEqual([])
  const unnamed = [
    'Update the formatter and/or the parser so dates are padded.',
    'Update the formatter as described at https://example.com/docs/format so dates are padded.',
    'Update the formatter on Node.js so dates are padded.',
  ]
  for (const text of unnamed) await dispatch($, { prompt: text + pad, description: text.slice(0, 20), subagent_type: 'general-purpose' })
  await flush()
  expect(log.filter(filesMissing).length).toBe(3)
})

test('return: wording about what to send back counts', async ($, on) => {
  mock.env(on, {})
  engine(on)
  const log = watchLog(on)
  const base = 'Update src/lib/format.ts so dates are padded. Verify it with the build.'
  for (const tail of [' Return the diff.', ' Report what you changed.', ' Reply with a summary.', ' Output the list.', ' Hand back the path.']) {
    await dispatch($, { prompt: base + tail, description: tail, subagent_type: 'general-purpose' })
  }
  await flush()
  expect(log.filter(line => line.includes('return shape'))).toEqual([])
  await dispatch($, { prompt: base + ' Thanks very much, and good luck.', description: 'no return', subagent_type: 'general-purpose' })
  await flush()
  expect(log.filter(line => line.includes('return shape')).length).toBe(1)
})

test('a long brief that names files, done and return takes the cheap path', async ($, on) => {
  mock.env(on, {})
  engine(on)
  const log = watchLog(on)
  const long = `${COMPLETE}\n\n${'Background: the worker retries with exponential backoff. '.repeat(30)}`
  expect(long.length).toBeGreaterThan(1500)
  await dispatch($, { prompt: long })
  await flush()
  expect(log).toEqual([])
})

test('a fork is never linted', async ($, on) => {
  mock.env(on, {})
  const seen = engine(on)
  const log = watchLog(on)
  await dispatch($, { prompt: 'carry on', subagent_type: 'fork' })
  await flush()
  expect(seen.length).toBe(1)
  expect(log).toEqual([])
})

// ------------------------------------------------------------------------------------------ commands

function stubFill(on: any, reply: { isFilled: boolean }): Array<{ text: string; mode: string }> {
  const fills: Array<{ text: string; mode: string }> = []
  on('prompt.fill', (_$: any, e: any) => {
    fills.push({ text: e.text, mode: e.mode })
    return reply as any
  })
  return fills
}

const run = ($: any, args = '') => $.command.run({ command: 'dojo-brief', args }) as Promise<{ text?: string }>

test('session.start registers /dojo-brief as an immediate command that takes [stats]', async ($, on) => {
  mock.env(on, {})
  const specs: any[] = []
  on('command.register', (_$: any, e: any) => {
    specs.push(e)
    return { value: { command: e.name } } as any
  })
  on('session.start', (_$: any, e: any) => ({ cwd: e.cwd }) as any)
  await $.session.start({ cwd: '/work', surface: 'terminal', isInteractive: true } as any)
  expect(specs.length).toBe(1)
  expect(specs[0].name).toBe('dojo-brief')
  expect(specs[0].argumentHint).toBe('[stats]')
  expect(specs[0].immediate).toBe(true)
})

test('/dojo-brief fills the prompt with the six-field template', async ($, on) => {
  mock.env(on, {})
  const fills = stubFill(on, { isFilled: true })
  const r = await run($)
  expect(r.text).toBe('Template inserted in the prompt.')
  expect(fills.length).toBe(1)
  expect(fills[0]?.mode).toBe('insert')
  const text = fills[0]?.text ?? ''
  for (const heading of ['## Goal', '## Owned files', '## Done-check', '## Facts', '## Return shape', '## Rules you carry']) {
    expect(text).toMatch(heading)
  }
  // every field has its one-line hint, and the headings come in the delegate skill's order
  expect(text).toMatch('<One outcome')
  expect(text).toMatch('<path:line>')
  expect(text).toMatch('No git add, commit or push')
  expect(text.indexOf('## Goal')).toBeLessThan(text.indexOf('## Owned files'))
  expect(text.indexOf('## Owned files')).toBeLessThan(text.indexOf('## Done-check'))
  expect(text.indexOf('## Done-check')).toBeLessThan(text.indexOf('## Facts'))
  expect(text.indexOf('## Facts')).toBeLessThan(text.indexOf('## Return shape'))
  expect(text.indexOf('## Return shape')).toBeLessThan(text.indexOf('## Rules you carry'))
})

test('/dojo-brief answers with the template when the prompt box would not take it', async ($, on) => {
  mock.env(on, {})
  stubFill(on, { isFilled: false })
  const r = await run($)
  expect(r.text).toMatch('## Goal')
  expect(r.text).toMatch('## Rules you carry')
  expect(r.text).not.toMatch('template inserted')
})

test('/dojo-brief stats before any dispatch says nothing was linted', async ($, on) => {
  mock.env(on, {})
  const r = await run($, 'stats')
  expect(r.text).toMatch(/^No subagent briefs linted yet/)
})

test('/dojo-brief stats reports the session tally', async ($, on) => {
  mock.env(on, {})
  engine(on)
  watchLog(on)
  await dispatch($)
  await dispatch($, { prompt: THIN, description: 'thin one' })
  await dispatch($, { prompt: PARTIAL, description: 'partial one' })
  await dispatch($, { prompt: 'carry on', subagent_type: 'fork', description: 'fork one' })
  const r = await run($, ' Stats ')
  const text = r.text ?? ''
  expect(text).toMatch('3 briefs linted, 1 complete, 2 missing a field (mode notice).')
  expect(text).toMatch('Missing by field:')
  expect(text).toMatch('detail (under 200 chars) 1')
  expect(text).toMatch('owned files 1')
  expect(text).toMatch('done-check 2')
  expect(text).toMatch('return shape 2')
  expect(text).toMatch('Forks skipped: 1.')
})

test('/dojo-brief stats counts the send-backs', { options: { mode: 'sendback' } }, async ($, on) => {
  mock.env(on, {})
  engine(on)
  watchLog(on)
  await dispatch($, { prompt: THIN, description: 'job' })
  await dispatch($, { prompt: THIN, description: 'job' })
  const r = await run($, 'stats')
  expect(r.text).toMatch('2 briefs linted, 0 complete, 2 missing a field (mode sendback).')
  expect(r.text).toMatch('Sent back once: 1.')
})

test('/dojo-brief with an unknown argument says how to use it', async ($, on) => {
  mock.env(on, {})
  const fills = stubFill(on, { isFilled: true })
  const r = await run($, 'bogus')
  expect(r.text).toMatch(/^Unknown argument/)
  expect(r.text).toMatch('/dojo-brief')
  expect(fills.length).toBe(0)
})

// ----------------------------------------------------------------------------------- kill switches

const OFF_ENVS: Array<Record<string, string>> = [{ DOJO_BRIEF_OFF: '1' }, { DOJO_OFF: '1' }, { DOJO_BRIEF_OFF: 'true' }, { DOJO_OFF: 'yes' }]
for (const env of OFF_ENVS) {
  test(`env ${JSON.stringify(env)} passes everything silently`, { options: { mode: 'sendback' } }, async ($, on) => {
    mock.env(on, env)
    const seen = engine(on)
    const log = watchLog(on)
    const first: any = await dispatch($, { prompt: THIN, description: 'job' })
    const second: any = await dispatch($, { prompt: THIN, description: 'other job' })
    await flush()
    expect(first.deny).toBe(undefined)
    expect(second.deny).toBe(undefined)
    expect(seen.length).toBe(2)
    expect(log).toEqual([])
  })
}

test('env: the command stands down too', async ($, on) => {
  mock.env(on, { DOJO_BRIEF_OFF: '1' })
  const fills = stubFill(on, { isFilled: true })
  const r = await run($)
  expect(r.text).toMatch(/^Off \(DOJO_OFF/)
  expect(fills.length).toBe(0)
})

test('env negative control: DOJO_BRIEF_OFF=0 still lints', async ($, on) => {
  mock.env(on, { DOJO_BRIEF_OFF: '0', DOJO_OFF: '' })
  engine(on)
  const log = watchLog(on)
  await dispatch($, { prompt: THIN, description: 'job' })
  await flush()
  expect(log.length).toBe(1)
})

// -------------------------------------------------------------------------------------- the rest of the call

test('the call travels on untouched: the lint never rewrites model, prompt or description', async ($, on) => {
  mock.env(on, {})
  const seen: any[] = []
  on('tool.call', (_$: any, e: any) => {
    seen.push(e)
    return { result: { agentId: 'a1', content: [] } as any, text: 'ok' } as any
  })
  watchLog(on)
  await dispatch($, { prompt: THIN, description: 'job', model: 'haiku', name: 'worker', run_in_background: false })
  expect(seen.length).toBe(1)
  expect(seen[0].prompt).toBe(THIN)
  expect(seen[0].description).toBe('job')
  expect(seen[0].model).toBe('haiku')
  expect(seen[0].name).toBe('worker')
})

test('lint_briefs false switches the lint off; /dojo-brief still inserts the template', { options: { lint_briefs: false, mode: 'sendback' } }, async ($, on) => {
  mock.env(on, {})
  const seen = engine(on)
  const log = watchLog(on)
  const fills = stubFill(on, { isFilled: true })
  const r = await dispatch($, { prompt: THIN, description: 'Fix Retry Bug' })
  await flush()
  expect((r as any).deny).toBe(undefined)
  expect(seen.length).toBe(1)
  expect(log).toEqual([])
  const answer = await run($)
  expect(answer.text).toBe('Template inserted in the prompt.')
  expect(fills.length).toBe(1)
})

test('the classic fallback name /dojo-brief:brief is answered by the mod too', async ($, on) => {
  mock.env(on, {})
  const fills = stubFill(on, { isFilled: true })
  const answer = (await $.command.run({ command: 'dojo-brief:brief', args: '' } as any)) as { text?: string }
  expect(answer.text).toBe('Template inserted in the prompt.')
  expect(fills.length).toBe(1)
})
