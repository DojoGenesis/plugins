import { update } from 'claude-code'
import type { Register } from 'claude-code'
import { renderBand, HIDE_WIDTH } from './band'
import {
  addUsage, buildBand, dayKey, estimateUsd, fitBand, formatBudget, formatTokens, formatUsd, UNITS_PER_USD,
} from './ledger'
import type { Ledger } from './ledger'

// dojo-meter mod (early access). It watches every model request of the session, subagents and workflow
// agents included, and does four things with what it sees:
//   - keeps a per-loop x model ledger and prices it from the shared table (hooks/pricing.ts), for the band;
//   - draws the band above the prompt: spend by tier, last-request context size, cache-read share;
//   - toasts at 70 and 90 percent of budget_usd and when the context passes context_warn_tokens;
//   - adds the session's spend to a daily total in $.store.
// It never rewrites a tool call, an agent or a request, and it never throws into the turn: every piece of
// accounting sits in its own try/catch and the hooks always hand the event on.
//
// The ledger lives in this module (not in $.state): a step hook that updated one shared atom would fight itself
// under a workflow's fan-out. Only the small formatted band, and the hidden flag, go to $.state. A hot reload
// resets the ledger and the flush marker together, so nothing is counted twice.

const bandRef = { plugin: 'dojo-meter', key: 'band' } as const
const hiddenRef = { plugin: 'dojo-meter', key: 'hidden' } as const

const DAY_PREFIX = 'day:'
const KEEP_DAYS = 60
const DAY_MS = 86400000

type EnvReader = { env: { get: (name: string) => Promise<string | undefined> } }
type KillMemo = { isRead: boolean; reason?: string }

const isOn = (value: string | undefined): boolean =>
  typeof value === 'string' && ['1', 'true', 'yes'].includes(value.trim().toLowerCase())

// The names `$.env.get` may read must be string literals, so each is spelled out. The answer cannot change
// while the process runs, so it is read once and remembered: one host round trip, not one per step.
async function killReason($: EnvReader, memo: KillMemo): Promise<string | undefined> {
  if (memo.isRead) return memo.reason
  let reason: string | undefined
  try {
    const off = await $.env.get('DOJO_OFF')
    const meterOff = await $.env.get('DOJO_METER_OFF')
    reason = isOn(off) ? 'DOJO_OFF' : isOn(meterOff) ? 'DOJO_METER_OFF' : undefined
  } catch (_err) {
    reason = undefined
  }
  memo.isRead = true
  memo.reason = reason
  return reason
}

function asFlag(value: unknown, fallback: boolean): boolean {
  if (typeof value === 'boolean') return value
  if (typeof value === 'string') {
    const text = value.trim().toLowerCase()
    if (['false', '0', 'no', 'off'].includes(text)) return false
    if (['true', '1', 'yes', 'on'].includes(text)) return true
  }
  return fallback
}

// 0 is off for both numbers; anything unusable is off too.
function asLimit(value: unknown, fallback: number): number {
  const n = typeof value === 'number' ? value : typeof value === 'string' ? Number(value.trim()) : NaN
  if (value === undefined || value === null || value === '') return fallback
  return Number.isFinite(n) && n > 0 ? n : 0
}

type StoredDay = { microUsd: number; unpricedTokens: number }

function asStoredDay(value: unknown): StoredDay {
  const v = (typeof value === 'object' && value !== null ? value : {}) as Record<string, unknown>
  const micro = typeof v.microUsd === 'number' && Number.isFinite(v.microUsd) && v.microUsd >= 0 ? v.microUsd : 0
  const unpriced = typeof v.unpricedTokens === 'number' && Number.isFinite(v.unpricedTokens) && v.unpricedTokens >= 0 ? v.unpricedTokens : 0
  return { microUsd: micro, unpricedTokens: unpriced }
}

export const register: Register = (on, options) => {
  const showBand = asFlag(options.show_band, true)
  const budgetUsd = asLimit(options.budget_usd, 0)
  const contextWarn = asLimit(options.context_warn_tokens, 400000)
  const budgetUnits = Math.round(budgetUsd * UNITS_PER_USD)

  const memo: KillMemo = { isRead: false }
  const ledger: Ledger = new Map()
  let ctxTokens: number | undefined
  let ctxWindow: number | undefined

  // Daily totals: what this session already added to today's stored total, and today's total as last read.
  let flushedUnits = 0
  let flushedUnpriced = 0
  let today: { day: string; units: number; unpriced: number } | undefined
  let prunedDay = ''

  // Each toast fires once; one jump past both budget marks shows only the higher one.
  const shown = { b70: false, b90: false }
  let ctxArmed = true

  let lastBand = ''

  // Recomputes the band and writes it only when its text changed. `write` closes over `$` at the call site.
  const publish = async (write: (view: ReturnType<typeof buildBand>) => Promise<unknown>): Promise<void> => {
    const view = buildBand({ ledger, ctxTokens, ctxWindow, todayBaseUnits: today?.units, todayUnpricedTokens: today?.unpriced, flushedUnits })
    const text = JSON.stringify(view)
    if (text === lastBand) return
    await write(view)
    lastBand = text
  }

  on('turn.step', async function* ($, e, next) {
    const res = yield* next(e)
    try {
      if (res.usage && (await killReason($, memo)) === undefined) {
        const size = addUsage(ledger, e.agentId ?? 'main', res.usage)
        if (e.agentId === undefined && size !== undefined) ctxTokens = size
        await publish(view => $.state.set(bandRef, view))
      }
    } catch (_err) {
      // The meter never breaks a turn.
    }
    return res
  })

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    if (e.agentId !== undefined) return result
    try {
      if ((await killReason($, memo)) !== undefined) return result

      try {
        const usage = await $.session.usage()
        const window = usage.context.window
        if (typeof window === 'number' && Number.isFinite(window) && window > 0) ctxWindow = window
      } catch (_err) {
        // No context window known: the band shows tokens without a percent.
      }

      const estimate = estimateUsd(ledger)

      try {
        if (budgetUnits > 0) {
          const now = estimate.total
          const percent = Math.floor((now * 100) / budgetUnits)
          // Tokens from a model with no price are left out of `now`, so the toast says the figure is partial.
          const partial = estimate.unpricedTokens > 0 ? ' (partial: some models are unpriced)' : ''
          const text = (): string =>
            `dojo-meter: session estimate ${formatUsd(now)}${partial} is ${percent}% of your ${formatBudget(budgetUsd)} budget ` +
            '\u2014 a list-price estimate for this session only. Set budget_usd to 0 to turn this off.'
          if (!shown.b90 && now * 10 >= budgetUnits * 9) {
            shown.b90 = true
            shown.b70 = true
            $.ui.toast(text())
          } else if (!shown.b70 && now * 10 >= budgetUnits * 7) {
            shown.b70 = true
            $.ui.toast(text())
          }
        }
        if (contextWarn > 0 && ctxTokens !== undefined) {
          if (ctxTokens > contextWarn) {
            if (ctxArmed) {
              ctxArmed = false
              $.ui.toast(
                `dojo-meter: context is ${formatTokens(ctxTokens)} tokens, over your ${formatTokens(contextWarn)} warning ` +
                  '— every request re-reads it. Run /compact, or set context_warn_tokens to 0 to turn this off.',
              )
            }
          } else if (ctxTokens * 10 < contextWarn * 7) {
            ctxArmed = true
          }
        }
      } catch (_err) {
        // A failed toast is not worth a failed turn.
      }

      try {
        const now = await $.clock.now()
        const day = dayKey(now)
        if (today !== undefined && today.day !== day) today = undefined
        const deltaUnits = estimate.total - flushedUnits
        const deltaUnpriced = estimate.unpricedTokens - flushedUnpriced
        if (deltaUnits > 0 || deltaUnpriced > 0) {
          const key = DAY_PREFIX + day
          const stored = asStoredDay(await $.store.get(key))
          const updated: StoredDay = {
            microUsd: stored.microUsd + Math.round(deltaUnits / 1e4),
            unpricedTokens: stored.unpricedTokens + Math.max(0, deltaUnpriced),
          }
          await $.store.set(key, updated)
          flushedUnits = estimate.total
          flushedUnpriced = estimate.unpricedTokens
          today = { day, units: updated.microUsd * 1e4, unpriced: updated.unpricedTokens }
          if (prunedDay !== day) {
            prunedDay = day
            const cutoff = DAY_PREFIX + dayKey(now - KEEP_DAYS * DAY_MS)
            for (const stale of await $.store.keys()) {
              if (stale.startsWith(DAY_PREFIX) && stale < cutoff) await $.store.delete(stale)
            }
          }
        }
      } catch (_err) {
        // The daily total is best effort: a failed write is retried with the next turn's delta.
      }

      await publish(view => $.state.set(bandRef, view))
    } catch (_err) {
      // The meter never breaks a turn.
    }
    return result
  })

  on('command.run', { command: 'dojo-meter:band' }, async ($, e) => {
    try {
      const reason = await killReason($, memo)
      if (reason !== undefined) {
        return { text: `dojo-meter: the band is off (${reason}=1). Unset it and start a new session to turn it back on.` }
      }
      const arg = (typeof e.args === 'string' ? e.args : '').trim().toLowerCase()
      const note = showBand ? '' : ' The show_band option is off, so nothing draws until you turn it on in the plugin settings.'
      const { value } = await $.state.get(hiddenRef)
      const isHidden = value === true
      if (arg === 'status') return { text: `dojo-meter: the band is ${isHidden ? 'hidden' : 'shown'}.${note}` }
      if (arg !== '' && arg !== 'on' && arg !== 'off' && arg !== 'toggle') {
        return { text: `dojo-meter: unknown argument "${arg.slice(0, 20)}". Use on, off, toggle or status.` }
      }
      const wantHidden = arg === 'on' ? false : arg === 'off' ? true : !isHidden
      await update($, hiddenRef, () => wantHidden)
      return { text: `dojo-meter: the band is now ${wantHidden ? 'hidden' : 'shown'}.${note}` }
    } catch (_err) {
      return { text: 'dojo-meter: the band command failed; the meter itself is unaffected.' }
    }
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    try {
      const { value: view } = await $.state.get(bandRef)
      const { value: hidden } = await $.state.get(hiddenRef)
      if (!showBand || hidden === true || !view || e.props.hasSurvey || memo.reason !== undefined) return next(e)
      const text = fitBand(view, e.props.bodyColumns - HIDE_WIDTH)
      return renderBand($.ui.resolve(e), text, () => update($, hiddenRef, () => true))
    } catch (_err) {
      // A band that cannot be drawn steps aside: the engine draws what it would have drawn without us.
      return next(e)
    }
  })
}
