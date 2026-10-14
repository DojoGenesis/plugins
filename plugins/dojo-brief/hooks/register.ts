import type { Register } from 'claude-code'

// dojo-brief mod (early access). Lints the brief of every subagent dispatch against the six fields the suite's
// `dojo-protocol:delegate` skill asks for: Goal, Owned files, Done-check, Facts (path:line), Return shape, Rules
// carried. A thin brief is the root cause of stalled subagents and unusable returns, and the subagent sees nothing
// but the brief.
//
// What it can see from the text alone: that the brief is not a one-liner, that it names files, that it says what
// done is, and that it says what to send back. It does not try to judge Goal, Facts or Rules: those are prose, and a
// lint that guessed at them would only teach the model to pad. So four checks, deliberately loose:
//   detail       the prompt is at least `min_chars` characters
//   owned files  a path-like token, or wording that scopes files or a directory
//   done-check   a verify/test/build/check wording, or "done means"
//   return shape a return/report/output wording
// Read-only agent types (the four orchestration mods share this list) write nothing, so a done-check is not asked of them. A fork inherits the
// parent's whole context and is never linted.
//
// Modes (option `mode`):
//   notice    (default) pass the dispatch on and log one dim line naming what is missing
//   sendback  refuse the FIRST dispatch whose brief misses a field, once per description; a second dispatch with the
//             same description goes through (what is still missing is logged)
//   off       pass everything
// The command is `/dojo-brief`, not `/brief`: Claude Code ships its own `/brief` (toggle brief-only mode), a name a
// plugin cannot register (`claude plugin validate` stops calling the hook "answers its own command").
// It does not touch model routing: dojo-router fills `model` in. It stands down under DOJO_OFF / DOJO_BRIEF_OFF.
// The judgement happens before `next` is called: a foreground subagent keeps `next` waiting until it is done.

type Mode = 'notice' | 'sendback' | 'off'
type Field = 'thin' | 'files' | 'done' | 'return'

const FIELDS: readonly Field[] = ['thin', 'files', 'done', 'return']

// The names `$.env.get` may read must be string literals, so each is spelled out here.
type EnvReader = { env: { get: (name: string) => Promise<string | undefined> } }
type Logger = { ui: { log: (text: string) => void } }

const isOn = (value: string | undefined): boolean =>
  typeof value === 'string' && ['1', 'true', 'yes'].includes(value.trim().toLowerCase())

async function standDown($: EnvReader): Promise<boolean> {
  const off = await $.env.get('DOJO_OFF')
  const briefOff = await $.env.get('DOJO_BRIEF_OFF')
  return isOn(off) || isOn(briefOff)
}

function say($: Logger, text: string): void {
  $.ui.log(text)
}

function asMode(value: unknown): Mode {
  const text = typeof value === 'string' ? value.trim().toLowerCase() : ''
  return text === 'sendback' || text === 'off' ? text : 'notice'
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

function asMinChars(value: unknown): number {
  const n = typeof value === 'number' ? value : typeof value === 'string' ? Number(value.trim()) : NaN
  return Number.isFinite(n) && n >= 0 ? Math.floor(n) : 200
}

// ------------------------------------------------------------------------------------------------ the lint

// Agent types not expected to write (the four orchestration mods share this list).
const READ_ONLY = new Set([
  'Explore',
  'Plan',
  'claude-code-guide',
  'statusline-setup',
  'dojo-protocol:scout',
  'dojo-protocol:reviewer',
  'dojo-protocol:judge',
])
const READ_ONLY_SUFFIX = [':scout', ':reviewer', ':judge', ':researcher']

function typeOf(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function isReadOnly(type: string): boolean {
  return READ_ONLY.has(type) || READ_ONLY_SUFFIX.some(suffix => type.endsWith(suffix))
}

const EXTENSIONS = 'tsx?|jsx?|mjs|cjs|py|go|rs|mdx?|json|ya?ml|toml|sh|css|html?|sql|txt'
// A bare file name with a known extension (register.ts). Frameworks spelled "Node.js" are not files.
const BARE_FILE = new RegExp(`^[\\w@-][\\w@.-]*\\.(?:${EXTENSIONS})$`, 'i')
const NOT_A_FILE = /^(?:node|next|vue|react|three|d3|p5|chart|express|nuxt|alpine|ember|backbone|socket|chart)\.js$/i
const HAS_EXTENSION = new RegExp(`\\.(?:${EXTENSIONS})$`, 'i')

// Wording that scopes the files: "Files:", "Owned files", "files you own", "directory", "write only", ...
const FILES_WORDING =
  /\b(?:owned\s+files?|files?\s+you\s+own|you\s+own|you\s+may\s+(?:write|edit)|write\s+only|only\s+(?:write|edit)|read[- ]only|directory|directories|folder|do\s+not\s+(?:edit|touch|write))\b|\b(?:files?|paths?|dirs?)\s*:/i

const DONE_WORDING = [
  /\bdone(?:-check|\s+means|\s+when|:)/i,
  /\b(?:verify|verified|verification|passes|pass|exit\s+0|exit\s+code)\b/i,
  /\brun\s+`?[\w./-]+/i,
  /\b(?:tests?|builds?|checks?|lint|tsc|pytest|assert)\b/i,
]

const RETURN_WORDING =
  /\b(?:return|returns|report|reply\s+with|respond\s+with|output|deliver|hand\s+back|send\s+back|answer\s+with)\b/i

// Does one whitespace-separated token look like a path?
function looksLikePath(raw: string): boolean {
  const token = raw
    .replace(/^[`'"(\[<{]+/, '')
    .replace(/[`'")\]>},;:!?.]+$/, '')
    .replace(/:\d+(?:-\d+)?$/, '')
  if (token === '' || token.includes('://')) return false
  if (token.includes('/')) {
    if (/^(?:~|\.{1,2})?\//.test(token)) return token.length > 1
    if (token.endsWith('/')) return /[A-Za-z]/.test(token)
    return HAS_EXTENSION.test(token) || /\/[\w@-]+\.[A-Za-z][A-Za-z0-9]{0,5}$/.test(token)
  }
  return BARE_FILE.test(token) && !NOT_A_FILE.test(token)
}

function namesFiles(prompt: string): boolean {
  if (FILES_WORDING.test(prompt)) return true
  // A backticked path counts even with no extension (`src/hooks`).
  for (const match of prompt.matchAll(/`([^`\n]+)`/g)) {
    const inner = (match[1] ?? '').trim()
    if (inner.includes('/') && !inner.includes('://') && !/\s/.test(inner)) return true
  }
  return prompt.split(/\s+/).some(looksLikePath)
}

const namesDone = (prompt: string): boolean => DONE_WORDING.some(rule => rule.test(prompt))
const namesReturn = (prompt: string): boolean => RETURN_WORDING.test(prompt)

// The fields a brief lacks. A fork inherits the parent's context, so it is never linted.
function lint(prompt: string, subagentType: string, minChars: number): Field[] {
  const type = subagentType === '' ? 'general-purpose' : subagentType
  if (type === 'fork') return []
  const hasFiles = namesFiles(prompt)
  const hasDone = isReadOnly(type) || namesDone(prompt)
  const hasReturn = namesReturn(prompt)
  // The cheap path: a long brief that says all three needs no further look.
  if (prompt.length >= 1500 && hasFiles && hasDone && hasReturn) return []
  const missing: Field[] = []
  if (prompt.length < minChars) missing.push('thin')
  if (!hasFiles) missing.push('files')
  if (!hasDone) missing.push('done')
  if (!hasReturn) missing.push('return')
  return missing
}

function label(field: Field, minChars: number): string {
  if (field === 'thin') return `detail (under ${minChars} chars)`
  if (field === 'files') return 'owned files'
  if (field === 'done') return 'done-check'
  return 'return shape'
}

const nameOf = (list: readonly Field[], minChars: number): string => list.map(f => label(f, minChars)).join(', ')

// How the brief is called in a line: its description, kept short.
function titleOf(description: unknown, type: string, prompt: string): string {
  const text = typeof description === 'string' ? description.trim() : ''
  const base = text !== '' ? text : type !== '' ? type : prompt.trim().slice(0, 40)
  const one = base.replace(/\s+/g, ' ')
  return one.length > 60 ? `${one.slice(0, 57)}...` : one === '' ? 'subagent' : one
}

// The key a sent-back description is remembered under.
function keyOf(description: unknown, prompt: string): string {
  const text = typeof description === 'string' ? description.trim().toLowerCase() : ''
  return text !== '' ? text : prompt.trim().slice(0, 80).toLowerCase()
}

// ------------------------------------------------------------------------------------------------ the template

const TEMPLATE = `## Goal
<One outcome, and why it matters. What is out of scope.>

## Owned files (write only these)
- \`<path>\`
- \`<path>\`
You may read anything. If the job needs a file that is not on this list, stop and report what you need and why. Do not edit it.

## Done-check
Run this in this session and show the output and exit code:
\`<command>\`
Pass means: <exit 0 / these lines appear>. Do not pipe it through tail, head or grep.

## Facts already established
- \`<path:line>\`: <what is there>
- Decision (from <contract file>): <one line>

## Return shape
- Files changed
- Commands run, with exit codes
- Anything unfinished, and why
- Keep it under <N> lines. Anything bigger goes to \`<path>\`; reply with the path and one line.

## Rules you carry
- Read before you edit; keep context small (grep first, read excerpts).
- Done means the done-check ran and you showed its result.
- Cite \`path:line\` for facts about the code.
- No git add, commit or push unless this brief says so.
- If a fix fails twice for the same reason, stop and state the causal chain and the smallest experiment.
`

type PromptFiller = {
  prompt: { fill: (input: { text: string; mode?: 'insert' | 'append' | 'replace' }) => Promise<{ isFilled: boolean }> }
}

// Puts the template in the prompt box at the cursor. When the box cannot take it, the template is the answer.
// Command answers carry no `dojo-brief:` lead: the engine already heads a plugin command's output with its name.
async function insertTemplate($: PromptFiller): Promise<string> {
  let isFilled = false
  try {
    isFilled = (await $.prompt.fill({ text: TEMPLATE, mode: 'insert' })).isFilled
  } catch (_err) {
    isFilled = false
  }
  return isFilled ? 'Template inserted in the prompt.' : `The prompt box would not take the template; here it is.\n\n${TEMPLATE}`
}

// ------------------------------------------------------------------------------------------------ the module

type Tally = {
  linted: number
  complete: number
  missing: number
  sentBack: number
  forks: number
  byField: Record<Field, number>
}

const freshTally = (): Tally => ({
  linted: 0,
  complete: 0,
  missing: 0,
  sentBack: 0,
  forks: 0,
  byField: { thin: 0, files: 0, done: 0, return: 0 },
})

const plural = (n: number, word: string): string => `${n} ${word}${n === 1 ? '' : 's'}`

function statsText(tally: Tally, mode: Mode, minChars: number): string {
  if (tally.linted === 0 && tally.forks === 0) {
    return `No subagent briefs linted yet this session (mode ${mode}).`
  }
  const lines = [
    `${plural(tally.linted, 'brief')} linted, ${tally.complete} complete, ${tally.missing} missing a field (mode ${mode}).`,
  ]
  if (tally.missing > 0) {
    const parts = FIELDS.filter(f => tally.byField[f] > 0).map(f => `${label(f, minChars)} ${tally.byField[f]}`)
    lines.push(`Missing by field: ${parts.join(', ')}.`)
  }
  if (tally.sentBack > 0) lines.push(`Sent back once: ${tally.sentBack}.`)
  if (tally.forks > 0) lines.push(`Forks skipped: ${tally.forks}.`)
  return lines.join('\n')
}

export const register: Register = (on, options) => {
  // lint_briefs false switches the lint off (as mode off); /dojo-brief still answers.
  const mode: Mode = asFlag(options.lint_briefs, true) ? asMode(options.mode) : 'off'
  const minChars = asMinChars(options.min_chars)

  // Per session activation: a reload of the plugin (an options change) starts the count again.
  const tally = freshTally()
  // Descriptions already sent back once (lowercased, trimmed).
  const sentBack = new Set<string>()

  on('tool.call', { tool: 'Agent' }, async ($, e, next) => {
    if (mode === 'off' || (await standDown($))) return next(e)
    const prompt = typeof e.prompt === 'string' ? e.prompt : ''
    const type = typeOf(e.subagent_type)
    if (type === 'fork') {
      tally.forks += 1
      return next(e)
    }
    const missing = lint(prompt, type, minChars)
    tally.linted += 1
    if (missing.length === 0) {
      tally.complete += 1
      return next(e)
    }
    tally.missing += 1
    for (const field of missing) tally.byField[field] += 1
    const title = titleOf(e.description, type, prompt)
    const names = nameOf(missing, minChars)

    if (mode === 'sendback') {
      const key = keyOf(e.description, prompt)
      if (!sentBack.has(key)) {
        sentBack.add(key)
        tally.sentBack += 1
        say($, `sent back '${title}': its brief is missing ${names}. A second dispatch with the same description goes through.`)
        return {
          deny: `dojo-brief: this brief is missing ${names}. A brief carries Goal, Owned files, Done-check, Facts (path:line), Return shape, Rules carried (dojo-protocol:delegate). Rewrite it and dispatch again; a second dispatch with the same description goes through.`,
        }
      }
      say($, `'${title}' went through after one send-back; its brief is still missing: ${names} (dojo-protocol:delegate)`)
      return next(e)
    }

    say($, `'${title}' brief is missing: ${names} (dojo-protocol:delegate)`)
    return next(e)
  }).catch(($, e, next) => next(e))

  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'dojo-brief',
      description: 'Insert the six-field subagent brief template in the prompt, or show this session’s brief lint tally',
      argumentHint: '[stats]',
      immediate: true,
    })
    return next(e)
  }).catch(($, e, next) => next(e))

  on('command.run', { command: ['dojo-brief', 'dojo-brief:brief'] }, async ($, e) => {
    try {
      if (await standDown($)) {
        return { text: 'Off (DOJO_OFF or DOJO_BRIEF_OFF is set). Unset it and start a new session to turn it back on.' }
      }
      const arg = (typeof e.args === 'string' ? e.args : '').trim().toLowerCase()
      if (arg === 'stats') return { text: statsText(tally, mode, minChars) }
      if (arg !== '') return { text: `Unknown argument "${arg.slice(0, 20)}". Use /dojo-brief for the template or /dojo-brief stats for the tally.` }
      return { text: await insertTemplate($) }
    } catch (_err) {
      return { text: 'The /dojo-brief command failed; the brief lint itself is unaffected.' }
    }
  })
}
