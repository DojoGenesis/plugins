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

Fixtures come from three places, and each says which in its `source` field: the five misfires reported from one session on 2026-10-16, the misfire
classes found in the field sample (paraphrased, every private detail removed), and synthetic cases written to test a
rule. A fixture marked `known_miss` records an error the hooks still make; it counts in the table but doesn't fail
the run, so the suite is a gate for new disagreements and an honest list of old ones.

Read this table for what it is. The fixtures were written from the misfire classes while the fixes were being made,
so the "after" numbers are in-sample: they show the fixes hold on the cases they were built for, not how the hooks
do on work nobody has seen. Section 2 has that number.

| hook | fixtures | before: precision / recall | after: precision / recall |
|---|---|---|---|
| dojo-verify (Stop) | 34 | 36% / 100% | 71% / 100% |
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
suite hook was collected from one maintainer's local Claude Code transcripts (2 to 17 October 2026, main sessions and
subagents): 382 firings across 12 hooks. The transcripts stay on that machine; only these counts are published.

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
