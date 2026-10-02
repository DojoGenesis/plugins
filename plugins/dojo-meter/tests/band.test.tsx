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
