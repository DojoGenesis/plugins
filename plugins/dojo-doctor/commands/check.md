---
description: "Check your hooks and settings for silent failures in interpreters, hook errors, injection size, always-on weight, the function-hooks flag and python3."
argument-hint: "[--days N] [--section NAME] [--json] [--all] [--home DIR]"
allowed-tools: Bash(python3:*)
---

!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py"`

The block above is the doctor's report, run with default settings. It is read-only: it ran no hook and changed no file. Typed arguments are not passed to that line, because the shell would read them before the script does.

How to relay it:

- Show the report as it is. Do not shorten the findings, and do not run any fix yourself. Say which findings the person can act on first, and quote each fix line as written. Editing settings is the person's call.
- "Could not check" is not "ok". Say so plainly for every section that printed it, and say what the report says it could not see.
- If the block above is empty, or is a "Shell command failed" error, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor.py"` once through Bash before concluding anything. If that also fails, python3 itself is not working here: that is the finding, so say so, and do not infer that the setup is healthy from empty output.
- If the person typed doctor flags (`--days 14`, `--section interpreters`, `--json`, `--all`, `--strict`, `--no-exec`, `--home DIR`, `--config-dir DIR`), re-run through Bash with exactly those flags, each as its own word. Do not pass free text to the script; answer a question from the report instead.
- Token figures are estimates (characters divided by 4). Call them estimates when you repeat them.

For what each section means and the first fix per finding, read `${CLAUDE_PLUGIN_ROOT}/skills/doctor/SKILL.md` and `${CLAUDE_PLUGIN_ROOT}/skills/doctor/findings.md`.
