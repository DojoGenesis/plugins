import type { Register } from 'claude-code'

// dojo-router mod (early access). Fills `model` in on unpinned built-in subagent dispatches, by role.
//
// Rules that keep it from overriding a pin it cannot see:
//  - a hook-set model outranks an agent definition's own pin, and a hook cannot read that pin, so only the
//    built-in types that carry none are routed (an allowlist, below). Plugin agents (a type with `:`), forks,
//    custom user or project agents and `statusline-setup` are left alone.
//  - a user or project agent that carries the name of a built-in (the engine offers it with a source other than
//    `built-in`) may pin its own model, so a name seen offered that way is never routed (agent.offer, below).
//  - a call that already names a model is left alone.
//  - it stands down under DOJO_OFF / DOJO_ROUTER_OFF, and when CLAUDE_CODE_SUBAGENT_MODEL(_FORCE) is set: a
//    hook-set model would beat the person's deliberate default, or the status line would name a model that
//    does not run.
// Routing happens in `tool.call`, above the classic PreToolUse hook of this plugin, so that hook sees the
// filled-in model. `agent.spawn` is a backstop for spawns that bypass the tool, and the one place opus is counted.

type Tier = 'haiku' | 'sonnet' | 'opus'
type Role = 'explore' | 'default'

const TIERS: readonly string[] = ['haiku', 'sonnet', 'opus']

// Built-in agent types whose built-in definition pins no model (verified against Claude Code 2.1.286; re-check
// on upgrade). `statusline-setup` pins its own model there, so it is deliberately absent.
const ROUTABLE = new Set(['general-purpose', 'Explore', 'Plan'])

// The names `$.env.get` may read must be string literals, so each is spelled out here.
type EnvReader = { env: { get: (name: string) => Promise<string | undefined> } }

const isOn = (value: string | undefined): boolean =>
  typeof value === 'string' && ['1', 'true', 'yes'].includes(value.trim().toLowerCase())

const isSet = (value: string | undefined): boolean => typeof value === 'string' && value.trim() !== ''

async function standDown($: EnvReader): Promise<boolean> {
  const off = await $.env.get('DOJO_OFF')
  const routerOff = await $.env.get('DOJO_ROUTER_OFF')
  const pinned = await $.env.get('CLAUDE_CODE_SUBAGENT_MODEL')
  const forced = await $.env.get('CLAUDE_CODE_SUBAGENT_MODEL_FORCE')
  return isOn(off) || isOn(routerOff) || isSet(pinned) || isSet(forced)
}

function asTier(value: unknown, fallback: Tier): Tier {
  const text = typeof value === 'string' ? value.trim().toLowerCase() : ''
  return TIERS.includes(text) ? (text as Tier) : fallback
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

function asCap(value: unknown): number {
  const n = typeof value === 'number' ? value : typeof value === 'string' ? Number(value.trim()) : NaN
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : 0
}

function nameOf(type: unknown): string | undefined {
  if (type !== undefined && type !== null && typeof type !== 'string') return undefined
  const trimmed = (type ?? '').trim()
  return trimmed === '' ? 'general-purpose' : trimmed
}

function roleOf(type: unknown, overridden: ReadonlySet<string>): Role | undefined {
  const name = nameOf(type)
  if (name === undefined || !ROUTABLE.has(name) || overridden.has(name)) return undefined
  return name === 'Explore' ? 'explore' : 'default'
}

const isNamed = (model: unknown): boolean =>
  typeof model === 'string' && model.trim() !== '' && model.trim().toLowerCase() !== 'inherit'

// `$` may only be handed to a function declared at the top of this file, so the toast lives here.
function showCapToast($: { ui: { toast: (text: string) => void } }, cap: number, explore: Tier, other: Tier): void {
  $.ui.toast(`dojo-router: opus cap reached (${cap}) — unpinned dispatches stop landing on opus: Explore now goes to ${explore}, the rest to ${other}. Set opus_cap to 0 to turn the cap off.`)
}

export const register: Register = (on, options) => {
  const autoRoute = asFlag(options.auto_route, true)
  const defaultTier = asTier(options.default_tier, 'sonnet')
  const exploreTier = asTier(options.explore_tier, 'haiku')
  const cap = asCap(options.opus_cap)

  // Per session activation, not per day: a reload of the plugin (an options change) starts it again.
  let opusSeen = 0
  let capNoticeShown = false
  let statusShown = false
  // Built-in names that a user or project agent has taken over, seen in the engine's agent offers.
  const overridden = new Set<string>()

  const capReached = (): boolean => cap > 0 && opusSeen >= cap
  // After the cap an unpinned dispatch must not land on opus again, even when default_tier is opus.
  const belowOpus = (tier: Tier): Tier => (tier === 'opus' ? 'sonnet' : tier)

  function decide(role: Role): { model: Tier; capChanged: boolean } | undefined {
    const base: Tier = role === 'explore' ? exploreTier : defaultTier
    const capped = capReached()
    if (!autoRoute && !capped) return undefined
    const model = capped ? belowOpus(base) : base
    return { model, capChanged: capped && (!autoRoute || model !== base) }
  }

  // True the first time it is asked, so the toast fires once per session activation.
  function claimNotice(): boolean {
    if (capNoticeShown) return false
    capNoticeShown = true
    return true
  }

  on('tool.call', { tool: 'Agent' }, async ($, e, next) => {
    if (isNamed(e.model)) return next(e)
    const role = roleOf(e.subagent_type, overridden)
    if (role === undefined) return next(e)
    if (await standDown($)) return next(e)
    const pick = decide(role)
    if (pick === undefined) return next(e)
    if (pick.capChanged && claimNotice()) showCapToast($, cap, belowOpus(exploreTier), belowOpus(defaultTier))
    statusShown = true
    $.ui.status(`dojo-router: ${e.subagent_type?.trim() || 'general-purpose'} -> ${pick.model}`)
    return next({ ...e, model: pick.model })
  }).catch(($, e, next) => next(e))

  // A built-in name offered from any other source is a user or project agent that replaces it. Its own pin
  // is out of this hook's sight, and a model set here would beat that pin, so the name is left alone.
  on('agent.offer', async ($, e, next) => {
    if (ROUTABLE.has(e.agent) && e.source !== 'built-in') overridden.add(e.agent)
    return next(e)
  }).catch(($, e, next) => next(e))

  // The status line names the last routing; clear it when the next turn starts so it never goes stale.
  on('turn.start', async ($, e, next) => {
    if (statusShown) {
      statusShown = false
      $.ui.status(undefined)
    }
    return next(e)
  }).catch(($, e, next) => next(e))

  on('agent.spawn', async ($, e, next) => {
    let input = e
    if (!isNamed(e.model) && e.fork !== true) {
      const role = roleOf(e.subagentType, overridden)
      const owner = e.provider?.plugin
      const foreign = typeof owner === 'string' && owner !== '' && owner !== 'engine'
      if (role !== undefined && !foreign && !(await standDown($))) {
        const pick = decide(role)
        if (pick !== undefined) {
          if (pick.capChanged && claimNotice()) showCapToast($, cap, belowOpus(exploreTier), belowOpus(defaultTier))
          statusShown = true
          $.ui.status(`dojo-router: ${e.subagentType?.trim() || 'general-purpose'} -> ${pick.model}`)
          input = { ...e, model: pick.model }
        }
      }
    }
    const result = await next(input)
    // The one place opus is counted: the resolved model of a spawn that went ahead, however it got there.
    if (result.deny === undefined && typeof result.model === 'string' && /opus/i.test(result.model)) {
      opusSeen += 1
      if (cap > 0 && opusSeen > cap && claimNotice()) showCapToast($, cap, belowOpus(exploreTier), belowOpus(defaultTier))
    }
    return result
  }).catch(($, e, next) => next(e))
}
