// The band's drawing. register.ts calls this from its `ui.render` hook, so every hook stays in register.ts and
// only the JSX lives here. The engine supplies the JSX factory as a global: nothing in this file may declare,
// import or take as a parameter a name that shadows it (the engine then logs "hook was skipped" and draws
// nothing). tests/test_plugin_shape.py checks for that.

// The element table `$.ui.resolve(e)` returns for AbovePrompt (terminal and desktop share these three).
export type BandUi = { Box: any; Text: any; Button: any }

// Room the Hide button takes beside the text, in character cells.
export const HIDE_WIDTH = 10

// `below` is what is drawn beneath the band (another plugin's band, such as dojo-fleet's, or the engine's): the band
// goes above it and never replaces it. Nothing beneath draws the band alone, as before.
export function renderBand(ui: BandUi, text: string, onHide: () => unknown, below?: unknown) {
  const { Box, Text, Button } = ui
  const band = (
    <Box>
      <Text dimColor>{text} </Text>
      <Button key="hide" label="Hide" onPress={onHide} />
    </Box>
  )
  if (below === undefined || below === null || below === false) return band
  return (
    <Box flexDirection="column">
      {band}
      {below}
    </Box>
  )
}
