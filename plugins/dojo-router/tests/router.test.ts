import { expect, mock, test } from 'claude-code/testing'

// The kit stands the engine beneath the plugin: hooks the test registers with `on` sit below it. Note what the
// kit does NOT do: it does not run the plugin's classic command hooks (hooks.json). The classic hook is tested
// by the unittest suite; here the test's own tool.call hook plays the layer beneath the mod, where classic
// PreToolUse sits in a session, and shows what that layer would receive.

// A model value the router must never touch: it is named, so it is left exactly as the caller wrote it.
const NAMED_OTHER = 'opus[1m]'

type Seen = { model?: string; subagent_type?: string; description?: string; prompt?: string }

function beneath(on: any): Seen[] {
  const seen: Seen[] = []
  on('tool.call', (_$: any, e: any) => {
    seen.push({ model: e.model, subagent_type: e.subagent_type, description: e.description, prompt: e.prompt })
    return { result: { agentId: `a${seen.length}`, content: [] } as any, text: 'ok' } as any
  })
  return seen
}

function watchUi(on: any): { status: Array<string | undefined>; toast: string[] } {
  const rows = { status: [] as Array<string | undefined>, toast: [] as string[] }
  on('ui.status', (_$: any, e: any) => { rows.status.push(e.text as string | undefined); return {} })
  on('ui.toast', (_$: any, e: any) => { rows.toast.push(String(e.text)); return {} })
  return rows
}

const call = ($: any, extra: Record<string, unknown> = {}) =>
  $.tool.call({ tool: 'Agent', description: 'look around', prompt: 'find the thing', ...extra } as any)

// ---------------------------------------------------------------------------------------------- tool.call

test('tool.call: unpinned dispatches are filled in by role, and the layer beneath receives the model', async ($, on) => {
  mock.env(on, {})
  const seen = beneath(on)
  const ui = watchUi(on)
  await call($)
  await call($, { subagent_type: 'general-purpose' })
  await call($, { subagent_type: 'Explore' })
  await call($, { subagent_type: 'Plan' })
  expect(seen.map(s => s.model)).toEqual(['sonnet', 'sonnet', 'haiku', 'sonnet'])
  // the rest of the call travels untouched, which is what the classic hook beneath will see
  expect(seen[0]?.description).toBe('look around')
  expect(seen[0]?.prompt).toBe('find the thing')
  expect(seen[2]?.subagent_type).toBe('Explore')
  expect(ui.status.length).toBe(4)
  expect(ui.status[0]).toMatch('dojo-router')
  expect(ui.status[0]).toMatch('sonnet')
  expect(ui.status[2]).toMatch('Explore')
  expect(ui.status[2]).toMatch('haiku')
})

test('tool.call: default_tier and explore_tier options are honoured', { options: { default_tier: 'haiku', explore_tier: 'sonnet' } }, async ($, on) => {
  mock.env(on, {})
  const seen = beneath(on)
  await call($)
  await call($, { subagent_type: 'Explore' })
  expect(seen.map(s => s.model)).toEqual(['haiku', 'sonnet'])
})

test('tool.call: a model the caller named, a plugin agent, a fork and custom agents are left alone', async ($, on) => {
  mock.env(on, {})
  const seen = beneath(on)
  const ui = watchUi(on)
  await call($, { model: 'opus' })
  await call($, { model: 'haiku', subagent_type: 'Explore' })
  await call($, { model: NAMED_OTHER })
  await call($, { subagent_type: 'some-plugin:reviewer' })
  await call($, { subagent_type: 'fork' })
  await call($, { subagent_type: 'statusline-setup' })
  await call($, { subagent_type: 'my-custom-agent' })
  expect(seen.map(s => s.model)).toEqual(['opus', 'haiku', NAMED_OTHER, undefined, undefined, undefined, undefined])
  expect(ui.status).toEqual([])
})

test('tool.call: auto_route false leaves the call alone', { options: { auto_route: false } }, async ($, on) => {
  mock.env(on, {})
  const seen = beneath(on)
  const ui = watchUi(on)
  await call($)
  await call($, { subagent_type: 'Explore' })
  expect(seen.map(s => s.model)).toEqual([undefined, undefined])
  expect(ui.status).toEqual([])
})

for (const env of [
  { DOJO_OFF: '1' },
  { DOJO_ROUTER_OFF: '1' },
  { CLAUDE_CODE_SUBAGENT_MODEL: 'haiku' },
  { CLAUDE_CODE_SUBAGENT_MODEL_FORCE: 'opus' },
]) {
  test(`env ${Object.keys(env)[0]} leaves tool.call and agent.spawn untouched`, async ($, on) => {
    mock.env(on, env)
    const seen = beneath(on)
    const spawned: Array<string | undefined> = []
    on('agent.spawn', (_$: any, e: any) => { spawned.push(e.model); return { model: e.model ?? 'inherit', agentId: 'a' } })
    await call($)
    await $.agent.spawn({ prompt: 'p' } as any)
    expect(seen[0]?.model).toBe(undefined)
    expect(spawned[0]).toBe(undefined)
  })
}

test('env negative control: DOJO_OFF=0 still routes', async ($, on) => {
  mock.env(on, { DOJO_OFF: '0', DOJO_ROUTER_OFF: '' })
  const seen = beneath(on)
  await call($)
  expect(seen[0]?.model).toBe('sonnet')
})

// ------------------------------------------------------------------------------------------- agent.spawn

function spawnBeneath(on: any, resolved = 'inherit'): Array<{ model?: string }> {
  const seen: Array<{ model?: string }> = []
  on('agent.spawn', (_$: any, e: any) => {
    seen.push({ model: e.model })
    return { model: e.model ?? resolved, agentId: `s${seen.length}` }
  })
  return seen
}

test('agent.spawn backstop: built-in types are routed by role', async ($, on) => {
  mock.env(on, {})
  const seen = spawnBeneath(on)
  await $.agent.spawn({ prompt: 'bare' } as any)
  await $.agent.spawn({ prompt: 'gp', subagentType: 'general-purpose' } as any)
  await $.agent.spawn({ prompt: 'explore', subagentType: 'Explore' } as any)
  await $.agent.spawn({ prompt: 'plan', subagentType: 'Plan' } as any)
  expect(seen.map(s => s.model)).toEqual(['sonnet', 'sonnet', 'haiku', 'sonnet'])
})

test('agent.spawn backstop: forks, plugin agents, custom agents, named models and other providers are untouched', async ($, on) => {
  mock.env(on, {})
  const seen = spawnBeneath(on)
  const ui = watchUi(on)
  await $.agent.spawn({ prompt: 'p', subagentType: 'Explore', fork: true } as any)
  await $.agent.spawn({ prompt: 'p', subagentType: 'a:b' } as any)
  await $.agent.spawn({ prompt: 'p', subagentType: 'statusline-setup' } as any)
  await $.agent.spawn({ prompt: 'p', subagentType: 'my-custom-agent' } as any)
  await $.agent.spawn({ prompt: 'p', model: 'opus' } as any)
  await $.agent.spawn({ prompt: 'p', subagentType: 'general-purpose', provider: { plugin: 'other', tier: 'user' } } as any)
  expect(seen.map(s => s.model)).toEqual([undefined, undefined, undefined, undefined, 'opus', undefined])
  expect(ui.status).toEqual([])
})

test('agent.spawn backstop: an engine-provided spawn is routed', async ($, on) => {
  mock.env(on, {})
  const seen = spawnBeneath(on)
  await $.agent.spawn({ prompt: 'p', subagentType: 'general-purpose', provider: { plugin: 'engine', tier: 'core' } } as any)
  expect(seen[0]?.model).toBe('sonnet')
})

test('agent.spawn backstop: a model already filled in by tool.call is not changed again', async ($, on) => {
  mock.env(on, {})
  const seen = spawnBeneath(on)
  await $.agent.spawn({ prompt: 'p', subagentType: 'Explore', model: 'sonnet' } as any)
  expect(seen[0]?.model).toBe('sonnet')
})

test('agent.spawn backstop: auto_route false leaves spawns alone', { options: { auto_route: false } }, async ($, on) => {
  mock.env(on, {})
  const seen = spawnBeneath(on)
  await $.agent.spawn({ prompt: 'p' } as any)
  expect(seen[0]?.model).toBe(undefined)
})

// ------------------------------------------------------------------------- overridden built-in names

// The engine's own answer to an offer, standing beneath the plugin.
function answerOffers(on: any): void {
  on('agent.offer', () => ({ isOffered: true }))
}

const offer = ($: any, agent: string, source: string) =>
  $.agent.offer({ agent, description: 'offered', source, provider: { plugin: 'engine', tier: 'core' } } as any)

test('tool.call: a built-in name that a user agent has taken over is left alone, the others are still routed', async ($, on) => {
  mock.env(on, {})
  answerOffers(on)
  const seen = beneath(on)
  const ui = watchUi(on)
  await offer($, 'Explore', 'userSettings')
  await call($, { subagent_type: 'Explore' })
  await call($, { subagent_type: 'Plan' })
  await call($)
  expect(seen.map(s => s.model)).toEqual([undefined, 'sonnet', 'sonnet'])
  expect(ui.status.length).toBe(2)
})

test('tool.call: an offer from the built-in source does not stop the routing', async ($, on) => {
  mock.env(on, {})
  answerOffers(on)
  const seen = beneath(on)
  await offer($, 'Explore', 'built-in')
  await offer($, 'my-custom-agent', 'userSettings')
  await call($, { subagent_type: 'Explore' })
  expect(seen[0]?.model).toBe('haiku')
})

test('agent.spawn backstop: a taken-over built-in name is left alone too', async ($, on) => {
  mock.env(on, {})
  answerOffers(on)
  const seen = spawnBeneath(on)
  await offer($, 'general-purpose', 'projectSettings')
  await $.agent.spawn({ prompt: 'p', subagentType: 'general-purpose' } as any)
  await $.agent.spawn({ prompt: 'p', subagentType: 'Plan' } as any)
  expect(seen.map(s => s.model)).toEqual([undefined, 'sonnet'])
})

// ----------------------------------------------------------------------------------------- status line

test('the status line is cleared when the next turn starts, and only once', async ($, on) => {
  mock.env(on, {})
  beneath(on)
  on('turn.start', (_$: any, e: any) => ({ turnId: e.turnId }))
  const ui = watchUi(on)
  await $.turn.start({ text: 'before anything is routed', turnId: 't0' } as any)
  expect(ui.status).toEqual([])
  await call($)
  expect(ui.status.length).toBe(1)
  await $.turn.start({ text: 'next', turnId: 't1' } as any)
  await $.turn.start({ text: 'again', turnId: 't2' } as any)
  expect(ui.status.length).toBe(2)
  expect(ui.status[1]).toBe(undefined)
})

// ------------------------------------------------------------------------------------------------ opus cap

test('opus_cap: after N opus spawns Explore keeps explore_tier and the rest go to default_tier, with one toast', { options: { auto_route: false, opus_cap: 2 } }, async ($, on) => {
  mock.env(on, {})
  const ui = watchUi(on)
  const seen = beneath(on)
  on('agent.spawn', (_$: any, e: any) => ({ model: e.model ?? 'claude-opus-x', agentId: 'a' }))
  await $.agent.spawn({ prompt: '1' } as any)
  await $.agent.spawn({ prompt: '2' } as any)
  await call($)
  await call($, { subagent_type: 'Explore' })
  await call($)
  expect(seen.map(s => s.model)).toEqual(['sonnet', 'haiku', 'sonnet'])
  expect(ui.toast.length).toBe(1)
  expect(ui.toast[0]).toMatch('dojo-router')
  expect(ui.toast[0]).toMatch('opus cap')
  expect(ui.toast[0]).toMatch('Explore now goes to haiku, the rest to sonnet')
})

test('opus_cap: before the cap nothing is routed when auto_route is off', { options: { auto_route: false, opus_cap: 3 } }, async ($, on) => {
  mock.env(on, {})
  const ui = watchUi(on)
  const seen = beneath(on)
  on('agent.spawn', (_$: any, e: any) => ({ model: e.model ?? 'claude-opus-x', agentId: 'a' }))
  await $.agent.spawn({ prompt: '1' } as any)
  await $.agent.spawn({ prompt: '2' } as any)
  await call($)
  expect(seen[0]?.model).toBe(undefined)
  expect(ui.toast).toEqual([])
})

test('opus_cap: an explicit opus after the cap is counted but never overridden', { options: { auto_route: false, opus_cap: 1 } }, async ($, on) => {
  mock.env(on, {})
  const ui = watchUi(on)
  const seen = beneath(on)
  const spawned: Array<string | undefined> = []
  on('agent.spawn', (_$: any, e: any) => { spawned.push(e.model); return { model: e.model ?? 'claude-opus-x', agentId: 'a' } })
  await $.agent.spawn({ prompt: '1' } as any)
  await call($, { model: 'opus' })
  await $.agent.spawn({ prompt: '2', model: 'opus' } as any)
  expect(seen[0]?.model).toBe('opus')
  expect(spawned[1]).toBe('opus')
  expect(ui.toast.length).toBe(1)
})

test('opus_cap: a denied spawn is not counted', { options: { auto_route: false, opus_cap: 1 } }, async ($, on) => {
  mock.env(on, {})
  const ui = watchUi(on)
  const seen = beneath(on)
  let denyNext = true
  on('agent.spawn', (_$: any, e: any) => {
    if (denyNext) { denyNext = false; return { deny: 'no' } as any }
    return { model: e.model ?? 'claude-opus-x', agentId: 'a' }
  })
  await $.agent.spawn({ prompt: '1' } as any)
  await call($)
  expect(seen[0]?.model).toBe(undefined)
  expect(ui.toast).toEqual([])
})

test('opus_cap 0 never routes or toasts', { options: { auto_route: false, opus_cap: 0 } }, async ($, on) => {
  mock.env(on, {})
  const ui = watchUi(on)
  const seen = beneath(on)
  on('agent.spawn', (_$: any, e: any) => ({ model: e.model ?? 'claude-opus-x', agentId: 'a' }))
  for (let i = 0; i < 4; i++) await $.agent.spawn({ prompt: String(i) } as any)
  await call($)
  expect(seen[0]?.model).toBe(undefined)
  expect(ui.toast).toEqual([])
})

test('opus_cap with default_tier opus falls back to sonnet after the cap', { options: { default_tier: 'opus', opus_cap: 1 } }, async ($, on) => {
  mock.env(on, {})
  const ui = watchUi(on)
  const seen = beneath(on)
  on('agent.spawn', (_$: any, e: any) => ({ model: e.model ?? 'claude-opus-x', agentId: 'a' }))
  await call($)
  expect(seen[0]?.model).toBe('opus')
  await $.agent.spawn({ prompt: '1', model: 'opus' } as any)
  await call($)
  expect(seen[1]?.model).toBe('sonnet')
  expect(ui.toast.length).toBe(1)
})

test('opus_cap bites without auto_route only when the engine resolves to opus', { options: { auto_route: true, opus_cap: 1 } }, async ($, on) => {
  mock.env(on, {})
  const seen = beneath(on)
  on('agent.spawn', (_$: any, e: any) => ({ model: e.model ?? 'claude-sonnet-x', agentId: 'a' }))
  await $.agent.spawn({ prompt: '1' } as any)
  await call($)
  expect(seen[0]?.model).toBe('sonnet')
})

// ------------------------------------------------------------------------------------------------ fail-safe

test('a failure inside the router never stops the dispatch', async ($, on) => {
  // No mock.env here, so `$.env.get` has nothing beneath it and the hook body fails. The engine reports the
  // failure, the plugin's .catch hands the call on unchanged, and the dispatch still reaches the layer beneath.
  const seen = beneath(on)
  const spawned: Array<string | undefined> = []
  on('agent.spawn', (_$: any, e: any) => { spawned.push(e.model); return { model: e.model ?? 'inherit', agentId: 'a' } })
  const r: any = await call($)
  await $.agent.spawn({ prompt: 'p' } as any)
  expect(r.deny).toBe(undefined)
  expect(seen.length).toBe(1)
  expect(seen[0]?.model).toBe(undefined)
  expect(spawned).toEqual([undefined])
})

// ------------------------------------------------------------------------------------------ odd options

// The kit reads an option the way a session does: a value outside a field's list is unset and the manifest
// default fills in. The mod also coerces for itself, so neither path can hand the schema a tier it rejects.
// (A string or negative opus_cap cannot be tried here: the engine refuses it against userConfig before the
// module loads. The mod's own coercion of such values is a second line behind that.)
test('an invalid default_tier never reaches the schema', { options: { default_tier: 'gpt', explore_tier: 'nope' } as any }, async ($, on) => {
  mock.env(on, {})
  const seen = beneath(on)
  await call($)
  await call($, { subagent_type: 'Explore' })
  expect(seen.map(s => s.model)).toEqual(['sonnet', 'haiku'])
})
