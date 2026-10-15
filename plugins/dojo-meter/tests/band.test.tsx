import { expect, test } from 'claude-code/testing'
import { PROPS, complete, runBand, step, usageOf, world } from './helpers'

const M = 1000000

for (const surface of ['terminal', 'desktop'] as const) {
  test(`the band draws the tier split, total, context and cache share on ${surface}`, async ($, on) => {
    const w = world(on)
    await step($, w, usageOf('claude-opus-5-5', { input: 1000, read: 90000, write: 9000 })) // main, 100k context
    await step($, w, usageOf('claude-haiku-4-5', { output: M }), 'sub-1')
    await complete($)
    const ui = await $.ui.mount({ plugin: 'dojo-meter', surface, component: 'AbovePrompt', props: PROPS })
    const text = (await ui.find({ type: 'Text', text: /meter/ }))?.text ?? ''
    expect(text).toContain('opus $')
    expect(text).toContain('haiku $5.00')
    expect(text).toMatch(/≈ \$\d/)
    expect(text).toContain('ctx 100k (10%)')
    expect(text).toContain('cache 90%')
    expect(await ui.find({ type: 'Button', key: 'hide' })).toBeDefined()
    await ui.unmount()
  })

  test(`the Hide button hides the band on ${surface}`, async ($, on) => {
    const w = world(on)
    await step($, w, usageOf('claude-haiku-4-5', { input: M }))
    const ui = await $.ui.mount({ plugin: 'dojo-meter', surface, component: 'AbovePrompt', props: PROPS })
    expect(await ui.find({ type: 'Text', text: /meter/ })).toBeDefined()
    await ui.press({ key: 'hide' })
    expect(await ui.find({ type: 'Text', text: /meter/ })).toBeUndefined()
    await ui.unmount()
    const again = await runBand($, 'status')
    expect(again.text).toBe('dojo-meter: the band is hidden.')
  })

  test(`nothing is drawn on ${surface} when the ledger is empty or a survey is open`, async ($, on) => {
    const w = world(on)
    let ui = await $.ui.mount({ plugin: 'dojo-meter', surface, component: 'AbovePrompt', props: PROPS })
    expect(await ui.find({ type: 'Text', text: /meter/ })).toBeUndefined()
    await ui.unmount()
    await step($, w, usageOf('claude-haiku-4-5', { input: M }))
    ui = await $.ui.mount({ plugin: 'dojo-meter', surface, component: 'AbovePrompt', props: { ...PROPS, hasSurvey: true } })
    expect(await ui.find({ type: 'Text', text: /meter/ })).toBeUndefined()
    await ui.unmount()
  })

  test(`the text fits a 40-column body on ${surface}`, async ($, on) => {
    const w = world(on)
    await step($, w, usageOf('claude-opus-5-5', { input: 1000, read: 90000, write: 9000 }))
    await step($, w, usageOf('claude-sonnet-5-5', { input: M }), 'sub-1')
    await step($, w, usageOf('claude-haiku-4-5', { output: M }), 'sub-2')
    await complete($)
    const ui = await $.ui.mount({ plugin: 'dojo-meter', surface, component: 'AbovePrompt', props: { ...PROPS, bodyColumns: 40 } })
    const text = (await ui.find({ type: 'Text', text: /meter/ }))?.text ?? ''
    expect(text.length).toBeGreaterThan(0)
    expect(text.length).toBeLessThanOrEqual(40)
    await ui.unmount()
  })

  test(`show_band=false draws nothing on ${surface}`, { options: { show_band: false } }, async ($, on) => {
    const w = world(on)
    await step($, w, usageOf('claude-haiku-4-5', { input: M }))
    const ui = await $.ui.mount({ plugin: 'dojo-meter', surface, component: 'AbovePrompt', props: PROPS })
    expect(await ui.find({ type: 'Text', text: /meter/ })).toBeUndefined()
    await ui.unmount()
    const status = await runBand($, 'status')
    expect(status.text).toContain('show_band option is off')
  })
}

// ------------------------------------------------------------------------------------- stacked with another band

// The 2026-10-14 field test: with dojo-fleet installed beside the meter, the Fleet band never drew. The meter's
// AbovePrompt handler returned its band without calling next(), so no handler after it ran. The band now goes above
// whatever is beneath. A handler registered in a test sits beneath the plugin, so the stand-in below plays
// dojo-fleet's role: it calls next() for what is beneath it and draws its chips above that.
const chipsAbove = (on: any, calls?: { n: number }) =>
  on('ui.render', { component: 'AbovePrompt' }, async (_$: any, e: any, next: any) => {
    if (calls) calls.n += 1
    const below = await next(e)
    return { type: 'Box', props: {}, children: [{ type: 'Text', props: {}, children: ['fleet ● #1 build 3s Bash'] }, below] }
  })

for (const surface of ['terminal', 'desktop'] as const) {
  test(`the band and a band beneath it both draw on ${surface}`, async ($, on) => {
    chipsAbove(on)
    const w = world(on)
    await step($, w, usageOf('claude-haiku-5-5', { input: 1000, output: 2000 }))
    await complete($)
    const ui = await $.ui.mount({ plugin: 'dojo-meter', surface, component: 'AbovePrompt', props: PROPS })
    expect(await ui.find({ type: 'Text', text: /meter/ })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /fleet ● #1 build/ })).toBeDefined()
    expect(await ui.find({ type: 'Button', key: 'hide' })).toBeDefined()
    await ui.unmount()
  })

  test(`a hidden band leaves the band beneath alone on ${surface}`, async ($, on) => {
    chipsAbove(on)
    const w = world(on)
    await step($, w, usageOf('claude-haiku-5-5', { input: 1000 }))
    const ui = await $.ui.mount({ plugin: 'dojo-meter', surface, component: 'AbovePrompt', props: PROPS })
    await ui.press({ key: 'hide' })
    expect(await ui.find({ type: 'Text', text: /meter/ })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: /fleet ● #1 build/ })).toBeDefined()
    await ui.unmount()
  })

  test(`the handler beneath runs once per render, and a band that cannot draw leaves it intact on ${surface}`, async ($, on) => {
    const calls = { n: 0 }
    chipsAbove(on, calls)
    const w = world(on)
    await step($, w, usageOf('claude-haiku-5-5', { input: 1000 }))
    const ui = await $.ui.mount({ plugin: 'dojo-meter', surface, component: 'AbovePrompt', props: PROPS })
    expect(calls.n).toBe(1)
    await ui.unmount()
    const survey = await $.ui.mount({ plugin: 'dojo-meter', surface, component: 'AbovePrompt', props: { ...PROPS, hasSurvey: true } })
    expect(await survey.find({ type: 'Text', text: /meter/ })).toBeUndefined()
    expect(await survey.find({ type: 'Text', text: /fleet ● #1 build/ })).toBeDefined()
    await survey.unmount()
  })
}
