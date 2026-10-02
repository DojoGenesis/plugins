# dojo-verify

"Done" means a check ran and passed in this session. Flags claims of success with no evidence behind them.

Part of the Dojo Genesis suite. It makes rule 5 of the Dojo Protocol ("done means verified") a hook instead of a reminder: when the final message says tests pass, it's fixed, it's deployed, and no check has passed since the last change, the stop is sent back once.

## Install

```
/plugin marketplace add DojoGenesis/plugins
/plugin install dojo-verify@dojo-genesis
```

## What's in it

| Component | What it does |
| --- | --- |
| `hooks/stop_evidence.py` | Classic Stop hook. Reads the newest part of the session transcript, finds the last change the main thread made (an edit tool, or a command that writes files), and reads the final message for a success claim. If it finds a claim and no recognized check came back clean after that change, it blocks the stop once with a reason that tells the model to run the check or say plainly that it's unverified. A session with no change in it isn't judged. |
| `skills/evidence/` | One skill: the six evidence rules, a table of what counts as evidence, and a three-line done template. |
| `hooks/register.ts` | The mod (early access): shows `UNVERIFIED` in the status line and a toast, and counts subagents as dispatched, returned and failed. It only shows; it can't block. |
| `evals/` | Two eval scaffolds (`claim-needs-check`, `unverified-disclosed`). They are not run by anything in this repo. |

## Two tiers

**Classic (the core).** The Stop hook is a Python 3 script using only the standard library. It works on a stock macOS `python3` and needs nothing enabled. No model calls, no network, nothing written into your project. Its only state is a small marker file under `${CLAUDE_PLUGIN_DATA}` (or the system temp directory) so one finished turn isn't blocked twice.

**Mod (early access).** Function hooks are off on many accounts. To try the mod, enable them first:

```
export CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1
```

(or add it under `env` in `~/.claude/settings.json`), then install the plugin. The mod adds what only the engine sees:

- a session ledger of main-thread tool calls: the last change, and whether a clean check ran after it. It shows an `UNVERIFIED` flag when the final answer claims success and the ledger has a change with no clean check after it;
- `agents: dispatched N / returned M / failed F`, with `(K outstanding)` while some haven't answered. A returned agent is one whose turn ended with a non-empty answer. The count is per turn: agents that have settled drop out at your next prompt, and ones still running carry over.

The status line is one line per plugin, so both go in a single string. The mod makes no model calls. Without function hooks everything above the mod still applies.

## The rule

A success claim is backed when a recognized check ran, and came back clean, **after the last change** in the session. The check can be in an earlier prompt of the same session: the evidence is the session's, not the turn's. A change after the check (another edit, a file-writing command) puts the claim back to unbacked. If the session made no change, nothing is judged.

### What counts as a change

- The edit tools: `Edit`, `Write`, `MultiEdit`, `NotebookEdit`. One whose result was an error didn't change anything and doesn't count.
- A Bash command that writes files: an output redirect (`> f`, `>> f`, `>| f`, `&> f`), `tee`, `sed -i`, `awk -i inplace`, `mv`, `cp`, `rm`, `mkdir`, `touch`, `find -delete`, `find -exec` or `xargs` running one of these, `wget` (unless it prints to stdout), `tar x`, `unzip`, `git checkout`, `git restore`, `git reset`, `git apply`, `git merge`, `git pull`, `git stash`, `git clone`, `gh pr checkout`, a package install or removal (`npm install`, `pnpm add`, `pip install`), a formatter that rewrites (`prettier --write`, `ruff format`, `cargo fmt`, `go fmt`), `node -e` or `python3 -c` code that writes a file, and similar.
- Shell compounds are read too: the keyword that opens a clause (`do`, `then`, `else`, `elif`, `if`, `while`, `until`, `{`, `!`) isn't the program. `for f in src/*.py; do sed -i ... "$f"; done`, `if [ -f a.py ]; then sed -i ... a.py; fi` and `{ sed -i ... a.py; }` are changes, and `for t in tests/test_*.py; do python3 "$t"; done` is a check (the loop variable is read as the check script it iterates over). The keyword is skipped again after a wrapper (`time { rm -rf build; }` is a change).
- A heredoc body is read by what receives it. `cat > f <<EOF` writes text. `bash <<EOF` runs the body as commands, so a `sed -i` inside it is a change and a test run inside it is a check. `python3 - <<EOF` or `node <<EOF` runs it as code, and it's a change when the code writes a file.
- A command that exited non-zero still ran, so what it wrote counts: `sed -i ... && pytest` that fails is a change followed by a failed check. Only a segment that never started changed nothing, and that is judged one segment at a time: a command the engine refused (a hook, a permission prompt) changed nothing, and so did a program the shell reported as not found and whatever came after it in the same `&&` chain. The report is read in bash's wording (`bash: pytest: command not found`), zsh's (`zsh:1: command not found: pytest`, `(eval):1: command not found: rm`) and dash's (`sh: 1: npx: not found`), and a wrapper that was not found (`npx tsc` with `npx: not found`) counts like the program itself. What ran before it did run, so `sed -i ... && pytest` with `pytest: command not found` is still a change. `Permission denied` is an ordinary runtime error, not a refusal to start: `rm -rf build && cat secret` changed the files.
- Not changes: reads, `git commit`, `git add`, `git push`, a redirect to `/dev/null`, anything that only touches the temp directory (`git diff > /tmp/x.diff`, `Write /tmp/notes.md`, `rm -rf /tmp/scratch`), and a `tee` or redirect downstream of a check in the same pipe (`pytest | tee out.log` saves the check's output; it doesn't change the code).
- Dispatching a subagent isn't a change here. Edits made inside a subagent aren't in the main transcript, so a session where only agents edited files isn't judged.

### What counts as a claim

- **Strong claims:** tests pass, the suite passes or is green, CI is green, all checks pass, "all 112 passed", `112/112 passed`, "12 passed, 0 failed", "130 tests, all passing", everything passes, no failures, both pass, `Tests: passing`, all green, verified, fixed, deployed, confirmed working, build passes or builds clean, typecheck or lint clean ("lint and typecheck are clean"). A strong word right after "a", "the", "with" and the like ("a fixed seed", "the deployed copy") is read as an adjective and skipped.
- **Weak words** (done, works, is working, builds) are skipped in "how it works" phrasing.
- A claim is skipped when it's negated ("not verified", "isn't fixed"; a negation stops at "and" and "but", so "no regressions and all tests pass" is still a claim), a question (see below), or future or conditional ("once it's deployed", "if the tests pass", "need to get the tests passing"). Fenced code blocks and inline code are ignored; an unclosed fence hides only its own line.
- **A question is skipped, a claim followed by a question is not.** "Is it fixed?", "Should I deploy it?" and "Want me to commit?" claim nothing. "Fixed it and all tests pass, want me to commit?", "All tests pass; should I open a PR?" and "Fixed the parser and the build is green — shall I push?" claim something and then ask, so the part before the question is judged. The question starts at the first comma, semicolon, dash or "and"/"so" that is followed by a question opener ("want me", "should I", "right?"); with no opener, at the last comma, semicolon or dash. A question with none of those has nothing to judge.
- **A question that asserts something is judged for that part.** An opener doesn't hide a claim that comes after "now that", "since", "because", "given" or "as" and a clause: "Want me to commit now that all tests pass?", "Should I commit, since all tests pass?" and "Shall I push it now that it's fixed and verified?" claim the tests pass, so they need a check behind them. A condition or a timing claims nothing ("Should I commit as soon as the tests pass?", "Want me to deploy once the build is green?", "Should I mark this as fixed?"). "Should be fixed now and all tests pass, want me to commit?" starts with a hedge, not a question, so its first part is judged.
- **Disclosures are narrow.** Only an explicit statement that the work is unverified, untested or not run excuses a claim. It has to say so about the work itself ("unverified", "untested in prod", "I couldn't run the tests", "I haven't verified it", "it hasn't been tested", "the fix wasn't tested"). It excuses the claims in its own clause and in the clause beside it, where clauses are cut at `;` and before "but", "and", "though" and the like, and never past the sentence. "Fixed the parser (unverified)", "Fixed the typo; not tested", "Deployed, untested in prod" and "Fixed it, but I couldn't run the tests" are fine. "Fixed and deployed. I couldn't verify it in production." is flagged, because the claim sits in a sentence of its own.
- **A description of the bug, or of how you debugged it, isn't a disclosure, in most wordings.** "The loader never checked the file size", "we didn't check for null", "the token wasn't validated", "I couldn't reproduce it at first", "it was never validated before reaching the parser" say what was wrong, not that the fix is unchecked. A first-person history is read the same way when it carries a history marker: "It failed in CI because we never ran the migration there; fixed", "Previously we never validated it; all tests pass now", "I never ran it on Python 3.9 before; fixed", "we didn't test it before but it's fixed now". A time marker anywhere in the clause makes any such statement a history: "previously", "earlier", "originally", "at first", "last week", "yesterday", "until", "in the original PR", "root cause", "slipped through" before it, and "before", "ago", "yesterday", "which is why" or "which is how" after it. A statement in the past tense ("never", "didn't", "was not") is also a history when it has a cause: "because" before it, "since", "as" or "when" right before it ("CI was red since we never ran the migration"), or "until", "hence", "so it crashed", "which broke prod" after it. A reason for not running is not a history: "I couldn't run the tests because Docker is down", "Because Docker is down, I couldn't run the tests" and "Fixed it, but because the fixture DB is gone I couldn't run the tests" are still disclosures. Without a marker, "we never tested it on Windows" is ambiguous and is read as a disclosure (see Honest limits).

### What counts as a check

A Bash command that ran a test, build, lint, typecheck, `curl`, Playwright or similar runner, whose result was not an error and whose output shows no failure markers. The command is parsed, not substring-matched, so `ls build/`, `cat test_output.log`, `echo "pytest passed"`, the shell builtin `test -f x` and `git commit -m "fix tests"` don't count.

- Runners recognized include `pytest`, `vitest`, `jest`, `go test`, `cargo test`, `npm|pnpm|yarn|bun test`, `make test|check`, `node --test`, `ctest`, `mix test`, `bundle exec rake test`, `php artisan test`, `tsc`, `eslint`, `ruff check`, and `claude plugin test|validate`.
- A test or check script counts by its name: `python3 tests/test_x.py`, `./scripts/test.sh`, `bash scripts/release-check.sh`, `node tests/a.test.js`. A runner in a `tests` folder counts too (`python3 tests/*.py`, `python3 tests/run.py`), but a folder alone doesn't make a script a check (`python3 tests/seed.py` doesn't count), and a script under a `fixtures`, `helpers` or `data` folder never counts: `python3 tests/fixtures/make_data.py` builds test data, it doesn't test anything.
- A package-manager run of a tool (`pnpm tsc --noEmit`, `yarn jest`) counts like the tool.
- `--version`, `--help`, `--collect-only` and `--listTests` runs don't count, and neither do dry runs (`make -n test`, `just --dry-run`).
- A check whose exit code was swallowed (`|| true`, `; true`, a pipe into `tail` without `pipefail`, or `CHECK && echo ok || echo broken`) counts only if its output is visible and clean, and not at all when its own stdout goes to a file (`pytest > out.log; echo done`).
- A check in the `then` branch of an `if` that has an `else` or `elif` after it is masked, the way `|| echo` masks one: only one branch runs, so `if [ -d tests ]; then pytest -q; else echo "no tests dir"; fi` with the output `no tests dir` ran no check. The `else` branch's echo is its handler phrase. It counts when its own output is visible and doesn't just show the `else` branch.
- In one command line, order matters: `sed -i ... && pytest` is a change followed by a check, and backs the claim; `pytest && sed -i ...` is a check followed by a change, and doesn't.
- A background run counts when its completion notice reports exit code 0.
- A browser tool call that navigates, takes a screenshot or snapshot, or reads the page, with a non-error result, counts; listing tabs or servers doesn't.

## Modes and kill switches

Set `mode` in the plugin's settings (`userConfig`):

| Mode | What happens |
| --- | --- |
| `block` (default) | Block the stop once with `{"decision":"block","reason":"dojo-verify: ..."}`. |
| `warn` | Show a system message and don't block. |
| `off` | Silent. The mod goes inert too. |

Environment switches, checked in this order: `DOJO_OFF=1` (the whole suite), then `DOJO_VERIFY_OFF=1` (this plugin). `1`, `true` and `yes` turn it off; `0` does not. The mod also reads both.

Two more settings affect the mod only: `show_status` and `toast_unverified` (both default on).

## Honest limits

- **It matches text.** Claim detection is a pattern list, so it can false-positive and false-negative. A "done" in an odd sentence can slip past, and an unusual phrasing can trip it. The set of patterns is in `hooks/patterns.json`.
- **A session with no change in it isn't judged.** That includes a chat-only session: "all tests pass" typed from memory, with nothing edited, passes, because the hook can't tell a description from a report without a change to anchor it. It also includes a session whose only edits happened inside a subagent.
- **After an unchecked change, descriptive words can be flagged.** Once the session has a change with no clean check after it, a later reply that says "your site is deployed on Pages" or "the bug was fixed in 2.3" is read as a claim. Run the check, or write the sentence so it says what it is.
- **A disclosure covers the clause beside it, whatever it names.** "All tests pass; I couldn't test the deploy" is excused, though the caveat is about the deploy and the claim is about the tests. The hook doesn't compare what the caveat names with what the claim says. A claim two clauses away from the caveat isn't excused.
- **Bug histories are told apart by markers, not by meaning.** "The bug slipped through; we never tested it on Windows; fixed" has no marker in the clause that holds "we never tested it", so the hook reads it as a disclosure and lets the claim through. A history worded with none of the markers above can still excuse a claim. The markers are a list, so a new way of telling a history ("our mistake: we never ran it") can still be read as a disclosure, and a disclosure told with a cause ("Since I didn't run the tests, treat it as unconfirmed") can be read as a history.
- **It proves a check ran, not that it was the right check.** Running a linter on an untouched package, or `curl` against an unrelated URL, satisfies it. That judgement is the model's and yours; the `evidence` skill is where it's taught.
- **A later failing check doesn't cancel an earlier passing one.** `pytest` passes, then `npm run build` fails without writing anything, then "tests pass" is backed. Evidence isn't revoked by a failure that came after it, unless that command also changed files.
- **Some changes are invisible to it.** A script that writes files (`python3 gen.py`) isn't known to be a change, nor is a download with `curl -o` or an archive made with `tar c`, and `git push` and deploy commands aren't changes either, so a "deployed" claim after `wrangler deploy` is backed by any earlier clean check. Load the live page; the `evidence` skill says why. A script named like a check (`scripts/check_env.py`) counts as one, whatever it checks.
- **Shell compounds are read by keyword, not run.** `case`, functions, `for (( ))` loops and loops over `$(...)` output aren't unpacked, and a loop variable is read as a check script only when the `for ... in` list names one (`tests/test_*.py`). Which program a "command not found" names is read from the message, so a wrapper that reports the failure another way (`uv run foo`) is not matched and its writes count. Which branch of an `if` ran is guessed from the output (the `else` branch's echo), not from the condition, so a then-branch check next to an `else` needs visible output that isn't just the `else` branch's.
- **It only sees the main thread.** A subagent's own test run isn't in the main transcript, so it can't back a claim either.
- **It blocks once per prompt.** After a block, the continuation arrives with `stop_hook_active` set and the hook never blocks twice in a row. A marker keyed on the session and the prompt means the same message is never blocked twice.
- **The mod can't block.** `turn.complete` can only display. Its status is information.
- **The mod's session starts when it loads.** Changes made before it loaded aren't in its ledger. It also can't see a background run's completion notice, so it doesn't count a background check, while the classic hook does.
- **Compaction ends the view.** Changes before the latest compaction summary aren't seen, so a session that compacted after its last edit isn't judged until it changes something again.
- **It reads only the newest part of the transcript**, under a time budget. A change older than that isn't seen, and then nothing is judged. A test writes a transcript on either side of the limit to prove it.
- **It reads only the start and the end of a very long message**: the first 4,000 and the last 12,000 characters, and at most 400 sentences. A claim in the middle of a message longer than that isn't seen. The limit is what keeps the pattern matching fast on any input, in the hook and in the mod, which runs inside the engine.
- **A scratch file outside the project isn't a change.** Anything under `/tmp`, `/private/tmp`, `/var/folders` or `$TMPDIR` is ignored, so a session that only rewrites files there is read as unchanged. The mod's classifier is a copy of the hook's, so both read the same lists.

## Tests

```
cd plugins/dojo-verify && python3 -m unittest discover -s tests -v
CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/dojo-verify
claude plugin validate --strict plugins/dojo-verify
```

The Python and mod tests run the same case table (`tests/cases.json`, copied to `tests/cases.ts`): claims, commands, and whole sessions. `hooks/patterns.ts` is a copy of `hooks/patterns.json` made by `scripts/sync_patterns.py`; a test fails if either copy drifts.

Tested with Claude Code 2.1.286.

License: Apache-2.0.
