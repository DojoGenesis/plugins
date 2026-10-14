---
description: "Which subagent holds which file, and the writes that were refused. Needs the mod (function hooks)."
allowed-tools: ["Read(${CLAUDE_PLUGIN_ROOT}/README.md)"]
---

Lanes are a mod, and the mod answers this command itself (also as `/lanes`). If you are reading this, the mod is not running and no lane is held: tell the user in one sentence that dojo-lanes needs `export CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` and a new session.
