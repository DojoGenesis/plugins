import { expect, test } from 'claude-code/testing'
import { PROPS, bandText, complete, localNoon, runBand, step, usageOf, world } from './helpers'

const M = 1000000
// sonnet-5-5 output is $10 per million tokens, so N x 100k output tokens cost N dollars and add no context.
const dollars = (n: number) => usageOf('claude-sonnet-5-5', { output: n * 100000 })

test('budget toasts fire once at 70 and once at 90 percent, never again', { options: { budget_usd: 10 } }, async ($, on) => {
  const w = world(on)
  await step($, w, dollars(6))
  await complete($)
  expect(w.toasts).toEqual([])
  await step($, w, dollars(1)) // 7.00 in all: exactly 70 percent counts
  await complete($)
  expect(w.toasts).toHaveLength(1)
  expect(w.toasts[0]).toMatch(/^dojo-meter: session estimate \$7\.00 is 70% of your \$10 budget/)
  expect(w.toasts[0]).toContain('budget_usd')
  await step($, w, dollars(1))
  await complete($) // 8.00: nothing new
  await step($, w, dollars(1))
  await complete($) // 9.00: the 90 percent mark
  expect(w.toasts).toHaveLength(2)
  expect(w.toasts[1]).toContain('$9.00 is 90%')
  await step($, w, dollars(5))
  await complete($) // 14.00: both marks already shown
  await complete($)
  expect(w.toasts).toHaveLength(2)
})

test('a budget toast says partial when some tokens had no price', { options: { budget_usd: 10 } }, async ($, on) => {
  const w = world(on)
  await step($, w, usageOf('claude-future-9', { input: 1234 }))
  await step($, w, dollars(7))
  await complete($)
  expect(w.toasts).toHaveLength(1)
  expect(w.toasts[0]).toContain('session estimate $7.00 (partial: some models are unpriced) is 70%')
})

test('a fully priced session budget toast carries no partial label', { options: { budget_usd: 10 } }, async ($, on) => {
  const w = world(on)
  await step($, w, dollars(7))
  await complete($)
  expect(w.toasts).toHaveLength(1)
  expect(w.toasts[0]).not.toContain('partial')
})

test('a single jump past both marks shows only the 90 percent toast', { options: { budget_usd: 10 } }, async ($, on) => {
  const w = world(on)
  await step($, w, dollars(9.5))
  await complete($)
  expect(w.toasts).toHaveLength(1)
  expect(w.toasts[0]).toContain('$9.50 is 95%')
  await step($, w, dollars(1))
  await complete($)
  expect(w.toasts).toHaveLength(1)
})

test('budget_usd 0 never toasts', async ($, on) => {
  const w = world(on)
  await step($, w, dollars(100))
  await complete($)
  expect(w.toasts).toEqual([])
})

test('a subagent turn.complete neither flushes nor toasts', { options: { budget_usd: 10 } }, async ($, on) => {
  const w = world(on)
  await step($, w, dollars(19), 'sub-1')
  await complete($, 'sub-1')
  expect(w.toasts).toEqual([])
  expect(w.storeSets).toEqual([])
  await complete($) // the main turn ends: now the session's spend, subagent included, is counted
  expect(w.toasts).toHaveLength(1)
  expect(w.storeSets).toHaveLength(1)
})

test('the context toast fires once per crossing and re-arms below 70 percent of the threshold', async ($, on) => {
  const w = world(on)
  const at = (tokens: number) => step($, w, usageOf('claude-haiku-4-5', { input: tokens }))
  await at(401000)
  await complete($)
  expect(w.toasts).toHaveLength(1)
  expect(w.toasts[0]).toContain('/compact')
  expect(w.toasts[0]).toContain('context_warn_tokens')
  expect(w.toasts[0]?.startsWith('dojo-meter: ')).toBe(true)
  await at(399000)
  await complete($)
  await at(401000)
  await complete($)
  expect(w.toasts).toHaveLength(1) // 399k never dropped below 280k, so it stayed disarmed
  await at(100000) // a compaction
  await complete($)
  await at(401000)
  await complete($)
  expect(w.toasts).toHaveLength(2)
})

test('the context size counts input, cache read and cache creation of the last main request', async ($, on) => {
  const w = world(on)
  await step($, w, usageOf('claude-haiku-4-5', { input: 1000, read: 200000, write: 200000 }))
  await complete($)
  expect(w.toasts).toHaveLength(1)
  // A subagent's large request is not the main context.
  await step($, w, usageOf('claude-haiku-4-5', { input: 100 }))
  await step($, w, usageOf('claude-haiku-4-5', { input: 900000 }), 'sub-1')
  await complete($)
  expect(w.toasts).toHaveLength(1)
})

test('context_warn_tokens 0 never toasts, and an option sets the threshold', { options: { context_warn_tokens: 0 } }, async ($, on) => {
  const w = world(on)
  await step($, w, usageOf('claude-haiku-4-5', { input: 900000 }))
  await complete($)
  expect(w.toasts).toEqual([])
})

test('a lower context_warn_tokens fires sooner', { options: { context_warn_tokens: 50000 } }, async ($, on) => {
  const w = world(on)
  await step($, w, usageOf('claude-haiku-4-5', { input: 60000 }))
  await complete($)
  expect(w.toasts).toHaveLength(1)
  expect(w.toasts[0]).toContain('context is 60k tokens')
})

for (const [name, env] of [['DOJO_OFF', { DOJO_OFF: '1' }], ['DOJO_METER_OFF', { DOJO_METER_OFF: '1' }]] as const) {
  test(`${name}=1 turns every hook into a pass-through`, { options: { budget_usd: 1 } }, async ($, on) => {
    const w = world(on, { env })
    const chunks = await step($, w, usageOf('claude-sonnet-5-5', { output: 10 * M }))
    expect(chunks[0].stopReason).toBe('end_turn')
    // Straight after the step, before any other hook has read the switches: nothing was recorded for the band.
    expect(await bandText($)).toBe('')
    const done = await complete($)
    expect(done.text).toBe('done')
    expect(w.toasts).toEqual([])
    expect(w.storeSets).toEqual([])
    expect(await bandText($)).toBe('')
    const answer = await runBand($, 'toggle')
    expect(answer.text).toContain(`the band is off (${name}=1)`)
  })
}

test('DOJO_OFF=0 and an empty DOJO_METER_OFF leave the meter fully active', { options: { budget_usd: 10 } }, async ($, on) => {
  const w = world(on, { env: { DOJO_OFF: '0', DOJO_METER_OFF: '' } })
  await step($, w, dollars(8))
  await complete($)
  expect(w.toasts).toHaveLength(1)
  expect(w.storeSets).toHaveLength(1)
  expect(await bandText($)).toContain('sonnet $8.00')
})

test('daily totals are written under day:<local date> and never counted twice', async ($, on) => {
  const w = world(on, { now: localNoon(2026, 10, 2) })
  await step($, w, dollars(2))
  await complete($)
  expect(w.storeSets).toHaveLength(1)
  expect(w.storeSets[0]?.key).toBe('day:2026-10-02')
  expect((w.storeSets[0]?.value as any).microUsd).toBe(2000000)
  await complete($) // nothing new since the last flush
  expect(w.storeSets).toHaveLength(1)
  await step($, w, dollars(1))
  await complete($)
  expect(w.storeSets).toHaveLength(2)
  expect((w.storeSets[1]?.value as any).microUsd).toBe(3000000) // 2 + the 1 that is new, not 2 + 3
  expect(await bandText($)).toContain('today $3.00')
})

test('an unpriced-only session never shows today as $0.00', async ($, on) => {
  const w = world(on)
  await step($, w, usageOf('claude-future-9', { input: 1234 }))
  await complete($)
  const text = await bandText($, 'terminal', { ...PROPS, bodyColumns: 200 })
  expect(text).toContain('today unpriced')
  expect(text).not.toContain('today $0.00')
  await step($, w, dollars(1))
  await complete($)
  expect(await bandText($, 'terminal', { ...PROPS, bodyColumns: 200 })).toContain('today $1.00 (partial)')
})

test('another session adds to the same day, and a new local day starts a new key', async ($, on) => {
  const w = world(on, { now: localNoon(2026, 10, 2), entries: { 'day:2026-10-02': { microUsd: 5000000, unpricedTokens: 0 } } })
  await step($, w, dollars(2))
  await complete($)
  expect((w.kv.get('day:2026-10-02') as any).microUsd).toBe(7000000)
  await w.clock.advance(13 * 3600 * 1000) // past local midnight
  await step($, w, dollars(1))
  await complete($)
  expect((w.kv.get('day:2026-10-03') as any).microUsd).toBe(1000000)
  expect((w.kv.get('day:2026-10-02') as any).microUsd).toBe(7000000)
})

test('daily keys older than 60 days are pruned, other keys are left alone', async ($, on) => {
  const w = world(on, {
    now: localNoon(2026, 10, 2),
    entries: {
      'day:2026-07-01': { microUsd: 1, unpricedTokens: 0 },
      'day:2026-08-02': { microUsd: 1, unpricedTokens: 0 },
      'day:2026-08-04': { microUsd: 1, unpricedTokens: 0 },
      'day:2026-09-20': { microUsd: 1, unpricedTokens: 0 },
      'other': 'keep',
    },
  })
  await step($, w, dollars(1))
  await complete($)
  expect(w.deleted.sort()).toEqual(['day:2026-07-01', 'day:2026-08-02'])
  expect(w.kv.has('other')).toBe(true)
  expect(w.kv.has('day:2026-08-04')).toBe(true)
})

test('unpriced tokens are tallied in the daily total, not priced', async ($, on) => {
  const w = world(on)
  await step($, w, usageOf('claude-future-9', { input: 1234 }))
  await complete($)
  expect(w.storeSets).toHaveLength(1)
  expect((w.storeSets[0]?.value as any).microUsd).toBe(0)
  expect((w.storeSets[0]?.value as any).unpricedTokens).toBe(1234)
})

test('a failing store write or usage read leaves the turn result alone', { options: { budget_usd: 10 } }, async ($, on) => {
  const w = world(on, { failStoreSet: true, failUsage: true })
  await step($, w, dollars(8))
  const done = await complete($)
  expect(done.text).toBe('done')
  expect(w.toasts).toHaveLength(1) // the budget toast does not depend on either call
  await step($, w, dollars(1))
  const again = await complete($)
  expect(again.text).toBe('done')
})

test('/dojo-meter:band answers on, off, toggle and status with one line, and rejects nonsense', async ($, on) => {
  const w = world(on)
  await step($, w, usageOf('claude-haiku-4-5', { input: M }))
  const run = async (args: string) => (await runBand($, args)).text as string
  expect(await run('status')).toBe('dojo-meter: the band is shown.')
  expect(await run('off')).toBe('dojo-meter: the band is now hidden.')
  expect(await bandText($)).toBe('')
  expect(await run('status')).toBe('dojo-meter: the band is hidden.')
  expect(await run(' ON ')).toBe('dojo-meter: the band is now shown.')
  expect(await bandText($)).toContain('haiku $1.00')
  expect(await run('toggle')).toBe('dojo-meter: the band is now hidden.')
  expect(await run('')).toBe('dojo-meter: the band is now shown.')
  const bogus = await run('sideways')
  expect(bogus).toContain('unknown argument "sideways"')
  expect(bogus).toContain('on, off, toggle or status')
  expect(await run('status')).toBe('dojo-meter: the band is shown.') // bogus left it alone
})
