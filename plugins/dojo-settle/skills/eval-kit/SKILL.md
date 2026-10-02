---
name: eval-kit
description: "Use when scaffolding or reading claude plugin eval runs: write case.yaml, pilot one run under a cost cap, confirm the plugin loaded, then read the with-minus-without delta."
model: inherit
category: learn-research
---

# eval-kit

`claude plugin eval` runs a case against your plugin and, by default, against a baseline with the plugin absent. The number worth reading is the difference between the two arms, and it only means something if the plugin actually loaded in the with arm.

**Runs spend money.** This plugin ships scaffolds only. No eval from this suite has been run, so there is no figure from them yet. Never start one without an explicit cost cap and the person's yes.

## 1. Write the case

Copy `${CLAUDE_PLUGIN_ROOT}/templates/case.yaml` into the plugin's `evals/<case-name>/case.yaml` and edit it. (`claude plugin eval init --bare <name>` writes a different, blank prompt-and-graders layout; without `--bare` it starts an interview and needs an interactive terminal.) Fields:

- Top level: `schema_version` (quoted, `"1.0"`), `name`, `description`, `tags`, `runs` (at most 50), `graders` (at least one), `expected_outcome`. Optional: `plugins`, `context` (`add_dirs`, `scaffold_script`, `history_file`).
- `execution`: `prompt`, `max_turns` (at most 200), `timeout_seconds` (at most 3600), `model`, `allowed_tools`; also `append_system_prompt`, `env`, `artifact_publish`. Set the timeout generously: a run that times out is graded on what it finished, which is often nothing.
- Graders, each with a unique `name`, an optional `weight`, and `arm`. Unknown keys are rejected.
  - `tool_used`: `tool`, `input_match`, `min`, `max`.
  - `tool_order`: `before`, `after`.
  - `regex`: `target` (`last_message`, `trace`, `files`, `mock_calls`, or `{source: file, path: <relative path>}`; a bare path string is rejected), `pattern`, `flags`, `match` (`contains`, `not_contains`, `count:N`).
  - `file_exists`: `path`, `exists`.
  - `llm`: `criteria`, `focus` (takes the same values as a regex `target`).
  - `baseline`: `baseline_file`, `criteria`.
- `arm: with-only` marks a grader as a fired-indicator: it shows whether the plugin did something and adds nothing to the score. A `tool_used` grader on `Skill` is display-only by default under with/without, so a must-not-fire check on a skill needs `min: 0`, `max: 0`, `arm: both`.

`claude plugin validate` does not read case.yaml. A clean validate says nothing about your cases; a broken one fails only when someone pays to run it. Check keys against the list above.

Write the prompt so it stands alone: code inline, no absolute paths, no home-directory paths, since cases run in a sandbox directory. Someone other than the plugin's author should write the prompts. Include at least one case where the plugin should not fire, with a grader that rewards it staying out.

## 2. Pilot gate

```
claude plugin eval --runs 1 --ablation with-without --no-scaffold --no-publish --max-cost-usd <cap> \
  --allow-tools Write Edit "Bash(python3:*)" --judge-model opus <plugin-path>
```

Tools follow graders: `Bash`, `Write` and `Edit` (also `WebFetch` and `mcp__*`) are gated, and a run only gets them through `--allow-tools`. Grant exactly what the prompt needs, scoped as above, and list in `allowed_tools` only tools a grader or the task uses. Without the grant the with arm can't do the task and the delta means nothing.

`--no-publish` is required because publishing to claude.ai is the default. Then:

1. Open `<evals>/results/*/aggregate-result.json` and check `suite.plugins` lists your plugin with an empty problems list (the codes include `manifest_invalid`, `disabled_by_default`, `will_not_load`, `identity_unverified` and `archive_not_probed`; any entry counts). If one is there, the with arm ran without the plugin and any delta means nothing. Fix that first.
2. Read the top-level `costUsd`, multiply by the number of runs you plan, tell the person the figure, and get their go.
3. Set `--judge-model opus` for `llm` graders; the default judge is haiku. The judge must be a different, larger model than `execution.model`, because a model favors its own output. Give an `llm` grader that judges ordering `focus: trace`; `last_message` is the default and can't see earlier turns.
4. `--trust-plugin` only on an explicit yes.

Exit codes: with the default `--threshold 1.0`, exit 1 is normal when scores are partial; it isn't a crash. `--max-cost-usd` exits 2 when it trips. Useful flags: `--runs`, `--case`, `--tag`, `-j`, `--report`.

## 3. Read the delta

The headline is the with-plugin score minus the without-plugin score, per case.

- Use three or more runs per case before you read anything into a gap. One run is a pilot.
- Compare against the spread between repeat runs of the same arm. A gap inside that spread isn't a finding.
- Look at the sign across cases before the size. Consistent direction in many cases beats one big number.
- Read the case where the plugin should lose first. If the with arm wins there, suspect the grader.
- A grader written by the same person who wrote the plugin tends to reward what the plugin does. Check that each score-bearing grader would fail on a run that's actually bad.
- State what you ran: runs, cap, model, date, tool version. Report a figure only with that next to it.

## Scaffolds in this plugin

`${CLAUDE_PLUGIN_ROOT}/evals/protocol-should-lose/case.yaml` and `${CLAUDE_PLUGIN_ROOT}/evals/with-without-delta/case.yaml`. Both are tagged `scaffold` and `not-run`.
