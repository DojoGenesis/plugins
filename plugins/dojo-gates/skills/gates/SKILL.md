---
name: gates
description: Use when a dojo-gates guard denies or warns on a Bash, Read or Edit call, or when you need its guard ids and overrides (staging, pushed-rewrite, secret-print, token-url, big-read, mac-timeout, masked-exit).
model: inherit
category: govern-publish
---

# gates

dojo-gates runs ten small guards as hooks. A deny names the guard id and what to do instead. Do that; don't look for a way around it. No guard calls a model or the network.

## The guards

| id | event | what it stops | do this instead |
|---|---|---|---|
| staging | Bash | `git add -A`, `git add --all`, `git add .`, `git add :/`, the same with `git stage`, `git commit -a` / `-am` | stage explicit paths: `git add src/a.py src/b.py`, check `git status`, commit |
| pushed-rewrite | Bash | `git commit --amend`, `git rebase`, `git reset --hard <ref>` when the commits are already on a remote branch; force pushes that would drop commits the remote has | make a new commit or a revert; to match the remote, `git reset --hard origin/<branch>` |
| secret-print | Bash | echoing a secret-shaped variable (name ends in TOKEN, SECRET, PASSWORD, KEY or the like; `MAX_TOKENS`, `TOKEN_LIMIT` and `API_KEY_FILE` are fine) to the terminal, a file or the clipboard, feeding one to a program that prints its stdin (`cat <<< "$TOKEN"`), `printenv` or `env` with no target, reading or grepping `.env*` files (globs too) | `[ -n "$NAME" ] && echo set`, `echo ${#NAME}`, read `.env.example`, `grep -q`; to give a secret to a program, `prog <<< "$NAME"` |
| token-url | Bash | a token or password typed into a git, curl, gh or wget command or URL | credential helper, `gh auth`, `-H "Authorization: Bearer $VAR"`, SSH remote |
| big-read | Read | reading a file over 256 KB with no `offset` or `limit` | `grep -n 'pattern' file`, then Read with `offset` and `limit` |
| mac-timeout | Bash | `timeout N cmd` on macOS when neither `timeout` nor `gtimeout` exists | the Bash tool's `timeout` parameter, `gtimeout` after `brew install coreutils`, or `perl -e 'alarm shift; exec @ARGV' N cmd` |
| masked-exit | Bash (warns) | a test, build or lint command piped into `tail`, `head`, `grep` or `tee`, then `&& git commit` or `&& git push` | run the check alone and read its result, or `set -o pipefail` |
| config-first | after Bash | output showing an authorization error, a refused connection, a missing command or a missing path | check env, settings and credentials before reading code (once per session per kind) |
| empty-probe | after Bash | a grep, rg, find, fd, ls, curl -s or jq that printed nothing | prove the probe finds a known positive before trusting the empty result (once per session) |
| claude-md-reach | Write, Edit | off by default: the first edit under a directory whose nearest CLAUDE.md wasn't loaded | Read that CLAUDE.md, then edit |

## Overrides (for the person, not the model)

These are read from the environment Claude Code started with, never from a command's text, so a prefix like `DOJO_GATES_SKIP=staging git add -A` does nothing.

- `DOJO_GATES_SKIP=staging,big-read` turns off just those ids.
- `DOJO_GATES_OFF=1` turns off every guard in this plugin; `DOJO_OFF=1` turns off the whole Dojo suite.
- `claude_md_reach` is a plugin option (boolean, default false); set it in the plugin's settings to turn that guard on.

If a guard blocks something you believe is right, say so and ask the person; don't try to dodge it with `eval`, a script file or another indirection.

## Honest limits

- These are token and pattern checks over the command text, not a shell parser. They follow `&&`, `|`, `;`, subshells, `$( )`, `bash -c`, `eval`, here-strings, leading redirections, and wrappers such as `sudo`, `env`, `xargs` and `find -exec`, one level at a time. Deeper indirection, scripts, aliases, `parallel` and `coproc NAME { ...; }` get past them.
- Bash only. Other tools that run git or print files are not covered.
- `git add -u` stages every tracked change but isn't blocked. `git pull --rebase` isn't checked.
- big-read overlaps Claude Code's own read-size limit; it mainly changes when the refusal lands and what it points at.
- pushed-rewrite asks whether the commits are on a remote branch you already fetched; it never fetches. A force push is denied only when it would drop commits the remote has. `reset --soft`, `--mixed`, `--keep`, `--merge` and `push --mirror` aren't checked.
- secret-print can't follow a secret through a script or `cp`, and doesn't catch `sed` or `awk` over a `.env` file, or `set` / `export -p`. Writing a secret to a file (`> .npmrc`) is denied too, since the next `cat` would print it; the person can allow that with the skip override.
- claude-md-reach guesses what was loaded from where the session started plus what Claude Code reports; treat it as a nudge.
