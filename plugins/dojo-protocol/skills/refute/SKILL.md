---
name: refute
description: "Use when reviewing a change or testing a claim: a finding needs path:line and a check that shows it; a clean pass says so."
model: inherit
category: repo-docs-health
---

# Refute

The author of a change shares its assumptions, so a review by the same context tends to approve it. Review from a fresh context, against the goal, and try to refute every finding, and every claim of success, before it counts.

A review can end clean. If there is no real defect, the answer is `no defects found`, plus what you checked. Do not manufacture findings to look useful.

## Who reviews

- Default: `dojo-protocol:reviewer` (sonnet). Fresh context, Read/Glob/Grep/Bash. Give it the goal and the files, not your conclusion.
- Claims that need a hard second look (an agent's "all green", a risky merge): `dojo-protocol:judge` (opus). It tries to refute, and it re-runs checks itself.
- The reviewer is read-only by instruction. Its tools list is the only hard limit; Bash can still write if told to.

## Steps

1. **Scope.** Collect the diff or the files, and read the goal. If there is nothing to review, say so and stop.
2. **Read in full.** Read whole files, not only the changed lines; bugs sit where new code meets old.
3. **Pass with three lenses**, in one pass, as prompts and not as a quota:
   - *Breaks in production:* worst input, failing dependency, double run, concurrent run, swallowed error, resource left open.
   - *Hard to maintain:* names that hide intent, hidden coupling, magic values, tests that pin implementation instead of behavior.
   - *Security:* untrusted input reaching a command or query, secrets in code or logs, missing access checks, new attack surface.
4. **Refute each finding.** A finding stays only if it has a `path:line` and a check: a command, a failing test, or a concrete input that shows the problem. Run the check. If it cannot be shown, drop it from the findings and log it as a suspicion with the reason.
5. **Rank** what survives: critical (data loss, security hole, broken build), high, medium, low.
6. **Verdict.** Either `no defects found` (with what you checked) or the ranked list.

## Output

```
Verdict: no defects found | defects found
Checked: <files read, commands run, results>
Findings:
  1. [high] path/file.py:42 - what breaks - how to reproduce
Dropped suspicions: <what, and why it could not be shown>
Returned: <reviewers dispatched / returned>
```

## Traps

- A dead reviewer looks the same as a clean one. Count returns: if a reviewer produced nothing, it did not review.
- An agent's verdict is a claim. When it says clean, ask what it ran.
- A check built from the code under test cannot fail where that code is wrong. Prefer an independent input.
- Gates raise the floor; they do not certify the result. Say what the review did not cover.
- Review the goal as well as the code: a change can be correct and still solve the wrong problem.

Related: rule 5 and rule 6 in `${CLAUDE_PLUGIN_ROOT}/PROTOCOL.md`; `delegate` for briefing the reviewer.
