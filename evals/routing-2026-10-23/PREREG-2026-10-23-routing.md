# Pre-registration: does routing change cost or quality against all-opus?

Everything above the marker line near the end of this file is the pre-registration. Its digest was recorded with
`prereg.py freeze` and committed before any run. Results go below the marker, so adding them does not change the
digest.

## 1. What is decided

Whether the READMEs of dojo-router (0.1.1) and dojo-flow (0.1.0) may state a measured effect of routing on cost or
quality. Both say today that nothing measures what routing changes and claim no savings. That stance stays unless
the rule below says otherwise. Per plugin, the rule's verdict maps to what its README may say:

- **Saves, no measured loss:** the README may cite the measured cost ratio with its conditions (tasks, runs, date,
  Claude Code version, plugin version) and a link to this file.
- **Saves, quality not resolved:** the README may cite the cost ratio and must say the quality difference was not
  resolved at this sample size.
- **Saves at a quality cost:** the README cites both, the saving and the loss.
- **No detectable difference in cost:** the README keeps "no savings claimed" and may add that a pre-registered eval
  found no detectable difference on these tasks.
- **Costs more:** the README says routing did not save on these tasks.
- **Inconclusive** (routing did not take effect, the study could not run in this harness, or too few runs
  finished): the README stays as it is, and this file says why.

The decision is Cruz's. This experiment produces the recommendation. Funding: Cruz's ruling of 2026-10-23 (item 4
of `handoffs/2026-10-23_windows-decisions-for-cruz.md` in TresPies-AI-Orchestration), a hard cap of $100 for all
eval spend, pilots and judge included.

## 2. Incumbent, measured here

The incumbent is all-opus, measured in this harness, never quoted.

- **dojo-router:** the session runs on Opus with no routing plugin, so a subagent dispatch that names no model runs
  on the session's model. That is the without arm of a `--ablation with-without` run. Whether Claude Code itself
  pins some subagents to a smaller model when no plugin intervenes is measured, not assumed: the share of subagent
  runs that used an Opus model in this arm is reported.
- **dojo-flow:** the same build workflow, same goal, tracks and gates, with every role's model set to `opus`
  through `args.models`. Effort per role stays at the workflow's defaults in both arms, so only the model changes.

## 3. References and confound

- **Cost reference:** the eval's own per-run cost minus the judge's cost (`costUsd` minus `judge_cost_usd`), called
  agent cost below: the executor session plus every subagent and workflow agent it started. It is the list-price
  equivalent that Claude Code computes. The runs bill to the logged-in claude.ai subscription, so it measures usage,
  not an invoice.
- **Cost attribution (second view):** the model id and token use of each subagent and workflow agent, read from
  the run transcripts kept with `--keep-temp`. It shows whether routing took effect and where the money went. If
  the transcripts turn out not to be kept or readable, this view is "not measured" and the cost reference stands
  alone; the arms differ only in routing, so a cost difference is still attributable to it.
- **Quality, primary:** hidden acceptance tests. The independent author wrote them with each task; they are kept
  outside the plugin directories and are never in the agent's sandbox. `grade_hidden.py` runs them on each kept
  work directory after the run. Deterministic.
- **Quality, independent second:** `quality-judge`, an `llm` grader with `focus: files`, judged by Opus
  (`--judge-model opus`) against the case's expected outcome. It reads files only, not the trace, so the router's
  warning text in the trace can't prime it.
- **Confound the judge brings:** it is Opus grading code that, in the all-opus arm, Opus wrote. A model tends to
  favour its own output, so the judge could lean toward the all-opus arm. The hidden tests can't lean either way,
  so a quality loss counts only when the hidden tests show it, and the judge must agree in sign.
- **Confound in the task set:** the dojo-router prompts ask the agent to use subagents. Without that request an
  Opus session might not dispatch at all, and routing would have nothing to act on. The result applies to sessions
  that delegate, not to every session.
- **Not references:** `dispatched` (an Agent call happened), `hook-warned` (the router's warning appears in the
  trace, with-only), `workflow-ran` and `scorecard-relayed` (dojo-flow ran and its verdict came back). They show
  what happened and enter no metric.

## 4. The rule and the bars

### Decision rule

Definitions, for each study (R: dojo-router; F: dojo-flow) separately:

- **A run counts** when the eval reports an agent cost for it and `grade_hidden.py` returns PASS or FAIL for its
  work directory. A run that hits `max_turns` or times out counts and is graded on what it left. A harness error
  with no agent output (for example a rate limit) and a hidden-test COULD NOT RUN are missing: reported by cell,
  never re-run, never imputed.
- **Agent cost** c = `costUsd` − `judge_cost_usd` for the run.
- **Pooled mean cost per arm** = the mean over the study's cases of each case's mean c, so every case weighs the
  same. Cost pools every case of the study, the careful case included.
- **Cost ratio** ρ = routed pooled mean / all-opus pooled mean, with a 95% percentile bootstrap interval:
  resample runs with replacement within each case and arm, 10,000 resamples, seed 20261023.
- **Quality** = the hidden-test pass rate per arm, pooled over the study's standard cases (the careful case is
  judged separately, below). F has only one standard task, so F's quality pools both of its tasks, and the
  careful-case check still applies to the careful task alone. Δq = routed rate − all-opus rate, with a 95%
  Newcombe hybrid score interval (method 10). Δj is the same difference for `quality-judge` (a run passes when
  the judge's verdict is PASS).
- **Routing took effect** when, in the routed arm, at least half of the subagent and workflow-agent runs used a
  non-Opus model, and that share is at least 25 points above the all-opus arm's. If the transcripts can't show it,
  this is "not measured".

The rule, applied per study:

1. **Cost.** Savings detected when ρ's interval lies entirely below 1. Increase detected when it lies entirely
   above 1. Otherwise no detectable difference.
2. **Quality.** Loss detected when Δq's interval lies entirely below 0 and Δj ≤ 0. Non-inferior when Δq's lower
   bound is −0.15 or above and Δj ≥ −0.15. Otherwise not resolved. (A gain, Δq's interval entirely above 0 with
   Δj ≥ 0, is reported as unexpected.)
3. **Careful case.** Harm flagged when the routed arm has at least 2 fewer hidden-test passes than the all-opus
   arm on the careful case, out of that cell's runs.
4. **Verdict.** Savings and non-inferior: "saves, no measured loss". Savings and not resolved: "saves, quality not
   resolved". Savings and loss: "saves at a quality cost". No detectable difference: "no detectable difference in
   cost". Increase: "costs more". A flagged careful-case harm is added to any verdict and must appear in the
   README text the verdict allows.
5. **Inconclusive** overrides 4 when: fewer than half of the planned runs (after any reduction in section 6)
   counted in either arm; or no savings were detected and routing did not take effect or was not measured (a null
   where routing may never have acted says nothing about routing); or the study could not run in this harness
   (section 6, pilot). In F the workflow script sets each agent's model from the map itself, so routing counts as
   having acted there unless the transcripts show otherwise.

### Numeric bars

- n: R runs 5 cases × 6 runs × 2 arms = 60 runs (24 per arm on standard cases, 6 per arm on the careful case).
  F runs 2 tasks × 5 runs × 2 arms = 20 runs (10 per arm). The reduction ladder in section 6 may lower these
  before a main run starts, never after.
- Cost bar: ρ's 95% interval entirely below 1.00 (savings) or entirely above 1.00 (increase).
- Quality bars: loss when Δq's 95% interval is entirely below 0; non-inferiority margin −0.15.
- Careful-case harm bar: 2 or more fewer hidden-test passes in the routed arm.
- Manipulation bar: at least 50% of routed-arm subagent runs on a non-Opus model, and 25 points above all-opus.
- Null: ρ's interval includes 1. Keep "no savings claimed".
- Power, stated in advance. Quality: with 24 runs per arm and both arms passing nearly every run, the Newcombe
  interval for Δq is about ±0.14, so non-inferiority at −0.15 can only be shown when both arms nearly always pass;
  only a large drop is detected as a loss (from a perfect all-opus arm, 24 of 24 against 18 of 24 gives an interval
  of −0.45 to −0.06, so about 25 points; from a lower start, more). F's 10 runs per arm can detect only a drop of
  about 40 to 50 points and cannot show non-inferiority at all (10 of 10 in both arms gives ±0.28), so F's quality
  outcome can only be "loss" or "not resolved". Cost: the spread between runs is unknown until the pilot. If
  routing moves most subagent spend off Opus, a ratio near 0.7 should resolve at these n; a ratio near 0.95
  probably won't, and a null then does not show there is no saving.

## 5. What would refute the option you want

The option the builder wants is that routing saves money without hurting quality; that is why both plugins
exist. It is refuted, in plain terms, by any of these:

- ρ's interval includes 1 or lies above it: no saving shown on these tasks.
- The hidden tests show a quality loss (Δq's interval entirely below 0).
- The careful case flags harm.
- In R, the all-opus arm already runs half or more of its subagents on a non-Opus model: Claude Code's default
  already routes, and the plugin has little left to do.
- The routed arm saves only by doing less (fewer subagents, fewer turns) while its hidden-test pass rate falls.

## 6. Frozen grid and held-out tasks

### Frozen grid

Two studies, each run once. R runs first, then F.

**Study R (dojo-router)**

```
claude plugin eval plugins/dojo-router --case 'hr-*' --runs 6 --ablation with-without --scaffold --keep-temp \
  --no-publish --judge-model opus --allow-tools Bash Edit Write --max-cost-usd <cap-R> -j 2 \
  --json <results>/r-main.json --output-dir <results>/r-main
```

- Cases: `hr-note-cache`, `hr-page-size`, `hr-reminder-every`, `hr-retry-limit` (standard); `hr-limiter-starve`
  (careful).
- Executor `model: opus` in every case, `max_turns` 16, `timeout_seconds` 900. Allowed tools: Read, Edit, Write,
  Bash, Glob, Grep, Agent, Skill.
- dojo-router 0.1.1 at the commit that adds this file, every option at its default (`mode` warn, `default_tier`
  sonnet, `explore_tier` haiku, `auto_route` true, `opus_cap` 0). The operator's shell sets
  `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`, so the mod tier routes if the eval passes that variable to its child;
  whether it does is pilot check P2. Whichever tier acts is the with arm, and the write-up names it.

**Study F (dojo-flow)**

```
claude plugin eval plugins/dojo-flow --case 'hf-*' --runs 5 --ablation none --scaffold --keep-temp \
  --no-publish --judge-model opus --allow-tools Bash Edit Write --max-cost-usd <cap-F> -j 2 \
  --json <results>/f-main.json --output-dir <results>/f-main
```

- Cases: `hf-gradebook-routed`, `hf-gradebook-allopus` (standard task); `hf-semver-ranges-routed`,
  `hf-semver-ranges-allopus` (careful task). Each task has two case files, `-routed` and `-allopus`, identical
  except the `models` value in the prompt. Routed passes the workflow's own defaults explicitly (scout haiku, builder sonnet, integrator sonnet,
  reviewer sonnet, checker haiku, judge opus); all-opus passes `opus` for all six roles.
- Executor `model: opus`, `max_turns` 12, `timeout_seconds` 1800. Allowed tools: Read, Edit, Write, Glob, Grep,
  Bash, Skill, Workflow (Edit and Write are there for the workflow's builders; the prompt tells the session itself
  not to edit). dojo-flow 0.1.0 at the commit that adds this file.
- The evaluator's prompt, the same for every F case apart from the args block:
  > Run the dojo-flow build workflow on this repository with exactly the arguments below. Call the Workflow tool
  > with name "dojo-flow:build"; if that name is not known, call it with scriptPath set to the plugin's
  > workflows/build.js. Set repo to the absolute path of the current directory (run pwd to get it). Do not change
  > the goal, tracks, gates or models, and do not edit any file yourself. Wait for the workflow to finish, then
  > reply with its scorecard exactly as returned.

**Hidden tests.** After each main run, `grade_hidden.py grade <case> <kept work dir>` for every run. Before the
freeze, `grade_hidden.py selfcheck` was run on every case: the scaffold as written must FAIL the hidden tests and
the scaffold with the author's reference laid over it must PASS (the known-bad and known-good inputs).

**Pilot first, excluded from analysis.** The same two commands with `--runs 1`: R is 10 runs with a cap of $5, F is
4 runs with a cap of $12. Its only purposes:

- P1: the plugin loads (`suite.plugins` lists it with an empty problems list).
- P2: in R's with arm, which tier acted: the mod (dispatches that named no model ran on a non-Opus model) or the
  classic hook only (its warning in the trace), or neither.
- P3: `--keep-temp` keeps each run's work directory and transcripts, and `grade_hidden.py` runs on them.
- P4: every grader runs without error.
- P5: in F, the child can call the Workflow tool, the workflow reaches a scorecard within the run, and its agents'
  cost is inside the run's cost.
- P6: agent cost and judge cost per run, per study.

If a check fails and the fix touches no prompt, grader, metric, rule or n (a flag, a path, a granted tool, a field
the eval reads differently than assumed), make it, record a dated amendment below the marker, and pilot that study
again; the re-pilot counts against the cap. If F's P5 can't be fixed that way, F is not run, and its result is
"could not run in this harness" with the pilot evidence. If P2 shows neither tier acting, R still runs and the
write-up says so; the rule's manipulation bar then decides how a null reads. The analysis script that implements
section 4 is written after the pilot and committed, with its sha256 below the marker, before any main run.

**Stop rule and cap arithmetic.** The cap is $100 for every `claude plugin eval` invocation: pilots, re-pilots, main
runs, judge included. Each invocation's top-level `costUsd` goes into `spend-ledger.md` as soon as it ends.

- Every invocation gets `--max-cost-usd` before it starts. The eval checks its cap before it launches each run, so
  it can overrun by the runs in flight (2 at `-j 2`). Reserve for that: 2 × the largest pilot cost per run in that
  study × 1.5.
- Pilot caps: R $5, F $12.
- Main cap R = min(1.3 × R's pilot cost per run × 60, $35, $100 − all spend so far − R's reserve).
- Main cap F = min(1.3 × F's pilot cost per run × 20, $100 − all spend so far − F's reserve).
- If a study's projected main cost (pilot cost per run × planned runs) doesn't fit its cap, lower runs per case
  before it starts, in this order, until it fits: F to 4, R to 5, F to 3, R to 4. If F doesn't fit at 3, F is not
  run, and the write-up says it wasn't for budget.
- If a cap trips mid-run: stop, analyse the runs that finished, report them as partial. No top-up runs, no re-runs
  of single cases.

**Cost estimate, before any run.** Guesses, at list prices of $4 / $20 per million input / output tokens for Opus
5.5 and $2 / $10 for Sonnet 5.5 (Haiku's price was not looked up): an R run of up to 16 turns with two or three
subagents at about $0.25–0.50 including the judge, so $15–30 for R's main run; an F run (about ten workflow agents
on three tiers, or all on Opus) at about $1.50–4, so $30–80 for F's main run, which is why the reduction ladder
exists. Pilots about $4 and $10. Not counted in the cap: the task author's and this session's own usage, which
build the eval but are not eval runs.

### Baseline arm (without)

- **R:** produced by `--ablation with-without`: the same cases, model and flags, with dojo-router absent. Every
  case pins the executor to `opus`, and each eval child starts from a fresh config directory and home with no user
  plugins or settings, so an unpinned dispatch in this arm runs on Opus unless Claude Code itself picks another
  model, which the transcripts show.
- **F:** `--ablation none`. The all-opus arm is the `-allopus` case of each task, run beside the `-routed` case
  with the same flags. Both arms load dojo-flow, because the workflow under test lives in it.

The headline is the routed-minus-all-opus difference in each study, never one arm's number alone.

### Held-out task author

An independent model instance (Claude Sonnet 5.5, a subagent of the session building this eval) given only
`held-out-brief.md`, pasted into its instructions, and told not to read any repository, plugin or file outside its
output folder. It wrote the prompts, scaffolds, hidden tests and reference solutions, and for F the goal, tracks
and gates, and it checked that each hidden test fails on the scaffold and passes on its reference. It is not the
builder of either plugin, but it is a model, not a person. The evaluator (the same building session) wrote the
graders, F's instruction wrapper and this rule, and changed none of the author's text except where an amendment
below says so. Cruz accepted a model author for the dojo-verify eval on 2026-10-17; this eval uses the same kind
of author under the 2026-10-23 funding ruling, and the write-up names it as a handicap.

### Task where the protocol should lose

One careful task per study, written to make routing lose.

- **R:** `hr-limiter-starve`. A token bucket starves clients that retry or poll more often than one token
  interval, and the prompt asks the agent to have a subagent review the bucket and find the real cause; the
  visible tests pass before the fix, and a plausible fix that banks idle time still fails the hidden tests. The
  work the prompt asks the agent to hand to a helper needs judgment, not lookup. Routed, that helper runs on
  Sonnet (a general-purpose dispatch goes to `default_tier`) or Haiku (an Explore dispatch), where all-opus gives
  it Opus. Routing should do no better here and may do worse.
- **F:** `hf-semver-ranges`. The `semver` track must implement full Semantic Versioning 2.0 precedence; a quick
  version passes the 10 visible tests and fails 11 hidden ones. That track's builder must get a subtle rule right.
  Routed, the builder is Sonnet; all-opus, it is Opus.

If the routed arm does better than all-opus on a careful case by 2 or more hidden-test passes, suspect the harness
or the hidden tests before reading anything into it.

MEASUREMENTS BEGIN BELOW THIS LINE

## Status note before any spend (2026-10-23 21:15 UTC)

The digest above, `d66e5b96bc78d9987d5fc13f60b3b85918b60b1bd0bd04676631bf505645187a`, was recorded at
21:14:21 UTC, committed as `7404987`, and pushed to `refs/heads/eval/routing-2026-10-23` at 21:15:15 UTC, before
the first eval invocation at 21:15:42 UTC. The digest and the cap arithmetic went to Cruz in the session's first
status message, and into the shared notes of the session group, before anything was spent.

## Amendment 1 (2026-10-23, after the pilots, before any main run)

Four fixes, each of the kinds section 6 allows (a flag, a granted tool, a field the eval reads differently than
assumed). No prompt, criterion, metric, rule or n changed. The pilots (ledger rows 1 to 6, $8.48 in all) are
excluded from analysis.

1. **`--trust-plugin` added** to both commands. Without it the eval stops at an interactive trust prompt that a
   non-interactive shell can't answer. The plugins are this repository's own code.
2. **No shell for any agent.** The first R pilot started no agent and spent $0.12 (the in-eval judge only): on
   this Windows machine the eval refuses any run that grants a shell tool, because the Windows sandbox is behind a
   feature gate that is off for this session and the eval sets `failIfUnavailable`. The grants are now
   `--allow-tools Edit Write` for R and `--allow-tools Edit Write Workflow` for F. Agents and workflow agents in
   both arms can read, search, edit, write and dispatch, but can run no command: no tests, no gates, no git, no
   `pwd`. This holds for both arms alike. `hr-reminder-every`'s "run them when you're done" can't be followed, and
   F's integrator and audit can't run the gates, so no F scorecard can say VERIFIED. Read every result here as
   what routing does in a session without a shell. The hidden tests run outside the eval and are unaffected.
3. **Workflow granted in F.** It is a gated tool. The first F pilot withheld it, and no workflow ran ($0.54).
4. **The files judge runs outside the eval.** On this machine the eval hands the `focus: files` judge an empty
   view ("(no file changes)") even when the agent changed files: in the R pilot it voted FAIL three times on all
   10 runs, all of which pass the hidden tests. `judge_files.py` runs the same grader after the eval: the same
   criteria string, read from each case.yaml; Opus; three votes, the majority deciding; and files only, never
   the trace. The files are the run's changes against a fresh scaffold. Planted inputs: scaffold plus reference
   PASS 3 of 3; the scaffold untouched FAIL 3 of 3. On the 10 R pilot runs it voted PASS 3 of 3 on all 10,
   agreeing with the hidden tests. Each vote is `claude -p --model opus` on the same claude.ai login, with no
   tools, setting sources, MCP servers or slash commands; a probe showed no user hook reaches it. The in-eval
   `quality-judge` still runs (about $0.006 a run) and its verdicts are void; Δj uses `judge_files.py`. Its
   spend is outside `claude plugin eval`, so it is logged in the ledger and counted against the $100.

**Pilot checks.**

- P1: both plugins load; `suite.plugins` lists dojo-router 0.1.1 and dojo-flow 0.1.0, with no problems listed.
- P2: in R's with arm, the session named a model on every Agent dispatch by itself, so there was no unpinned
  dispatch for either tier to act on (`hook-warned` 0 of 5). 8 of 9 with-arm subagents ran on
  `claude-haiku-5-5` or `claude-sonnet-5-5`; on the careful task the session chose Opus for its helper. In the
  without arm, all 11 subagents ran on `claude-opus-5-5`, Explore included, so the baseline is all-Opus as
  assumed. What made the with arm name models is not isolated here; the plugin's `router` skill is in its
  context, and its hooks never fired.
- P3: each kept run holds its work directory (`home/cwd`) and transcripts with exact model ids
  (`config/projects/.../subagents/*.jsonl`; F's workflow agents under `subagents/workflows/wf_*/`).
  `grade_hidden.py` runs on them: 10 of 10 R pilot runs PASS.
- P4: every grader runs; `quality-judge` is void, as item 4 says.
- P5: in F the Workflow tool works once granted, and the workflow reached a scorecard in 4 of 4 runs. Run costs of
  $0.75–0.88 are well above what the session's own transcript accounts for, consistent with the workflow agent's
  cost being inside the run. **But in all 4 the contract gate (role `judge`, Opus in both arms) returned REFUSED:
  it found the two tracks coupled, because one calls the other's functions and the visible tests import both
  modules. Only the contract agent was dispatched, so no routed role ran.** Two of the refusals also say the gate
  was never given the track prompts. That is true of `build.js`: the contract prompt lists track names and owned
  files only, while asking the gate to check that "each track prompt matches the code". Under section 6, P5 passes
  (the workflow runs and reports in this harness), so F's main run goes ahead as frozen. If the gate keeps
  refusing, the rule's manipulation bar decides how that reads. dojo-flow is the artifact under test and is not
  changed here.
- P6, cost per run: R $0.371 in the eval (the largest single run $0.549), plus $0.081 for the files judge. F
  $0.797 (the largest $0.881).

**Caps, by the stop rule.** Spent so far: $8.4803.

- R reserve = 2 × 0.549 × 1.5 = $1.65. R main cap = min(1.3 × 0.3709 × 60 = $28.93, $35, 100 − 8.48 − 1.65 =
  $89.87) = **$28.93**. Projected: $22.26 for the eval and $4.86 for the files judge. Runs stay at 6 per case.
- F reserve = 2 × 0.881 × 1.5 = $2.64. F main cap = min(1.3 × 0.7968 × 20 = $20.72, 100 − spend at that point −
  2.64), worked out from the ledger before F starts. Projected: $15.94 for the eval and about $1.60 for the files
  judge. Runs stay at 5 per case.
- Projected total, pilots included: about $53.

**Analysis code, frozen before any main run** (sha256 of each file as committed with this amendment):
- `d6498c583dd8fe408747ccd622da19113e0903c5eda5ae1950f9d587922bd33c`  `analyze.py`
- `811595b01977df1277df9b8609c13f4a0b94f5c8202cd1fd8e3e122676ea8961`  `stats.py`
- `86a1fdf9ba6d73020d6e5ab5788d3640e647f2f5c23d5d325cf242634a2cfd66`  `grade_hidden.py`
- `aef332021ec17eef39e5c0cb1b300e67a2932437173f4a97c0b65072391a61a5`  `judge_files.py`
- `24f82686ef6bd94f6af10eaadaa38770455c6d0c9709a0d422f68a5f06f498bb`  `judge_runs.py`
- `7d27f380fe1c66048d032d8b6af6d48f5faecec93a558625346bcc3b87d5f085`  `build_cases.py`

## Results

(Empty until the run. Raw numbers per cell go here, including the cells that make routing look bad.)

## Ruling applied mechanically

## What outranks the ruling

## Gaps and handicaps

## Digest check after write-up
