import type { Register } from 'claude-code'
import { PATTERNS } from './patterns'

// dojo-verify mod (early access). The classic Stop hook is the plugin's core: it can block a "done" that has no
// check behind it. The mod adds what only the engine sees, and it can only show, never block:
//  - a session ledger of the main-loop tool calls, taken from tool.call: the last change (an edit tool, or a Bash
//    command that writes files) and whether a clean check ran after it. An UNVERIFIED status (and toast) shows
//    when the final answer claims success and the ledger has a change with no clean check after it. A session
//    with no change in it is not judged;
//  - a count of subagents: dispatched, returned (a non-empty answer), failed, and still outstanding.
// It makes no model calls. It stands down under DOJO_OFF / DOJO_VERIFY_OFF and when mode is `off`.
//
// The claim and check patterns are the same table the classic hook reads (hooks/patterns.json, copied into
// patterns.ts by scripts/sync_patterns.py); the algorithms below are line-for-line ports of stop_evidence.py,
// and tests/cases.json runs through both. This process runs the claim patterns on every main-thread answer, so
// the text they read is capped (its start and its end, see limits in patterns.json) and none of them can be slow.
//
// Rule for every hook below: the work that has to happen once (next) happens once. Recording runs after
// `await next(e)` inside try/catch, and the hook returns what next returned, untouched. A catch that calls
// next again would run the tool or start the agent a second time.

const P: any = PATTERNS

type Claim = { tier: 'strong' | 'weak'; word: string; sentence: string }
type Ledger = { mutated: boolean; ok: boolean }
type Seg = [string, string]
// [kind, level, handler phrase]: a 'mut' changes files; a 'check' at level 0 counts, at level 1 it is masked
// (needs visible clean output), at level 2 it is masked and its stdout goes to a file
type Event = ['check' | 'mut', number, string]
type Kind = { kind: 'check' } | { kind: 'mut' } | { kind: 'shell'; inner: string }

const WS = ' \t\r\n\f\v'
const ENV_ASSIGN = /^[A-Za-z_][A-Za-z0-9_]*=/
const DURATION = /^\d+(?:\.\d+)?[smhd]?$/
const TOKEN = /[\w']+/g
const FENCE = /```[\s\S]*?```/g
const STRAY_FENCE = /```[^\n]*/g
const INLINE_CODE = /`[^`\n]*`/g
const REDIRECT_FD = /\d*>&\d+/g
const REDIRECT_ERR = /(?<![\w])2>>?\s*[^\s;&|<>]+/g
const REDIRECT_OUT = /(?:&>>?|\d*>>?\|?)\s*([^\s;&|<>]+)/g
const QUOTED = /'[^']*'|"(?:\\.|[^"\\])*"/g
const HEREDOC = /(?<!<)<<(-?)\s*(['"]?)([A-Za-z_]\w*)\2/g
const MARK = '\u0001'
const MARKED = new RegExp(MARK + '(\\d+)' + MARK, 'g')
const MAX_QUOTE = 60

// ------------------------------------------------------------------------------------------------ patterns

function claimRx(body: string): RegExp {
  return new RegExp(P.claim_edges.before + '(?:' + body + ')' + P.claim_edges.after, 'gi')
}

const STRONG: RegExp[] = P.strong.map(claimRx)
const WEAK: RegExp[] = P.weak.map(claimRx)
const DISCLOSURE: RegExp[] = P.disclosure.map((b: string) => new RegExp(b, 'i'))
const FRAMES: RegExp[] = P.disclosure_frames.map((b: string) => new RegExp(b, 'gi'))
const HISTORY_BEFORE = new RegExp(P.history.before, 'i')
const HISTORY_AFTER = new RegExp(P.history.after, 'i')
const HISTORY_PAST_FRAME = new RegExp(P.history.past_frame, 'i')
const HISTORY_PAST_BEFORE = new RegExp(P.history.past_before, 'i')
const HISTORY_PAST_NEAR = new RegExp(P.history.past_near, 'i')
const HISTORY_PAST_AFTER = new RegExp(P.history.past_after, 'i')
const Q_LEAD = new RegExp(P.question.lead, 'i')
const Q_MID = new RegExp(P.question.mid, 'i')
const Q_SOFT = new RegExp(P.question.soft_boundary, 'gi')
const Q_HARD = new RegExp(P.question.hard_boundary, 'gi')
const Q_ASSERTING = new RegExp(P.question.asserting, 'i')
const CLAUSE_BREAK = new RegExp(P.clause_break, 'gi')
const LIMITS = P.limits
const FAILURE = new RegExp(P.failure_markers)
const NEGATORS = new Set<string>(P.negators)
const CUT_WORDS = new Set<string>(P.negation_cut_words)
const CUT_CHARS: string = P.negation_cut_chars
const FUTURE = new Set<string>(P.future_before)
const FUTURE_PHRASES = new Set<string>(P.future_phrases.map((x: string[]) => x.join(' ')))
const NEGATED_AFTER = new Set<string>(P.negated_after)
const WEAK_SKIP = new Set<string>(P.weak_skip_before.words)
const ATTRIBUTIVE_WORDS = new Set<string>(P.attributive.words)
const ATTRIBUTIVE_BEFORE = new Set<string>(P.attributive.before)

const CHECK = P.check
const CHECK_ANY = new Set<string>(CHECK.any)
const CHECK_SUB: Record<string, string[][]> = {}
for (const k of Object.keys(CHECK.sub)) CHECK_SUB[k] = CHECK.sub[k].map((v: string) => v.split(/\s+/))
const CHECK_FLAG: Record<string, string[]> = CHECK.flag
const ALIASES: Record<string, string> = CHECK.aliases
const SCRIPT_RUNNERS = new Set<string>(CHECK.script_runners)
const SCRIPT_RE = new RegExp(CHECK.script_pattern)
const SCRIPT_SKIP = new Set<string>(CHECK.script_skip_first)
const TASK_RUNNERS = new Set<string>(CHECK.task_runners)
const TASK_RE = new RegExp(CHECK.task_pattern)
const PREFIX_WRAPPERS = new Set<string>(CHECK.prefix_wrappers)
const TIMEOUT_WRAPPERS = new Set<string>(CHECK.timeout_wrappers)
const WRAPPER_PAIRS: string[][] = CHECK.wrapper_pairs
const SHELL_C = new Set<string>(CHECK.shell_c)
const SHELL_RESERVED = new Set<string>(CHECK.shell_reserved)
const LOOP_WORDS = new Set<string>(CHECK.loop_words)
const PYTHON_RE = new RegExp(CHECK.python_re)
const ERREXIT_RE = new RegExp(CHECK.errexit_re)
const PIPEFAIL_RE = new RegExp(CHECK.pipefail_re)
const BROWSER_RE = new RegExp(CHECK.browser_tool_re, 'i')
const NOOP_FLAGS = new Set<string>(CHECK.noop_flags)
const TASK_NOOP_FLAGS = new Set<string>(CHECK.task_noop_flags)
const VAR_SUFFIXES: string[] = CHECK.var_program_suffixes
const INTERPRETERS = new Set<string>(CHECK.interpreters)
const SCRIPT_EXTS = new Set<string>(CHECK.script_exts)
const SCRIPT_DIRS = new Set<string>(CHECK.script_dirs)
const SCRIPT_DIR_NAME_RE = new RegExp(CHECK.script_dir_name_re, 'i')
const SCRIPT_SKIP_DIRS = new Set<string>(CHECK.script_skip_dirs)
const SCRIPT_NAME_RE = new RegExp(CHECK.script_name_re, 'i')
const INLINE_INTERPRETERS = new Set<string>(CHECK.inline_interpreters)
const INLINE_FLAGS = new Set<string>(CHECK.inline_code_flags)

const MUTATE = P.mutate
const MUT_TOOLS = new Set<string>(MUTATE.tools)
const MUT_PROGRAMS = new Set<string>(MUTATE.programs)
const MUT_SUB: Record<string, string[][]> = {}
for (const k of Object.keys(MUTATE.sub)) MUT_SUB[k] = MUTATE.sub[k].map((v: string) => v.split(/\s+/))
const MUT_FLAG_PREFIX: Record<string, string[]> = MUTATE.flag_prefix
const SINK_PROGRAMS = new Set<string>(MUTATE.sink_programs)
const NULL_TARGETS = new Set<string>(MUTATE.null_targets)
const DEST_PROGRAMS = new Set<string>(MUTATE.dest_programs)
const XARGS_VALUE = new Set<string>(MUTATE.xargs_value_flags)
const TEMP_PREFIXES: string[] = MUTATE.temp_prefixes
const REFUSED = new RegExp(MUTATE.refused_markers, 'i')
const NOT_FOUND = new RegExp(MUTATE.not_found_re, 'gi')
const NOT_FOUND_SKIP = new Set<string>(MUTATE.not_found_skip)
const INTERP_WRITE = new RegExp(MUTATE.interp_write_re)

// ------------------------------------------------------------------------------------------------ claims

function normalizeText(text: string): string {
  return text
    .replace(FENCE, ' ')
    .replace(STRAY_FENCE, ' ') // an unclosed fence hides only its own line, not the rest of the message
    .replace(INLINE_CODE, ' ')
    .replace(/’/g, "'")
    .replace(/‘/g, "'")
    .replace(/“/g, '"')
    .replace(/”/g, '"')
}

function splitSentences(text: string): Array<[string, string]> {
  const out: Array<[string, string]> = []
  let cur: string[] = []
  const n = text.length
  for (let i = 0; i < n; i++) {
    const ch = text[i] as string
    if (ch === '\n') {
      out.push([cur.join(''), ''])
      cur = []
    } else if (ch === '.' || ch === '!' || ch === '?') {
      let j = i
      while (j + 1 < n && '.!?'.includes(text[j + 1] as string)) j++
      const nxt = j + 1 < n ? (text[j + 1] as string) : ''
      cur.push(text.slice(i, j + 1))
      if (nxt === '' || WS.includes(nxt)) {
        out.push([cur.join(''), text[j] as string])
        cur = []
      }
      i = j
    } else {
      cur.push(ch)
    }
  }
  if (cur.length > 0) out.push([cur.join(''), ''])
  return out
}

function words(text: string): string[] {
  return text.toLowerCase().match(TOKEN) ?? []
}

function guarded(sentence: string, index: number, matched: string, tier: string): boolean {
  let prefix = sentence.slice(0, index)
  let cut = -1
  for (const c of CUT_CHARS) cut = Math.max(cut, prefix.lastIndexOf(c))
  if (cut >= 0) prefix = prefix.slice(cut + 1)
  let ws = words(prefix)
  for (let i = ws.length - 1; i >= 0; i--) {
    if (CUT_WORDS.has(ws[i] as string)) { // "No regressions and all tests pass": the 'no' belongs to the first clause
      ws = ws.slice(i + 1)
      break
    }
  }
  for (const w of ws.slice(-P.negation_window)) if (NEGATORS.has(w) || w.endsWith("n't")) return true
  const near = ws.slice(-P.future_window)
  for (const w of near) if (FUTURE.has(w) || w.endsWith("'ll")) return true
  for (let i = 0; i < near.length - 1; i++) if (FUTURE_PHRASES.has((near[i] as string) + ' ' + (near[i + 1] as string))) return true // "yet to be deployed"
  if (tier === 'weak') {
    for (const w of ws.slice(-P.weak_skip_before.window)) if (WEAK_SKIP.has(w)) return true
  } else if (ws.length > 0 && ATTRIBUTIVE_BEFORE.has(ws[ws.length - 1] as string) && ATTRIBUTIVE_WORDS.has(matched.toLowerCase())) {
    return true // "a fixed seed", "the deployed copy": the word describes a noun, it does not claim anything
  }
  const after = /^\s*([\w']+)/.exec(sentence.slice(index + matched.length))
  return after !== null && NEGATED_AFTER.has((after[1] as string).toLowerCase())
}

function headTail(text: string, head: number, tail: number): string {
  return text.length <= head + tail ? text : text.slice(0, head) + '\n' + text.slice(text.length - tail)
}

// [start, end) spans of the clauses of one sentence, cut at ';' and before 'but', 'and', 'though' ...
function splitClauses(sentence: string): Array<[number, number]> {
  const spans: Array<[number, number]> = []
  let start = 0
  for (const m of sentence.matchAll(CLAUSE_BREAK)) {
    const at = m.index as number
    spans.push([start, at])
    start = at + m[0].length
  }
  spans.push([start, sentence.length])
  return spans
}

// A disclosure excuses the claims in its own clause and in the clause beside it, and nothing further away.
function excused(pos: number, spans: Array<[number, number]>, flags: boolean[]): boolean {
  for (let i = 0; i < spans.length; i++) {
    if (pos < (spans[i] as [number, number])[1] || i === spans.length - 1) {
      return flags.slice(Math.max(0, i - 1), i + 2).some(f => f)
    }
  }
  return false
}

// Is this frame telling how the bug came about, rather than the state of this work? A time marker around it
// ('previously', 'until now', 'in the original PR', 'ago') makes it a history. So does a cause, for a frame in the
// past tense ('never', "didn't", 'was not'): 'because' before it, 'since', 'as', 'when' right before it, or 'until',
// 'hence', 'which broke ...' after it. A frame about the present or about being unable ("I haven't run it", "I
// couldn't run it") has a reason, not a cause: 'Because Docker is down, I couldn't run the tests' is a disclosure.
function isHistory(pre: string, post: string, frame: string): boolean {
  if (HISTORY_BEFORE.test(pre) || HISTORY_AFTER.test(post)) return true
  if (HISTORY_PAST_FRAME.test(frame)) return HISTORY_PAST_BEFORE.test(pre) || HISTORY_PAST_NEAR.test(pre) || HISTORY_PAST_AFTER.test(post)
  return false
}

// Does this clause say, explicitly, that the work is unverified, untested or was not run? 'unverified' and 'untested'
// say it outright. A first-person frame ('I didn't run the tests', 'it hasn't been tested') says it too, unless the
// clause is telling a history: 'it failed because we never ran the migration', 'we didn't test it before'. Those
// describe how the bug came about, not the state of this fix.
function clauseDiscloses(text: string): boolean {
  if (DISCLOSURE.some(rx => rx.test(text))) return true
  for (const rx of FRAMES) {
    for (const m of text.matchAll(rx)) {
      const at = m.index as number
      if (isHistory(text.slice(0, at), text.slice(at + m[0].length), m[0])) continue
      return true
    }
  }
  return false
}

// What comes before the question in a sentence that ends in '?', or null when the sentence is all question. 'Is it
// fixed?' claims nothing. 'Fixed it and all tests pass, want me to commit?' claims something and then asks: the
// claim part is what gets judged. The question starts at the first ',', ';', dash or conjunction followed by a
// question opener ('want me', 'should I', 'right'); failing that, the last ',', ';' or dash starts it. A question
// with none of those has no claim part.
//
// A sentence that opens with a question word can still assert something after a subordinator that takes the claim
// as given: 'Want me to commit now that all tests pass?', 'Should I push, since the build is green?'. The claim part
// is what follows it. ('Should be fixed now', with nothing after 'should' to ask about, is not a question opener.)
function questionClaimPart(sentence: string): string | null {
  if (Q_LEAD.test(sentence)) {
    const a = Q_ASSERTING.exec(sentence)
    const tail = a === null ? '' : sentence.slice(a.index + a[0].length)
    return tail.trim() === '' ? null : tail
  }
  let cut = -1
  for (const m of sentence.matchAll(Q_SOFT)) {
    if (Q_MID.test(sentence.slice((m.index as number) + m[0].length))) {
      cut = m.index as number
      break
    }
  }
  if (cut < 0) for (const m of sentence.matchAll(Q_HARD)) cut = m.index as number
  if (cut <= 0) return null
  const head = sentence.slice(0, cut)
  return head.trim() === '' ? null : head
}

// A session with no change in it (no edit, no write, no file-writing command) is never judged. A question is not a
// claim, but a claim followed by a question in the same sentence is still judged. A disclosure excuses the claims in
// its own clause and the clause beside it, within one sentence; every other negation applies per claim. Only the
// start and the end of a very long message are read.
function detectClaim(text: string, mutated: boolean): Claim | null {
  if (!mutated || typeof text !== 'string' || text.trim() === '') return null
  let sentences = splitSentences(normalizeText(headTail(text, LIMITS.raw_head, LIMITS.raw_tail)))
  if (sentences.length > LIMITS.max_sentences_head + LIMITS.max_sentences_tail) {
    sentences = [...sentences.slice(0, LIMITS.max_sentences_head), ...sentences.slice(sentences.length - LIMITS.max_sentences_tail)]
  }
  for (const [raw, term] of sentences) {
    if (raw.trim() === '') continue
    let s = headTail(raw, LIMITS.sentence_head, LIMITS.sentence_tail)
    if (term === '?') {
      const part = questionClaimPart(s)
      if (part === null) continue
      s = part
    }
    const spans = splitClauses(s)
    const flags = spans.map(([a, b]) => clauseDiscloses(s.slice(a, b)))
    const anyDisclosure = flags.some(f => f)
    for (const tier of ['strong', 'weak'] as const) {
      for (const rx of tier === 'strong' ? STRONG : WEAK) {
        for (const m of s.matchAll(rx)) {
          if (anyDisclosure && excused(m.index as number, spans, flags)) continue
          if (!guarded(s, m.index as number, m[0], tier)) return { tier, word: m[0], sentence: s.trim() }
        }
      }
    }
  }
  return null
}

function quote(sentence: string): string {
  let s = sentence.replace(/[\x00-\x1f\x7f\s]+/g, ' ').trim().replace(/"/g, "'")
  if (s.length > MAX_QUOTE) s = s.slice(0, MAX_QUOTE - 3).trimEnd() + '...'
  return s
}

// ------------------------------------------------------------------------------------------------ checks

function splitSegments(cmd: string): Seg[] {
  const segs: Seg[] = []
  const cur: string[] = []
  const n = cmd.length
  let quoteChar = ''
  let depth = 0
  const push = (op: string): void => {
    segs.push([cur.join('').trim(), op])
    cur.length = 0
  }
  for (let i = 0; i < n; i++) {
    const c = cmd[i] as string
    const nxt = i + 1 < n ? (cmd[i + 1] as string) : ''
    if (quoteChar !== '') {
      cur.push(c)
      if (c === '\\' && quoteChar === '"' && nxt !== '') {
        cur.push(nxt)
        i++
      } else if (c === quoteChar) {
        quoteChar = ''
      }
    } else if (c === '\\' && nxt !== '') {
      cur.push(c, nxt)
      i++
    } else if (c === "'" || c === '"') {
      quoteChar = c
      cur.push(c)
    } else if (c === '#' && (cur.length === 0 || cur[cur.length - 1] === ' ' || cur[cur.length - 1] === '\t')) {
      while (i + 1 < n && cmd[i + 1] !== '\n') i++
    } else if (c === '$' && nxt === '(') {
      depth++
      cur.push('$(')
      i++
    } else if (c === ')' && depth > 0) {
      depth--
      cur.push(c)
    } else if (depth > 0) {
      cur.push(c)
    } else if (c === '\n') {
      push('\n')
    } else if (c === ';') {
      push(';')
    } else if (c === '&') {
      if (nxt === '&') {
        push('&&')
        i++
      } else if (nxt === '>' || (cur.length > 0 && cur[cur.length - 1] === '>')) {
        cur.push(c)
      } else {
        push('&')
      }
    } else if (c === '|') {
      if (cur.length > 0 && cur[cur.length - 1] === '>') {
        cur.push(c) // '>|' forces a redirect: it is not a pipe
      } else if (nxt === '|') {
        push('||')
        i++
      } else if (nxt === '&') {
        push('|')
        i++
      } else {
        push('|')
      }
    } else {
      cur.push(c)
    }
  }
  push('')
  return segs.filter(s => s[0] !== '')
}

// The subset of POSIX word splitting the classifier needs; null on an unterminated quote.
function shellWords(text: string): string[] | null {
  const out: string[] = []
  let cur = ''
  let inWord = false
  let q = ''
  for (let i = 0; i < text.length; i++) {
    const c = text[i] as string
    const nxt = i + 1 < text.length ? (text[i + 1] as string) : ''
    if (q !== '') {
      if (c === q) q = ''
      else if (q === '"' && c === '\\' && (nxt === '"' || nxt === '\\')) cur += text[++i] as string
      else cur += c
    } else if (c === '\\' && nxt !== '') {
      cur += text[++i] as string
      inWord = true
    } else if (c === "'" || c === '"') {
      q = c
      inWord = true
    } else if (WS.includes(c)) {
      if (inWord) {
        out.push(cur)
        cur = ''
        inWord = false
      }
    } else {
      cur += c
      inWord = true
    }
  }
  if (q !== '') return null
  if (inWord) out.push(cur)
  return out
}

function splitWords(input: string): string[] {
  let text = input.trim()
  while (text.startsWith('(')) text = text.slice(1).trimStart()
  const closes = text.split(')').length - 1
  const opens = text.split('(').length - 1
  if (closes > opens && !text.includes('$(')) text = text.replace(/\)+$/, '').trimEnd()
  return shellWords(text) ?? text.split(/\s+/).filter(t => t !== '')
}

// The words once the shell keywords that open a compound command are off: do, then, else, elif, if, while, { ...
function stripReserved(words: string[]): string[] {
  let k = 0
  while (k < words.length && SHELL_RESERVED.has(words[k] as string)) k++
  return words.slice(k)
}

function tokens(input: string): string[] {
  return stripReserved(splitWords(input))
}

const LOOP_VAR = /^\$(\w+)$|^\$\{(\w+)\}$/

// Remember what 'for x in a b c' iterates over, so a later '$x' can be read as one of those words.
function loopHeader(words: string[], loops: Map<string, string[]>): void {
  if (words.length >= 3 && words[2] === 'in' && /^\w+$/.test(words[1] as string)) loops.set(words[1] as string, words.slice(3))
}

// A loop variable that stands for a check script ('for t in tests/test_*.py; do python3 "$t"') is that script.
function loopValue(token: string, loops: Map<string, string[]>): string {
  const m = LOOP_VAR.exec(token)
  if (m === null) return token
  for (const w of loops.get((m[1] ?? m[2]) as string) ?? []) if (isCheckScript(w)) return w
  return token
}

function base(token: string): string {
  return token.includes('/') ? (token.split('/').pop() as string) : token
}

// [the command without its heredoc bodies, the bodies in the order of their '<<' operators]. A body is text for the
// program that reads it: 'cat > f <<EOF' writes text, 'bash <<EOF' runs it as commands, 'python3 - <<EOF' as code.
function splitHeredocs(cmd: string): [string, string[]] {
  if (!cmd.includes('<<')) return [cmd, []]
  const out: string[] = []
  const bodies: string[] = []
  const pending: Array<[string, boolean, string[]]> = []
  for (const line of cmd.split('\n')) {
    if (pending.length > 0) {
      const [delim, tabs, buf] = pending[0] as [string, boolean, string[]]
      if ((tabs ? line.replace(/^\t+/, '') : line).trim() === delim) {
        bodies.push(buf.join('\n'))
        pending.shift()
      } else {
        buf.push(line)
      }
      continue
    }
    out.push(line)
    for (const m of line.matchAll(HEREDOC)) pending.push([m[3] as string, m[1] === '-', []])
  }
  for (const [, , buf] of pending) bodies.push(buf.join('\n')) // a heredoc that never closes still ran
  return [out.join('\n'), bodies]
}

// [program token, argument tokens] once env assignments and wrappers (env, time, timeout, uv run ...) are off.
function unwrap(input: string[]): [string, string[]] | null {
  let toks = input
  let k = 0
  while (k < toks.length && ENV_ASSIGN.test(toks[k] as string)) k++
  toks = toks.slice(k)
  let settled = false
  for (let n = 0; n < 8; n++) {
    toks = stripReserved(toks) // 'time { rm -rf build; }': the brace opens a group, it is not the program
    if (toks.length === 0) return null
    const prog = base(toks[0] as string)
    if (PREFIX_WRAPPERS.has(prog)) {
      toks = toks.slice(1)
      while (toks.length > 0 && ((toks[0] as string).startsWith('-') || ENV_ASSIGN.test(toks[0] as string))) toks = toks.slice(1)
      continue
    }
    if (TIMEOUT_WRAPPERS.has(prog)) {
      toks = toks.slice(1)
      while (toks.length > 0 && (toks[0] as string).startsWith('-')) toks = toks.slice(1)
      if (toks.length > 0 && DURATION.test(toks[0] as string)) toks = toks.slice(1)
      continue
    }
    let paired = false
    for (const [first, second] of WRAPPER_PAIRS) {
      if (prog === first && toks.length > 1 && toks[1] === second) {
        toks = toks.slice(2)
        while (toks.length > 0 && (toks[0] as string).startsWith('-')) toks = toks.slice(1)
        paired = true
        break
      }
    }
    if (paired) continue
    settled = true
    break
  }
  if (!settled || toks.length === 0) return null
  return [toks[0] as string, toks.slice(1)]
}

// The program a token names: its basename, an alias, or the tool a variable holds ($CLAUDE_BIN -> claude).
function programName(raw: string): string {
  let b = base(raw)
  if (b.startsWith('$')) {
    let name = b.replace(/^\$\{?|\}$/g, '').toLowerCase()
    for (const suffix of VAR_SUFFIXES) {
      if (name.endsWith(suffix)) {
        name = name.slice(0, name.length - suffix.length)
        break
      }
    }
    b = name.replace(/_/g, '-')
  }
  return ALIASES[b] ?? b
}

// A test or check script by its name (test_x.py, a.test.js, scripts/test.sh, release-check.sh), or a runner in a tests
// folder (tests/*.py, tests/run.py). A folder alone doesn't make a script a check: tests/seed.py isn't one. And a script
// under a fixtures, helpers or data folder never is one: those make data for tests, they don't run them.
function isCheckScript(path: string): boolean {
  const parts = path.replace(/\\/g, '/').split('/')
  const name = parts[parts.length - 1] as string
  const dot = name.lastIndexOf('.')
  if (dot <= 0 || !SCRIPT_EXTS.has(name.slice(dot).toLowerCase())) return false
  if (parts.slice(0, -1).some(d => SCRIPT_SKIP_DIRS.has(d))) return false
  const stem = name.slice(0, dot)
  if (SCRIPT_NAME_RE.test(stem)) return true
  return parts.slice(0, -1).some(d => SCRIPT_DIRS.has(d)) && SCRIPT_DIR_NAME_RE.test(stem)
}

function scriptArgIsCheck(args: string[]): boolean {
  for (const a of args) {
    if (a.startsWith('-')) continue
    return isCheckScript(a)
  }
  return false
}

// A check, a nested shell command, or null: is this program run a check?
function classifyCheck(raw: string, input: string[]): Kind | null {
  let prog = programName(raw)
  let args = input
  if (args.some(a => NOOP_FLAGS.has(a))) return null // --version, --help, --collect-only: nothing was checked
  if (raw.includes('/') && isCheckScript(raw)) return { kind: 'check' } // ./scripts/test.sh
  if (SHELL_C.has(prog)) {
    for (let idx = 0; idx < args.length; idx++) {
      const a = args[idx] as string
      if (a.startsWith('-') && !a.startsWith('--') && a.endsWith('c') && idx + 1 < args.length) {
        return { kind: 'shell', inner: args[idx + 1] as string }
      }
    }
    return scriptArgIsCheck(args) ? { kind: 'check' } : null // bash scripts/release-check.sh
  }
  if (PYTHON_RE.test(prog)) {
    const idx = args.slice(0, 4).indexOf('-m')
    if (idx >= 0) {
      if (idx + 1 >= args.length) return null
      const mod = base(args[idx + 1] as string)
      prog = ALIASES[mod] ?? mod
      args = args.slice(idx + 2)
      if (args.some(a => NOOP_FLAGS.has(a))) return null
    } else {
      return scriptArgIsCheck(args) ? { kind: 'check' } : null // python3 tests/test_x.py
    }
  } else if (INTERPRETERS.has(prog) && scriptArgIsCheck(args)) {
    return { kind: 'check' } // node tests/x.test.js
  }
  if (CHECK_ANY.has(prog)) {
    if (prog === 'tsc' && args.includes('--init')) return null
    return { kind: 'check' }
  }
  const nonflag = args.filter(a => !a.startsWith('-'))
  const subs = CHECK_SUB[prog]
  if (subs !== undefined) {
    for (const parts of subs) {
      if (parts.every((part, i) => nonflag[i] === part)) return { kind: 'check' }
    }
  }
  const flags = CHECK_FLAG[prog]
  if (flags !== undefined) {
    for (const f of flags) if (args.includes(f)) return { kind: 'check' }
  }
  if (SCRIPT_RUNNERS.has(prog)) {
    if (nonflag.length === 0 || SCRIPT_SKIP.has(nonflag[0] as string)) return null
    for (const a of nonflag.slice(0, 4)) {
      if (a === 'run' || a === 'run-script' || a === 'exec') continue
      if (SCRIPT_RE.test(a)) return { kind: 'check' }
    }
    for (let i = 0; i < args.length; i++) {
      const a = args[i] as string
      if (a.startsWith('-') || a === 'run' || a === 'run-script' || a === 'exec') continue
      // 'pnpm tsc --noEmit', 'yarn jest': the first real argument is a tool, so classify it as one
      const inner = classify(args.slice(i))
      return inner !== null && inner.kind === 'check' ? inner : null
    }
    return null
  }
  if (TASK_RUNNERS.has(prog)) {
    if (args.some(a => TASK_NOOP_FLAGS.has(a))) return null // make -n test only prints what it would run
    for (const a of nonflag.slice(0, 3)) if (TASK_RE.test(a)) return { kind: 'check' }
    return null
  }
  return null
}

// True for a path in the temp directory: a scratch file, not the project.
function isTemp(path: string): boolean {
  return TEMP_PREFIXES.some(prefix => path.startsWith(prefix) || path === prefix.replace(/\/+$/, ''))
}

// True for 'python3 -c ...' or 'node -e ...' whose code writes, moves or removes files.
function inlineCodeWrites(args: string[]): boolean {
  const i = args.findIndex(a => INLINE_FLAGS.has(a))
  return i >= 0 && args.slice(i + 1).some(x => INTERP_WRITE.test(x))
}

// 'find -delete', or 'find -exec <a program that changes files> ... ;'.
function findMutates(args: string[], depth: number): boolean {
  if (args.some(a => ['-delete', '-fprint', '-fprint0', '-fprintf', '-fls'].includes(a))) return true
  let i = 0
  while (i < args.length) {
    if (['-exec', '-execdir', '-ok', '-okdir'].includes(args[i] as string)) {
      let j = i + 1
      const sub: string[] = []
      while (j < args.length && args[j] !== ';' && args[j] !== '+') {
        sub.push(args[j] as string)
        j++
      }
      if (runMutates(sub, depth)) return true
      i = j
    }
    i++
  }
  return false
}

// The command xargs runs: its arguments once its own options (and their values) are off.
function xargsInner(args: string[]): string[] {
  let i = 0
  while (i < args.length) {
    const a = args[i] as string
    if (a === '--') {
      i++
      break
    }
    if (!a.startsWith('-')) break
    i += XARGS_VALUE.has(a) ? 2 : 1
  }
  return args.slice(i)
}

// tar x..., tar -xzf, tar --extract: it unpacks into the working tree. Listing and creating don't.
function tarExtracts(args: string[]): boolean {
  for (let i = 0; i < args.length; i++) {
    const a = args[i] as string
    if (a === '--extract' || a === '--get' || a.startsWith('--extract=')) return true
    if (a.startsWith('--')) continue
    if (/^-[A-Za-z]*x[A-Za-z]*$/.test(a) || (i === 0 && /^[A-Za-z]*x[A-Za-z]*$/.test(a))) return true
  }
  return false
}

// wget saves a file unless it is told to print to stdout (-O -) or only to look (--spider).
function wgetWrites(args: string[]): boolean {
  for (let i = 0; i < args.length; i++) {
    const a = args[i] as string
    if (a === '--spider' || /^-[A-Za-z]*O-$/.test(a)) return false
    if (/^-[A-Za-z]*O$/.test(a) && i + 1 < args.length && args[i + 1] === '-') return false
  }
  return true
}

// True when this program run changes files: mv, rm, sed -i, git checkout, npm install, a formatter ...
function mutates(raw: string, input: string[], depth = 0): boolean {
  let prog = programName(raw)
  let args = input
  if ((PYTHON_RE.test(prog) || INLINE_INTERPRETERS.has(prog)) && inlineCodeWrites(args)) return true
  if (PYTHON_RE.test(prog) && args.slice(0, 4).includes('-m')) {
    const idx = args.indexOf('-m')
    if (idx + 1 >= args.length) return false
    prog = programName(args[idx + 1] as string)
    args = args.slice(idx + 2)
  }
  const nonflag = args.filter(a => !a.startsWith('-'))
  if (prog === 'find') return findMutates(args, depth)
  if (prog === 'xargs') return runMutates(xargsInner(args), depth)
  if (prog === 'awk' || prog === 'gawk') return args.some(a => a === 'inplace' || a.endsWith('=inplace') || a === '-iinplace')
  if (prog === 'wget') return wgetWrites(args)
  if (prog === 'tar') return tarExtracts(args)
  if (MUT_PROGRAMS.has(prog)) {
    if (nonflag.length > 0 && nonflag.every(isTemp)) return false // it only touches scratch files
    if (DEST_PROGRAMS.has(prog) && nonflag.length > 0 && isTemp(nonflag[nonflag.length - 1] as string)) return false // copies into the temp directory
    return true
  }
  if (SINK_PROGRAMS.has(prog)) return nonflag.some(a => !NULL_TARGETS.has(a) && !isTemp(a)) // 'tee /dev/null' writes nothing
  for (const parts of MUT_SUB[prog] ?? []) {
    if (parts.every((part, i) => nonflag[i] === part)) return true
  }
  for (const pref of MUT_FLAG_PREFIX[prog] ?? []) {
    if (args.some(a => a.startsWith(pref))) return true
  }
  return false
}

// Does running these tokens as a command change files? (the command after 'xargs' or 'find -exec')
function runMutates(toks: string[], depth: number): boolean {
  if (toks.length === 0 || depth > 3) return false
  const kind = classify(toks, depth + 1)
  if (kind === null) return false
  if (kind.kind === 'mut') return true
  if (kind.kind === 'shell') return commandEvents(kind.inner, depth + 1).some(ev => ev[0] === 'mut')
  return false
}

function classify(input: string[], depth = 0): Kind | null {
  const u = unwrap(input)
  if (u === null) return null
  const kind = classifyCheck(u[0], u[1])
  if (kind !== null) return kind
  return mutates(u[0], u[1], depth) ? { kind: 'mut' } : null
}

// What a heredoc body is for the program that reads it: commands for a shell, code for an interpreter. 'bash <<EOF'
// and 'sh -s <<EOF' run the body as commands. 'python3 - <<EOF' and 'node <<EOF' run it as code, which counts as a
// change when it writes files. For anything else ('cat > f <<EOF') the body is text.
function heredocKind(toks: string[], body: string): Kind | null {
  const u = unwrap(toks.filter(t => !t.startsWith('<<')))
  if (u === null) return null
  const [raw, args] = u
  const prog = programName(raw)
  if (args.some(a => !a.startsWith('-'))) return null // it runs a script file; the heredoc is only its input
  if (SHELL_C.has(prog)) {
    if (args.some(a => a.startsWith('-') && !a.startsWith('--') && a.endsWith('c'))) return null
    return { kind: 'shell', inner: body }
  }
  if ((PYTHON_RE.test(prog) || INLINE_INTERPRETERS.has(prog)) && INTERP_WRITE.test(body)) return { kind: 'mut' }
  return null
}

// True when the segment sends its stdout to a file (> out.log, >/dev/null, &>x), so its output is not shown.
function stdoutSilenced(text: string): boolean {
  const t = text.replace(QUOTED, ' ').replace(REDIRECT_FD, ' ').replace(REDIRECT_ERR, ' ')
  return t.includes('>')
}

// The literal an echo/printf handler prints, or '' for any other handler.
function handlerPhrase(text: string): string {
  const toks = tokens(text)
  if (toks.length === 0 || !['echo', 'printf'].includes(base(toks[0] as string))) return ''
  return toks.slice(1).filter(t => !t.startsWith('-')).join(' ').replace(/\\n/g, ' ').trim()
}

// [masked, phrase] for the '||' after segment k: 'exit 1' and 'false' keep the failure, anything else eats it.
function orHandler(segs: Seg[], k: number): [boolean, string] {
  const next = (segs[k + 1] as Seg)[0]
  const nxt = tokens(next)
  const first = nxt.length > 0 ? base(nxt[0] as string) : ''
  if (first === 'exit' || first === 'return') return [nxt.length > 1 && nxt[1] === '0', '']
  if (first === 'false') return [false, '']
  return [true, handlerPhrase(next)]
}

// [masked, phrase]: masked when the command's exit status would not reflect segment idx ('|| true', '| tail',
// '; more', and 'CHECK && A || B', where a failed check falls through to B).
function masked(segs: Seg[], idx: number, pipefail: boolean, errexit: boolean): [boolean, string] {
  if (idx === segs.length - 1) return [false, '']
  const op = (segs[idx] as Seg)[1]
  if (op === '&&') {
    for (let k = idx; k < segs.length - 1; k++) {
      const opK = (segs[k] as Seg)[1]
      if (opK === ';' || opK === '\n' || opK === '&') return [false, '']
      if (opK === '||') return orHandler(segs, k)
    }
    return [false, '']
  }
  if (op === '|') return [!pipefail, '']
  if (op === '||') return orHandler(segs, idx)
  if (op === ';' || op === '\n') return [!errexit, '']
  return [false, '']
}

// True when the segment redirects output into a file (> f, >> f, &> f), not /dev/null, a descriptor or a temp file.
function writesRedirect(text: string): boolean {
  const quoted: string[] = []
  const t = text
    .replace(QUOTED, m => {
      quoted.push(m)
      return MARK + String(quoted.length - 1) + MARK
    })
    .replace(REDIRECT_FD, ' ')
  for (const m of t.matchAll(REDIRECT_OUT)) {
    const target = (m[1] as string).replace(MARKED, (_all, n: string) => (quoted[Number(n)] as string).slice(1, -1))
    if (target.startsWith('(') || NULL_TARGETS.has(target) || target.startsWith('/dev/fd/') || isTemp(target)) continue
    return true
  }
  return false
}

// Did the shell say it could not find the program of this segment, or a wrapper in front of it ('npx tsc')?
function notFound(toks: string[], unwrapped: [string, string[]], missing: Set<string>): boolean {
  const [prog, args] = unwrapped
  const wrappers = toks.slice(0, toks.length - args.length - 1)
  return missing.has(base(prog)) || wrappers.some(w => missing.has(base(w)))
}

// {segment index: handler phrase} for the segments in a 'then' branch that has an 'else' or 'elif' after it. 'if [ -d
// tests ]; then pytest -q; else echo "no tests dir"; fi' runs only one branch. When the output is the else branch's
// echo, the check in the then branch never ran, so it is masked the way '|| echo' masks one, and the echo is its
// handler phrase.
function branchMasks(segs: Seg[], segWords: string[][]): Map<number, string> {
  const out = new Map<number, string>()
  const stack: Array<{ state: string; then: number[]; elseUnread: boolean }> = [] // one frame per open 'if'
  segs.forEach(([text], idx) => {
    const ws = segWords[idx] as string[]
    const open = stack[stack.length - 1]
    if (open !== undefined && open.state === 'else' && open.elseUnread && ws.length > 0 && !SHELL_RESERVED.has(ws[0] as string)) {
      for (const i of open.then) out.set(i, handlerPhrase(text)) // 'else' alone on its line: the echo is the next segment
      open.elseUnread = false
    }
    for (const w of ws) {
      if (!SHELL_RESERVED.has(w)) break
      const top = stack[stack.length - 1]
      if (w === 'if') {
        stack.push({ state: 'cond', then: [], elseUnread: false })
      } else if (w === 'then' && top !== undefined) {
        top.state = 'then'
      } else if (w === 'elif' && top !== undefined) {
        for (const i of top.then) if (!out.has(i)) out.set(i, '') // a later branch may be the one that ran
        top.state = 'cond'
      } else if (w === 'else' && top !== undefined) {
        const phrase = handlerPhrase(text)
        for (const i of top.then) out.set(i, phrase)
        top.state = 'else'
        top.elseUnread = ws.length === 1
      }
    }
    if (ws.length > 0 && ws[0] === 'fi') {
      stack.pop()
    } else {
      const top = stack[stack.length - 1]
      if (top !== undefined && top.state === 'then') top.then.push(idx)
    }
  })
  return out
}

// Events in the order they happen in cmd. A 'mut' changes files. A 'check' has a level: 0 its exit status counts;
// 1 masked, counts only with visible clean output; 2 masked and its stdout goes to a file, so it cannot count. A
// file-writing segment downstream of a check in the same pipe (pytest | tee out.log) captures that check's output
// and is not a change.
//
// `missing` is the set of program names the shell said it could not find. A segment that runs one of them never
// started, and neither did the segments after it in the same '&&' chain; what ran before it did run.
function commandEvents(input: string, depth = 0, missing?: Set<string>): Event[] {
  if (depth > 3 || typeof input !== 'string') return []
  const [cmd, bodies] = splitHeredocs(input)
  const segs = splitSegments(cmd)
  const pipefail = PIPEFAIL_RE.test(cmd)
  const errexit = ERREXIT_RE.test(cmd)
  const found: Event[] = []
  let chainCheck = false
  let prevOp = ''
  const loops = new Map<string, string[]>()
  let blocked = false
  const segWords = segs.map(([text]) => splitWords(text))
  const branches = branchMasks(segs, segWords)
  segs.forEach(([text, op], idx) => {
    const piped = prevOp === '|'
    prevOp = op
    if (!piped) chainCheck = false
    const words = segWords[idx] as string[]
    if (words.length > 0 && LOOP_WORDS.has(words[0] as string)) {
      loopHeader(words, loops)
      return
    }
    const stripped = stripReserved(words)
    const toks = loops.size > 0 ? stripped.map(t => loopValue(t, loops)) : stripped
    let heredoc: Kind | null = null
    for (const _m of text.matchAll(HEREDOC)) {
      const body = bodies.length > 0 ? (bodies.shift() as string) : ''
      if (heredoc === null) heredoc = heredocKind(toks, body)
    }
    let started = true
    if (missing !== undefined && missing.size > 0) {
      const u = unwrap(toks)
      started = !(blocked || (u !== null && notFound(toks, u, missing)))
      blocked = !started && op === '&&'
    }
    let kind: Kind | null = null
    if (started) {
      kind = classify(toks, depth)
      if (kind === null) kind = heredoc
    } // else it never started; only its output redirect (the shell opens it first) can have written
    if (kind === null && writesRedirect(text)) kind = { kind: 'mut' }
    if (kind === null) return
    if (kind.kind === 'mut') {
      if (!(piped && chainCheck)) found.push(['mut', 0, ''])
      return
    }
    chainCheck = true
    if (op === '&') return
    let [isMasked, phrase] = masked(segs, idx, pipefail, errexit)
    const branch = branches.get(idx)
    if (branch !== undefined) {
      // in a then branch with an else after it: the other branch may be what ran
      isMasked = true
      phrase = branch !== '' ? branch : phrase
    }
    const level = isMasked ? (stdoutSilenced(text) ? 2 : 1) : 0
    if (kind.kind === 'check') {
      found.push(['check', level, phrase])
    } else {
      for (const [innerKind, innerLevel, innerPhrase] of commandEvents(kind.inner, depth + 1, missing)) {
        found.push(innerKind === 'check' && level > innerLevel ? [innerKind, level, phrase] : [innerKind, innerLevel, innerPhrase])
      }
    }
  })
  return found
}

function checkCounts(level: number, phrase: string, output: string): boolean {
  if (level === 0) return true
  if (level === 1) return output.trim() !== '' && !(phrase !== '' && output.toLowerCase().includes(phrase.toLowerCase()))
  return false
}

// ------------------------------------------------------------------------------------------------ state

// One State per load of the module (register runs again on a reload, and the state starts over with it).
type State = {
  ledger: Ledger
  unverified: string | undefined
  dispatched: Set<string>
  outcomes: Map<string, 'returned' | 'failed'>
}

function freshState(): State {
  return { ledger: { mutated: false, ok: false }, unverified: undefined, dispatched: new Set(), outcomes: new Map() }
}

function tally(s: State): string {
  let returned = 0
  let failed = 0
  for (const id of s.dispatched) {
    const o = s.outcomes.get(id)
    if (o === 'returned') returned++
    else if (o === 'failed') failed++
  }
  const outstanding = s.dispatched.size - returned - failed
  return `agents: dispatched ${s.dispatched.size} / returned ${returned} / failed ${failed}` + (outstanding > 0 ? ` (${outstanding} outstanding)` : '')
}

// The program names a shell reported as 'command not found' (bash, zsh and dash word it differently). bash: 'bash:
// pytest: command not found'. zsh: 'zsh:1: command not found: pytest', '(eval):1: command not found: rm'. dash: 'sh: 1:
// npx: not found'. A shell's own name and a line number are not the program.
function missingPrograms(text: string): Set<string> {
  const names = new Set<string>()
  for (const m of text.matchAll(NOT_FOUND)) {
    const name = ((m[1] ?? m[2] ?? m[3]) ?? '').replace(/^['"`]+|['"`]+$/g, '')
    if (name === '' || /^\d+$/.test(name) || NOT_FOUND_SKIP.has(name.toLowerCase())) continue
    names.add(base(name))
  }
  return names
}

// The ledger is the session's, not the turn's: `mutated` once anything has changed files, `ok` while a clean
// check has run since the last change. A change clears `ok`; a clean check sets it.
function record(s: State, tool: string, input: Record<string, unknown>, r: { deny?: unknown; isError?: unknown; text?: unknown }): void {
  if (MUT_TOOLS.has(tool)) {
    const path = typeof input.file_path === 'string' ? input.file_path : input.notebook_path
    // a refused edit changed nothing, and a scratch file in the temp directory is not the project
    if (r.deny === undefined && r.isError !== true && !(typeof path === 'string' && isTemp(path))) {
      s.ledger.mutated = true
      s.ledger.ok = false
    }
  } else if (tool === 'Bash') {
    const failed = r.deny !== undefined || r.isError === true
    const text = typeof r.text === 'string' ? r.text : ''
    // A command that exited non-zero still ran, so what it wrote is on disk. Only one that never started changed
    // nothing: one the engine refused (a hook, a permission prompt), or a program the shell could not find, which is
    // judged per segment: in 'sed -i ... && pytest' with 'pytest: command not found', the sed ran.
    const shortError = r.isError === true && text.length <= 400
    const notRun = r.deny !== undefined || (shortError && REFUSED.test(text))
    const missing = shortError ? missingPrograms(text) : new Set<string>()
    // a background run has not finished, so nothing it printed is evidence yet
    const clean = !failed && input.run_in_background !== true && !text.startsWith('Exit code') && !FAILURE.test(text.slice(0, 200000))
    const cmd = typeof input.command === 'string' ? input.command : ''
    for (const [kind, level, phrase] of commandEvents(cmd, 0, missing)) {
      if (kind === 'mut') {
        if (!notRun) {
          s.ledger.mutated = true
          s.ledger.ok = false
        }
      } else if (clean && checkCounts(level, phrase, text)) {
        s.ledger.ok = true
      }
    }
  } else if (BROWSER_RE.test(tool)) {
    if (r.deny === undefined && r.isError !== true) s.ledger.ok = true
  }
}

// ------------------------------------------------------------------------------------------------ options

function asFlag(value: unknown, fallback: boolean): boolean {
  if (typeof value === 'boolean') return value
  if (typeof value === 'string') {
    const t = value.trim().toLowerCase()
    if (t === 'false' || t === '0' || t === 'no' || t === 'off') return false
    if (t === 'true' || t === '1' || t === 'yes' || t === 'on') return true
  }
  return fallback
}

function isOn(value: string | undefined): boolean {
  return typeof value === 'string' && ['1', 'true', 'yes'].includes(value.trim().toLowerCase())
}

// `$` may only be handed to a function declared at the top of this file, and `$.env.get` takes string literals.
type EnvReader = { env: { get: (name: string) => Promise<string | undefined> } }
type StatusUi = { ui: { status: (text: string | undefined) => void } }
type ToastUi = { ui: { toast: (text: string, options?: { timeoutMs?: number }) => void } }

async function standDown($: EnvReader, modeOff: boolean): Promise<boolean> {
  if (modeOff) return true
  const all = await $.env.get('DOJO_OFF')
  const mine = await $.env.get('DOJO_VERIFY_OFF')
  return isOn(all) || isOn(mine)
}

function refresh($: StatusUi, show: boolean, s: State): void {
  if (!show) return
  const parts: string[] = []
  if (s.unverified !== undefined) parts.push(s.unverified)
  if (s.dispatched.size > 0) parts.push(tally(s))
  $.ui.status(parts.length > 0 ? 'dojo-verify: ' + parts.join(' · ') : undefined)
}

function warnUnverified($: ToastUi, claim: Claim): void {
  $.ui.toast(
    `dojo-verify: UNVERIFIED — "${quote(claim.sentence)}" with no passing check since the last change. Run the check, or say plainly it is unverified in the same sentence.`,
    { timeoutMs: 8000 },
  )
}

// ------------------------------------------------------------------------------------------------ hooks

export const register: Register = (on, options) => {
  const modeOff = typeof options.mode === 'string' && options.mode.trim().toLowerCase() === 'off'
  const showStatus = asFlag(options.show_status, true)
  const toastUnverified = asFlag(options.toast_unverified, true)
  const s = freshState()

  // A new human prompt clears the UNVERIFIED flag and starts a new agent count. The ledger is the session's and
  // is kept. A continuation (empty text, e.g. a background-task wake) keeps everything.
  on('turn.start', async ($, e, next) => {
    try {
      if (e.text !== '' && !(await standDown($, modeOff))) {
        s.unverified = undefined
        // The agent count is per turn: agents that have settled drop out, agents still running carry over.
        for (const id of [...s.dispatched]) {
          if (s.outcomes.has(id)) s.dispatched.delete(id)
        }
        for (const id of [...s.outcomes.keys()]) {
          if (!s.dispatched.has(id)) s.outcomes.delete(id)
        }
        refresh($, showStatus, s)
      }
    } catch {
      // the mod only shows things: never let it break a turn
    }
    return next(e)
  })

  on('tool.call', async ($, e, next) => {
    const r = await next(e)
    if (e.agentId === undefined) {
      try {
        if (!(await standDown($, modeOff))) record(s, e.tool, e as unknown as Record<string, unknown>, r)
      } catch {
        // recording is best effort
      }
    }
    return r
  })

  on('agent.spawn', async ($, e, next) => {
    const r = await next(e)
    try {
      if (r.deny === undefined && r.agentId !== undefined && !(await standDown($, modeOff))) {
        s.dispatched.add(r.agentId)
        refresh($, showStatus, s)
      }
    } catch {
      // best effort
    }
    return r
  })

  on('turn.complete', async ($, e, next) => {
    const r = await next(e)
    try {
      if (await standDown($, modeOff)) return r
      if (e.agentId !== undefined) {
        const answered = e.reason === 'answer' && e.answer.trim() !== ''
        if (answered) s.outcomes.set(e.agentId, 'returned')
        else if (s.outcomes.get(e.agentId) !== 'returned') s.outcomes.set(e.agentId, 'failed')
      } else {
        const claim = e.reason === 'answer' ? detectClaim(e.answer, s.ledger.mutated) : null
        if (claim !== null && !s.ledger.ok) {
          s.unverified = `UNVERIFIED ("${quote(claim.sentence)}" \u2014 no passing check since the last change)`
          if (toastUnverified) warnUnverified($, claim)
        } else {
          s.unverified = undefined
        }
      }
      refresh($, showStatus, s)
    } catch {
      // best effort
    }
    return r
  })
}
