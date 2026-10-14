---
description: "Insert the subagent brief template, or show the brief lint tally. Needs the mod (function hooks)."
argument-hint: "[stats]"
allowed-tools: ["Read(${CLAUDE_PLUGIN_ROOT}/README.md)"]
---

The brief lint is a mod, and the mod answers this command itself (also as `/dojo-brief`). If you are reading this, the mod is not running: tell the user in one sentence that dojo-brief needs `export CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` and a new session.
