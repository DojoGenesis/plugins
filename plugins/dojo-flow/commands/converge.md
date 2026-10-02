---
description: "Audit by lens, then have three opus verifiers try to refute each serious finding. Audit-only by default; a fix runs only if you say yes. Scorecard counts returns."
argument-hint: "<what to audit>"
allowed-tools: Read, Glob, Grep, Bash(python3:*)
---

Audit this with the converge workflow: $ARGUMENTS

The workflow calls sonnet once per lens, then three opus verifiers per critical or high finding. That spends tokens on two tiers and grows with the number of lenses and findings. Tell the person that first.

## 1. Choose the lenses

A lens is `{name, prompt}`: one question, one angle, read-only. You need at least one; there are no defaults, on purpose. Copy and adapt these:

```
{"name": "correctness", "prompt": "Find places where the code does not do what its comments, names or tests say it does. Cite file and line."}
{"name": "tests", "prompt": "Find behaviour that no test covers and tests that cannot fail. Cite file and line."}
{"name": "docs-vs-code", "prompt": "Find claims in the README and docs that the code contradicts. Cite both."}
```

## 2. Audit only (the default)

Call the Workflow tool (not the Skill tool; the command and the workflow share a name):

```
Workflow({
  name: "dojo-flow:converge",
  args: { lenses: [ {name, prompt} ], repo: "<absolute repo path>" }
})
```

If the tool does not know that name (names are fixed when the session starts, so a plugin installed a minute ago is not visible yet), use `Workflow({ scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/converge.js", args: { ... } })`.

Nothing is changed in this mode. The result lists every finding with its status: confirmed, refuted (kept in the result, not hidden), unresolved (the verifiers did not reach a majority), or not verified (medium and low are below the threshold; anything over the per-lens cap is logged and listed in `droppedByCap`).

Optional args: `topPerLens` (1 to 20, default 5), `models`, `effort`, `gates`. The only other keys are `lenses`, `fix`, `fixTracks` and `repo`. Any other key is refused before anything runs, and the refusal names it.

## 3. Fix (only with an explicit yes)

Fixing edits files. Ask the person first, name the checks that will judge the result, and only then add `fix: true` and `gates: ["<command>", ...]` to the args. `fix` must be the boolean `true`; anything else means audit only. With no gates the fix phase is refused, because nothing would confirm it. Confirmed findings are fixed by sonnet on file sets that cannot overlap, then the checks are run twice and the tree is compared with the ownership map.

## 4. Report it straight

Relay the scorecard text exactly as returned: verdict, dispatched, returned and failed counts, and every reason. An audit-only run says REVIEWED and never claims a fix. A lens that died is not a clean lens: say which ones returned nothing. If a fix run says VERIFIED, run one of the gates yourself in this session and show the result before you say it is done.
