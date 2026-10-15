// Pure logic for dojo-fixcards: reading a guard's refusal text. No engine calls here.

export type Refusal = {
  // The guard's plugin name: 'dojo-gates', 'dojo-lanes', ...
  mod: string
  // The guard's rule id when the text carries one ('staging'), else null.
  rule: string | null
  // The sentence(s) saying why, without the fix sentences.
  reason: string
  // The fix sentence(s) as prose.
  advice: string
  // The backticked spans of the fix sentences, minus spans that only quote the refused command.
  fixes: string[]
  // A VAR=value override the text names, e.g. 'DOJO_GATES_SKIP=staging'.
  allow: string | null
  // For dojo-lanes: the file and the holder's name.
  path: { file: string; holder: string; claimed: string | null } | null
  raw: string
}

const MOD = /(?:^|[\s:])(dojo-[a-z0-9]+(?:-[a-z0-9]+)*): /
const RULE = /^([a-z0-9]+(?:-[a-z0-9]+)*) — /
const LANE = /^(.+?) is in (.+?)'s lane(?: \(claimed (.+?) ago\))?\.\s*/
const ALLOW = /\b([A-Z][A-Z0-9_]*_[A-Z0-9_]*=[A-Za-z0-9_.,:\/-]*[A-Za-z0-9_])/

// Sentence cut: a full stop, then a space and a capital letter or a backtick-free start.
function sentences(text: string): string[] {
  return text
    .split(/(?<=[.!?])\s+(?=[A-Z])/)
    .map(s => s.trim())
    .filter(s => s !== '')
}

const spansOf = (text: string): string[] => {
  const out: string[] = []
  for (const m of text.matchAll(/`([^`]+)`/g)) { const span = m[1] ?? ''; if (span !== '' && !out.includes(span)) out.push(span) }
  return out
}

export function parseRefusal(text: string): Refusal | null {
  if (typeof text !== 'string') return null
  const hit = MOD.exec(text)
  if (hit === null) return null
  const mod = hit[1] ?? ''
  let rest = text.slice(hit.index + hit[0].length).trim()
  const allowMatch = ALLOW.exec(rest)
  const allow = allowMatch === null ? null : (allowMatch[1] ?? null)

  const base = { mod, allow, raw: text }
  const lane = LANE.exec(rest)
  if (lane !== null && mod === 'dojo-lanes') {
    const after = sentences(rest.slice(lane[0].length))
    // The last sentence is the instruction ("Don't write it: ..."), the rest says why.
    const advice = after.length > 1 ? (after[after.length - 1] ?? '') : ''
    const reason = after.length > 1 ? after.slice(0, -1).join(' ') : after.join(' ')
    return { ...base, rule: null, reason, advice, fixes: spansOf(advice), path: { file: lane[1] ?? '', holder: lane[2] ?? '', claimed: lane[3] ?? null } }
  }

  let rule: string | null = null
  const ruled = RULE.exec(rest)
  if (ruled !== null) {
    rule = ruled[1] ?? null
    rest = rest.slice(ruled[0].length)
  }
  const parts = sentences(rest)
  // An override sentence ("To allow it on purpose, set ...") is the allow line, not a fix.
  const body = parts.filter(s => !/^To allow it on purpose/i.test(s))
  if (rule === null || body.length < 2) {
    return { ...base, rule, reason: body.join(' '), advice: '', fixes: [], path: null }
  }
  const reason = body[0] ?? ''
  const advice = body.slice(1).join(' ')
  return { ...base, rule, reason, advice, fixes: spansOf(advice), path: null }
}

// The text of an errored result, whatever shape the engine hands over.
export function textOf(value: unknown, depth = 0): string {
  if (typeof value === 'string') return value
  if (depth > 3 || value === null || typeof value !== 'object') return ''
  if (Array.isArray(value)) return value.map(v => textOf(v, depth + 1)).filter(s => s !== '').join('\n')
  const rec = value as Record<string, unknown>
  for (const key of ['text', 'error', 'message', 'stderr', 'content']) {
    const got = textOf(rec[key], depth + 1)
    if (got !== '') return got
  }
  return ''
}

export const isOn = (value: string | undefined): boolean => /^(1|true|yes|on)$/i.test((value ?? '').trim())

export function statusLine(isOff: boolean, drawn: number): string {
  return `${isOff ? 'off' : 'on'} · ${drawn} card${drawn === 1 ? '' : 's'} drawn this session`
}
