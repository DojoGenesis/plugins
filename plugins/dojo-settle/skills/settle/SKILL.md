---
name: settle
description: Use when a claim or a choice needs evidence before it changes anything. Write the hypothesis, decision rule and numeric bar, hash them before the first run, then apply the rule as written. A null result is a result.
model: inherit
category: learn-research
---

# settle

An experiment will be read by someone who wants one answer. Every choice left open until after the data (which reference, which cells, which threshold, when to stop) is a place wanting leaks into the verdict, and it leaks honestly: nobody feels like they're cheating. Close those choices first, then prove the order.

Use it when a benchmark, a vendor or a hunch says the alternative is better and adopting it would change behavior; when a constant (a timeout, a window, a threshold) looks wrong and someone is about to tune it; when an old figure is about to be quoted as settled. Skip it when the change is free and reversible, when no measurement could change the decision, or when the problem is a bug (that's debugging: state the causal chain and the one experiment that turns it on and off).

Files: `${CLAUDE_PLUGIN_ROOT}/templates/prereg.md` is the skeleton. `${CLAUDE_PLUGIN_ROOT}/scripts/prereg.py` has three commands:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/prereg.py" create study/prereg.md --title "..." [--rule ... --bar ... --refutation ...]
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/prereg.py" freeze study/prereg.md
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/prereg.py" verify study/prereg.md [--expect <digest>]
```

`create` writes the skeleton and never overwrites. `freeze` refuses until the marker is there, no `{{placeholder}}` is left in the prose, and each of these holds more than placeholders such as TBD, TODO, n/a or `...` (an HTML comment that is never closed is refused too): what is decided, incumbent, references, decision rule, numeric bars, refutation, frozen grid, baseline arm, held-out author and the task where the protocol should lose. It then records the sha256 of everything above the marker line in `<file>.sha256`. `verify` recomputes it. Exit 0 means the digests match, 1 means they differ or the file was refused, 2 means it couldn't run.

## The nine steps

1. **Pre-register, and write nothing else yet.** Freeze checks ten sections: what is decided and what changes under each outcome (if nothing changes either way, stop); the incumbent, which you measure here rather than quote; the references and which of them could fake the result; the decision rule; the numeric bars, including the null that means keep the incumbent; what would refute the option you want; the frozen grid; the without arm (step 2); who wrote the held-out tasks (step 3); and the task where the protocol should lose (step 5). `create` lays these out.
2. **Baseline arm.** Run a without arm beside the with arm: the same tasks with the change absent. The headline is the with-minus-without difference, never the with score alone.
3. **Hold-out.** The test tasks are written by someone who didn't build the thing under test. Record who in the file. Nothing checks it, so say so if it's the builder.
4. **Two references.** Scoring a candidate against its own output measures agreement with itself. Carry a second, independent reference and require the bar in both.
5. **Include a task where the protocol should lose.** One where the thing under test should do worse than leaving it out, or do nothing. If it wins there too, suspect the harness.
6. **Freeze, then record the digest outside the file.** Run `freeze`, copy the digest into a commit message or a note to your reviewer, and only then measure. The sidecar sits next to the document and can be rewritten with it; the outside copy is what makes the ordering mean something.
7. **Measure the incumbent first, then the whole grid.** Reproduce the incumbent's published figure with no change to the product; if you can't, you've found a bug in the record, not a result. Run every frozen cell, including the ones that make your favorite look bad. Plant one known-bad input and one known-good input and check the harness scores them the way you'd expect; a pass is not evidence a check fired until it has failed on something that should fail.
8. **Apply the rule mechanically.** Replicate on a second sample and compare deltas. Split one sample in half to see the noise floor; if the halves differ by more than your bar, no single winner is nameable and saying so is the finding. If only the direction replicates, report the sign pattern and don't print a decimal the noise can't support. Name every configuration that disagreed with itself. If the null fires, say so and keep the incumbent.
9. **Write what outranks the ruling, then close.** The mechanism the measurement exposed on the way is often worth more than the verdict; give it a section. Then list gaps (what you couldn't test), anything found broken and left alone, and any input the arms don't share. Run `verify` with `--expect` and paste the output.

## If the grid turns out to be wrong

Don't extend it quietly. Finish the frozen grid, then run the addition as a labelled follow-up with its own rule, and say in the write-up that it came after seeing results. To amend the pre-registration itself, `create` a v2 file that cites v1's digest; `freeze` won't overwrite a recorded digest.

## What the digest does and doesn't show

A match shows the text above the marker is byte-for-byte what it was when you recorded the digest. It doesn't show the text is true, who wrote it, or when: the timestamp in the sidecar is your local clock. Don't call it tamper-proof. Line endings and a leading byte-order mark are normalized, so a different checkout of the same file still matches.

## Anti-patterns

- Writing the rule after seeing the numbers.
- One reference that is the candidate's own output.
- Naming a winner inside the noise floor.
- Dropping the configuration that disagreed with itself.
- Treating a null as a wasted day. It's what makes every non-null believable.
- Shipping the ruling without the section on what outranks it.
- Writing the held-out tasks yourself and calling them held out.
