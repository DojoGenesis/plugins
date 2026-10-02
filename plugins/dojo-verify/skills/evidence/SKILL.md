---
name: evidence
description: Use when you are about to write "done", "fixed", "verified" or "tests pass", or to repeat a subagent's report. Covers what counts as evidence and how to write the done line.
model: inherit
category: govern-publish
---

# Evidence before "done"

A claim is a sentence you wrote. Evidence is output you watched appear in this session. The dojo-verify Stop hook checks the small version of this: did a check run after your last change, and did it come back clean? It cannot tell whether the check was the right one. That part is yours.

## The six rules

1. **A report is a claim.** Yours, a subagent's, a script's own "complete", a ticked box in generated docs. Run the gate yourself and look at the files an agent says it wrote. A "verified" with no saved artifact is unverified.
2. **Load the real page after a deploy or a migration.** Typecheck, unit tests, API output and database rows can all be green while the page is visibly broken (a response header that blocks the image host, for example). Open or fetch the page and look at what a person would look at.
3. **Empty output is not evidence.** A probe that prints nothing may never have run: a missing binary, a bad flag, a search tool that skips ignored folders. Before you trust a negative, point the same probe at something you know is there. A list read has the same trap: compare what you got with the total the source reports, because a first page looks like the whole list.
4. **A check built by the code under test cannot catch its own bug.** Fixtures made through the library inherit its blind spots. Hand-write the bad input the library refuses to build, and force a control to fail once so you have seen it fire.
5. **Count returns, not dispatches.** Say "dispatched N, returned M, failed F". An agent that died looks exactly like one that found nothing. Judge background work by what landed on disk, not by what the agent said about itself.
6. **A hash beats a version.** A version number says bytes changed; a checksum or commit id shows which bytes. Compare what is running with what you built.

## What counts as evidence

| You are about to say | Evidence that backs it |
| --- | --- |
| tests pass | the test command's own output in this session, with counts and a clean exit |
| it builds, typechecks, lints | the command ran in this session and printed no errors |
| it's fixed | the failing case run before and after, same command |
| it's deployed | the live URL fetched or loaded, and the served version compared by hash |
| the migration is done | run on a copy first, then row counts compared on the real thing |
| the list is complete | the count you hold against the total the source reports |
| the agent finished | its answer is non-empty and the files it names exist |

A check that exits 0 while its output shows failures, or whose exit code a `| tail` or `|| true` swallowed, is not evidence. Read the output.

## The done line

```
Ran:    <the command>
Result: <counts and exit status, one line>
Where:  <path or URL to look at>
```

When you could not run a check, say so in the same sentence as the claim: `Fixed the parser (unverified: there is no test suite here).` The hook excuses a claim only when its own sentence says the work is unverified, untested or not run, in the same clause or the one beside it. `Fixed.` on one line and `I could not test it.` on the next still reads as a claim with nothing behind it, and so does a bug description such as "we never checked for null".

## When the Stop hook sends you back

Run the check and show its result, or say plainly that it is unverified, in the same sentence as the claim. Either one ends the loop. A check has to come after your last edit: an earlier run doesn't count once you've changed a file since. Rewording "fixed" to slip past the pattern is the failure the hook exists for.

More: the Dojo Protocol, rules 5, 6 and 9. Short cases and the claim-to-check map are in `${CLAUDE_PLUGIN_ROOT}/skills/evidence/rules.md`.
