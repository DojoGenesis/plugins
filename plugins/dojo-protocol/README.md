# dojo-protocol

The Dojo Protocol for Claude Code: ten rules at session start, a scout→contract→build→verify spine, and role agents pinned to the right model.

The ten rules are in [PROTOCOL.md](PROTOCOL.md). That file is the single source of truth: the hook injects it, and nothing else in this plugin copies it.

## Install

```
/plugin marketplace add DojoGenesis/plugins
/plugin install dojo-protocol@dojo-genesis
```

Start a new session. The rules arrive as context at session start; there is nothing to configure.

## What's in it

| Component | Count | Names |
|---|---|---|
| SessionStart hook | 1 | `hooks/session_start.py` injects `PROTOCOL.md` |
| Agents | 4 | `dojo-protocol:scout` (haiku), `dojo-protocol:builder` (sonnet), `dojo-protocol:reviewer` (sonnet), `dojo-protocol:judge` (opus) |
| Skills | 5 | `protocol`, `scout-first`, `contract`, `refute`, `delegate` |
| Output style | 1 | `status-and-path` |
| Eval scaffolds | 4 | `scout-before-edit`, `cites-file-line`, `no-edit-when-told`, `trivial-fix-stays-inline` |
| Commands | 0 | none, to keep the always-on description weight small |

Counts are checked against the files on disk by this plugin's tests. Skill and agent descriptions together stay under the suite's 1,000-character always-on budget, also checked by a test.

### Agents

| Agent | Model | Tools | Max turns | Job |
|---|---|---|---|---|
| `dojo-protocol:scout` | haiku | Read, Glob, Grep | 15 | map the ground; `path:line` citations; never edits |
| `dojo-protocol:builder` | sonnet | Read, Edit, Write, Bash, Glob, Grep | 40 | make a briefed change in owned files and run the done-check |
| `dojo-protocol:reviewer` | sonnet | Read, Glob, Grep, Bash | 25 | fresh-eyes review; reports `no defects found` when that is true |
| `dojo-protocol:judge` | opus | Read, Glob, Grep, Bash | 25 | adversarial; treats unverified claims as refuted until checked |

Always call them by the qualified id (`dojo-protocol:scout`, `dojo-protocol:builder`, `dojo-protocol:reviewer`, `dojo-protocol:judge`), so they cannot be confused with another plugin's agents of the same name. The agent bodies carry the rules they need, because subagents do not receive the session-start text.

### Output style

`status-and-path` puts a status line first, and sends big deliverables to a file with a path and a one-line summary. It is optional. Pick it under Output style in `/config`. It keeps Claude Code's coding instructions.

## Tier

Classic. This plugin has no mod and works with function hooks off.

## Kill switches and overrides

| Setting | Effect |
|---|---|
| `DOJO_PROTOCOL_OFF=1` | the hook injects nothing |
| `DOJO_OFF=1` | turns off every Dojo plugin, including this one |
| `./DOJO.md` in the project | its text is injected in place of `PROTOCOL.md` |

Only the exact value `1` turns a switch on. The switches win over a `DOJO.md`: with one set, nothing is injected.

How `DOJO.md` is handled:

- It is read from the working directory Claude Code reports for the session. It is not searched for in parent directories. The name must be exactly `DOJO.md`; `dojo.md` is ignored, even on a case-insensitive filesystem such as the macOS default.
- It is used only if it is a regular, non-empty file whose real path stays inside that directory. A symlink that points elsewhere, a directory, a pipe or an empty file is ignored, and the built-in protocol is injected instead.
- A project directory that can be entered but not listed (for example mode 311) is treated as having no `DOJO.md`: the built-in protocol is injected, with no message.
- The injected text is capped at 8,000 characters in total. A longer file is cut with a visible note. The cap keeps the whole text in front of the model: Claude Code moves very large hook context to disk and shows the model only a preview.
- When `DOJO.md` replaces the protocol, you see a one-line message saying so at a fresh start. Resume, clear and compact inject the same text without repeating the message.

The hook fails open. If its input is unreadable, the plugin file is missing, or anything else goes wrong, it prints nothing and exits 0.

## Honest limits

- The protocol is injected text. Nothing enforces it. It makes the rules present, not binding.
- It reaches the main thread only. Subagents get no session-start text, so briefs have to carry their rules (the `delegate` skill covers this).
- A `DOJO.md` longer than the cap is cut.
- The agents' `tools` lists are the only hard limits here. The `dojo-protocol:builder`, `dojo-protocol:reviewer` and `dojo-protocol:judge` agents have Bash, so "read-only" and "no git add, commit or push" are instructions for them, not controls. File ownership in the `contract` skill is a practice you write into briefs and check afterward; no hook blocks a write.
- `dojo-protocol:scout` declares `effort: low`. That setting may have no effect on haiku, so rely on its model pin and its tools list, not on its effort.
- Nothing in this plugin measures cost or quality. The four eval cases are scaffolds. Tests here check their shape against the case schema, but none has been executed; run them on purpose, with a cost cap.

## Tests

```
cd plugins/dojo-protocol && python3 -m unittest discover -s tests -v
```

The hook script runs on Python 3.9 (macOS `/usr/bin/python3`) with only the standard library.

Tested with Claude Code 2.1.286.

License: Apache-2.0.
