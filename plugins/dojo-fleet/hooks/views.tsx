// The fleet's drawings. register.ts computes what to show and the callbacks, and calls these from its `ui.render`
// hooks, so every hook stays in register.ts and only the JSX lives here. The engine supplies the JSX factory as a
// global: nothing in this file may declare, import or take as a parameter a name that shadows it (the engine then
// logs "hook was skipped" and draws nothing). tests/test_plugin_shape.py checks for that.

import type { RowParts } from './model'

// The element table `$.ui.resolve(e)` returns; `Input` is absent where the surface draws no field (mobile).
export type FleetUi = { Box: any; Text: any; Button: any; Input?: any }

export type Tone = 'claude' | 'suggestion' | 'warning' | 'success' | 'error' | 'subtle'

export type PaneRow = {
  id: string
  glyph: string
  tone: Tone
  parts: RowParts
  // The tail keeps the default color while an agent runs unflagged; otherwise it takes the row's tone.
  isPlain: boolean
  isSelected: boolean
  isFirst: boolean
}

export type PaneDetail = {
  id: string
  n: number
  title: string
  facts: string
  stallLine?: string
  stats: string
  brief?: string
  answer?: string
  canSteer: boolean
  canNudge: boolean
  canStop: boolean
}

export type PaneView = {
  title: string
  threshold: string
  isEmpty: boolean
  rows: PaneRow[]
  cols: { id: number; label: number; model: number; age: number; work: number }
  more: number
  detail?: PaneDetail
}

export type FleetActions = {
  select: (id: string) => unknown
  steer: (id: string, text: string) => unknown
  nudge: (id: string) => unknown
  stop: (id: string) => unknown
  close: () => unknown
  open: () => unknown
  hide: () => unknown
}

export function renderPane(ui: FleetUi, view: PaneView, act: FleetActions) {
  const { Box, Text, Button, Input } = ui
  const detail = view.detail
  return (
    <Box flexDirection="column">
      <Box flexDirection="row" gap={2}>
        <Text bold>{view.title}</Text>
        <Text dimColor>{view.threshold}</Text>
      </Box>
      {view.isEmpty && <Text dimColor>No subagent yet. Dispatch a fan-out and each agent shows here, live.</Text>}
      {view.rows.map(row => (
        // A drawn tree collapses runs of spaces, so the columns are boxes of fixed width, after one Button handle.
        <Box key={`line:${row.id}`} flexDirection="row" gap={1}>
          <Button
            key={`row:${row.id}`}
            plain
            autoFocus={row.isFirst && detail === undefined ? true : undefined}
            onPress={() => act.select(row.id)}
          >
            <Text color={row.tone}>{row.glyph}</Text>
            {` ${row.parts.id.padEnd(view.cols.id)}`}
          </Button>
          <Box width={view.cols.label}>
            <Text wrap="truncate-end" bold={row.isSelected}>
              {row.parts.label}
            </Text>
          </Box>
          <Box width={view.cols.model}>
            <Text dimColor>{row.parts.model}</Text>
          </Box>
          <Box width={view.cols.age} justifyContent="flex-end">
            <Text>{row.parts.age}</Text>
          </Box>
          <Box width={view.cols.work}>
            <Text dimColor>{row.parts.work}</Text>
          </Box>
          <Text color={row.isPlain ? undefined : row.tone} wrap="truncate-end">
            {row.parts.tail}
          </Text>
        </Box>
      ))}
      {view.more > 0 && <Text dimColor>{`+${view.more} more (oldest settled)`}</Text>}
      {view.rows.length > 0 && detail === undefined && <Text dimColor>Pick a row to steer, nudge or stop that agent.</Text>}
      {detail !== undefined && (
        <Box flexDirection="column" marginTop={1} borderStyle="round" paddingX={1}>
          <Text>
            <Text bold>{detail.title}</Text>
            <Text dimColor>{`  ${detail.facts}`}</Text>
          </Text>
          {detail.stallLine !== undefined && <Text color="warning">{detail.stallLine}</Text>}
          {detail.canSteer && Input !== undefined && (
            <Input
              key="steer"
              label="Steer"
              placeholder={`message for #${detail.n}; Enter sends it into its loop`}
              submitLabel="Send"
              onSubmit={(value: string) => act.steer(detail.id, value)}
            />
          )}
          <Box flexDirection="row" gap={1}>
            {detail.canNudge && <Button key="nudge" label="Nudge" onPress={() => act.nudge(detail.id)} />}
            {detail.canStop && <Button key="stop" label="Stop" onPress={() => act.stop(detail.id)} />}
            <Button key="close" label="Close" onPress={() => act.close()} />
            <Text dimColor>{detail.stats}</Text>
          </Box>
          {detail.brief !== undefined && (
            <Text dimColor wrap="truncate-end">
              {`brief  ${detail.brief}`}
            </Text>
          )}
          {detail.answer !== undefined && <Text wrap="truncate-end">{detail.answer}</Text>}
        </Box>
      )}
    </Box>
  )
}

export type AgentBarView = { id: string; glyph: string; tone: Tone; text: string; canNudge: boolean; canStop: boolean }

// With an agent's transcript open: the prompt below already messages that agent, so the band shows what the engine
// does not (writes, stall or park, fleet number) and the actions. `below` is what is drawn beneath (another
// plugin's band, or the engine's): wrapped, never replaced.
export function renderAgentBar(ui: FleetUi, view: AgentBarView, act: FleetActions, below: unknown) {
  const { Box, Text, Button } = ui
  return (
    <Box flexDirection="column">
      <Box flexDirection="row" gap={1}>
        <Text>
          <Text color={view.tone}>{view.glyph}</Text>
          {` ${view.text}`}
        </Text>
        {view.canNudge && <Button key="nudge" label="Nudge" onPress={() => act.nudge(view.id)} />}
        {view.canStop && <Button key="stop" label="Stop" onPress={() => act.stop(view.id)} />}
        <Button key="open" label="Fleet" onPress={() => act.open()} />
      </Box>
      {below}
    </Box>
  )
}

export type Chip = { id: string; tone: Tone; text: string }

// One chip per agent in play, the counts, Open and Hide; then whatever is drawn beneath.
export function renderChips(ui: FleetUi, chips: Chip[], hidden: number, tally: string, act: FleetActions, below: unknown) {
  const { Box, Text, Button } = ui
  return (
    <Box flexDirection="column">
      <Box flexDirection="row" gap={2}>
        <Text dimColor>fleet</Text>
        {chips.map(chip => (
          <Text key={`chip:${chip.id}`} color={chip.tone}>
            {chip.text}
          </Text>
        ))}
        {hidden > 0 && <Text dimColor>{`+${hidden}`}</Text>}
        <Text dimColor>{tally}</Text>
        <Box flexDirection="row" gap={1}>
          <Button key="open" label="Open" onPress={() => act.open()} />
          <Button key="hide" label="Hide" onPress={() => act.hide()} />
        </Box>
      </Box>
      {below}
    </Box>
  )
}
