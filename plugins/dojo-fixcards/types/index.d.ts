// dojo-fixcards' state contract: held by the host for the session.

declare module 'claude-code' {
  interface PluginState {
    'dojo-fixcards': {
      // /fixcards off: every row is drawn by the engine again.
      isOff: boolean
      // Unique refused calls drawn as a card this session.
      drawn: number
      // The tool_use_ids already counted, so a retried event counts once.
      seen: string[]
    }
  }
}
