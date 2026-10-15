---
description: "Show whether refused tool calls are drawn as fix cards, or turn the cards on or off. Needs the mod (function hooks)."
argument-hint: "[status|on|off]"
allowed-tools: ["Read(${CLAUDE_PLUGIN_ROOT}/README.md)"]
---

Fix cards are a mod, and the mod answers this command itself (also as `/fixcards`). If you are reading this, the mod is not running and refusals show as plain errors: tell the user in one sentence that dojo-fixcards needs `export CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` and a new session (the Claude desktop app runs mods without it).
