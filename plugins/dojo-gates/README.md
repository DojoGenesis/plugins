# dojo-gates

Deterministic guards for the mistakes that waste a day: blanket staging, rewriting pushed commits, printing secrets, oversized reads, silent probes.

Each guard is a plain hook script. It looks at the tool call, and either lets it through, blocks it with a one-line reason and the fix, or adds a short note. No guard calls a model or the network.

## Install

```
/plugin marketplace add DojoGenesis/plugins
/plugin install dojo-gates@dojo-genesis
```

Tested with Claude Code 2.1.286. Classic tier only: hooks and a skill, no mod (`mod tier: none`), so nothing needs function hooks turned on.

## The guards

| id | event | rule |
|---|---|---|
| staging | before Bash | deny `git add -A`, `git add --all`, `git add .`, `git add :/` (the whole-tree pathspec), their `git stage` synonym, and `git commit -a` / `-am`; stage explicit paths |
| pushed-rewrite | before Bash | deny `git commit --amend`, `git rebase` and `git reset --hard <ref>` when the commits are already on a remote branch, and force pushes that would drop commits the remote branch already has |
| secret-print | before Bash | deny echoing secret-shaped variables (a name that ends in `KEY`, `TOKEN`, `SECRET`, `PASSWORD` or the like, and isn't `MAX_TOKENS`, `TOKEN_LIMIT`, `API_KEY_FILE` or another description of one; the `${NAME:+..}${NAME:-..}` idiom included), feeding one to `cat`, `tee`, `sed` and other programs that print their stdin, `printenv` or `env` with no target, and reading or grepping `.env*` files (the `.env*` glob too) |
| token-url | before Bash | deny tokens and passwords typed into git, curl, gh or wget arguments and URLs |
| big-read | before Read | deny reading a file over 256 KB when neither `offset` nor `limit` is given |
| mac-timeout | before Bash | on macOS, deny `timeout N cmd` when neither `timeout` nor `gtimeout` exists, with the fix |
| masked-exit | before Bash | warn when a test, build or lint command is piped into `tail`, `head`, `grep` or `tee` and then `&& git commit` or `&& git push` |
| config-first | after Bash | note an authorization error, refused connection, missing command or missing path: check env, settings and credentials before code (once per session per kind) |
| empty-probe | after Bash | note a search or probe that printed nothing: prove it sees a known positive first (once per session) |
| claude-md-reach | before Write, Edit | off by default; deny once per file when the nearest CLAUDE.md was never loaded |

Every deny names its guard id and says what to do instead. The `gates` skill lists the same table with the alternatives, so the model can read it when a guard fires.

## Components

Counted from disk:

| what | count |
|---|---|
| skills | 1 (`gates`) |
| agents | 0 |
| commands | 0 |
| registered hook entry scripts | 4 (`bash_guard.py`, `read_guard.py`, `claude_md_reach.py`, `bash_after.py`) |
| shared hook modules | 3 (`_common.py`, `_shell.py`, `_guards.py`) |
| guards | 10 |
| hook events | PreToolUse, PostToolUse, PostToolUseFailure, InstructionsLoaded |
| eval scaffolds | 4, not run (`evals/`) |

`bash_after.py` serves both PostToolUse and PostToolUseFailure, because Claude Code reports a Bash command that exits non-zero as a failure event. `claude_md_reach.py` also records InstructionsLoaded events, but only when its option is on.

## Option

- `claude_md_reach` (boolean, default false): turn on the CLAUDE.md reach guard.

## Kill switches

Set these in the environment Claude Code starts with (or under `env` in `settings.json`). The hooks read their own environment, never the text of a command, so typing a prefix in front of a command does nothing.

- `DOJO_OFF=1` turns off the whole Dojo suite.
- `DOJO_GATES_OFF=1` turns off every guard in this plugin.
- `DOJO_GATES_SKIP=staging,big-read` turns off only the ids you list.

## Honest limits

- These are token and pattern checks over the command text, not a shell parser. They follow `&&`, `||`, `|`, `;`, subshells, `$( )`, backticks, `bash -c`, `eval`, here-strings, redirections written before the verb, and the wrappers `sudo`, `env`, `command`, `time`, `timeout`, `nice`, `xargs`, `watch`, `caffeinate`, `arch` and `find -exec`. Deeper indirection, script files, aliases, `parallel`, `coproc NAME { ...; }` and `env -S` get past them. ANSI-C quotes (`$'...'`) are read with their backslash escapes; an unquoted `$(cmd)` or `$VAR` in command position is treated as if it may expand to nothing, so the next word counts as the verb.
- Bash only. Other tools that touch git or print files are not covered.
- `git add -u` stages every tracked change and is not blocked. `git pull --rebase` is not checked.
- Heredoc text is not scanned as commands, so the usual `git commit -m "$(cat <<'EOF' ... EOF)"` form passes whatever the message says. An unquoted heredoc (`<<EOF`) does run its `$( )` and backticks, and those are scanned.
- pushed-rewrite looks at the remote branches you already have locally and never fetches. It checks `commit --amend`, `rebase`, `reset --hard <ref>` and force pushes; `reset --soft`, `--mixed`, `--keep` and `--merge`, and `push --mirror`, are not checked. A force push is denied only when it would drop commits the remote branch already has: a force push that matches the remote or only adds commits on top of it is allowed, because nothing is lost. It follows `cd`, `pushd`/`popd`, `git -C`, `--git-dir`, `--work-tree` and `GIT_DIR=` to the repository they name; a path built from a variable it can't see is skipped. A `cd` inside `( ... )` ends with the group. Rebase controls that finish an in-flight rebase (`--abort`, `--continue`, `--skip`, `--quit`, `--edit-todo`) are always allowed. `git reset --hard origin/<branch>` is allowed.
- secret-print treats a name as secret when its last segment is a secret noun: `TOKEN`, `SECRET`, `PASSWORD`, `PASSWD`, `API_KEY`, `ACCESS_KEY`, `PRIVATE_KEY`, `CLIENT_SECRET`, `AUTH`, `CREDENTIALS`, `PAT`, or `KEY` (`MASTERKEY` and `githubToken` count). A trailing `_VALUE`, `_BASE` or `_DATA` doesn't change that (`SECRET_KEY_BASE` is still a secret). A name that ends in a metadata suffix (`_PATH`, `_FILE`, `_DIR`, `_LIMIT`, `_COUNT`, `_SIZE`, `_LEN`, `_TTL`, `_NAME`, `_ID`, `_URL`, `_HOST`, `_PORT`, `_TYPE`, `_ENV`, `_MAX`, `_MIN` and a few more), one that starts `MAX_`, `MIN_` or `NUM_`, and a `PUBLIC_KEY` are not treated as secrets, so `echo $MAX_TOKENS` and `echo "$SSH_KEY_PATH"` pass. A name that merely contains the word (`KEYCHAIN`, `KEYBOARD`, `TOKENIZERS_PARALLELISM`) passes too. It denies `echo` or `printf` of a secret wherever the output goes: a file (`> .npmrc`) or a clipboard tool (`| pbcopy`) is no exception, because a later `cat` reads it back. To hand a secret to a program, feed it on stdin (`gh auth login --with-token <<< "$GH_TOKEN"`); that is allowed unless the program prints its stdin (`cat`, `tee`, `sed`, `awk`, `tr`, `base64`, `jq`, `grep`, a shell, `python`, `xargs` and a few more). The guard cannot follow a secret through a script, `cp` or a program it doesn't know prints its input; it does not catch `sed`, `awk` or `sort` over a `.env` file, or `set`, `export -p` and `declare -p`.
- Beyond the contract list, secret-print also denies `grep` or `rg` on `.env*` files unless the call only tests for presence (`-q`, `-c`, `-l`, `-L`), treats `.envrc` as a secrets file, and denies a glob that would expand to one (`.env*`, `.env.[a-z]*`, `.*`). `.env.example*` is allowed.
- config-first stays quiet about an authorization number on an assertion line (`AssertionError: status: 403 != 200`) when the command is a test, build or lint run; a missing command or a refused connection during a test run still notes.
- big-read overlaps Claude Code's own read-size limit. It mainly changes when the refusal lands and what it points at: before the read, toward grep.
- claude-md-reach cannot see everything Claude Code loaded. It combines InstructionsLoaded events with the directory the session started in; whether InstructionsLoaded reaches plugin command hooks in your build has not been observed in a live session, so expect an occasional one-time nudge for a file that was loaded.
- config-first and empty-probe read the tool's output, which Claude Code can truncate.
- Timing is not claimed here. Each Bash call starts one Python process; git is only run, read-only and for at most three seconds in total, when the command itself contains a history-rewriting verb.

## Layout

```
.claude-plugin/plugin.json
hooks/hooks.json
hooks/bash_guard.py  read_guard.py  claude_md_reach.py  bash_after.py
hooks/_common.py  _shell.py  _guards.py
skills/gates/SKILL.md
tests/        python3 -m unittest discover -s tests -v
evals/        scaffolds only
```

Apache-2.0.
