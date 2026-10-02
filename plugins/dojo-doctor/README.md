# dojo-doctor

Find the hooks and settings that fail or cost you silently: broken interpreters, noisy injections, always-on token weight, flags that are off.

Part of the Dojo Genesis suite. Tier: **classic**. There are no hooks and no mod in this plugin, so nothing runs unless you call it.

## Install

```
/plugin marketplace add DojoGenesis/plugins
/plugin install dojo-doctor@dojo-genesis
```

Then run:

```
/dojo-doctor:check
```

## What it checks

| # | Section | Question it answers |
|---|---|---|
| 1 | interpreters | For every hook command in your settings and in each enabled plugin: is the program there under a bare `PATH=/usr/bin:/bin`, and under your own PATH? Bare `python`, missing programs and scripts, a missing exec bit and bad shebang lines are flagged. |
| 2 | hook failures | Which hooks recorded errors, timeouts or failed async runs in recent transcripts, and which plugin or settings file owns each one? |
| 3 | injection weight | How many bytes do hooks put into context per event and per session, where the transcript recorded it? |
| 4 | always-on weight | How much description text do your skills, agents and commands keep in context all the time, per plugin? |
| 5 | function hooks flag | Are mods (function hooks) on or off, which source decided, and does any enabled plugin ship a mod the flag would leave inert? |
| 6 | python3 | Is python3 there under a bare PATH and under yours, and is it 3.9 or newer? |

Each section ends as **ok**, **problem** (with a one-line fix) or **could not check**. Could not check is not ok: it means the doctor could not see.

Flags: `--days N` (window for transcripts), `--section NAME` (one or more of interpreters, failures, injection, weight, flag, python), `--all` (lift the row caps), `--json`, `--strict` (exit 1 when a problem is found; the default exit is 0 so the report always shows), `--no-exec` (skip the one version probe), `--home DIR` or `--config-dir DIR` (read another config folder).

## Components

- `commands/check.md`: `/dojo-doctor:check`, which runs `scripts/doctor.py`.
- `scripts/doctor.py`: the read-only check. One file, Python standard library only, Python 3.9 or newer.
- `skills/doctor/SKILL.md`: when to run it and how to read each section.
- `skills/doctor/findings.md`: one entry per finding id, loaded on demand.

## An example report

This is made-up output with invented names, to show the shape.

```
dojo-doctor 0.1.0: read-only check; nothing was run, nothing was changed
Summary: 2 problems, 1 could not check

1. interpreters: PROBLEM
   - [PROBLEM] interp-bare-python: example-plugin [SessionStart]: bare `python` in hook command
       fix: use python3 (python3 hooks/nudge.py)

2. hook failures: PROBLEM
   - [PROBLEM] hook-failing: Example nudge: example-plugin -- repeated errors; interpreter missing; exit 127
       fix: run the command by hand in a bare shell (env -i PATH=/usr/bin:/bin); a bare python becomes python3

3. injection weight: COULD NOT CHECK
   - [could not check] no-transcripts: nothing scanned: no transcript files changed in the window

5. function hooks flag: OK
   Function hooks (mods): ON -- this shell's environment
```

## What it reads, and what it never does

It reads: your user, project and local `settings.json` files; the hook files, skill, agent and command front matter of enabled plugins; the cached feature entry in `~/.claude.json`; and transcript files from the last few days.

It never executes a hook command and never writes a file, not even a cache. It opens only regular files, with a size limit: a pipe, device or folder where a config, hook, agent, command or transcript file should be is reported or skipped, never read, so such an entry cannot stall the check. Printed paths are shortened with `~`, and anything that looks like a secret in a command or an error line is redacted before it is printed. Hook error text is shown as quoted data, not as instructions.

The single thing it runs is `python3 --version` for the python3 found under a bare PATH, with no input, a short timeout and a minimal environment, and only when that is not the interpreter already running the check. `--no-exec` turns even that off.

## Kill switches

None: nothing runs unless you call it.

## Honest limits

- Transcripts record only some hook runs, so the failure and injection counts are lower bounds. Per-hook injection sizes exist only for the runs a transcript kept; per-event totals are the reliable figure.
- Token figures are estimates: characters divided by 4, or bytes divided by 4. They are not a tokenizer's count.
- The scan stops at a time budget and says how much it covered. A partial scan prints a coverage line and the failures and injection sections show could not check instead of ok, because what was not read is not ruled out.
- The PATH the doctor sees is the PATH of the shell that ran it. Claude Code started from the Dock or a scheduler may have a different one, which is why every program is checked under both a bare PATH and yours.
- Command parsing is a heuristic. It judges the first word of each simple command, looks through common wrappers and one level of `bash -c`, and does not expand command substitutions or shell functions. Commands it cannot resolve are counted as could not check, never guessed.
- Plugins loaded with `--plugin-dir` and managed (organisation) plugins and settings are not visible to it. Hooks declared inside a skill's or command's own front matter, and components a `plugin.json` points at outside the default folders, are not scanned. MCP server weight is not measured.
- The function-hooks flag also depends on a server-side cache that can lag. A missing cache entry is reported as on by default.
- The listing budget it compares against is derived from Claude Code's current rules and is marked as of the version below; it can change.
- A failing hook can stay in the report for the rest of the window, since old transcript lines remain. The report says when a config file changed after the last failure.

## Tested with

Claude Code 2.1.286.

## License

Apache-2.0.
