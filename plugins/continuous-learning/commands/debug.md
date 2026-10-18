---
name: debug
description: Runs 7-step systematic debugging. Use when given an error to diagnose.
argument_hint: "<symptom, error message, or problem description>"
skill: skills/debugging/SKILL.md
---

# /debug

Systematic debugging following a 7-step methodology. Never jumps to fixing without reproducing.

## Behavior

### Step 1: Reproduce

Help the user reproduce the problem consistently:
- What are the exact steps to trigger the issue?
- Does it happen every time or intermittently?
- If intermittent, what patterns exist? (time of day, data size, load)

**You can't fix what you can't reproduce.** Invest time here.

### Step 2: Isolate

Narrow the scope to the specific component:
- Which component, file, function, or line?
- Use **bisection strategy** if the cause is unclear — split the system in half, test each half, repeat

If **~~repository** is connected, use git history to find when the issue was introduced.

### Step 3: Hypothesize

Generate 3-5 possible causes ranked by likelihood:

| # | Hypothesis | Likelihood | Evidence For | Evidence Against |
|---|-----------|-----------|-------------|-----------------|
| 1 | [Most likely] | 70% | [Supporting] | [Contradicting] |
| 2 | [Second] | 20% | [Supporting] | [Contradicting] |
| 3 | [Edge case] | 10% | [Supporting] | [Contradicting] |

For each: what evidence would confirm or reject this?

### Step 4: Test

For the most likely hypothesis, design a targeted test:
- Add logging to confirm the cause
- Isolate variables (remove dependencies, simplify data)
- Apply targeted fix and observe

Document: hypothesis, test method, result (confirmed/rejected), evidence.

### Step 5: Fix

Once cause is confirmed:
- Implement minimal fix
- Add error handling or validation where appropriate
- Add monitoring to catch future instances
- If risky, define a rollback plan

If **~~repository** is connected, suggest specific code changes or logging additions.

### Step 6: Verify

Confirm the fix resolves the original symptom AND doesn't introduce regressions:
- [ ] Original reproduction steps no longer fail
- [ ] Edge cases also work
- [ ] No regressions (other features still work)

### Step 7: Learn

Ask: **Is this a pattern that could recur?**
- If yes, offer to `/plant` a seed (wisdom-garden cross-reference)
- Document what happened for future reference
- Identify systemic improvements to prevent similar bugs

## Output

Debug report with:
- **Symptom** — exact error message or unexpected behavior
- **Reproduction Steps** — how to trigger the issue
- **Hypotheses Tested** — table with hypothesis, result, evidence
- **Root Cause** — what actually caused the issue and why
- **Fix Applied** — what was changed
- **Verification** — confirmation checklist
- **Prevention Seed** — lesson to preserve, systemic improvement to prevent recurrence
