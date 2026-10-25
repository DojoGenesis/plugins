import { expect, mock, test } from 'claude-code/testing'

import type { GardenRead, GardenWeek } from '../types'
import {
  DAY_MS, WEEK_MS, addedFiles, classifyPath, computeCard, newestCompression, parseFront, recurrenceTimes, ritualCounts, staleFlags, verdicts,
} from '../hooks/score'

// Mod kit tests. The hooks a test registers with `on` sit beneath the plugin and stand for the engine: here a
// memory repo in memory at /mem, git answering from canned logs, and a session that costs $1.50.

const T0 = Date.UTC(2026, 9, 20, 12)
const ROOT = '/mem'
const sec = (t: number) => String(Math.floor(t / 1000))

const FILES: Record<string, string> = {
  '/mem/MEMORY.md': '# index\n',
  '/mem/seed_fresh.md': '---\nname: fresh\nupdated: 2026-10-18\n---\nbody\n',
  '/mem/seed_old.md': '---\nname: old-one\nmetadata:\n  updated: 2026-05-01\n---\nbody\n',
  '/mem/feedback_expired.md': '---\nname: expired\nvalid_until: 2026-10-01\n---\nbody\n',
  '/mem/seed_new.md': '---\nname: new-one\nsupersedes: [seed_replaced]\nverified: 2026-10-19\n---\n',
  '/mem/seed_replaced.md': '---\nname: replaced\nupdated: 2026-10-10\n---\n',
}

FILES['/home/x/.claude/convergence-ledger.md'] = [
  '2026-10-03 convergence', 'ritual: 2026-10-18 09:12 offered sessions=26 dirty=4 sid=a', 'ritual: 2026-10-18 09:13 declined reason="shipping"',
  'ritual: 2026-09-01 10:00 offered sessions=30 dirty=1 sid=b',
].join('\n')

const REC_LOG = [`@@${sec(T0 - 2 * DAY_MS)}`, '+++ b/seed_fresh.md', '+The guard fired again on a pushed commit.', '+unrelated line',
  `@@${sec(T0 - 20 * DAY_MS)}`, '+It recurred in the build.'].join('\n')
const ADD_LOG = [`@@${sec(T0 - DAY_MS)}`, '', 'seed_new.md', 'skills/new-skill/SKILL.md', `@@${sec(T0 - 15 * DAY_MS)}`, '', 'seed_fresh.md'].join('\n')

// Where the memory repo keeps its store. `root` is the repo (git, compressions/); `storeDir` is the folder that holds
// MEMORY.md and the seed files: the root itself in the older layout, <root>/memory once the store moved there, when
// the root keeps only a pointer MEMORY.md.
type Layout = { root: string; storeDir: string; files: Record<string, string> }
const POINTER = '# MEMORY.md moved to memory/MEMORY.md\n\nThe live index is memory/MEMORY.md.\n'

function place(root: string, isNested: boolean, extra: Record<string, string> = {}): Layout {
  const storeDir = isNested ? `${root}/memory` : root
  const files: Record<string, string> = {}
  for (const [path, text] of Object.entries(FILES)) files[path.startsWith(`${ROOT}/`) ? `${storeDir}/${path.slice(ROOT.length + 1)}` : path] = text
  if (isNested) files[`${root}/MEMORY.md`] = POINTER
  return { root, storeDir, files: { ...files, ...extra } }
}

// The direct children of a folder in a layout's files; a folder with none is one that does not exist.
function listDir(files: Record<string, string>, dir: string) {
  const prefix = `${dir.replace(/\/+$/, '')}/`
  const seen = new Map<string, 'file' | 'dir'>()
  for (const path of Object.keys(files)) {
    if (!path.startsWith(prefix)) continue
    const [head, ...rest] = path.slice(prefix.length).split('/')
    if (head) seen.set(head, rest.length > 0 ? 'dir' : seen.get(head) ?? 'file')
  }
  return [...seen].map(([name, kind]) => ({ name, kind, size: 1, mtimeMs: 0, isLink: false }))
}

type World = { toasts: string[]; clock: ReturnType<typeof mock.clock>; gitCalls: number; gitCwds: string[]; store: Map<string, unknown> }

function world(on: any, store: Record<string, unknown> = {}, env: Record<string, string> = {}, layout: Layout = place(ROOT, false)): World {
  const w: World = { toasts: [], clock: mock.clock(on, { now: T0 }), gitCalls: 0, gitCwds: [], store: new Map(Object.entries(store)) }
  mock.env(on, { HOME: '/home/x', ...env })
  // The plugin's own store, kept here so a test can read what the plugin wrote.
  const copy = (v: unknown) => (v === undefined ? undefined : JSON.parse(JSON.stringify(v)))
  on('store.get', (_$: any, e: any) => ({ value: copy(w.store.get(e.key)) }))
  on('store.set', (_$: any, e: any) => {
    w.store.set(e.key, copy(e.value))
    return { value: undefined }
  })
  on('store.delete', (_$: any, e: any) => {
    w.store.delete(e.key)
    return { value: undefined }
  })
  on('store.keys', () => ({ value: [...w.store.keys()] }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.toast', (_$: any, e: any) => {
    w.toasts.push(String(e.text ?? e.message ?? JSON.stringify(e)))
    return { value: undefined }
  })
  on('command.register', (_$: any, e: any) => ({ value: { command: e.name } }))
  on('session.id', () => ({ value: 'sess-1' }))
  on('session.usage', () => ({ value: { startedAt: T0, context: {}, rateLimits: [], cost: { usd: 1.5 } } }))
  on('fs.exists', (_$: any, e: any) => ({ value: e.path in layout.files }))
  on('fs.read', (_$: any, e: any) => {
    if (!(e.path in layout.files)) throw new Error('ENOENT')
    return { value: layout.files[e.path] }
  })
  on('fs.list', (_$: any, e: any) => {
    // compressions/ stays at the repo root in every layout.
    if (e.path === `${layout.root}/compressions`) {
      return { value: ['compression_log_2026-10-03_convergence.md', 'compression_log_2026-08-13_x.md', 'harvest.jsonl']
        .map(name => ({ name, kind: 'file', size: 1, mtimeMs: 0, isLink: false })) }
    }
    const entries = listDir(layout.files, e.path)
    if (entries.length === 0) throw new Error('ENOENT')
    return { value: entries }
  })
  on('process.run', (_$: any, e: any) => {
    w.gitCalls += 1
    w.gitCwds.push(String(e.init?.cwd))
    const argv: string[] = [...e.argv]
    const stdout = argv.includes('--diff-filter=A') ? ADD_LOG : REC_LOG
    return { value: { exitCode: 0, stdout, stderr: '' } }
  })
  on('tool.call', () => ({ result: {}, text: 'ok' }))
  on('turn.complete', (_$: any, e: any) => ({ text: e.answer }))
  on('session.start', (_$: any, e: any) => ({ cwd: e.cwd }))
  return w
}

const start = ($: any) => $.session.start({ source: 'startup', cwd: '/work', surface: 'terminal', isInteractive: true })
let turns = 0
const complete = ($: any) => $.turn.complete({ answer: 'done', durationMs: 1, isAborted: false, turnId: `t${++turns}`, reason: 'answer' })

const PANE = (surface: 'terminal' | 'desktop') => ({
  plugin: 'wisdom-garden',
  surface,
  component: 'Pane',
  requestId: 'garden-score',
  props: { title: 'Garden score', isFocused: true, bodyColumns: 80, placement: 'dock', scroll: { offset: 0, bodyRows: 40 }, view: {} },
}) as const

// ---- pure rules

test('memory files and skills are told apart from other reads', async () => {
  expect(classifyPath('/mem/seed_zero-overlap.md')).toEqual({ id: 'seed_zero-overlap', kind: 'seed' })
  expect(classifyPath('C:\\Users\\x\\mem\\feedback_a.md')).toEqual({ id: 'feedback_a', kind: 'feedback' })
  expect(classifyPath('/repo/skills/seed-library/SKILL.md')).toEqual({ id: 'skill:seed-library', kind: 'skill' })
  expect(classifyPath('/repo/README.md')).toBe(undefined)
  expect(classifyPath('/repo/notes/seedling.md')).toBe(undefined)
})

test('frontmatter: typed links at the top level, updated under metadata, block lists', async () => {
  const f = parseFront('---\nname: a\nsupersedes:\n  - old-a\n  - "old-b"\nsuperseded_by: c\nvalid_until: 2026-11-01\nmetadata:\n  updated: 2026-01-02\n  name: nested\n---\n')
  expect(f.name).toBe('a')
  expect(f.supersedes).toEqual(['old-a', 'old-b'])
  expect(f.supersededBy).toBe('c')
  expect(f.validUntil).toBe('2026-11-01')
  expect(f.updated).toBe('2026-01-02')
  expect(parseFront('no frontmatter').supersedes).toEqual([])
})

test('stale: past valid_until, superseded_by, and verified-or-updated over the limit; no dates is never stale', async () => {
  expect(staleFlags(parseFront('---\nvalid_until: 2026-10-01\n---'), T0, 90)).toEqual(['expired'])
  expect(staleFlags(parseFront('---\nsuperseded_by: x\n---'), T0, 90)).toEqual(['superseded'])
  expect(staleFlags(parseFront('---\nupdated: 2026-05-01\n---'), T0, 90)).toEqual(['old'])
  // verified wins over an old updated
  expect(staleFlags(parseFront('---\nupdated: 2026-01-01\nverified: 2026-10-01\n---'), T0, 90)).toEqual([])
  expect(staleFlags(parseFront('---\nupdated: 2026-05-01\n---'), T0, 0)).toEqual([])
  expect(staleFlags(parseFront('---\nname: x\n---'), T0, 90)).toEqual([])
})

test('git parsing: recurrence notes by commit time, added files, newest compression log by its name', async () => {
  expect(recurrenceTimes(REC_LOG)).toEqual([Math.floor((T0 - 2 * DAY_MS) / 1000) * 1000, Math.floor((T0 - 20 * DAY_MS) / 1000) * 1000])
  expect(addedFiles(ADD_LOG).map(a => a.path)).toEqual(['seed_new.md', 'skills/new-skill/SKILL.md', 'seed_fresh.md'])
  expect(newestCompression(['compression_log_2026-08-13_a.md', 'compression_log_2026-10-03_b.md', 'germs.jsonl'])).toBe(Date.UTC(2026, 9, 3))
  expect(newestCompression([])).toBe(undefined)
})

test('the card: this week against the four weeks before, stale reads counted, superseded ids matched', async () => {
  const reads: GardenRead[] = [
    { id: 'seed_a', kind: 'seed', t: T0 - DAY_MS, s: 's1' },
    { id: 'seed_a', kind: 'seed', t: T0 - 2 * DAY_MS, s: 's1' },
    { id: 'seed_b', kind: 'seed', t: T0 - DAY_MS, s: 's2', stale: ['old'] },
    { id: 'seed_replaced', kind: 'seed', t: T0 - DAY_MS, s: 's2' },
    { id: 'seed_c', kind: 'seed', t: T0 - 10 * DAY_MS, s: 's0' },
  ]
  const card = computeCard({
    now: T0, reads, superseded: new Set(['seed_replaced']), notes: [],
    sessions: [{ s: 's1', t: T0 - DAY_MS, usd: 2, turns: 4 }, { s: 's2', t: T0 - DAY_MS, usd: 4, turns: 6 }, { s: 's0', t: T0 - 10 * DAY_MS, usd: 9, turns: 20 }],
    recurrences: [T0 - DAY_MS, T0 - 9 * DAY_MS, T0 - 30 * DAY_MS, T0 - 40 * DAY_MS],
    added: [{ path: 'seed_x.md', t: T0 - DAY_MS }, { path: 'a/SKILL.md', t: T0 - 8 * DAY_MS }],
    lastCompression: T0 - 17 * DAY_MS,
  })
  const by = (k: string) => card.metrics.find(m => m.key === k)
  expect([by('repeats')?.week, by('repeats')?.base]).toEqual([1, 0.5])
  expect([by('cost')?.week, by('cost')?.base]).toEqual([3, 9])
  expect([by('turns')?.week, by('turns')?.base]).toEqual([5, 20])
  expect([by('newSeeds')?.week, by('newSkills')?.week, by('newSkills')?.base]).toEqual([1, 0, 0.25])
  expect([by('reused')?.week, by('reused')?.base]).toEqual([3, 0.25])
  expect(by('stale')?.week).toBe(2)
  expect(card.staleIds).toEqual(['seed_b', 'seed_replaced'])
  expect(card.cadence.days).toBe(17)
  expect(card.cadence.sessionsSince).toBe(3)
})

test('the compounding reading waits for four weeks and holds to its fixed bars', async () => {
  const card = computeCard({ now: T0, reads: [], sessions: [], superseded: new Set(), notes: [], recurrences: [], added: [] })
  const weeks = (series: number[]): GardenWeek[] => series.map((v, i) => ({ at: T0 - (series.length - i) * WEEK_MS, activeSeeds: null, values: { newSeeds: v, repeats: v } }))
  expect(verdicts(weeks([1, 2, 3]), card)).toEqual([])
  const read = (series: number[], key: string) => verdicts(weeks(series), card).find(v => v.key === key)?.reading
  expect(read([1, 2, 4, 8, 16], 'newSeeds')).toBe('compounding')
  expect(read([1, 5, 9, 13, 17], 'newSeeds')).toBe('linear')
  expect(read([1, 9, 13, 14, 14.5], 'newSeeds')).toBe('saturating')
  expect(read([1, 2, 3, 2, 1], 'newSeeds')).toBe('not improving')
  // lower is better for repeats: a falling series improves
  expect(read([16, 8, 4, 2, 1], 'repeats')).toBe('saturating')
  expect(read([1, 2, 3, 4, 5], 'cost')).toBe('too few weeks')
})

test('ritual ledger rows are counted inside the week only', async () => {
  const text = FILES['/home/x/.claude/convergence-ledger.md'] ?? ''
  expect(ritualCounts(text, T0 - WEEK_MS, T0)).toEqual({ offered: 1, accepted: 0, declined: 1 })
})

// ---- the hooks

test('a read of a memory file is logged with its stale flags; other reads are not', async ($, on) => {
  const w = world(on)
  await start($)
  await $.tool.call({ tool: 'Read', file_path: '/mem/seed_old.md' } as any)
  await $.tool.call({ tool: 'Read', file_path: '/mem/feedback_expired.md' } as any)
  await $.tool.call({ tool: 'Read', file_path: '/mem/seed_fresh.md' } as any)
  await $.tool.call({ tool: 'Read', file_path: '/work/README.md' } as any)
  await $.tool.call({ tool: 'Skill', skill: 'seed-library' } as any)
  const reads = w.store.get('reads') as GardenRead[]
  expect(reads.map(r => [r.id, r.stale ?? []])).toEqual([
    ['seed_old', ['old']], ['feedback_expired', ['expired']], ['seed_fresh', []], ['skill:seed-library', []],
  ])
  expect(reads[0]?.name).toBe('old-one')
})

test('each main-thread turn updates the session row: turns counted, cost from the session ledger', async ($, on) => {
  const w = world(on)
  await start($)
  await complete($)
  await complete($)
  const rows = w.store.get('sessions') as { s: string; turns: number; usd?: number }[]
  expect(rows).toEqual([{ s: 'sess-1', t: T0, turns: 2, usd: 1.5 }])
})

test('/garden-score scores, saves the week, and draws the card on terminal and desktop', { options: { memory_root: ROOT } }, async ($, on) => {
  const w = world(on)
  await start($)
  await $.tool.call({ tool: 'Read', file_path: '/mem/seed_replaced.md' } as any)
  await complete($)
  const ran = await $.command.run({ command: 'garden-score', args: '' } as any)
  expect(ran.text).toBe('Garden score opened in a pane.')
  expect(w.gitCalls >= 2).toBe(true)
  const weeks = w.store.get('weeks') as GardenWeek[]
  expect(weeks.length).toBe(1)
  expect(weeks[0]?.values.newSeeds).toBe(1)
  expect(weeks[0]?.values.stale).toBe(1)

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount(PANE(surface))
    expect((await ui.find({ type: 'Text', text: /Harvest cadence/ }))?.text).toBe('Harvest cadence')
    expect((await ui.find({ type: 'Text', text: /Last compression log 17 days ago/ })) !== undefined).toBe(true)
    expect((await ui.find({ type: 'Text', text: /seed_replaced/ })) !== undefined).toBe(true)
    expect((await ui.find({ type: 'Text', text: /Needs 3 more weekly rows/ })) !== undefined).toBe(true)
    expect((await ui.find({ type: 'Text', text: /1 offered, 0 accepted, 1 declined/ })) !== undefined).toBe(true)
    await ui.unmount()
  }
})

test('/garden-score text answers with the card as text', { options: { memory_root: ROOT } }, async ($, on) => {
  world(on)
  await start($)
  const ran = await $.command.run({ command: 'garden-score', args: 'text' } as any)
  const text = ran.text ?? ''
  expect(text.split('\n')[0]).toBe('Garden score, week ending 2026-10-20 (vs the 4 weeks before)')
  expect(text.includes('New seeds: 1 this week, 0.3 a week before (better)')).toBe(true)
  expect(text.includes('last compression log 17 days ago')).toBe(true)
})

test('the weekly toast comes once a week, at session start', async ($, on) => {
  const w = world(on, { lastScoreAt: T0 - 8 * DAY_MS })
  await start($)
  await w.clock.advance(1)
  expect(w.toasts.length).toBe(1)
  expect(w.toasts[0]?.includes('/garden-score')).toBe(true)
  await start($)
  await w.clock.advance(1)
  expect(w.toasts.length).toBe(1)
})

test('DOJO_OFF turns the mod into a pass-through', async ($, on) => {
  const w = world(on, {}, { DOJO_OFF: '1' })
  await start($)
  await $.tool.call({ tool: 'Read', file_path: '/mem/seed_old.md' } as any)
  expect(w.store.get('reads')).toBe(undefined)
})

test('with no memory_root, the repo is found under the home folder, else the card says how to set it', async ($, on) => {
  world(on)
  await start($)
  const ran = await $.command.run({ command: 'garden-score', args: 'text' } as any)
  expect((ran.text ?? '').includes('No memory repo found. Set memory_root in the plugin settings.')).toBe(true)
})

// ---- where the store lives

// The memory repo moved its store into memory/ and left a pointer MEMORY.md at the root; compressions/ stayed at the
// root. Every layout below must score the same store: 4 active seeds, and seed_replaced read as superseded.
const HOME_REPO = '/home/x/.hermes/orchestration/trespies-memory'
const LAYOUTS: { name: string; layout: Layout; options: Record<string, unknown> }[] = [
  { name: 'store in memory/, memory_root set to the repo root', layout: place(ROOT, true), options: { memory_root: ROOT } },
  { name: 'store at the root (older layout), memory_root set', layout: place(ROOT, false), options: { memory_root: ROOT } },
  { name: 'a memory/ folder with no MEMORY.md is not the store', layout: place(ROOT, false, { [`${ROOT}/memory/notes.txt`]: 'x' }), options: { memory_root: ROOT } },
  { name: 'store in memory/, repo found under the home folder', layout: place(HOME_REPO, true), options: {} },
  { name: 'store at the root, repo found under the home folder', layout: place(HOME_REPO, false), options: {} },
]

for (const { name, layout, options } of LAYOUTS) {
  test(`the store is read from the right folder: ${name}`, { options }, async ($, on) => {
    const w = world(on, {}, {}, layout)
    await start($)
    await $.tool.call({ tool: 'Read', file_path: `${layout.storeDir}/seed_replaced.md` } as any)
    const ran = await $.command.run({ command: 'garden-score', args: '' } as any)
    expect(ran.text).toBe('Garden score opened in a pane.')

    // The seeds and the superseded link come from the store folder, not from the pointer file at the root.
    const weeks = w.store.get('weeks') as GardenWeek[]
    expect(weeks[0]?.activeSeeds).toBe(4)
    expect(weeks[0]?.values.stale).toBe(1)
    const ui = await $.ui.mount(PANE('terminal'))
    expect((await ui.find({ type: 'Text', text: /4 active seeds/ })) !== undefined).toBe(true)
    expect((await ui.find({ type: 'Text', text: /seed_replaced/ })) !== undefined).toBe(true)
    // compressions/ and git stay with the repo root.
    expect((await ui.find({ type: 'Text', text: /Last compression log 17 days ago/ })) !== undefined).toBe(true)
    expect(w.gitCwds.length >= 2).toBe(true)
    expect(w.gitCwds.every(cwd => cwd === layout.root)).toBe(true)
    await ui.unmount()

    const text = (await $.command.run({ command: 'garden-score', args: 'text' } as any)).text ?? ''
    expect(text.includes('could not be listed')).toBe(false)
    expect(text.includes('No compressions folder')).toBe(false)
    expect(text.includes('No memory repo found')).toBe(false)
  })
}
