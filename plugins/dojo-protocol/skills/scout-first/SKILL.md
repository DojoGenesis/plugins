---
name: scout-first
description: "Use when about to edit unread code: search, then read the slice; a small model maps, a larger one changes."
model: inherit
category: scout-position
---

# Scout first

Edit what you have read, and read as little as it takes. Two steps: find the ground, then change it.

## 1. Measure before you spec

Before writing a plan, a spec or an edit, collect facts from the code as it is now. A plan written from memory describes the code you imagine. Measure, then write the delta from what you measured.

- Find: Grep for the symbol, string or route; Glob for the file shape. Note `path:line`.
- Size it before opening it. A big file read whole burns context and often fails outright. If a file is large, read a range around the match.
- Read the slice: the function, its callers, and the test that covers it. Stop when you can state what the code does without guessing.
- Record what you found as `path:line` facts. These go in the brief, the contract or your plan.

## 2. Send a scout for wide questions

When the question spans more than a few files, hand it to `dojo-protocol:scout` (haiku; Read, Glob and Grep only). Give it one narrow question and ask for `path:line` citations. It cannot run builds or git, so ask it only things that reading answers.

A scout that returns "not found" must list its searches. Run one more search yourself before you accept a negative; a search can be pointed at the wrong directory or skipped by an ignore rule.

## 3. Scout the risky code yourself

If you delegate both the scouting and the building, nobody holds the territory. Read the highest-risk code first-hand: the part where a wrong assumption costs the most (migrations, auth, anything irreversible). Let scouts cover the broad, low-risk ground. When the work is done, re-read the sources the change depends on, because they may have moved.

## 4. A small fix does not need any of this

A change under ten lines in one file stays in the main thread: search, read, edit, check. Do not spawn a scout or builder for it.

## Checklist

- [ ] I can point to `path:line` for every code fact in my plan.
- [ ] I read the code I am about to edit in this session.
- [ ] Large files were read by range, not whole.
- [ ] Any "not found" came with the searches that produced it.
- [ ] I read the riskiest part myself.

Related: rule 2 and rule 3 in `${CLAUDE_PLUGIN_ROOT}/PROTOCOL.md`; the `delegate` skill for how to brief the scout.
