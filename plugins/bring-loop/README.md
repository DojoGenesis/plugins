# bring-loop — Claude Code plugin

The Bring Loop adapter for Claude Code. Install the plugin, then in any
project run the `bring-setup` skill once. From then on:

- **SessionStart** injects TODAY'S BRING (one outward action, your week
  streams, your streak) — only in projects with a `bring/` directory.
- **`bring` skill**: say "bring it" and the agent stages the action (draft up,
  recipient confirmed, brief summarized) and stops at the edge — you execute.
  It logs outcomes only on your word; a skip with a reason is a valid day.
- **Stop hook** adds one quiet line if the day's bring went untouched. Never
  blocks anything.

Contract and file formats: [../SPEC.md](../SPEC.md). Core CLI (works without
Claude Code at all): [scripts/bring_core.py](scripts/bring_core.py).

---

*Distribution copy. Canonical source: [github.com/DojoGenesis/bring-loop](https://github.com/DojoGenesis/bring-loop) (\plugin/\ dir) - sync from there, do not edit here. Synced 2026-07-04 @ v0.1.0.*
