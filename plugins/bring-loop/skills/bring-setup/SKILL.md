---
name: bring-setup
description: Initialize the bring loop in the current project — scaffold bring/actions.md + ledger, seed the first real outward actions from conversation, and explain the daily contract. Use when the user says "set up bring-loop", "install the bring loop", "start gating my sends", or asks how to get the BringItCruz effect in their system.
model: inherit
category: productivity
---

# Bring-setup — initialize the loop in this project

1. Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/bring_core.py" init` from the
   project root. It scaffolds `bring/actions.md` (with a template) and an
   empty `bring/ledger.jsonl`. It never overwrites existing files.
2. **Seed real actions immediately** — an empty queue teaches nothing. Ask the
   user: "What are 2-3 outward actions you've been sitting on — a send, a
   decision, a finished thing that isn't shipped?" Write them into
   `bring/actions.md` as H2 sections with `kind:` and (if known) `due:`.
   Delete the template example.
3. Show them today's brief (`brief`) so they see the shape: ONE action, the
   deck, the week streams, the streak.
4. Explain the contract in two sentences: the loop surfaces and stages; they
   execute. A logged skip with a reason is a valid day.
5. Optional wiring beyond this plugin (their call): `brief` in a shell rc or
   editor task for non-Claude surfaces; `check` in CI if they want the
   scoreboard parity-gated. Do not wire anything outside this project without
   being asked.

Configuration lives in the actions.md frontmatter: `weekly_send_cap`
(default 5) and `weekends_free` (default true). Respect whatever they set —
cadence is theirs, the invariants are not.
