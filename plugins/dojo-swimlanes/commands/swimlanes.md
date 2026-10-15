---
description: "Every subagent of the latest fan-out as a timeline: one lane per agent, a mark per tool call. Needs the mod (function hooks)."
argument-hint: "[text|all]"
allowed-tools: ["Read(${CLAUDE_PLUGIN_ROOT}/README.md)"]
---

Swimlanes is a mod, and the mod answers this command itself (also as `/swimlanes`). If you are reading this, the mod is not running and nothing was recorded: tell the user in one sentence that dojo-swimlanes needs `export CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` and a new session (the Claude desktop app runs mods without it).
