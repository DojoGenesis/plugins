import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { GardenCard, GardenRead, GardenSession, GardenWeek } from '../types'
import {
  DAY_MS, KEEP_MS, KEEP_READS, KEEP_SESSIONS, KEEP_WEEKS, VERDICT_WEEKS, WEEK_MS,
  addedFiles, cardText, classifyPath, computeCard, direction, fmt, newestCompression, parseFront, recurrenceTimes,
  ritualLine, staleFlags, verdicts, weekOf,
} from './score'

// wisdom-garden mod (early access): the weekly compounding score. It keeps a reuse log of every memory file and
// skill the session reads, a per-session cost and turn count, and once a week turns those, plus the memory repo's
// git history and compression logs, into a card: fewer repeat mistakes, faster and cheaper work, new capability,
// stale-memory harm, and harvest cadence. /garden-score opens the card in a pane, terminal and desktop alike.
// It only watches: it never blocks or rewrites a call, and every piece of accounting sits in its own try/catch.

const PANE = 'garden-score'
const COMMAND = 'garden-score'

const cardAtom = atom({ plugin: 'wisdom-garden', key: 'card' } as const, null as GardenCard | null)
const weeksAtom = atom({ plugin: 'wisdom-garden', key: 'weeks' } as const, [] as GardenWeek[])
const busyAtom = atom({ plugin: 'wisdom-garden', key: 'busy' } as const, false)

const READS = 'reads'
const SESSIONS = 'sessions'
const WEEKS = 'weeks'
const LAST = 'lastScoreAt'

const isOn = (value: string | undefined): boolean =>
  typeof value === 'string' && ['1', 'true', 'yes', 'on'].includes(value.trim().toLowerCase())

function asNumber(value: unknown, fallback: number): number {
  const n = typeof value === 'number' ? value : typeof value === 'string' && value.trim() !== '' ? Number(value.trim()) : NaN
  return Number.isFinite(n) && n >= 0 ? n : fallback
}

const asList = <T,>(value: unknown): T[] => (Array.isArray(value) ? (value as T[]) : [])

const join = (dir: string, name: string): string => `${dir.replace(/[\\/]+$/, '')}/${name}`

// The names `$.env.get` may read must be string literals, so each is spelled out.
async function standDown($: EngineInterface): Promise<boolean> {
  try {
    return isOn(await $.env.get('DOJO_OFF')) || isOn(await $.env.get('GARDEN_SCORE_OFF'))
  } catch (_err) {
    return false
  }
}

async function homeDirs($: EngineInterface): Promise<string[]> {
  const out: string[] = []
  for (const value of [await $.env.get('HOME'), await $.env.get('USERPROFILE')]) {
    if (value && !out.includes(value)) out.push(value)
  }
  return out
}

// The memory repo: the memory_root option, else the first known layout under the home folder that holds MEMORY.md.
async function findRoot($: EngineInterface, configured: string): Promise<string | undefined> {
  const tries: string[] = []
  if (configured.trim() !== '') tries.push(configured.trim())
  for (const home of await homeDirs($)) {
    tries.push(join(home, 'TresPies-AI-Orchestration'), join(home, '.hermes/orchestration/trespies-memory'))
  }
  for (const dir of tries) {
    try {
      if (await $.fs.exists(join(dir, 'MEMORY.md'))) return dir
    } catch (_err) {
      // An unreadable candidate is skipped.
    }
  }
  return undefined
}

async function git($: EngineInterface, root: string, args: string[]): Promise<string | undefined> {
  try {
    const run = await $.process.run(['git', '-c', 'core.quotePath=false', ...args], { cwd: root, timeoutMs: 60000 })
    return run.exitCode === 0 ? run.stdout : undefined
  } catch (_err) {
    // No git, or no $.process on this host.
    return undefined
  }
}

type Ctx = {
  configuredRoot: string
  staleDays: number
  // Store writes are read-modify-write; one chain keeps parallel tool calls from losing each other's rows.
  chain: Promise<unknown>
}

function serial<T>(ctx: Ctx, work: () => Promise<T>): Promise<T> {
  const run = ctx.chain.then(work, work)
  ctx.chain = run.catch(() => undefined)
  return run
}

function logRead($: EngineInterface, ctx: Ctx, row: GardenRead): Promise<void> {
  return serial(ctx, async () => {
    const list = asList<GardenRead>(await $.store.get(READS))
    list.push(row)
    const cutoff = row.t - KEEP_MS
    await $.store.set(READS, list.filter(r => r.t >= cutoff).slice(-KEEP_READS))
  })
}

async function score($: EngineInterface, ctx: Ctx, isSaving: boolean): Promise<GardenCard> {
  const now = await $.clock.now()
  const notes: string[] = []
  const root = await findRoot($, ctx.configuredRoot)
  const reads = asList<GardenRead>(await $.store.get(READS))
  const sessions = asList<GardenSession>(await $.store.get(SESSIONS))
  const superseded = new Set<string>()
  let recurrences: number[] | undefined
  let added: { path: string; t: number }[] | undefined
  let lastCompression: number | undefined
  let activeSeeds: number | undefined

  if (root === undefined) {
    notes.push('No memory repo found. Set memory_root in the plugin settings.')
  } else {
    const since = `--since=${new Date(now - 5 * WEEK_MS).toISOString()}`
    const recLog = await git($, root, ['log', since, '--no-color', '--format=@@%ct', '-p', '--unified=0', '--',
      ':(glob)**/seed_*.md', ':(glob)**/feedback_*.md'])
    const addLog = await git($, root, ['log', since, '--no-color', '--diff-filter=A', '--name-only', '--format=@@%ct', '--',
      ':(glob)**/seed_*.md', ':(glob)**/SKILL.md'])
    if (recLog !== undefined) recurrences = recurrenceTimes(recLog)
    if (addLog !== undefined) added = addedFiles(addLog)
    if (recLog === undefined || addLog === undefined) notes.push('git history could not be read in the memory repo.')
    if ((await git($, root, ['rev-parse', '--is-shallow-repository']))?.trim() === 'true') {
      notes.push('The memory repo is a shallow clone: its oldest commit reads as adding every file, so new seeds and notes run high.')
    }

    try {
      lastCompression = newestCompression((await $.fs.list(join(root, 'compressions'))).map(f => f.name))
    } catch (_err) {
      notes.push('No compressions folder in the memory repo.')
    }

    try {
      const files = (await $.fs.list(root)).filter(f => f.kind === 'file' && classifyPath(f.name) !== undefined)
      activeSeeds = files.filter(f => /^seed_/i.test(f.name)).length
      for (const f of files.slice(0, 3000)) {
        try {
          const front = parseFront((await $.fs.read(join(root, f.name))).slice(0, 8000))
          for (const slug of front.supersedes) superseded.add(slug.replace(/\.md$/i, ''))
          if (front.supersededBy) {
            superseded.add(f.name.replace(/\.md$/i, ''))
            if (front.name) superseded.add(front.name)
          }
        } catch (_err) {
          // One unreadable file does not stop the scan.
        }
      }
    } catch (_err) {
      notes.push('The memory repo could not be listed.')
    }
  }

  let ritualLedger: string | undefined
  for (const home of await homeDirs($)) {
    try {
      ritualLedger = await $.fs.read(join(home, '.claude/convergence-ledger.md'))
      break
    } catch (_err) {
      // No ledger here: the drift ritual hook has not run on this machine.
    }
  }
  const card = computeCard({ now, reads, sessions, recurrences, added, superseded, lastCompression, activeSeeds, memoryRoot: root, ritualLedger, notes })
  if (reads.length === 0) card.notes.push('The reuse log is empty: it fills as sessions read memory files and skills.')

  let weeks = asList<GardenWeek>(await $.store.get(WEEKS))
  const lastSaved = weeks.reduce((a, w) => Math.max(a, w.at), 0)
  if (isSaving && now - lastSaved >= WEEK_MS - DAY_MS / 2) {
    weeks = [...weeks, weekOf(card)].slice(-KEEP_WEEKS)
    await $.store.set(WEEKS, weeks)
    await $.store.set(LAST, now)
  }
  // Prune the session log here, once a week at most, rather than on every turn.
  const cutoff = now - KEEP_MS
  if (sessions.some(s => s.t < cutoff)) {
    await serial(ctx, async () => {
      const list = asList<GardenSession>(await $.store.get(SESSIONS))
      await $.store.set(SESSIONS, list.filter(s => s.t >= cutoff).slice(-KEEP_SESSIONS))
    })
  }
  await update($, cardAtom, () => card)
  await update($, weeksAtom, () => weeks)
  return card
}

async function refresh($: EngineInterface, ctx: Ctx): Promise<GardenCard> {
  await update($, busyAtom, () => true)
  try {
    return await score($, ctx, true)
  } finally {
    await update($, busyAtom, () => false)
  }
}

export const register: Register = (on, options) => {
  const ctx: Ctx = {
    configuredRoot: typeof options.memory_root === 'string' ? options.memory_root : '',
    staleDays: asNumber(options.stale_days, 90),
    chain: Promise.resolve(),
  }
  const weekly = options.weekly_toast !== false && options.weekly_toast !== 'false'
  let isOff = false

  on('session.start', async ($, e, next) => {
    const started = await next(e)
    isOff = await standDown($)
    if (isOff) return started
    try {
      await $.command.register({
        name: COMMAND,
        description: 'Weekly compounding score: repeat mistakes, cost per session, new capability, stale-memory reads, harvest cadence.',
        argumentHint: '[text]',
        immediate: true,
      })
    } catch (_err) {
      // No command on this host; the weekly toast still works.
    }
    if (weekly) {
      // Off the session's path: the score reads git and the memory folder.
      void (async () => {
        try {
          const now = await $.clock.now()
          const last = asNumber(await $.store.get(LAST), 0)
          if (now - last < WEEK_MS) return
          const card = await refresh($, ctx)
          if (card) $.ui.toast(`Garden score for the week is ready: ${card.metrics.filter(m => direction(m) === 'better').length} of ${card.metrics.length} measures better. Run /${COMMAND}.`)
        } catch (_err) {
          // The weekly score is best effort.
        }
      })()
    }
    return started
  })

  on('tool.call', { tool: ['Read', 'Skill'] }, async ($, e, next) => {
    const result = await next(e)
    if (isOff || result.isError) return result
    try {
      const now = await $.clock.now()
      const s = await $.session.id()
      if (e.tool === 'Skill') {
        const name = String(e.skill ?? '').trim()
        if (name) await logRead($, ctx, { id: `skill:${name}`, kind: 'skill', t: now, s })
      } else if (e.tool === 'Read') {
        const path = String(e.file_path ?? '')
        const hit = classifyPath(path)
        if (hit) {
          const row: GardenRead = { id: hit.id, kind: hit.kind, t: now, s }
          if (hit.kind !== 'skill') {
            try {
              const front = parseFront((await $.fs.read(path)).slice(0, 8000))
              const stale = staleFlags(front, now, ctx.staleDays)
              if (front.name) row.name = front.name
              if (stale.length > 0) row.stale = stale
            } catch (_err) {
              // Read but not re-readable here: the read still counts.
            }
          }
          await logRead($, ctx, row)
        }
      }
    } catch (_err) {
      // The reuse log never breaks a tool call.
    }
    return result
  })

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    if (isOff || e.agentId !== undefined) return result
    try {
      const s = await $.session.id()
      const now = await $.clock.now()
      let usd: number | undefined
      try {
        usd = (await $.session.usage()).cost?.usd
      } catch (_err) {
        usd = undefined
      }
      await serial(ctx, async () => {
        const list = asList<GardenSession>(await $.store.get(SESSIONS))
        const at = list.findIndex(one => one.s === s)
        const prev: GardenSession = list[at] ?? { s, t: now, turns: 0 }
        const row: GardenSession = { ...prev, turns: prev.turns + 1, ...(usd === undefined ? {} : { usd }) }
        if (at >= 0) list[at] = row
        else list.push(row)
        await $.store.set(SESSIONS, list.slice(-KEEP_SESSIONS))
      })
    } catch (_err) {
      // A missed turn is a missed count, never a failed turn.
    }
    return result
  })

  on('command.run', { command: ['garden-score', 'wisdom-garden:garden-score'] }, async ($, e) => {
    if (isOff) return { text: 'Garden score is off (DOJO_OFF or GARDEN_SCORE_OFF is set).' }
    try {
      const card = await refresh($, ctx)
      const weeks = await read($, weeksAtom)
      if (!card) return { text: 'Garden score could not be computed.' }
      if (e.args.trim().toLowerCase() === 'text') return { text: cardText(card, weeks) }
      const { isPlaced } = await $.ui.open({ id: PANE, title: 'Garden score', focus: true })
      return { text: isPlaced ? 'Garden score opened in a pane.' : cardText(card, weeks) }
    } catch (_err) {
      return { text: 'Garden score could not be computed; the reuse log is unaffected.' }
    }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const card = await read($, cardAtom)
    const weeks = await read($, weeksAtom)
    const busy = await read($, busyAtom)
    const again = () => void refresh($, ctx)
    if (!card) {
      return (
        <Box flexDirection="column">
          <Text dimColor>{busy ? 'Scoring...' : 'No score yet.'}</Text>
          <Button key="score" onPress={again}>Score now</Button>
        </Box>
      )
    }
    const v = verdicts(weeks, card)
    const c = card.cadence
    const tone = (d: ReturnType<typeof direction>) => (d === 'better' ? 'green' : d === 'worse' ? 'red' : undefined)
    return (
      <Box flexDirection="column">
        <Text bold>{`Week ending ${new Date(card.at).toISOString().slice(0, 10)}, against the 4 weeks before`}</Text>
        <Text dimColor>{`${card.sessions} sessions, ${card.reads} memory and skill reads this week${card.activeSeeds === null ? '' : `, ${card.activeSeeds} active seeds`}`}</Text>
        <Box flexDirection="column" marginTop={1}>
          {card.metrics.map(m => (
            <Box key={`m:${m.key}`} flexDirection="column">
              <Text>
                <Text bold>{m.label}</Text>
                {`  ${fmt(m.week, m.unit)} this week, ${fmt(m.base, m.unit)} a week before`}
              </Text>
              {direction(m) !== undefined && <Text color={tone(direction(m))}>{`  ${direction(m)} (${m.better} is better)`}</Text>}
              {m.note !== undefined && <Text dimColor>{`  ${m.note}`}</Text>}
            </Box>
          ))}
        </Box>
        <Box flexDirection="column" marginTop={1}>
          <Text bold>Harvest cadence</Text>
          <Text color={c.days !== null && c.days > 14 ? 'red' : undefined}>
            {c.days === null ? '  No compression log found.' : `  Last compression log ${c.days} days ago, ${c.sessionsSince ?? 'n/a'} sessions since.`}
          </Text>
          {c.ritual !== null && <Text dimColor>{`  Ritual offers this week: ${ritualLine(c.ritual)}.`}</Text>}
        </Box>
        <Box flexDirection="column" marginTop={1}>
          <Text bold>Compounding reading</Text>
          {v.length === 0
            ? <Text dimColor>{`  Needs ${Math.max(0, VERDICT_WEEKS - weeks.length)} more weekly rows (${weeks.length} saved).`}</Text>
            : v.map(x => <Text>{`  ${x.label}: ${x.reading}`}</Text>)}
        </Box>
        {card.staleIds.length > 0 && (
          <Box flexDirection="column" marginTop={1}>
            <Text bold>Stale memory read this week</Text>
            {card.staleIds.map(id => <Text dimColor>{`  ${id}`}</Text>)}
          </Box>
        )}
        {card.notes.map(n => <Text dimColor>{n}</Text>)}
        <Button key="score" onPress={again}>{busy ? 'Scoring...' : 'Score again'}</Button>
      </Box>
    )
  })
}
