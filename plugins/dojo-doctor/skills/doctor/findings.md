# Finding reference

One entry per finding id the doctor can print. "Confirm" is a way to check by hand without running the hook itself. "Re-run" is how to see it gone.

All re-runs are `/dojo-doctor:check --section <name>`.

## interpreters

| id | meaning | confirm | fix |
|---|---|---|---|
| interp-bare-python | A hook command, an exec-form command or a script's shebang line asks for plain `python`. Stock macOS has no `python`, and version-manager shims only exist in your shell. | `env -i PATH=/usr/bin:/bin sh -c 'command -v python python3'` prints only python3. | Use `python3`; for a shebang, `#!/usr/bin/env python3`. |
| interp-missing | A program is on neither `/usr/bin:/bin` nor your current PATH. | `command -v <name>` in your shell, then the same under `env -i PATH=/usr/bin:/bin`. | Install it, or put the full path in the hook command. |
| interp-needs-path (note) | The program is only on your shell PATH. It breaks when Claude Code is started from the Dock, a scheduler or another launcher. | Same two commands as above; they differ. | Full path in the hook command, or start Claude Code from a terminal. |
| interp-missing-script | The hook script, or the script given to an interpreter, does not exist or is not a regular file (a folder, pipe or device). | `ls -l <path>` with the expanded path from the report. | Restore the file or fix the path. |
| interp-not-exec | The script is run directly but lacks the exec bit; the shell answers exit 126, "Permission denied". | `ls -l <path>` shows no `x`. | `chmod +x <path>`, or call it through `bash`/`python3`. |
| interp-manifest | `plugin.json` names a hooks file that is missing or lies outside the plugin folder, so the hooks do not load. | Open the plugin's `.claude-plugin/plugin.json` and check the `hooks` value. | Point it at a file inside the plugin, such as `./hooks/hooks.json`. |
| plugin-path-missing | A plugin is enabled but its install folder is gone, so it does not load. | `ls` the install path shown. | Reinstall it, or set it to false in `enabledPlugins`. |
| plugin-not-installed (note) | A plugin is enabled in settings but has no install record for this project. The doctor skipped it. | Look in `~/.claude/plugins/installed_plugins.json`. | Install it for this project, or remove the entry. |
| could-not-read | A settings or hook file exists but could not be read: it did not parse, it is too large, or it is not a regular file (a pipe or device). Its hooks were not judged. | `ls -l` the file named (a first character other than `-` is not a regular file); run a JSON checker on it. | Fix the syntax, or replace the odd entry with a regular file. |
| could-not-check-commands | Some commands use a variable the doctor cannot resolve, have an unbalanced quote or use a non-POSIX shell. | Read the commands in the file; they are not shown here. | None needed; this is a limit of the check, not a fault. |

Re-run: `--section interpreters`.

## hook failures

| id | meaning | confirm | fix |
|---|---|---|---|
| hook-failing | A hook's command recorded non-blocking errors in the window. The cause is classified: interpreter missing (127, "command not found"), not executable (126), missing script ("can't open file" or "No such file"), or the hook's own error. | Run the hook command by hand with a sample payload on stdin, under `env -i PATH=/usr/bin:/bin`. | See the cause; the interpreter findings above usually explain it. |
| hook-timeout | The hook was cancelled after hitting its timeout. | Time the command by hand. | Make it faster or raise its `timeout`. |
| hook-failing-async | An async hook returned a non-zero code. These records carry no command, so they are grouped by event only. | Find async hooks for that event in your settings and plugins. | Run each by hand with a sample payload. |
| no-transcripts | No transcript files in the window, or no transcript folder. The section could not check. | `ls ~/.claude/projects`. | Widen `--days`, or accept the limit. |
| scan-partial | The scan stopped at its time or size budget before every transcript in the window was read. A clean result covers only what was read, so the section is could not check, not ok. Problems found in the part that was read are still reported. | The coverage line says how many files were read. | Narrow `--days` and re-run. |
| no-hook-records | Transcripts were scanned and hooks are configured, but no hook record of any kind was seen. Either nothing ran, or the transcript format changed. | Open a recent transcript and search for `hook_`. | Run a session that triggers a hook, then re-run. |

Notes: a label that matches no current hook is reported as "no longer configured (may be fixed)" and does not make the section a problem. A label shared by several hooks is "ambiguous" and names each owner. When the owning file changed after the last failure, the line says so; re-run after a new session to confirm.

## injection weight

| id | meaning | confirm | fix |
|---|---|---|---|
| inject-heavy | The mean injected context per session for an event is at or above the flag line (10,000 bytes unless `--inject-bytes` changes it). | The report lists the event and, for SessionStart, the hooks behind it. | Trim what the hook prints, or print a pointer to a file. |

Per-event totals come from the context records only. The per-hook split comes from success records, which exist only for some runs; events without them say "per hook: not recorded".

## always-on weight

| id | meaning | confirm | fix |
|---|---|---|---|
| weight-heavy | The skill and command listing is larger than Claude Code's listing budget (derived from the context window and a fraction; `SLASH_COMMAND_TOOL_CHAR_BUDGET` overrides it). Over budget, lower-priority entries are cut to name only. | The report prints the total, the budget and the heaviest sources. | Shorten descriptions, or turn off plugins you do not use. |

The doctor counts description text plus `when_to_use`, caps each entry at the per-entry limit (1,536 characters, or `skillListingMaxDescChars` from your settings) and marks longer ones "cut". A skill with `disable-model-invocation: true` counts zero. A skill with no description counts its first body line (capped), and the report notes it. The total excludes bundled and claude.ai skills.

## function hooks flag

| id | meaning | confirm | fix |
|---|---|---|---|
| flag-off-mods-shipped | Function hooks are off and an enabled plugin ships a mod. The classic hooks of that plugin still run; the mod does not. | The report names the plugins and the source that decided. | `export CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` or add it under `env` in settings; restart. |
| flag-disabled-all-hooks | A settings file sets `disableAllHooks: true` while hooks are configured. None of them run. | Open the settings file named. | Remove the setting. |
| flag-register-orphan | A plugin ships `hooks/register.ts` but no hooks file lists it under `modules`, so it never loads. | Open the plugin's `hooks/hooks.json`. | Add `"modules": ["./register.ts"]`. |
| flag-module-missing | A hooks file lists a module that does not exist. | `ls` the path. | Create the file or remove the entry. |
| flag-unrecognised | The environment variable holds a value that is not 1/true/yes/on or 0/false/no/off. | `echo` it, or look at the settings `env` entry. | Set it to 1 or 0. |
| flag-cache-unreadable | The config file with the cached server value is missing or unreadable, so the report fell back to the default (on). | Look for `~/.claude.json`. | Start Claude Code once, or set the variable yourself. |
| flag-unknown | Mods are shipped but the flag state could not be determined. | See the source list in the report. | Set the variable explicitly. |

An environment variable that is set always overrides the cached server value. A missing cache entry means on by default; the cache can lag the server.

## python3

| id | meaning | confirm | fix |
|---|---|---|---|
| python-missing | python3 is on neither a bare PATH nor yours. Every hook that calls it fails with 127. | `env -i PATH=/usr/bin:/bin sh -c 'command -v python3'`. | Install python3. |
| python-needs-path (note) | python3 is only on your shell PATH. | Same command, with and without `env -i`. | Install it where a bare PATH sees it. |
| python-old | python3 is older than 3.9. | `python3 --version` under `env -i PATH=/usr/bin:/bin`. | Install a newer one. |
| python-broken | `python3 --version` failed under a bare PATH (for example a stub that needs developer tools). | The report quotes the output. | Repair or reinstall python3. |
| python-stub | `/usr/bin/python3` is the developer-tools stub and the tools are missing. It was not run, because running it opens an install prompt. | `xcode-select -p`. | Install the command line developer tools. |
| python-probe-timeout | `python3 --version` did not answer in time and was stopped. | Run it by hand. | Investigate why it hangs. |
| python-not-probed | The version probe was skipped (`--no-exec`, or no time left). | n/a | Re-run without `--no-exec`. |

The probe runs only for the python3 found under a bare PATH, only when it is not the interpreter already running the check, with no input and a short timeout.

## any section

| id | meaning |
|---|---|
| internal-error | The section raised an unexpected error. The other sections still printed. Report it with the exception name shown. |
| no-config-dir | The config folder was not found, so the section could not check. Pass `--home DIR` or `--config-dir DIR` if your config lives elsewhere. |
