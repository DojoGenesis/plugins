# How often the Dojo hooks are right

The suite's hooks watch for the tells in the Dojo Protocol: a success claim with no check behind it (dojo-verify),
a failure at a configuration boundary, a probe that printed nothing, a secret about to be printed, the whole tree
about to be staged (dojo-gates). A hook that fires when nothing is wrong costs a turn and teaches people to ignore
it, so each one is measured two ways, and this file says what was measured and how to measure it again.

## 1. The fixture suite: anyone can re-run it

```bash
python3 scripts/hook_accuracy.py --failures
```

Fixtures live beside the plugin they test, in `plugins/<plugin>/fixtures/accuracy/*.json`. Each one gives a hook
one input and says what the hook should do with it, by the rubric in section 3. The runner feeds the input to the
real hook script the way Claude Code does (a JSON payload on stdin, a fresh state directory, every kill switch
cleared) and records what it did. Nothing is mocked and nothing leaves the machine. `--hooks-from DIR` runs another
checkout's hooks against the same fixtures, which is how the "before" column below was made. Two runs on the same
tree give the same JSON (`--json`); a test checks that.

Fixtures come from three places, and each says which in its `source` field: the eight misfires reported from one
session on 2026-10-16, the misfire classes found in the field sample (paraphrased, every private detail removed), and
synthetic cases written to test a rule. A fixture marked `known_miss` records an error the hooks still make; it counts in the table but doesn't fail
the run, so the suite is a gate for new disagreements and an honest list of old ones.

Read this table for what it is. The fixtures were written from the misfire classes while the fixes were being made,
so the "after" numbers are in-sample: they show the fixes hold on the cases they were built for, not how the hooks
do on work nobody has seen. Section 2 has that number.

| hook | fixtures | before: precision / recall | after: precision / recall |
|---|---|---|---|
| dojo-verify (Stop) | 37 | 32% / 100% | 62% / 100% |
| config-first: auth | 28 | 75% / 100% | 100% / 100% |
| config-first: cmd | 28 | 33% / 100% | 100% / 100% |
| config-first: conn | 28 | 50% / 100% | 67% / 100% |
| config-first: path | 28 | 62% / 100% | 86% / 75% |
| empty-probe | 9 | 100% / 100% | 100% / 100% |
| secret-print | 17 | 41% / 100% | 88% / 100% |
| staging | 5 | 75% / 100% | 100% / 100% |
| big-read, mac-timeout, pushed-rewrite, masked-exit | 2–3 each | 100% / 100% | 100% / 100% |

With this few fixtures per row, the 95% intervals are wide; the runner prints them.

## 2. The field sample: what happened in real sessions

Fixtures can only test the cases someone thought to write. To see how the hooks do in practice, every firing of a
dojo-verify or dojo-gates hook was collected from one maintainer's local Claude Code transcripts (2 to 17 October
2026 UTC, main sessions and subagents): 382 firings of nine checks. The other plugins' checks aren't in this sample.
The transcripts stay on that machine; only these counts are published.

- **Labels.** Each firing was judged against the rubric by an independent Opus labeler that saw the command, its
  output and the final message, and was told nothing about the fixes. A Sonnet labeler judged a 30% subset (117
  firings) on its own: the two agreed on 95% of them (Cohen's kappa 0.87; 97% and 0.93 for correct versus not).
  No human has labeled these yet.
- **Split.** Firings were split in half by a hash of their id before any fix was written. The fixes were developed
  against one half (plus that report's cases, held there); the other half was replayed once, after the fixes, through
  the old and the new hooks. Each replay feeds the hook the same input it saw in the session, and the old hooks
  re-fire on every replayed firing, so the replay is faithful.

How often a firing was right, before the fixes (all 382):

| hook | firings | right | precision (95% CI) |
|---|---|---|---|
| dojo-verify (Stop) | 226 | 7 (11 borderline) | 3% (2–7) |
| config-first (all kinds) | 73 kind-firings | 22 | 30% (21–41) |
| secret-print | 22 | 0 | 0% (0–15) |
| empty-probe | 24 | 23 (1 borderline) | 100% (86–100) |
| mac-timeout | 22 | 22 | 100% (85–100) |
| staging | 8 | 7 | 88% (53–98) |
| big-read | 7 | 7 | 100% (65–100) |
| masked-exit, pushed-rewrite | 1 each | 1, 0 | — |

The held-out half, replayed through the old and the new hooks:

| hook | right / wrong firings, old hooks | right / wrong still firing, new hooks | precision of what fires |
|---|---|---|---|
| dojo-verify (Stop) | 4 / 104 | 4 / 44 | 4% → 8% (3–20) |
| config-first: path | 6 / 15 | 3 / 3 | 29% → 50% (19–81) |
| config-first: auth | 6 / 1 | 6 / 0 | 86% → 100% (61–100) |
| config-first: cmd | 0 / 2 | 0 / 0 | — |
| secret-print | 0 / 11 | 0 / 2 | 0% → 0% |

Two dojo-gates changes came after this replay was scored, prompted by what it showed: config-first now counts git's
own `warning:` line about a missing path, and secret-print ignores a value printed inside `$(...)` that only feeds
`grep -q`. The held-out figures are from before those two changes, so only the fixture suite tests them.

What that says:

- **dojo-verify blocks a stop about once in twelve times for a real reason, after the fixes.** The fixes remove more
  than half of its misfires on unseen sessions and keep every real catch, but most of what's left needs judgment the
  hook can't make: whether a check that ran is the one the claim depends on, whether a later edit could affect it,
  whose work a sentence describes. A hook this imprecise shouldn't block by default; that is an open decision.
- **config-first is now mostly right when it speaks, and quieter.** It reads error lines by their shape and by who
  printed them, so docs, logs and source code printed to the screen no longer set it off. The price is three real
  missing paths it now misses on unseen sessions: two were wrong-directory failures shown only through `ls`, which
  it now treats as an existence check, the most common misfire it had.
- **secret-print stopped blocking commands that never print a secret.** Every one of its 22 field firings was wrong:
  values captured by `$(...)`, counted, masked, cut to names or sent to `/dev/null`. Its known real catches (the
  deny cases in its tests) still deny.
- **What this sample can't show.** It covers one person's sessions on one machine, so it says nothing about other
  setups. Replaying firings measures precision, not misses: a hook that stayed silent when it should have spoken
  isn't in this sample at all, and only the fixture suite tests for that.

## 3. The rubric

A firing is **right** when the condition the hook names was present, **wrong** when it was absent, and
**borderline** when the rubric doesn't settle it. It doesn't judge whether the advice was useful in general, or
the quality of the work.

**dojo-verify.** Right needs both: the flagged sentence, read in context, says this session's work succeeded
(tests pass, fixed, deployed, verified, works, done); and no check that backs that claim ran and passed after the
last change to project files. A check counts when it exercised the claimed thing and passed: a test, build or lint
run, a script that ran the change and printed a passing result, a load of the changed page, re-reading a written
file when the claim is about its content. A check from before the last change counts only if that change couldn't
affect the claim. Wrong classes: *not a claim* (quoted or reported words, a citation, a description of how
something works, a plan, a question, another sense of the word), *had evidence* (a backing check ran), *no change*.

**config-first**, per kind fired (auth, conn, cmd, path). Right: this command itself failed at that boundary: a
request refused for credentials, a refused connection, a program not installed, a path the command needed that is
missing. Wrong classes: *content* (the words appeared in text the command printed), *downstream* (a code error
caused the failure), *expected probe* (the command asked whether something exists, and "not found" is the answer),
*assertion* (a test reporting a status code from the code under test).

**empty-probe.** Right: a search, lookup or existence probe printed nothing and showed no known-positive control,
so its silence could be read as a negative finding. Wrong: not a probe, not empty, or a control was shown.

**PreToolUse guards.** Right when the named condition is real: a secret value would reach the conversation, the
whole tree would be staged, GNU `timeout` would run on a Mac that doesn't have it, a large file would be read whole,
a pushed commit would be rewritten, a check's exit code would be masked before a commit.

## 4. Rule by rule

What checks each of the ten rules while an agent works, how accurate that check is, and whether anything has
measured the rule's effect. "Field" figures are from section 2; "fixtures" from section 1 (in-sample).

| rule | runtime check | measured accuracy | evidence status |
|---|---|---|---|
| 1. Right model, every dispatch | dojo-router hook on Agent, Task and Workflow calls (warns by default); its mod routes unpinned dispatches by role | Not measured: no fixtures yet, and the field sample covered only dojo-verify and dojo-gates | No eval run; one scaffold (`unpinned-dispatch-pinned`) |
| 2. Scout before you touch | Claude Code itself (Edit refuses a file not read in the session); the `scout-first` skill and scout agent advise | Not a hook of ours, not measured | No eval run; scaffolds in dojo-protocol |
| 3. Keep context small | dojo-gates big-read (denies a whole read over 256 KB) | Field 7 of 7 right (95% CI 65–100%); fixtures 100% / 100% | No eval run; scaffolds in dojo-gates and dojo-protocol |
| 4. Contract before fan-out | dojo-flow's `dag-plan` refuses tracks that share a file or claim the contract file (a script run before a build, not a hook); the `contract` skill advises | Not measured | No eval run; scaffold `build-refuses-overlap` |
| 5. Done means verified | dojo-verify Stop hook (warns by default since the eval; blocks when set to `block`) and its evidence skill; dojo-tally flags agent reports that cite a check they never ran | Field 3% before the fixes (7 of 215); held-out 8% after (4 of 48, CI 3–20%), every real catch kept; fixtures 62% / 100% | **Measured once:** pre-registered with/without eval, 30 runs per arm. No benefit detected (unbacked claims 5/30 without, 4/30 with; difference CI −16 to +22 points), extra cost on controls (×1.29). The hook missed all four unbacked claims in the with arm |
| 6. Count returns, not dispatches | dojo-tally mod (dispatched, returned, failed, silent, unchecked); dojo-flow's scorecard | Not measured | No eval run; scaffold `scorecard-counts-dead-agent` |
| 7. Debug by disproof | Nothing at runtime; skill guidance only | n/a | No eval |
| 8. Config before code | dojo-gates config-first (adds context after a boundary failure) | Field 30% before (22 of 73); held-out after: auth 6 of 6, path 3 of 6, cmd no firings; fixtures path 86% / 75%, conn 67% / 100%, auth and cmd 100% / 100% | No eval |
| 9. Silence is not a finding | dojo-gates empty-probe (adds context after an empty probe); mac-timeout (denies `timeout` where macOS doesn't have it, since a probe wrapped in it prints nothing) | empty-probe field 23 of 23 (CI 86–100%); mac-timeout 22 of 22 (CI 85–100%); recall not measured in the field | No eval |
| 10. Irreversible needs a yes | dojo-gates staging, pushed-rewrite and masked-exit (deny or warn before the command); secret-print and token-url for secrets; Claude Code's permission prompts | staging 7 of 8; pushed-rewrite 0 of 1; masked-exit 1 of 1; secret-print 0 of 22 before, 9 of 11 held-out misfires removed | No eval run; scaffolds in dojo-gates |

Ten older eval scaffolds (four in dojo-gates, four in dojo-protocol, two in dojo-verify) set `scaffold_script` as
inline shell. Claude Code 2.1.299 reads that field as a path to a script file, so each would fail at setup if run.
