# dojo-flow

Parallel builds that stay independent: a contract gate, scouts on small models, builders in the middle, judges at the ends, and a scorecard that counts returns.

Part of the Dojo Genesis protocol suite. It stands on its own: it does not need any other suite plugin.

## Install

```
/plugin marketplace add DojoGenesis/plugins
/plugin install dojo-flow@dojo-genesis
```

Restart the session after installing. Workflow names are fixed when a session starts, so a workflow from a plugin you just installed is not visible by name until then. The commands also say how to call the script by path.

## What's in it

| Part | What it does |
|---|---|
| `/dojo-flow:build <goal>` | Proposes tracks, files and checks, shows you the width of the fan-out, and runs the build workflow only after you say yes. |
| `/dojo-flow:converge <what to audit>` | Runs the converge workflow: audit lenses, adversarial verification, an optional fix, and a gate. Audit-only unless you say yes to a fix. |
| `workflows/build.js` | Contract (opus) → Scout (haiku, per track) → Advise (opus, per question) → Build (sonnet, per track) → Integrate (sonnet) → Audit (opus, then a sonnet faithfulness pass and a haiku accuracy pass). |
| `workflows/converge.js` | Audit (sonnet lenses in parallel) → Verify (three opus verifiers per critical or high finding) → Fix (sonnet, only with `fix: true`) → Gate (checks run twice, tree compared with the ownership map). |
| `scripts/dag_ops.py` | Standard-library graph checks: `validate`, `width`, `critical-path`, `cone`, `reduce`, and `tracks` (ownership overlap plus the width of the fan-out), so you see whether a fan-out is real before any model runs. |
| skill `dag-plan` | How to cut a goal into tracks that really are independent. |

Tier: workflows only. There are no hooks, no classic tier and no mod tier, so there is no kill-switch variable to set: nothing in this plugin runs unless you start it.

## How a run is guarded

- **Contract before fan-out.** Opus reads the goal and the repo, writes a contract file (default `.dojo/dag-contract.md` in the repo; it refuses to overwrite a file that exists, so a re-run in the same repo needs a new `contractPath` such as `.dojo/dag-contract-2.md`, or the old file removed after you've read it) and certifies every pair of tracks as independent. A coupled pair stops the run before a scout starts.
- **The ownership map is computed by the script**, not taken from a model. Overlapping files, duplicate names, globs, `..` and absolute paths outside the repo are refused before any model is called.
- **Every subagent call sets its model and effort.** Roles map to aliases: scout haiku, builder and integrator and reviewer sonnet, checker haiku, judge opus. `args.models` and `args.effort` override them by role; unknown roles and bad values are refused, never ignored.
- **Returns are counted.** The scorecard says how many calls were dispatched, returned and failed, with a label and reason for each failure. A call that threw or came back empty is a failure, not a clean result.
- **VERIFIED is a narrow word.** The scorecard says it only when every call returned, at least one check was given, the integrator and the audit each reported every given check as run with exit 0, the audit approved with no blockers and no unowned changes, every track reported complete, and both judgment passes ran clean. Anything else is UNVERIFIED with the reasons listed. An audit-only converge run says REVIEWED and never VERIFIED.

## Cost

Runs spend model tokens on all three tiers. How much depends on the number of tracks (or lenses and findings), and the plugin gives no number: it has not been measured. `maxTracks` (default 8, at most 16), `adviceCap` (default 3, at most 6) and `topPerLens` (default 5, at most 20) bound the fan-out, and anything trimmed by a cap is logged. The slash commands ask you before they start a run.

## Honest limits

- **Check results are reported by subagents.** A workflow script has no shell. The integrator and the audit each run your checks and report `{cmd, ran, exit}`, and the script compares those with the commands you gave. That is evidence from models, not from the script. Re-run one check yourself before you call it done; the commands tell Claude to.
- **Ownership is taught and audited, not enforced.** Builders are told which files they own; the script checks what they report, and the audit compares the tree with the map and reports any difference. Nothing blocks a write. A prompt is not a control, and builders share the live working tree.
- **Scouts and lenses are read-only by prompt only.**
- **Tree checks need git.** In a directory that is not a git repository the tree check cannot run, and the scorecard says so.
- **Not yet run end to end.** The workflow scripts are syntax-checked and run against a stub harness in this release's tests, which drive refusals, dead and throwing subagents, majority votes and the verdict table. No live run has been made, so how they behave with real models is not yet measured.
- **Do not resume an edited script.** Start a fresh run. Later stages of a pipeline spawn in completion order, so a resumed run does not reliably replay.
- **A null is a failure.** If the runtime skips a subagent or it dies, the call is counted as failed and the verdict cannot be VERIFIED.
- **Workflow tool availability.** The workflows need a Claude Code build that has the Workflow tool.
- **Checks are only as good as the commands you pass.** `gates: ["true"]` will pass.

## Layout

```
.claude-plugin/plugin.json
commands/build.md  commands/converge.md
skills/dag-plan/SKILL.md
workflows/build.js  workflows/converge.js
scripts/dag_ops.py
tests/            unittest; includes a Node stub harness (skipped with a printed reason if node is absent)
evals/            scaffolds only, never run (they spend money)
```

Run the tests:

```
cd plugins/dojo-flow && python3 -m unittest discover -s tests -v
```

Set `DOJO_NODE` to a node binary if `node` is not on your PATH. The workflow tests drive the scripts through a Node stub harness, so they need node. Under a stripped environment (for example `env -i PATH=/usr/bin:/bin`, which hides a Homebrew or nvm node), those tests print a notice that says why and are reported as skipped, not passed. Most of the suite is in that group, so a green run with those skipped has not exercised the workflows. Run them once with node visible.

Tested with Claude Code 2.1.286.

License: Apache-2.0.
