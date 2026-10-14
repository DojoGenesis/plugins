---
description: "Every subagent of this session in the Fleet pane: status, model, work done, stalls. Needs the mod (function hooks)."
argument-hint: "[list|engine]"
allowed-tools: ["Read(${CLAUDE_PLUGIN_ROOT}/README.md)"]
---

The Fleet pane is a mod, and the mod answers this command itself (also as `/fleet`). If you are reading this, the mod is not running: tell the user in one sentence that dojo-fleet needs `export CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` and a new session.
