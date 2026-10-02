import { expect, test } from 'claude-code/testing'
import { addUsage, cacheShare, estimateUsd, fitBand, formatTokens, formatUsd, normalizeModel, priceFor, priceKeyFor, tierOf } from '../hooks/ledger'
import { PRICING } from '../hooks/pricing'
import type { Ledger } from '../hooks/ledger'
import { VECTORS } from './vectors'
import { bandText, complete, step, usageOf, world } from './helpers'

const M = 1000000

test('normalizing and pricing follow the shared vectors', async () => {
  for (const [raw, normalized] of VECTORS.normalize) expect(normalizeModel(raw)).toBe(normalized)
  for (const [raw, priced] of VECTORS.priced) {
    const normalized = normalizeModel(raw)
    expect(priceKeyFor(normalized) ?? null).toBe(priced)
    if (priced === null) expect(priceFor(normalized)).toBeUndefined()
    else expect(priceFor(normalized)).toEqual(PRICING.models[priced])
  }
  for (const [raw, tier] of VECTORS.tiers) expect(tierOf(normalizeModel(raw))).toBe(tier)
  expect(priceFor('constructor')).toBeUndefined()
  expect(priceFor('constructor-x')).toBeUndefined()
  expect(priceKeyFor('__proto__')).toBeUndefined()
  expect(normalizeModel(undefined)).toBe('')
  expect(normalizeModel('x'.repeat(500))).toBe('')
})

test('arithmetic is exact on round numbers, cache writes at the 5-minute rate', async () => {
  const ledger: Ledger = new Map()
  addUsage(ledger, 'main', usageOf('claude-sonnet-5-5', { input: M, output: M, read: M, write: M }))
  const estimate = estimateUsd(ledger)
  // sonnet-5-5: input 2 + output 10 + read 0.2 + write 2 x 1.25 = 14.70
  expect(formatUsd(estimate.total)).toBe('$14.70')
  expect(estimate.byTier.sonnet).toBe(estimate.total)
  expect(estimate.unpricedTokens).toBe(0)
  expect(Math.abs((cacheShare(ledger) ?? 0) - 1 / 3) < 1e-9).toBe(true)
  expect(formatUsd(0)).toBe('$0.00')
  expect(formatUsd(1)).toBe('<$0.01')
  expect(formatTokens(184000)).toBe('184k')
  expect(formatTokens(1250000)).toBe('1.3M')
  expect(cacheShare(new Map())).toBeUndefined()
})

test('only finite non-negative numbers count', async () => {
  const ledger: Ledger = new Map()
  const bad = {
    model: 'claude-haiku-4-5',
    input_tokens: Number.NaN,
    output_tokens: -5,
    cache_read_input_tokens: '100',
    cache_creation_input_tokens: undefined,
  }
  expect(addUsage(ledger, 'main', bad)).toBe(0)
  expect(estimateUsd(ledger).total).toBe(0)
  expect(addUsage(ledger, 'main', null)).toBeUndefined()
  expect(addUsage(ledger, 'main', 'text')).toBeUndefined()
})

test('the band fits the width it is given', async () => {
  const band = { tiers: 'opus $4.20 · sonnet $1.10', total: '$5.30', ctx: '184k (46%)', cache: '92%', today: '$12.40' }
  for (const columns of [200, 90, 60, 40, 30, 20, 8]) {
    expect(fitBand(band, columns).length).toBeLessThanOrEqual(columns)
  }
  expect(fitBand(band, 200)).toContain('today $12.40')
  expect(fitBand(band, 200)).toContain('opus $4.20')
  expect(fitBand(band, 31)).toContain('$5.30')
})

test('main, subagent and workflow-agent steps land in separate rows and all count', async ($, on) => {
  const w = world(on)
  await step($, w, usageOf('claude-opus-5-5', { write: M }))                 // main loop, 4 x 1.25 = $5.00
  await step($, w, usageOf('claude-sonnet-5-5', { input: M }), 'sub-1')      // a subagent, $2.00
  await step($, w, usageOf('claude-haiku-4-5', { output: M }), 'wf-agent-7') // a workflow agent, $5.00
  await step($, w, usageOf('claude-haiku-4-5', { output: M }), 'wf-agent-8') // another, $5.00
  const text = await bandText($)
  expect(text).toContain('opus $5.00')
  expect(text).toContain('sonnet $2.00')
  expect(text).toContain('haiku $10.00')
  expect(text).toContain('≈ $17.00')
  expect(text).not.toContain('unpriced')
})

test('one model id in two spellings is one row, and the context is the last main request', async ($, on) => {
  const w = world(on)
  await step($, w, usageOf('claude-sonnet-5-5[1m]', { input: 10, read: 1000, write: 90 }))
  await step($, w, usageOf('claude-sonnet-5-5', { input: 5, read: 2000, write: 0 }), 'sub-1')
  expect(await bandText($)).toContain('ctx 1.1k')
  await complete($) // reads the window (1M here), so the band can show a percent
  const text = await bandText($)
  expect(text).toContain('ctx 1.1k (0%)') // the main request only: 10 + 1000 + 90
})

test('an unknown model is unpriced, never zero', async ($, on) => {
  const w = world(on)
  await step($, w, usageOf('claude-future-9', { input: M, output: M }))
  let text = await bandText($)
  expect(text).toContain('≈ unpriced')
  expect(text).not.toContain('$0.00')
  await step($, w, usageOf('claude-haiku-4-5', { input: M }))
  text = await bandText($)
  expect(text).toContain('haiku $1.00')
  expect(text).toContain('$1.00 (partial)')
  expect(text).not.toContain('+unpriced')
})

test('a known id with one known decoration is priced as that id', async ($, on) => {
  const w = world(on)
  await step($, w, usageOf('claude-opus-4-8-fast', { input: M }))        // opus-4-8 plus -fast: 5.00
  await step($, w, usageOf('claude-opus-5-5-fast-20260101', { input: M })) // opus-5-5 plus -fast and a date: 4.00
  await step($, w, usageOf('us.anthropic.claude-opus-5-v1:0', { input: M })) // a provider prefix and tag: 5.00
  const text = await bandText($)
  expect(text).toContain('opus $14.00')
  expect(text).not.toContain('unpriced')
  expect(text).not.toContain('partial')
})

test('a newer version number or an unknown suffix is never priced as a nearby id', async ($, on) => {
  const w = world(on)
  await step($, w, usageOf('claude-opus-5-6', { input: M }))
  await step($, w, usageOf('claude-opus-5-50', { input: M }))
  await step($, w, usageOf('claude-opus-5-5-preview', { input: M }))
  await step($, w, usageOf('claude-fable-5-2', { input: M }))
  const text = await bandText($)
  expect(text).toContain('≈ unpriced')
  expect(text).not.toContain('$')
  await step($, w, usageOf('claude-opus-5-5', { input: M }))
  const mixed = await bandText($)
  expect(mixed).toContain('opus $4.00')
  expect(mixed).toContain('≈ $4.00 (partial)')
})

test('an unpriced model with zero counts still makes the figure unpriced, not $0.00', async ($, on) => {
  const w = world(on)
  await step($, w, usageOf('claude-opus-5-6', {}))
  expect(await bandText($)).toContain('≈ unpriced')
  // A priced request with no tokens prices nothing: the figure stays unpriced and shows no empty tier.
  await step($, w, usageOf('claude-opus-5-5', {}))
  const text = await bandText($)
  expect(text).toContain('≈ unpriced')
  expect(text).not.toContain('$0.00')
  expect(text).not.toContain('opus $')
})

test('the estimate marks a figure unpriced on tokens, not on rows', async () => {
  const empty: Ledger = new Map()
  addUsage(empty, 'main', usageOf('claude-opus-5-6', {}))
  expect(estimateUsd(empty).hasPriced).toBe(false)
  const zeroPricedPlusUnpriced: Ledger = new Map()
  addUsage(zeroPricedPlusUnpriced, 'main', usageOf('claude-opus-5-5', {}))
  addUsage(zeroPricedPlusUnpriced, 'main', usageOf('claude-opus-5-6', { input: M }))
  expect(estimateUsd(zeroPricedPlusUnpriced).hasPriced).toBe(false)
  const onlyZeroPriced: Ledger = new Map()
  addUsage(onlyZeroPriced, 'main', usageOf('claude-opus-5-5', {}))
  expect(estimateUsd(onlyZeroPriced).hasPriced).toBe(true) // a true zero: nothing was used, nothing is unpriced
  const mixed: Ledger = new Map()
  addUsage(mixed, 'main', usageOf('claude-opus-5-5', { input: M }))
  addUsage(mixed, 'main', usageOf('claude-opus-5-6', { input: M }))
  const estimate = estimateUsd(mixed)
  expect(estimate.hasPriced).toBe(true)
  expect(estimate.unpricedTokens).toBe(M)
})

test('a family no known id covers stays unpriced', async ($, on) => {
  const w = world(on)
  await step($, w, usageOf('claude-opus-4-9', { input: M }))
  await step($, w, usageOf('claude-opus-50', { input: M }))
  const text = await bandText($)
  expect(text).toContain('≈ unpriced')
  expect(text).not.toContain('$0.00')
})

test('a step with no usage leaves the step alone', async ($, on) => {
  const w = world(on)
  const none = await step($, w, null)
  expect(none).toHaveLength(1)
  expect(none[0].stopReason).toBe('end_turn')
  expect(none[0].usage).toBeNull()
  expect(await bandText($)).toBe('')
})

test('an error from the step beneath is not swallowed', async ($, on) => {
  world(on, { stepError: 'engine down' })
  let message = ''
  try {
    const stream = $.turn.step({ turnId: 't1', index: 0, model: 'claude-haiku-4-5', messageCount: 1 })
    for await (const _chunk of stream) {
      // drain
    }
    await stream.result
  } catch (err: any) {
    message = String(err?.message ?? err)
  }
  expect(message).not.toBe('')
})

test('a completed turn leaves the ledger and the answer alone', async ($, on) => {
  const w = world(on)
  await step($, w, usageOf('claude-haiku-4-5', { input: M }))
  const done = await complete($)
  expect(done.text).toBe('done')
})
