---
name: doctor
description: "Use when hooks print errors, 'command not found' shows up, session start is slow, context is injected that nobody asked for, or mods do nothing: run /dojo-doctor:check and read it here."
model: inherit
category: agent-telemetry
---

# Reading the doctor

`/dojo-doctor:check` reads your settings, your plugins' hook files and your recent transcripts, and prints one report with six sections. It runs no hook and writes nothing. It is a doctor: it reads, you decide. The decision to edit settings is the person's (protocol rule 10, irreversible needs a yes).

## When to run it

- A hook error shows up in the transcript, or something says `command not found`.
- Session start feels slow, or the model quotes context nobody asked for.
- A mod (function hook) seems to do nothing.
- Before you blame a tool for being missing. Check the setup first (protocol rule 8, config before code).

Useful flags: `--days N` (window, default 7), `--section NAME` (one of interpreters, failures, injection, weight, flag, python), `--all` (lift the row caps), `--json`, `--no-exec` (skip the one `python3 --version` probe).

## Three statuses, and what they mean

- **ok**: the doctor looked and found nothing.
- **problem**: the doctor looked and found something, with a one-line fix.
- **could not check**: the doctor could not see. This is not ok. Say what it could not see and stop short of calling that part healthy (protocol rule 9, silence is not a finding).

## The six sections

1. **interpreters**: for each hook command, is the program there under a bare `PATH=/usr/bin:/bin` and under your own PATH? Bare `python`, missing programs, missing scripts, scripts without the exec bit and bad shebang lines are problems. A program that exists only on your shell PATH is a note: it breaks when Claude Code is started from outside a terminal.
2. **hook failures**: errors, timeouts and failed async hooks recorded in transcripts inside the window, grouped by the hook's status message or command and matched back to the plugin or settings file that owns it. Deliberate blocks from guards are left out on purpose. The coverage line says how much was scanned.
3. **injection weight**: bytes that hooks put into context per event and per session, in UTF-8 bytes, with an estimate of tokens (bytes / 4). Per-hook numbers exist only where the transcript recorded them; where it did not, the report says "not recorded", never zero.
4. **always-on weight**: per plugin, the description text of skills, agents and commands that sits in context all the time, in characters and estimated tokens (characters / 4). It also compares the skill and command listing with Claude Code's listing budget.
5. **function hooks flag**: whether mods are on, which source decided (environment, a settings `env` entry, or the cached server value), and whether any enabled plugin ships a mod that the flag would leave inert. A missing cache entry means on by default, not off.
6. **python3**: whether python3 exists under a bare PATH and under yours, and whether it is 3.9 or newer.

## First fix per finding class

- Bare `python` in a hook: change it to `python3`. Stock macOS has no `python`.
- Found only on your shell PATH: give the hook the full path to the program, or start Claude Code from a terminal.
- Not executable (exit 126, "Permission denied"): `chmod +x` the script, or call it through `bash` or `python3`.
- Missing script (or "can't open file"): restore it or fix the path.
- Heavy injection: make the hook print less, or print a pointer to a file the model reads only when needed.
- Heavy always-on weight: shorten the descriptions of the heaviest plugins, or turn off plugins you do not use.
- Mods inert: `export CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`, or add it under `env` in `~/.claude/settings.json`, then restart.
- python3 old or broken: install a newer one where a bare PATH can see it.

After a fix, run the same command again and look for the finding to be gone. A failure count can stay up for the rest of the window, because old transcript lines remain; the report says when the config changed after the last failure.

## Why it is built this way

- A tool that looks "not installed" is often just "not on PATH in this shell". A non-interactive shell does not load your profile, and a scheduled job gets a minimal PATH. So the doctor resolves under both and shows the difference, and reproduces a bare environment with `env -i PATH=/usr/bin:/bin`.
- Skipping when a tool crashes is a false pass. A harness that skipped whenever a binary failed stayed green through a two-week outage after an upgrade broke it. Absent means skip visibly; installed but crashing means fail. That is why section 6 runs the bare-PATH python3 once, with a timeout, instead of trusting that it exists.
- A probe that prints nothing may never have run. A diagnostic wrapped in a command that did not exist on the machine printed nothing and was read as "the service is wedged". That is why sections 2 and 3 say "could not check", not "ok", when they scanned files and saw no hook records at all.

Details for every finding id (what it means, how to confirm by hand, the fix) live in `${CLAUDE_PLUGIN_ROOT}/skills/doctor/findings.md`. Read it only when a finding needs more than the one-line fix.
