import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Refusal } from './model'
import { isOn, parseRefusal, statusLine, textOf } from './model'

// dojo-fixcards mod (early access). A tool call refused by a Dojo suite guard is drawn as a card in the
// transcript: who blocked it, why, and the fix as code. The card replaces the plain error block of a
// standalone row (ToolResult). A ToolUse row is left alone: a standalone row's ToolUse also carries the
// error text, and redrawing it would hide the call's own header and repeat the card under it.

const offAtom = atom({ plugin: 'dojo-fixcards', key: 'isOff' } as const, false)
const drawnAtom = atom({ plugin: 'dojo-fixcards', key: 'drawn' } as const, 0)
const seenAtom = atom({ plugin: 'dojo-fixcards', key: 'seen' } as const, [] as string[])

const MAX_SEEN = 500

// The names `$.env.get` may read must be string literals, so each is spelled out here.
async function standDown($: EngineInterface): Promise<boolean> {
  if (!isEnabled) return true
  return isOn(await $.env.get('DOJO_OFF')) || isOn(await $.env.get('DOJO_FIXCARDS_OFF'))
}

// The `enabled` option (userConfig): false turns the mod into a pass-through, as the kill switches do.
let isEnabled = true

function asFlag(value: unknown, fallback: boolean): boolean {
  if (typeof value === 'boolean') return value
  if (typeof value === 'string') {
    const text = value.trim().toLowerCase()
    if (['false', '0', 'no', 'off'].includes(text)) return false
    if (['true', '1', 'yes', 'on'].includes(text)) return true
  }
  return fallback
}

export const register: Register = (on, options) => {
  isEnabled = asFlag(options.enabled, true)
  on('session.start', async ($, e, next) => {
    if (!(await standDown($))) {
      for (const name of ['fixcards']) {
        await $.command.register({
          name,
          description: 'Redraw a tool call refused by a Dojo guard as a card with the fix. Usage: /fixcards [status|on|off]',
          argumentHint: '[status|on|off]',
          immediate: true,
        })
      }
    }
    return next(e)
  }).catch(($, e, next) => next(e))

  on('command.run', { command: ['fixcards', 'dojo-fixcards:fixcards'] }, async ($, e) => {
    const arg = e.args.trim().toLowerCase()
    if (arg === 'off' || arg === 'on') {
      // The render hooks read this atom, so a change redraws them.
      await update($, offAtom, () => arg === 'off')
    }
    const isOff = await read($, offAtom)
    const drawn = await read($, drawnAtom)
    return { text: statusLine(isOff, drawn) }
  }).catch(($, e, next) => next(e))

  // Counts a refused call once, at call time: a render hook may not write.
  on('tool.call', async ($, e, next) => {
    const ran = await next(e)
    try {
      const text = ran.deny !== undefined ? ran.deny : ran.isError === true ? (ran.text ?? textOf(ran.result)) : ''
      if (text !== '' && parseRefusal(text) !== null && !(await standDown($)) && !(await read($, offAtom))) {
        const id = e.tool_use_id
        if (typeof id === 'string') {
          await update($, seenAtom, seen => (seen.includes(id) ? seen : [...seen, id].slice(-MAX_SEEN)))
          const seen = await read($, seenAtom)
          await update($, drawnAtom, () => seen.length)
        }
      }
    } catch {
      // bookkeeping only: the call's result stands
    }
    return ran
  }).catch(($, e, next) => next(e))

  // The terminal draws a standalone row's error in its ToolResult block, so the card goes there. Other surfaces
  // leave this block to the ToolUse hook below (the desktop never raises a ToolResult at all), so no surface draws
  // a refusal twice.
  on('ui.render', { component: 'ToolResult' }, async ($, e, next) => {
    if (!e.props.isErrored || e.surface !== 'terminal') return next(e)
    if (await standDown($)) return next(e)
    if (await read($, offAtom)) return next(e)
    const refusal = parseRefusal(textOf(e.props.output))
    if (refusal === null) return next(e)
    return card($, e, refusal)
  }).catch(($, e, next) => next(e))

  // Seen live: the transcript folds reads and shell commands into one count line ("Read 1 file"), so a refused
  // call in a group has no ToolResult block of its own and the card above never drew. A group that holds a
  // refusal is unfolded; its rows are then ToolUse rows, and the refused one draws the card under itself.
  on('ui.render', { component: 'ToolGroup' }, async ($, e, next) => {
    if (e.props.isExpanded) return next(e)
    if (await standDown($)) return next(e)
    if (await read($, offAtom)) return next(e)
    const refused = e.props.calls.filter(call => call.isErrored && parseRefusal(textOf(call.output)) !== null)
    if (refused.length === 0) return next(e)
    for (const call of refused) if (typeof call.tool_use_id === 'string') unfolded.add(call.tool_use_id)
    return next({ ...e, props: { ...e.props, isExpanded: true } })
  }).catch(($, e, next) => next(e))

  // On the terminal, only rows this mod unfolded: a standalone row's refusal is drawn once, by its ToolResult block.
  // Elsewhere every refused row: a census of the desktop (2026-10-15, 123 draws) found no ToolResult site, and the
  // refusal arrived on a standalone ToolUse row with the guard's text in `output`.
  on('ui.render', { component: 'ToolUse' }, async ($, e, next) => {
    if (!e.props.isErrored) return next(e)
    if (e.surface === 'terminal' && !unfolded.has(e.props.tool_use_id)) return next(e)
    if (await standDown($)) return next(e)
    if (await read($, offAtom)) return next(e)
    const refusal = parseRefusal(textOf(e.props.output))
    if (refusal === null) return next(e)
    // The row keeps its own drawing, raw refusal text included: on 2.1.295 the terminal ignored a rewritten
    // `output` on an errored row (tried live), so the card goes under the row, not in place of its text.
    const row = await next(e)
    const { Box } = $.ui.resolve(e)
    return (
      <Box key="fixrow" flexDirection="column">
        {row}
        {card($, e, refusal)}
      </Box>
    )
  }).catch(($, e, next) => next(e))
}

// Rows of groups this mod unfolded, by tool_use_id. A drawing hint, not state: a reload empties it and the
// group's next draw fills it again, so it lives in the module and not in `$.state`.
const unfolded = new Set<string>()

// A span worth its own copyable block is a command: it has a space ("git status"). A lone word ("offset",
// "gtimeout") stays in the fix sentence, drawn with its inline code marks.
const isCommand = (span: string): boolean => /\s/.test(span.trim())

function card($: EngineInterface, e: any, r: Refusal) {
  const { Box, Text, Code, Markdown } = $.ui.resolve(e)
  const holder = r.path?.holder
  const commands = r.fixes.filter(isCommand)
  return (
    <Box key="fixcard" flexDirection="column" borderStyle="round" borderColor="#e76f51" paddingX={1} gap={1}>
      <Box key="head" flexDirection="row" gap={1}>
        <Text bold color="#e76f51">Blocked by {r.mod}</Text>
        {r.rule !== null && <Text dimColor>{`[${r.rule}]`}</Text>}
      </Box>
      <Text>{r.reason}</Text>
      {r.path !== null && (
        <Box key="lane" flexDirection="column">
          <Text bold>File</Text>
          <Code source={r.path.file} language="bash" />
          <Text>{`Held by ${r.path.holder}${r.path.claimed === null ? '' : `, claimed ${r.path.claimed} ago`}.`}</Text>
          <Text dimColor>{`Put the change in your report; the orchestrator applies it after ${holder} returns.`}</Text>
        </Box>
      )}
      {r.path === null && (r.advice !== '' || commands.length > 0) && (
        <Box key="fix" flexDirection="column">
          <Text bold>Fix</Text>
          {r.advice !== '' && <Markdown key="advice" text={r.advice} />}
          {commands.map(fix => (
            <Code key={`fix:${fix}`} source={fix} language="bash" />
          ))}
        </Box>
      )}
      {r.allow !== null && (
        <Box key="allow" flexDirection="column">
          <Text bold>To allow it on purpose</Text>
          <Code source={r.allow} language="bash" />
        </Box>
      )}
    </Box>
  )
}
