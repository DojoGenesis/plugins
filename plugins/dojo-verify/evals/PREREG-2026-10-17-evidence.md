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

## Results

(Empty until the run. Raw numbers per cell go here, including the cells that make `block` look bad.)

## Ruling applied mechanically

## What outranks the ruling

## Gaps and handicaps

## Digest check after write-up
