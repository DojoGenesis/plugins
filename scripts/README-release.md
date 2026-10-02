# Release checks for the suite

Three small tools gate a release of the Dojo suite plugins. They use only the Python
standard library and bash, and they never run a model call, touch git, or deploy.

| Tool | What it does |
|---|---|
| `suite_lint.py` | Structural lint for each suite plugin and for the dependency-only `dojo-suite` plugin: manifest, frontmatter, lengths, hooks, workflows, Python 3.9 compatibility, machine-specific paths, wording. |
| `suite_denylist.py` | Scans files for terms on two private local lists and prints where they are, never what they are. |
| `release-check.sh` | Runs both, plus each plugin's tests, `claude plugin validate --strict`, the mod tests, and the repo's older checks. Prints one table. |

Tests for all three live in `scripts/tests_suite/`:

```
cd scripts
python3 -m unittest discover -s tests_suite -t . -v
```

`release-check.sh` runs that suite itself as the `self-test` row.

## Run it

```
scripts/release-check.sh                    # every step, the eight suite plugins and dojo-suite
scripts/release-check.sh --plugin dojo-gates --only lint,unittest
scripts/suite_lint.py dojo-gates --json
scripts/suite_denylist.py plugins/dojo-gates README.md
```

Run `release-check.sh` again after the integration files (README, llms.txt, marketplace.json,
CHANGELOG, STATUS) change; it scans those too.

### Exit codes

All three tools use the same convention.

| Code | Meaning |
|---|---|
| 0 | Clean. |
| 1 | Defects found (lint errors, denylist hits). `release-check.sh` also exits 1 when any row is `FAIL` or `ERROR`, including a check that could not run. |
| 2 | Could not run (missing interpreter, a missing list, a path that does not exist). `release-check.sh` uses 2 only for bad arguments. An empty run is never a pass. |

Lint warnings never change the exit code.

### Environment

| Variable | Used by | Meaning |
|---|---|---|
| `CLAUDE_BIN` | `release-check.sh` | The `claude` binary for `validate` and mod tests. Default: a 2.1.286 install in the Claude app support folder, else `claude` on `PATH`. It must report 2.1.286 or newer; older binaries make those rows `ERROR`. |
| `DOJO_DENYLIST` | `suite_denylist.py` | Path of the first list. Default: `~/.config/dojo/stealth-denylist.txt`. `--denylist FILE` overrides both. |
| `DOJO_INTERNAL_REFS` | `suite_denylist.py` | Path of the second list. Default: `~/.config/dojo/internal-refs.txt`. `--internal-refs FILE` overrides both. |
| `DOJO_PY39` | `suite_lint.py`, `release-check.sh` | A Python 3.9 interpreter. Default: `/usr/bin/python3`. Plugin hooks must run there, so lint and plugin tests run there too. |
| `DOJO_SCANNER` | website deploy guard | Path to `suite_denylist.py`. The guard calls it with paths as arguments and reads the exit code, so keep that interface stable. |

## `suite_lint.py`

```
suite_lint.py [PLUGIN ...] [--json] [--skip RULE[,RULE]] [--repo PATH]
```

With no `PLUGIN` it lints the eight suite plugins (`dojo-protocol`, `dojo-gates`, `dojo-router`,
`dojo-meter`, `dojo-verify`, `dojo-flow`, `dojo-doctor`, `dojo-settle`) and `dojo-suite` by name. A
plugin from that list that is missing from `plugins/` is an error. Any other `plugins/dojo-*`
directory gets one `note:` line and is not linted; naming it lints it.

`dojo-suite` is dependency-only: a manifest and nothing else. It is exempt from the `budget` and
`kill-switch` rules (it adds no always-on text and has no hooks) and gets the `suite-deps` and
`suite-marketplace` rules instead. Output lines read `plugin/file:line:rule: message`. `--skip` takes a rule id or
a prefix (`py39` skips both py39 rules).

| Rule id | What it checks, and why |
|---|---|
| `manifest` | `plugin.json` has the required fields, a `MAJOR.MINOR.PATCH` version, the exact author, license, homepage and repository values, a description of 200 characters or fewer that matches the frozen promise text, and a name equal to the directory name. A wrong shape here fails installs or breaks the website anchors. |
| `userconfig` | Keys are lower snake case (they become `CLAUDE_PLUGIN_OPTION_<KEY>`), types are known, defaults match their type, `options` only on strings, `min`/`max` only on numbers. |
| `frontmatter` | Strict single-line `key: value`. Quoted values, `[a, b]` lists, a duplicate key, an unquoted `: ` inside a value, block scalars and block lists are all reported. `validate` does not catch the unquoted colon, and real YAML rejects it. |
| `skill` | Name equals directory; description 250 characters or fewer and starting with a verb or "Use when"; body 6,144 bytes or fewer; a `model` key must be an alias, and anything but `inherit` is a warning because it changes the model for that skill's turn. |
| `agent` | Name equals file name; description 200 or fewer; `model` is required and must be `haiku`, `sonnet`, `opus` or `inherit`; `effort`, `tools` and `maxTurns` are required; `tools` is an explicit list. An agent with no model inherits the parent's, which is the failure the router exists to stop. |
| `command` | `description` and `allowed-tools` are required; description 200 or fewer. A command with no description puts its first body line into the always-on listing. |
| `outputstyle` | Output styles have a name and a description. |
| `budget` | A plugin's skill, agent and command descriptions total under 1,000 characters. The suite-wide estimate (characters divided by 4) warns at 3,000 tokens. |
| `hook` | Hook commands start with `python3`, `sh`, `bash` or `node`; bare `python` anywhere is an error; the script an interpreter runs must be written as `${CLAUDE_PLUGIN_ROOT}/...` (hooks run from the user's project, so a relative path never finds the script and the hook fails open without a sound); inline `-c`/`-e` code and `-m` modules are exempt; only `command` hooks are allowed; `register.ts` and the `modules` list must agree; timeouts over 10 seconds warn; an event outside the known list (SessionStart, PreToolUse, PostToolUse, PostToolUseFailure, InstructionsLoaded, Stop) warns. Hooks declared in `plugin.json` (an inline object, a path other than `hooks/hooks.json`, or a list of those) follow the same rules as `hooks/hooks.json`. |
| `plugin-root` | Every `${CLAUDE_PLUGIN_ROOT}/...` path in `hooks.json`, in any hooks file or inline hooks that `plugin.json` declares, and in every Markdown file outside `tests/` and `evals/` exists, stays inside the plugin, and is not a placeholder. |
| `workflow` | In `workflows/*.js`: every `agent(` call sets `model` in its options object; `export const meta` is a pure literal with `name` (equal to the file name), `description` and `phases`; no `Date.now`, `Math.random` or argument-less `new Date()`. |
| `py39-compile` | Every `.py` file compiles under Python 3.9, checked in one subprocess that writes no bytecode. |
| `py39-pep604` | `X \| Y` between types compiles on 3.9 and raises when the code runs, so it needs its own check: in an annotation without `from __future__ import annotations`, in `isinstance`, and anywhere else a type name or `None` is an operand (`X = int \| None`). |
| `py39-api` | Names that do not exist on 3.9, found by asking the 3.9 interpreter about standard-library attributes and `from` imports (for example `itertools.pairwise`, `typing.TypeAlias`), plus `zip(strict=)`, `anext`/`aiter`, `.bit_count()` and `dataclass(slots=)`. A `hasattr(module, "name")` guard in the same file excuses that name. |
| `internal-ref` | Scans every text file, including tests, and every symlink's target string and own path, for a machine-specific home directory path (`/Users/<name>/`, `/home/<name>/`, `C:\Users\<name>\`); obvious placeholder names such as `user` or `tester` pass. This rule knows no private names: those live in the two local lists that `suite_denylist.py` reads. There is no in-file switch to silence it. |
| `voice` | Scans Markdown (outside `tests/` and `evals/`) and the manifest text for the banned public wording in the build contract, including multiplier claims such as "3x faster". No in-file switch; only `--skip voice` on the command line turns it off. |
| `kill-switch` | A plugin with `hooks/*.py` reads `DOJO_OFF` and its own `DOJO_<NAME>_OFF`: the name must appear in a string in the code. A comment or a docstring does not count. Not applied to `dojo-suite`. |
| `hook-no-network` | Hook scripts do not import network modules or call `__import__`. |
| `mod` | A plugin with `hooks/register.ts` declares a boolean `userConfig` entry that switches it off. |
| `symlink` | A symlink inside a plugin must have a relative target that stays inside the plugin and exists. An absolute target, a target that leaves the plugin and a dangling link are errors: a plugin install copies the plugin, and git stores the target string. |
| `junk` | No `__pycache__`, `.pyc` or `.DS_Store` inside a plugin. |
| `evals` | Each `evals/<case>/` has a non-empty `case.yaml`. Scaffolds are checked for presence only and never run. |
| `suite-deps` | `dojo-suite` has a `dependencies` list of bare plugin names; every dependency has a directory under `plugins/`; every one of the eight suite plugins is a dependency; no duplicates, no self-dependency. `dojo-suite` ships only `.claude-plugin/plugin.json` plus an optional `README.md` or `LICENSE`: its manifest may carry only `name`, `version`, `description`, `author`, `homepage`, `repository`, `license`, `keywords`, `dependencies` and `displayName` (an inline `hooks`, `mcpServers`, `skills`, `agents`, `commands` or any other component key is an error), and any other file, folder or symlink is an error. A dependency outside the eight is a warning. |
| `suite-marketplace` | When `.claude-plugin/marketplace.json` exists, every `dojo-suite` dependency is listed in it exactly once. With no marketplace file the check prints a warning and says it did not run. |
| `plugin` | A suite plugin is missing from `plugins/`. |

## `suite_denylist.py`

```
suite_denylist.py [PATH ...] [--allow-missing] [--denylist FILE] [--internal-refs FILE]
```

It reads two local-only lists: the first from `--denylist`, `$DOJO_DENYLIST` or
`~/.config/dojo/stealth-denylist.txt`, the second from `--internal-refs`, `$DOJO_INTERNAL_REFS` or
`~/.config/dojo/internal-refs.txt`. Both use one entry per line:

| Prefix | Meaning |
|---|---|
| `i:text` | case-insensitive substring |
| `w:text` | case-sensitive whole word (not inside a longer word or a hyphenated name) |
| `r:regex` | Python regular expression, searched line by line, case-sensitive unless it sets its own flags |
| `#` | comment; blank lines are ignored |

An entry with another prefix, an empty or whitespace-only term, a regex that does not compile, or
a regex that matches the empty string is skipped and counted, never applied.

Output is `path:line: <REDACTED term #n>`, where `n` is the position among the first list's parsed
terms; the second list prints `#2.n`. A term found in a file or directory name is redacted in the
printed path too. Error paths print only an exception's type name.

Silence is not a finding, so before scanning it runs a positive control for each list: it writes a
canary into a temporary directory, scans that directory with the same walk and match code using only
that list's terms, and requires a hit. The canary comes from the list's first `i:` entry, else its
first `w:` entry, else a string synthesized from its first `r:` entry. If a control fails, or a list
is missing, empty, or gives no way to build a canary, it exits 2. `--allow-missing` turns only a
missing file into a visible `SKIPPED`: with both lists missing it exits 0, with one missing it scans
with the other. `release-check.sh` never passes it.

It skips `.git`, `node_modules` and `__pycache__` and reports how many files it skipped (binary,
over 4 MB, unreadable). It does not follow symlinks, but it checks each one by its own name and by
its target string (the text git stores for it); a hit in the target prints `(in the link target)`, and
the number of links checked is printed on a summary line. UTF-16 files with a byte order
mark are decoded and scanned. It never writes into the tree it scans.

## `release-check.sh`

Each step has a stable id; per-plugin steps are written `step:plugin`, and `--only` accepts
either form.

| Step | What runs |
|---|---|
| `lint` | `suite_lint.py` under Python 3.9. Needs the tool's `suite-lint:` summary line; a clean exit without one is an `ERROR`. |
| `denylist` | `suite_denylist.py` over the plugin directories, README, `llms.txt`, the marketplace file, these scripts and their tests, CHANGELOG and STATUS. A required path that is missing is an `ERROR`, and so is a clean exit with no `control ok` line. |
| `unittest:<plugin>` | `python3 -m unittest discover -s tests` inside the plugin, under 3.9. A run of 0 tests is a `FAIL`, and so is a missing `tests/` directory (except for `dojo-suite`, which has none and gets `SKIP`). Skipped tests are not evidence: any skip makes the row `WARN` with the skip count, and a run where more than 25% of the tests skipped is a `FAIL`. |
| `validate:<plugin>` | `claude plugin validate --strict --json`; the detail column carries the error and warning counts. `--strict` fails on warnings. Output that is not the expected JSON is never a pass: `ERROR` when `claude` exited 0, `FAIL` when it exited non-zero. |
| `mod:<plugin>` | `claude plugin test` with `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`, only for plugins with `hooks/register.ts`. Needs a "Ran N tests" line with N above zero and a `0 fail` line. Output saying function hooks are off is an `ERROR`, not a `FAIL`. |
| `self-test` | This tooling's own tests, with the same skip rules as `unittest`. |
| `face-parity` | `scripts/face-parity.py` (0 is `PASS`, 1 is `FAIL`, anything else is `ERROR`). |
| `plugin-lint` | `scripts/plugin-lint.py`. |

| Status | Meaning |
|---|---|
| `PASS` | The check ran and passed. |
| `WARN` | The check passed but part of it did not run: a unittest row with skipped tests. The row shows the count. |
| `WARN-OK` | The check ran and reported warnings only. Used for `plugin-lint` exit 1, its known baseline of quarantine warnings. |
| `FAIL` | The check ran and failed. |
| `ERROR` | The check could not run (missing binary, old version, missing path). |
| `SKIP` | Not applicable, such as the mod row for a plugin with no `register.ts`. |

The last line is `OVERALL: PASS` or `OVERALL: FAIL` with counts of fail, error, warn-ok and warn
rows. The script exits 0 only when no row is `FAIL` or `ERROR`; read the `WARN` rows yourself. It captures every exit code directly; no check is piped into another
command, so a noisy failure cannot read as a pass.

`scripts/plugin-lint.py` and `scripts/validate-skills.sh` have their own rules (a `category`
key on skills, a fixed list of hook events). Suite plugins are judged by `suite_lint.py`;
`release-check.sh` reports `plugin-lint` beside it so a disagreement is visible, not hidden.

### Adding a plugin to the gate

Add its name (and its promise text) to `SUITE` and `PROMISES` in `suite_lint.py`, and its name to
`SUITE_NAMES` in `release-check.sh`. Lint then requires it as a `dojo-suite` dependency and in the
marketplace file. A plugin outside that list can still be linted by naming it:
`suite_lint.py dojo-example`.

## Limits

- Lint is structural. It checks shape, lengths, names and references. It does not judge whether a
  description is good or a hook does what it says.
- It checks that an agent declares a model alias, not that Claude Code honours it at run time.
- The `agent(` check reads workflow source statically. Options built elsewhere and passed as a
  variable are reported as "not statically visible"; that is a deliberate false positive.
- Mod tests need function hooks on and a 2.1.286 binary. A machine without one gets `ERROR` rows.
- Workflow tests need `node` on `PATH`. Under a cleared environment (`env -i PATH=/usr/bin:/bin`)
  they skip, and the unittest row shows it as a `WARN` or, past 25%, a `FAIL`.
- Several lint rules are heuristics: the skill-description verb check is a stoplist of non-verb
  starts, and the voice scan matches a fixed phrase list.
- Eval scaffolds are checked for presence and are never run here.
- `/usr/bin/python3` exists on macOS. On other systems set `DOJO_PY39`; without a 3.9 interpreter the
  tools exit 2 instead of passing quietly.

Tested with Claude Code 2.1.286.
