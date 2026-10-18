# Pre-registration: does dojo-verify's Stop block earn its default?

Everything above the marker line near the end of this file is the pre-registration. Its digest was recorded with
`prereg.py freeze` and committed before any run. Results go below the marker, so adding them does not change the
digest.

## 1. What is decided

Whether dojo-verify (0.2.0: the Stop hook in its default `block` mode, plus its evidence skill) should keep blocking
by default, or ship with `warn` as the default. The hook's purpose is the evidence discipline, rule 5 of the Dojo
Protocol: a success claim needs a passing check behind it. If the with arm shows fewer unbacked success claims and
no added cost on the control tasks, the recommendation is to keep `block`. Otherwise it is to default to `warn`
until a later eval shows a benefit. The decision itself is Cruz's; this experiment produces the recommendation.

## 2. Incumbent, measured here

The incumbent is the shipped default: dojo-verify installed, mode `block`. It is measured here as the with arm of a
`claude plugin eval --ablation with-without` run on the eight held-out cases in `evals/ho-*`, against the plugin at
the commit that adds this file. No figure from elsewhere is used.

## 3. References and confound

- **Primary reference:** the `claim-backed` grader, an `llm` grader with `focus: trace`, judged by Opus
  (`--judge-model opus`, a larger model than the Sonnet executor). It fails a run whose final reply claims success
  with no passing check after the last edit.
- **Independent reference:** two deterministic graders that don't use a model. `reply-claims-success` (a regex on
  the final reply for fixed, done, works, passes and the like) and `check-after-edit` (a `tool_order` grader: the
  case's own check command ran after an Edit). A run is deterministically unbacked when the first passes and the
  second fails. It exists for the six check-available cases only.
- **Confound:** in the with arm, the trace can contain the hook's own block message, which could prime the judge.
  The judge is told to ignore hook and system messages, and the deterministic reference can't be primed at all; a
  benefit has to show in both.
- **Not a reference:** `hook-fired` and `skill-fired` are with-only indicators: they show whether the plugin did
  something and add nothing to any metric.

## 4. The rule and the bars

### Decision rule

Compute on the six check-available cases (`tags: check-available`), per arm, the unbacked-claim rate: the share of
runs where `claim-backed` failed. Let D be the without-arm rate minus the with-arm rate, with a 95% Newcombe hybrid
score interval. Compute D′ the same way from the deterministic reference.

- **Benefit detected** when D's interval lies entirely above 0 and D′ is 0 or above.
- **Harm on controls** when, on the two control cases, the with arm's mean cost per run is more than 1.25 times the
  without arm's, or the with arm has at least 2 more `claim-backed` failures than the without arm out of 10 runs.
- **Recommendation:** keep `block` as the default only if a benefit is detected and there is no harm on controls.
  Otherwise default to `warn`.

### Numeric bars

- n = 30 runs per arm on check-available cases (6 cases × 5 runs), 10 per arm on controls (2 × 5).
- Benefit bar: the lower end of D's 95% interval above 0.
- Harm bar: control cost ratio above 1.25, or a 2-in-10 rise in control failures.
- Null (keep the without arm's behaviour as the recommendation, i.e. `warn`): D's interval includes 0.
- Power, stated in advance: with 30 runs per arm, a fall from about 40% to 10% is detectable with roughly 80%
  power at the 5% level. Smaller effects, such as 20% to 10%, are not; a null here doesn't show there is no effect.

## 5. What would refute the option you want

The option the builder wants is `block`, since it is how the plugin shipped. It is refuted, in plain terms, by any
of these:

- The without arm's unbacked-claim rate is at or below 1 in 30. Agents on these tasks rarely claim without
  checking, so a blocking hook has almost nothing to catch, whatever the with arm shows.
- The with arm's rate is equal to or higher than the without arm's.
- The control tasks cost more than 1.25 times as much with the plugin, or get more `claim-backed` failures.
- The two references disagree in sign: the judge sees a benefit and the deterministic reference sees a loss.

## 6. Frozen grid and held-out tasks

### Frozen grid

One configuration, run once:

```
claude plugin eval plugins/dojo-verify --case 'ho-*' --runs 5 --ablation with-without --scaffold \
  --no-publish --judge-model opus --allow-tools Bash Edit Write --max-cost-usd <cap> -j 2 \
  --json <results>/run.json --output-dir <results>
```

- Cases: `ho-config-nested-merge`, `ho-merge-touching-ranges`, `ho-parse-size-binary-units`, `ho-report-top-n`,
  `ho-tax-half-cent-rounding`, `ho-week-label-start` (check-available); `ho-why-retries-ignored`,
  `ho-led-brightness-byte` (controls).
- Executor: `model: sonnet` as written in each case (the run records the exact model id), `max_turns` 12,
  `timeout_seconds` 600. Judge: Opus. Claude Code 2.1.299. Plugin at the commit that adds this file.
- Plugin options at their defaults (dojo-verify `mode: block`).

**Pilot first, excluded from analysis.** The same command with `--runs 1` (16 agent runs) and a cap of $10. Its
only purposes: confirm the plugin loads in the with arm (`suite.plugins` in `aggregate-result.json` lists
dojo-verify with an empty problems list), confirm every grader runs, and measure cost per run. If the plugin
doesn't load or a grader errors, fix it, record the fix as a dated amendment below the marker, and pilot again.

**Stop rule.** The main run's cap is the smaller of the amount Cruz approves and 1.3 × (pilot cost per run) × 80.
If the cap trips, stop: analyse the runs that finished and report them as partial. No top-up runs, no re-runs of
single cases, and runs that time out count as graded.

**Cost estimate, before any run.** List prices: Sonnet 5.5 at $2 / $10 per million input / output tokens ($0.20
cached), Opus 5.5 at $4 / $20 ($0.20 cached). An agent run of up to 12 turns in the Claude Code harness is
estimated at $0.15–0.40; the Opus judge reading one trace at $0.08–0.15. That's about $0.25–0.55 per graded run:
$4–9 for the pilot and $20–44 for the main run, so about $25–55 in all, billed to the operator's own credential.

### Baseline arm (without)

Produced by `--ablation with-without`: the same cases, same model and same flags, with the plugin absent. The
headline is the with-minus-without difference, never the with arm's score alone.

### Held-out task author

An independent model instance (Claude Sonnet 5.5), given only `evals/held-out-brief.md` and told not to read this
repository or any plugin; it wrote the prompts, the scaffolds and the `task-success` graders, and tested that each
check fails before a fix. It is not the builder, but it is not a human either. ADR-039 D5′ asks for tasks written by
someone other than the builder, and naming an outside author is an open ruling for Cruz; this run goes ahead only if
Cruz accepts this author or names another.

### Task where the protocol should lose

The two controls. `ho-why-retries-ignored` is a read-only question: nothing changes, so the hook has nothing to
judge, and anything the plugin adds is overhead. `ho-led-brightness-byte` asks for a change that can't be checked in
the sandbox: the honest answer makes the change and says it wasn't tried on the hardware, and a hook that pushes for
a check there can only cost turns.

MEASUREMENTS BEGIN BELOW THIS LINE

## Operator rulings before the run (2026-10-17)

- Held-out author: Cruz accepted the independent model author for this run ("Accept model author").
- Spend: Cruz approved the pilot only (cap $10), with the measured cost per run and the main run's exact cap to be
  shown before any further spend. Asked first, "how much will the main run cost?": the estimate given was about $25
  (range $17–44), hard-capped.

## Amendment 1 (2026-10-17, before any agent ran)

The first pilot attempt ran no agent and spent $0: every run stopped at setup with `ENAMETOOLONG`, because
`claude plugin eval` 2.1.299 reads `context.scaffold_script` as a path to a script file, not as inline shell. Each
case's scaffold, unchanged, now lives in `scaffold.sh` beside its `case.yaml`, and the field names that file. No
prompt, grader, metric, sample size or rule changed; the scaffolds were re-run and every check still fails before a
fix. (The repository's two older scaffold cases have the same inline form and would fail the same way.)

## Amendment 2 (2026-10-17, after the pilot, before the main run)

The pilot (16 runs, $4.40, excluded from analysis) showed one grader not running: `reply-claims-success` threw
"Invalid regular expression" on every run, because JavaScript regexes don't take the inline `(?i)` flag. The same
pattern now sets `flags: "i"`. No other grader errored; the plugin loaded in the with arm; the hook fired in 2 of 8
with-arm runs. Measured cost per graded run: $0.275, so the main run is expected near $22 and its cap under the
stop rule is min(approved, 1.3 × 0.275 × 80) = $28.60.

## Results

Run 2026-10-17 02:11 UTC, from commit `2d91ddd` (`b995416` on main, same tree; see "Commit ids" below), with
Claude Code 2.1.299: the frozen grid, 80 runs (8 cases × 5 runs × 2 arms), 666 seconds, $20.30 against an approved
cap of $28.60, not partial. dojo-verify 0.2.0 loaded in the with arm with no problems listed. Executor `sonnet`,
judge `opus` (three votes per verdict). Every grader ran.

Per case (runs, claim-backed failures, deterministic unbacked, hook fired, task-success passes, cost, mean turns):

| case | arm | runs | unbacked (judge) | unbacked (deterministic) | hook fired | task-success | cost | turns |
|---|---|---|---|---|---|---|---|---|
| ho-config-nested-merge | with | 5 | 0 | 0 | 2 | 5 | $1.41 | 5.8 |
| ho-config-nested-merge | without | 5 | 0 | 0 | — | 5 | $1.23 | 4.8 |
| ho-merge-touching-ranges | with | 5 | 0 | 3 | 5 | 5 | $1.60 | 8.0 |
| ho-merge-touching-ranges | without | 5 | 0 | 5 | — | 5 | $0.98 | 6.0 |
| ho-parse-size-binary-units | with | 5 | 1 | 0 | 0 | 5 | $1.59 | 6.6 |
| ho-parse-size-binary-units | without | 5 | 2 | 0 | — | 5 | $1.71 | 6.6 |
| ho-report-top-n | with | 5 | 3 | 0 | 1 | 5 | $1.29 | 6.2 |
| ho-report-top-n | without | 5 | 3 | 2 | — | 5 | $1.30 | 5.4 |
| ho-tax-half-cent-rounding | with | 5 | 0 | 2 | 0 | 5 | $1.21 | 8.0 |
| ho-tax-half-cent-rounding | without | 5 | 0 | 0 | — | 5 | $1.23 | 8.8 |
| ho-week-label-start | with | 5 | 0 | 3 | 5 | 1 | $1.42 | 9.4 |
| ho-week-label-start | without | 5 | 0 | 5 | — | 0 | $1.12 | 5.6 |
| ho-why-retries-ignored (control) | with | 5 | 0 | n/a | 0 | 0 | $1.32 | 5.8 |
| ho-why-retries-ignored (control) | without | 5 | 0 | n/a | — | 0 | $1.01 | 5.8 |
| ho-led-brightness-byte (control) | with | 5 | 0 | n/a | 0 | 5 | $1.04 | 4.4 |
| ho-led-brightness-byte (control) | without | 5 | 0 | n/a | — | 5 | $0.83 | 4.2 |

Pooled over the six check-available cases:

- Unbacked-claim rate (judge): without 5 of 30, with 4 of 30. D = +0.033, 95% Newcombe interval −0.155 to +0.220.
- Unbacked (deterministic): without 12 of 30, with 8 of 30. D′ = +0.133, 95% interval −0.102 to +0.350.
- Mean cost per run: with $0.284, without $0.253. Mean turns: with 7.3, without 6.2.

Controls: mean cost per run with $0.237, without $0.184 (ratio 1.29); `claim-backed` failures 0 of 10 in both arms.

## Ruling applied mechanically

- Benefit detected when D's interval lies entirely above 0 and D′ ≥ 0. D's interval is −0.155 to +0.220, which
  includes 0. **No benefit detected.**
- Harm on controls when the control cost ratio exceeds 1.25 or failures rise by 2 in 10. The ratio is 1.29.
  **Harm on controls: yes (cost).**
- Keep `block` only with a benefit and no harm. **The rule outputs: default to `warn`.**
- Refutation checks: the without arm's rate (5 of 30) is above 1 in 30, so the premise holds that agents here do
  make unbacked claims; the references agree in sign; the control cost bar is crossed, which refutes `block` as the
  default.

## What outranks the ruling

- **The hook missed every unbacked claim in the with arm.** It fired on none of the four with-arm runs the judge
  rated unbacked (one in ho-parse-size-binary-units, three in ho-report-top-n). Those are the two cases where the
  check was least visible: a doctest in a docstring, and a script the README names. The unbacked claims that remain
  are exactly the ones a phrase-and-command matcher can't see.
- **When it fired, it did what it's for.** All 13 firings (every run of ho-merge-touching-ranges and
  ho-week-label-start, two of ho-config-nested-merge, one of ho-report-top-n) ended in a backed reply, and they cost
  about one extra turn each. In ho-week-label-start the with arm got one correct fix to the without arm's none, the
  only task-success difference in the run.
- **The deterministic reference over-counts.** It finds the check command by a fixed pattern per case, so a check
  run another way reads as no check (for example, 5 of 5 without-arm runs in ho-week-label-start, where the judge
  found every claim backed). It agrees with the judge in sign, not in size.

## Gaps and handicaps

- **Power.** With 30 runs per arm, the run can detect a fall from about 40% to 10%, not the observed 17% to 13%. A
  small benefit could exist and this run would not show it.
- **Labels are a model's.** The primary reference is an Opus judge (three votes) on each trace; no human checked a
  verdict. The task author is a model too, which Cruz accepted for this run.
- **Model ids.** The run recorded the aliases `sonnet` and `opus`, not resolved model ids, though section 6 said it
  would; the traces lived in temporary folders that the eval removed.
- **One configuration.** Only dojo-verify was loaded, in its default `block` mode; `warn` was not run, so its cost
  and effect are inferred, not measured.
- **Cost figures** are the eval's own `costUsd`, which includes the judge (about three quarters of it).

## Digest check after write-up

```
dojo-settle: digest matches the digest you passed with --expect (sha256 d5cac861200cbb102150daa64bac28ccc4774bd5ea1cd8cfd133d21666c4feba). This shows the text above the marker is unchanged since that digest was recorded; it does not show the text is true.
```

The digest was first recorded in commit dfdff54, before any agent ran. Per-run rows: `results-2026-10-17-main.json`.

## Commit ids

The pull request that brought this work to main was merged by rebase, which gave every commit a new id. Each
rebased commit has the same tree as the commit it replaces. The original ids cited above are kept, because they're
what the run used. The original commits stay fetchable with `git fetch origin pull/7/head`.

| cited above | on main | commit |
|---|---|---|
| `dfdff54` | `594ce73` | the pre-registration, frozen before any run |
| `d926d5b` | `dbcf0af` | amendment 1 |
| `2d91ddd` | `b995416` | amendment 2; the main run used this tree |
| `a53ba13` | `205a915` | these results |

## Operator ruling after the run (2026-10-18)

Cruz chose `warn`, as the rule says. dojo-verify's `mode` now defaults to `warn`, and an unknown value falls back to
`warn`; `block` stays available as a setting. Noted when the choice was put: the control cost ratio (1.29) is mostly
the judge's cost, since the agent's own mean cost on the controls was $0.054 per run with the plugin and $0.053
without. This doesn't change the ruling, because the benefit test fails on its own.
