---
description: "Cost report from your transcripts: tokens and estimated USD by model and by main thread versus subagents."
argument-hint: "[--session ID|--today|--days N|--project PATH|--all|--json]"
allowed-tools: ["Bash(${CLAUDE_PLUGIN_ROOT}/scripts/cost.py:*)"]
---

```!
"${CLAUDE_PLUGIN_ROOT}/scripts/cost.py" --default-session "${CLAUDE_SESSION_ID}" $ARGUMENTS
```

Show the report above to the user exactly as printed, in one code block, with no commentary.
