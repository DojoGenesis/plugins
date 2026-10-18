# Changelog — dojo-genesis

## Unreleased — 2.4.0 — hooks with measured accuracy

Every firing of a dojo-verify or dojo-gates hook in one maintainer's sessions (2–17 October UTC, 382 firings) was
labeled right or wrong against a written rubric by an independent labeler, with a second labeler on 30% (95%
agreement). Before these fixes, dojo-verify's Stop block was right 3% of the time, config-first 30% and secret-print
never. The fixes were made against half the firings and scored once on the other half. `ACCURACY.md` has the
method, the rubric and the tables. It started from five misfires reported from one session on 2026-10-16.

### Added

- **A fixture suite for the hooks** — `scripts/hook_accuracy.py` runs each hook script on fixtures with known
  answers (`plugins/<plugin>/fixtures/accuracy/`) and prints precision and recall per hook with 95% intervals;
  `--hooks-from` measures another checkout against the same fixtures. Fixtures marked `known_miss` record errors the
  hooks still make: they count, but don't fail the run.
- **A pre-registered with/without eval of dojo-verify's Stop block** —
  `plugins/dojo-verify/evals/PREREG-2026-10-17-evidence.md`, frozen before any run, with eight held-out cases. Its
  result, below the marker: no benefit detected, and its rule says the default should be `warn`. Following that rule
  (Cruz's ruling, 2026-10-18), the default is now `warn`; `block` stays one setting away.
- **A runtime health report** — `scripts/health_report.py` replays local Claude Code transcripts through the suite's
  own detector code and reports, per rule, what it counted and out of how many, with each finding's evidence and
  each detector's measured accuracy beside it. The same input gives byte-identical output.
- **A rule-by-rule table** in `ACCURACY.md`: for each of the ten rules, what checks it at runtime, how accurate that
  check is, and what has measured the rule's effect.

### Fixed

- **`dojo-verify` 0.2.0** — counts the checks people actually run: a program that exits clean and prints PASS or ok
  lines, `N passed`, `N/N pass`, `ALL PASS` or `0 failed`; `gh pr checks` and `gh run view/watch`; opening a rendered
  image after a visual change. The agent's own memory and notes (a Write or Edit there, or a Bash write that names
  them) no longer reset the evidence. Reads claims as the writer meant them: a leading negative covers its list
  ("Nothing is committed, pushed or deployed"); blockquotes, quoted spans and list items under a "says:" or "wrote:"
  line are someone else's words; "a paid verified review" and "Fixed scope" are adjectives; "works in", "Why it
  works", "go to Done" and "Click Done" are other senses; "the builder reports 1737 passed" is attributed. The mod
  mirrors every rule. On unseen sessions this removes 58% of its misfires and keeps every real catch; it is still
  right only about one time in twelve.
- **`dojo-gates` 0.2.0, config-first** — a line counts only when a program this command ran reports its own failure
  in a known shape (`bash: x: command not found`, `cat: x: No such file or directory`, git's `fatal:` and
  `warning:` path lines, `HTTP/1.1 401`, `connect ECONNREFUSED`), so printed docs, logs and source no longer fire it.
  `ls`, `stat` and `test` answering whether a path exists, a missing path after a code error, an unsplit variable
  run as a command, and a loop trying candidate programs are not configuration failures. A `cat` of a missing
  config file now fires, where it was skipped before.
- **`dojo-gates` 0.2.0, secret-print** — follows where the output goes: a value captured by `$(...)` for an
  assignment or a program that doesn't print it, piped into `grep -c`, `wc`, `cut -d= -f1`, a `sed 's/=.*/…/'` mask
  or `/dev/null`, an env file being written (`cat > .env`), and a loop variable bound to literal words no longer
  deny. The shell parser records each substitution's parent segment so the guard can tell.
- **`dojo-gates` 0.2.0, staging** — `git add -N` (intent to add) and `git add -n` (dry run) stage no content and no
  longer deny.

## Unreleased — 2.3.0 — the desktop pass

Found by running the mods in the Claude desktop app and recording what it draws (a census of every `ui.render` site it raised).

### Changed

- **`dojo-fleet` 0.2.0** — off the terminal (the desktop app, VS Code, mobile) the Fleet pane draws a card per agent in its state's colour: model, age, tools and writes, what it is doing now (`now Bash · 12s`), a stall line when flagged, the answer once settled, and Steer, Nudge and Stop on the card itself. The terminal's fixed-width columns had read raggedly in proportional type, and the actions waited behind a pick-a-row step. The terminal keeps its aligned rows. New option `auto_open` (default on): when two agents run at once the pane opens by itself, once per wave, without taking the keyboard; the engine places it only where there is room.
- **`dojo-swimlanes` 0.2.0** — legibility in a docked desktop pane. The chart is handed its width and height in CSS pixels (without them the desktop drew the image at its pixel size in device pixels, half size on a 2x screen); the time axis runs to hours and days with at most eight ticks (it stopped at 10 minutes, so half a day drew about seventy overlapping labels); idle stretches over 20 seconds between waves fold into a narrow break labelled `+12h`, so every wave keeps its width; axis labels that would overlap are dropped; larger type and lanes; the legend wraps on a narrow pane. Under the chart, one line per agent in the surface's own text: status, model, duration, tool calls, writes and refusals.

### Fixed

- **`dojo-fixcards` 0.1.1** — no card drew in the desktop app. The desktop raises no `ToolResult` site; a refused call arrives on a standalone `ToolUse` row with the guard's text in `output`. Off the terminal the card now goes under the refused tool row, and the result-block hook stands aside there, so no surface draws a refusal twice.

## 2026-10-15 — 2.2.0 — desktop mods

### Added

- **`dojo-swimlanes`** — a fan-out drawn as a timeline: one lane per agent, a mark per tool call, refusals in red, live in a pane. `/swimlanes`, `/swimlanes text`, `/swimlanes all`. The desktop app draws a chart; the terminal draws text strips.
- **`dojo-fixcards`** — a tool call a Dojo guard refuses is drawn as a card: who blocked it, why, and the fix as code you can copy. Reads dojo-gates and dojo-lanes refusal text; an unknown guard still gets a card with its reason. `/fixcards`.

Each is a function-hook mod (early access) with a classic fallback command, listed with the companions. Tested with Claude Code 2.1.295.

## Unreleased — 2.1.2 — mods: field-test fixes

### Fixed

- **`dojo-meter` 0.1.1** — `claude-haiku-5-5` had no row in the price table, so Haiku 5.5 turns read `unpriced` and every total beside them read `(partial)`. The row is there now at the published prices: $0.10 input, $0.50 output and $0.01 cache read per million tokens. Haiku 5.5 is priced per request on prompt length, so a request whose prompt (input, cache reads and cache writes together) is over 100,000 tokens is priced on the published second card, $0.50 / $2.50 / $0.05. The band keeps the two sizes in separate rows; the report prints the longer ones as their own row marked `>100k`, and `--json` rows gain `long_prompt` and `prompt_over_tokens`. A model with no second card is priced exactly as before.
- **`dojo-meter` 0.1.1, the band** — beside dojo-fleet, the meter's band hid Fleet's band in every session that had both installed. The meter's `AbovePrompt` handler returned its band without calling `next()`, so no handler after it ran; Fleet's band (which does wrap what is beneath it) drew only when the meter was off. The band now goes above whatever is beneath it, and the same stacked check passes in either registration order.
- **`dojo-router` 0.1.1 and `dojo-verify` 0.1.1** — the status line and the toasts led with a hand-written `dojo-router: ` or `dojo-verify: `, and the engine heads plugin output with the plugin's name as well, so users read `dojo-router: dojo-router: …`. The text drawn in the UI no longer carries the prefix; deny texts and the meta rows the model reads keep it. dojo-router's mod-test fix (b852405) had shipped without a version bump, so installed 0.1.0 copies still hold the old `tests/router.test.ts`; 0.1.1 carries the fixed one.
- **`dojo-fleet` 0.1.1** — in a pane about 60 columns wide the Fleet rows wrapped inside their cells (`haiku / 5.5`, `25 / s`, `● / #1`). The columns are now sized to the pane: the label gives way first, then the work column is dropped, and model and age are never wrapped (their text truncates if the pane is narrower still). A wide pane draws exactly as it did.

## 2026-10-14 — 2.1.1 — dojo-tally: /tally refute

### Fixed

- **`dojo-tally` 0.1.1** — `/refute <n>` was missing wherever dojo-protocol is installed (the whole suite): its `refute` skill holds the name, and Claude Code keeps it there. The judge is now reached with `/tally refute <n>`, which always works; the bare `/refute` stays as a shortcut where the name is free. The settle note, the `/tally` footer, the README and the promise say `/tally refute`.

## 2026-10-14 — 2.1.0 — orchestration mods

### Added

- **`dojo-fleet`** — the Fleet pane, a band above the prompt with one chip per agent, `/fleet`, `/steer`, and a stall check judged by tool calls and files written. An agent that ends a turn while the engine still holds it is shown as waiting, not done.
- **`dojo-lanes`** — the first subagent to write a file holds it while it runs; another running subagent's write to it is refused. The contract note on spawn, the rule-4 nudge, `/lanes`.
- **`dojo-tally`** — fan-out waves classified as returned, failed, silent or unchecked; a settle note added to the conversation; `/tally`; `/refute` sends a report to the judge agent.
- **`dojo-brief`** — each subagent brief linted at dispatch against the delegate skill (detail, owned files, done-check, return shape), as a notice or one send-back; `/dojo-brief` for the template and the tally.

Each is a function-hook mod (early access) with a classic fallback command, listed with the companions. Tested with Claude Code 2.1.295.

## 2026-10-02 — 2.0.0 — the Dojo protocol suite comes first

The marketplace now leads with a protocol suite for Claude Code: plugins and mods that put the right model on each job, keep context small, and don't call work done until a check passes. The library and the companions are unchanged apart from the fixes listed under Wave-0 and Cleanup, and no library plugin was removed.

### Added

- **`dojo-suite`** — an install bundle. `plugin.json` only, with the eight suite plugins as `dependencies` (bare names, resolved against this marketplace). No skills, agents, commands or hooks, so no always-on weight. `/plugin install dojo-suite@dojo-genesis` installs the set.
- **`dojo-protocol`** — the ten-rule protocol injected at session start, four role agents pinned to a model each, five skills.
- **`dojo-gates`** — ten deterministic guards (hooks) for blanket staging, rewriting pushed commits, printing secrets, token URLs, oversized reads, silent probes and similar. `hooks/guards.json` lists the guard ids so the count comes from a file.
- **`dojo-router`** — warns or blocks subagent and workflow dispatches that name no model; the mod (early access) fills one in by role.
- **`dojo-meter`** — a cost report from your transcripts (`/dojo-meter:cost`) and, with the mod, a live band.
- **`dojo-verify`** — a Stop hook that flags a success claim with no passing check after the last change; the mod (early access) adds status and a dispatched/returned tally.
- **`dojo-flow`** — workflow scripts for parallel builds and convergence audits, with a scorecard that counts returns.
- **`dojo-doctor`** — a read-only report on hooks and settings that fail or cost you silently.
- **`dojo-settle`** — pre-registered experiments, decision gates and eval scaffolds. Nothing was run; no with/without result exists yet.
- **`scripts/suite_table.py`** — generates the README suite table from the plugin directories; `--check` fails when the README drifts.

### Changed

- **`marketplace.json` 1.5.6 → 2.0.0.** The nine suite entries come first, then the library, then the companions. Each entry carries a `category` of `suite`, `library` or `companion`; suite entries also carry a `displayName`. Both fields pass `claude plugin validate`.
- **README and `llms.txt`** open with the premise, the install block and the suite table, then the library and the companions. Counts are generated from disk or checked against it.
- **`scripts/face-parity.py`** counts a plugin that ships agents, commands, workflows or dependencies as installable even with no skills, checks claims that name a group ("library plugins") against that group, and checks the README suite table against `scripts/suite_table.py`.
- **`scripts/plugin-lint.py`** accepts the hook events Claude Code 2.1.286 defines; its list had stopped at nine and rejected `PostToolUseFailure` and `InstructionsLoaded`.
- The suite skills carry `model: inherit` and a cluster `category:`, which `scripts/validate-skills.sh` and `scripts/plugin-lint.py` require of first-party skills.

### Wave-0 fixes (each is its own commit)

- **bring-loop 0.1.1 → 0.1.2** — synced from the canonical repo: every hook command and every command a skill tells you to run now says `python3`, because a bare `python` is missing on macOS and the hooks failed silently. The distribution copy keeps its `govern-publish` cluster category, and it now ships an MIT LICENSE.
- **pretext-pdf 0.2.0 → 0.2.1** — the export-logging hook exited 1 on every call that was not an export (its `set -e` fired before the check meant to handle that case). It now exits 0 whenever it does not apply, and on any error. The manifest description was also reworded.
- **kata-harness 0.1.2 → 0.1.3** — the homepage link pointed at a repository that does not exist (404). It now points at this plugin's directory in this repository, and the manifest names the repository.
- **Licence lines** — removed `license: proprietary` from nine first-party skills in continuous-learning, system-health and wisdom-garden (patch versions bumped). The repository is Apache-2.0.

### Cleanup

- **`community-skills` is slated for removal from the public repository in a follow-up (an operator step, not part of this change).** It holds harvested third-party skills and was never registered, so nothing installs from it; history will keep it. `dojo-craft` has a corrected `author` object (1.0.1) so the marketplace validates.
- Private product and repository names were removed from library skill text and from the kata-harness spec (patch versions bumped: agent-orchestration, continuous-learning, skill-forge, system-health, wisdom-garden, kata-harness).

### Not measured

The suite's effect on cost, speed or accuracy has not been measured. The counts and the always-on description weight are measured by script and published, with method and date, at https://dojogenesis.com/proof. The mods need function hooks enabled and are early access.

## 2026-10-02 — bring-loop v0.1.1 — generated queues stop hiding open multi-step items (v1.5.6)

Synced from canonical `DojoGenesis/bring-loop` @ `80acfe1`. `open_actions` used to drop any id that
had ever logged `sent`/`decided`. When `actions.md` is regenerated from an upstream source of truth,
multi-step items legitimately log `sent` while still open, so they vanished for good (6 of 55 in a
real queue, including the ranker's top item). Now `closed`/`shipped` hide permanently; on a generated
`actions.md` (`generated_utc:` or a `GENERATED by` header) `sent`/`decided` hide only until the next
regeneration. Hand-written files keep the old rule. Plugin version bumped 0.1.0 → 0.1.1 so the
version-keyed plugin cache re-copies (see the kata-harness v0.1.2 entry below).

## 2026-07-15 — kata-harness v0.1.2 — plugin version bumped so the cache can see the fix (v1.5.5)

### What happened

v1.5.4 synced the correct `roll_core.py`, and the distribution copy was verifiably right — but the
fix still could not reach an installed plugin. Claude Code's plugin cache is keyed by version
(`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`), and `7ab0505` had shipped changed
content under the already-published version 0.1.1, so nothing downstream could tell the content had
moved.

Observed on this machine, not theorised: `claude plugin update kata-harness@kata-harness` printed
"updated from 0.1.0 to 0.1.1", wrote `gitCommitSha: 7ab0505` into `installed_plugins.json`, and
served pre-fix bytes anyway — it cleared the `.orphaned_at` marker on the pre-existing 0.1.1 cache
dir and re-pointed the manifest at it without re-copying content. The manifest claimed a commit
whose code it did not contain. Only a sha256 of the file on disk caught it; the CLI reported
success throughout. Recovery took an uninstall plus removing the stale cache dir so the reinstall
had nothing to resurrect.

Canonical `48aab5e` bumps the plugin to 0.1.2. A fresh version key cannot collide with an existing
cache dir, so the copy is forced. It also revives the sync stamp below, which had been inert across
v1.5.2/v1.5.3/v1.5.4 — three consecutive syncs where the line could not move because neither the
date nor the plugin version had changed. A stamp that cannot move is not evidence of a sync.

### Changes

- **`plugins/kata-harness/.claude-plugin/plugin.json`** — version 0.1.1 → 0.1.2 (synced from
  canonical `48aab5e`). Upstream bumps two declarations in lockstep — the plugin manifest and the
  root single-plugin marketplace metadata — since `claude plugin tag` validates that the two agree
  and treats both as the release surface. Only the manifest is distributed here.
- **Sync line: `Synced 2026-07-15 @ v0.1.1` → `@ v0.1.2`** — first time it has moved since the
  plugin was added. Date is the *local* working day (2026-07-15 CDT); UTC had already rolled to
  07-16 when this was written, which is the same class of bug `7ab0505` fixed.
- No core change: `roll_core.py` untouched since v1.5.4 (sha256 `194d07da…`), byte-identical with
  both canonical copies, 67/67 upstream.
- **marketplace.json + README version**: 1.5.4 → 1.5.5. Counts unchanged (101/11).

## 2026-07-15 — kata-harness local-date resolve fix re-synced (v1.5.4)

### What happened

Canonical kata-harness landed `7ab0505`: `_resolve_now()` computed `today` off a UTC-aware
timestamp, so any `roll-resolve` / `roll-skip` fired after ~19:00 in a negative-UTC-offset zone
(Central included) was stamped with tomorrow's date once UTC had already rolled over — the ledger's
`date` field means "which local working day", the same contract as `bring.py`. Confirmed against a
real incident: a roll-skip at `utc=2026-07-16T01:30:05Z` (20:30 CDT on the 15th) landed as
`date=2026-07-16`. The intended `date.today()` live-usage branch was also unreachable, since
`now_ts` always resolves non-None via its own `_utc_now()` fallback. Re-synced the fixed core into
the distribution copy.

### Changes

- **`plugins/kata-harness/scripts/roll_core.py`** — `_resolve_now()` converts to the local date via
  `.astimezone().date()` before taking the date component; the true no-override path now reaches
  `date.today()`. No timezone is ever hardcoded (system-local only, per `bring.py`'s contract), so
  it stays correct on the Windows machine too. The `utc` field is untouched — still the true UTC
  instant. Synced from canonical `7ab0505`; byte-identical with both canonical copies
  (`scripts/` + `plugin/scripts/`, sha256 `194d07da…`). 67/67 tests green run directly against
  this distribution copy (62 + 5 new `ResolveNowLocalDateTests` regressions).
- Sync line unchanged (`Synced 2026-07-15 @ v0.1.1` — same day, plugin version not bumped upstream).
- **marketplace.json + README version**: 1.5.3 → 1.5.4. Counts unchanged (101/11).

## 2026-07-15 — kata-harness python3 text sweep re-synced (v1.5.3)

### What happened

Canonical kata-harness landed `4b5ce72`, finishing the interpreter fix that `301bf61` started:
every bare `python` invocation in the skill's command examples and `roll_core.py`'s usage/status
strings became `python3` (bare `python` doesn't exist on modern macOS). Re-synced both files into
the distribution copy — it now matches canonical HEAD exactly (verified per-file).

### Changes

- **`plugins/kata-harness/skills/kata-harness/SKILL.md`** — command examples `python` → `python3`
  (synced from canonical `4b5ce72`).
- **`plugins/kata-harness/scripts/roll_core.py`** — usage/status-face strings `python` → `python3`
  (synced; byte-identical with both canonical copies, 62/62 tests green upstream).
- Sync line unchanged (`Synced 2026-07-15 @ v0.1.1` — same day, plugin version not bumped upstream).
- **marketplace.json + README version**: 1.5.2 → 1.5.3. Counts unchanged (101/11).

## 2026-07-15 — kata-harness hook interpreter fix re-synced (v1.5.2)

### What happened

Canonical kata-harness landed `301bf61`: the SessionStart hook invoked bare `python`, which
modern macOS doesn't ship, so the roll-status injector had silently failed (exit 127) on every
session start. Re-synced the fixed `hooks.json` (`python3`) into the distribution copy. A wider
`python` → `python3` sweep of the skill text and `roll_core.py` usage strings is in flight
upstream; it re-syncs here when it lands.

### Changes

- **`plugins/kata-harness/hooks/hooks.json`** — hook command `python` → `python3` (synced from
  canonical HEAD `301bf61`; plugin version unchanged at 0.1.1).
- **marketplace.json + README version**: 1.5.1 → 1.5.2. Counts unchanged (101/11).

## 2026-07-15 — kata-harness setup fix re-synced (v1.5.1)

### What happened

The kata-harness-setup skill's missing-queue branch instructed running
`${CLAUDE_PLUGIN_ROOT}/scripts/bring_core.py init` — a file the kata-harness plugin never ships
(it bundles only `roll_core.py`, which vendors bring_core *functions* but deliberately has no
`init` verb). The branch failed in both dev and installed layouts. Fixed in the canonical repo
(kata-harness v0.1.1) and re-synced here: the step now invokes the bring-loop plugin's own
`bring-setup` skill by name (installing `bring-loop@dojo-genesis` first if absent) — one owner
for the queue scaffold format, no cross-plugin paths.

### Changes

- **`plugins/kata-harness/skills/kata-harness-setup/SKILL.md`** — step 1 missing-queue branch
  rewritten (synced from canonical).
- **`plugins/kata-harness/.claude-plugin/plugin.json`** — 0.1.0 → 0.1.1.
- **`plugins/kata-harness/README.md`** — sync line: Synced 2026-07-15 @ v0.1.1.
- **marketplace.json + README version**: 1.5.0 → 1.5.1. Counts unchanged (101/11).

## 2026-07-15 — Add kata-harness plugin (v1.5.0)

### What happened

Registered **kata-harness** as the 11th plugin — the Kata Roll runner that extends bring-loop:
bounded, self-terminating roll sessions (reps or minutes) over the same `bring/` queue, one bring
surfaced per tick, surface + stage only, session shape folded fresh from its own append-only
`bring/roll-ledger.jsonl`. Closes the HARNESS-STANDARD H4 gap: kata-harness's SPEC §7 committed to
this marketplace on 2026-07-13, but the listing didn't exist until now.

### Changes

- **`plugins/kata-harness/`** — distribution copy synced from the canonical repo
  (`github.com/DojoGenesis/kata-harness`, `plugin/` dir + `SPEC.md`/`NOTICE`), following
  bring-loop's pattern: plugin manifest, SessionStart roll-status injector (report-only,
  fail-open), `kata-harness` + `kata-harness-setup` skills (both `category: govern-publish`),
  self-contained `scripts/roll_core.py` (stdlib-only; MIT retained on the vendored
  `bring_core.py` functions — see its `NOTICE`), dist README with the sync line.
- **`.claude-plugin/marketplace.json`** — kata-harness entry registered; corpus claims
  99 skills/10 plugins → 101/11.
- **README.md** — headline + tagline counts, per-plugin table row (ROLL, 2 skills),
  cluster prose count, govern-publish cluster row, directory tree, version section.
- **llms.txt** — headline count, `## Plugins (11)` header + kata-harness bullet, clusters
  intro count, govern-publish roster (+2 skills).
- **marketplace.json + README version**: 1.4.4 → 1.5.0.

## 2026-07-11 — Marketplace renamed to `dojo-genesis` + publish-polish (v1.4.4)

### What happened

Renamed the marketplace **id** from `CoworkPluginsByDojoGenesis` to **`dojo-genesis`** before the public listing — the old id collided with Anthropic's Cowork product and didn't match the repo (`DojoGenesis/plugins`) or title. Installs are now `<plugin>@dojo-genesis`. Done now because renaming a marketplace id *after* it's listed breaks everyone's installs.

Scope note: only the marketplace **identity** changed (marketplace.json `name`, the CHANGELOG/STATUS/PORTABILITY titles, the lint-tool banner). The **local directory** `CoworkPluginsByDojoGenesis/` and the **GitHub repo** `DojoGenesis/plugins` are unchanged, so all script/hook references to the directory path stay as-is, and historical CHANGELOG entries keep their original wording.

### Changes

- **`.claude-plugin/marketplace.json`** `name`: `CoworkPluginsByDojoGenesis` → `dojo-genesis`.
- **README Quick Start**: replaced the stale "search + `.mcp.json`" block with the native flow — `/plugin marketplace add DojoGenesis/plugins` then `/plugin install <plugin>@dojo-genesis` — the exact path the `claude-plugins-community` audience uses.
- **README** "Each plugin is self-contained with…" corrected — only `skills/` is guaranteed (pretext-pdf has no plugin README; dojo-craft/bring-loop lack CONNECTORS/commands). Dead `llms.txt#clusters` fragment anchor dropped (doesn't resolve on GitHub plaintext).
- Identity references updated in STATUS.md, PORTABILITY.md, and the plugin-lint banner.
- **marketplace.json + README version**: 1.4.3 → 1.4.4.

### Deferred (non-blocking)

- `figma-to-code` / `design-system-selector` sit in `understand-codebase` with a flag that reads backwards; no cluster fits them cleanly, so left for a later taxonomy pass.
- `plugins/system-health/README.md` lists ~10 of its 20 skills (drift one level below the gated root faces).

## 2026-07-11 — Pre-publish review fixes (v1.4.3)

### What happened

An independent pre-publish review (different model) flagged three things that
would embarrass a public launch. All fixed; text-only, no structural change.

### Changes

- **`compression-ritual` Step 7 genericized** — the close-out step had hardcoded
  one private workspace's handoff mechanism (dead `handoffs/README.md` /
  `scripts/handoff-register.py` references, an issue-tracker label, a
  Mac↔Windows topology) into a skill anyone installs. Reworked 7a, the
  disposition table, scenario 3, an edge case, and the quality checklist to
  "use your workspace's own handoff/task mechanism" — the three-disposition
  design (hand off / next-step options / clean close) is unchanged.
- **Cluster-flag counts reconciled** — `README.md` `repo-docs-health` said
  "+3 dojo-craft dups" (truth: 2), `forge` said "+3 misfiled, +1 spans"
  (truth: 2 misfiled + 2 span); the Wave 2 CHANGELOG entry said "two MISFILED"
  then listed six. These are hand-carried annotations `face-parity` can't check.
- **Unverifiable claims removed, frontmatter example corrected** — dropped
  "all rated A+" (no skill carries a `quality:` field) and the unsourced
  "40-50% timeline reduction / 77 hours saved" tagline; rewrote the "How Skills
  Work" example and the llms.txt "Skill format" list to the real schema
  (`name` / `model` / `description` / `category` / `inputs` / `outputs`) — the
  old example showed `plugin` / `version` / `quality` / `triggers` fields that
  do not exist and omitted `category`, the field this release made lint-enforced.
- **marketplace.json + README version**: 1.4.2 → 1.4.3.

## 2026-07-11 — Cluster membership is metadata-only, never a physical move (v1.4.2)

### What happened

A Wave 4 was briefly implemented — physically moving `mcp-builder` and
`supply-chain-refresh` from `system-health` into `skill-forge` to match their
`forge` cluster — and then **reverted before it left this machine**, because
it is a breaking change: it renames `system-health:mcp-builder` →
`skill-forge:mcp-builder` (and the same for `supply-chain-refresh`), which
breaks every caller of the old invoke name. The forge-cluster grouping those
skills need is already fully carried by their `category: forge` metadata and
the cluster tables (added in Wave 2), so the move bought zero semantic value
at the cost of a real break. The two skills stay in `system-health`.

### The rule (now documented so it isn't re-attempted)

Cluster membership is a **lens**, expressed only through `category:` metadata
and the navigation tables — a `MISFILED` or `DUP` flag is descriptive, never a
to-do. Skills are never relocated between plugins to "fix" a cluster, because
the directory *is* the invoke name (`plugin:skill`). Recorded at the point of
temptation in `llms.txt` (`## Clusters` legend) and `README.md` (the cluster
section intro).

### Changes

- **`llms.txt`** + **`README.md`**: added the metadata-only / no-physical-move
  policy note beside the cluster flag legend.
- **marketplace.json + README version**: 1.4.1 → 1.4.2.

## 2026-07-11 — Wave 3: dedupe-in-place (v1.4.1)

### What happened

No renames, no moves — descriptions and pointers only. dojo-craft is
repositioned as the lean workbench (six single-file variants of flagship
skills elsewhere, plus two skills unique to it) rather than an undifferentiated
"practitioner's workbench," and every genuine near-duplicate pair surfaced by
the Wave 2 clustering pass now states its own boundary in its frontmatter
`description:` — the actual trigger surface skill dispatch reads, not just
the README table.

### Changes

- **`.claude-plugin/marketplace.json`**: dojo-craft's description rewritten
  to the lean-workbench framing, naming all six flagship pointers and the
  two unique skills.
- **`plugins/dojo-craft/README.md`**: rewritten — the skill table was
  showing only 4 of 8 skills and mis-named `community-claude-md-guardian` as
  `claude-md-guardian`; now lists all 8 with a "Full version" pointer column,
  and the "When to use" section covers all 8 instead of 4.
- **24 SKILL.md descriptions sharpened** with their twin's boundary + a
  "Full version: `plugin:skill`" pointer where applicable — the 6
  dojo-craft/flagship pairs (scout-writer/strategic-scout,
  convergence-checker/convergence-gate,
  community-claude-md-guardian/claude-md-guardian,
  codebase-viewer/codebase-cartography, memory-curator/memory-garden,
  seed-curator/seed-extraction), compression-ritual/session-compression,
  parallel-tracks/parallel-dispatch, web-research/web-research-external, the
  status trio (repo-status/status-template/status-writing), and the
  dispatch-shape trio (agent-dispatch-playbook/orchestration-pattern-selector/
  maestro-orchestration). All description edits verified single-line,
  under the 1024-char lint cap, no unrelated content touched.
- **marketplace.json + README version**: 1.4.0 → 1.4.1.

## 2026-07-11 — Wave 2: semantic cluster navigation layer (v1.4.0)

### What happened

Exposed 12 behavioral clusters that cross-cut the 10 plugins — a navigation
+ metadata layer on top of the existing plugin structure. No files moved.
Skills are grouped by what they *do* (scout-position, specify-commission,
dispatch-coordinate, remember-continue, seed-lifecycle, system-prompt-intel,
repo-docs-health, agent-telemetry, learn-research, understand-codebase,
forge, govern-publish), not just which plugin directory holds them —
surfacing dojo-craft's DUPs, six MISFILED skills (era-architecture,
adversarial-reviewer, figma-to-code, design-system-selector, mcp-builder,
supply-chain-refresh), and 3 skills whose function legitimately spans
plugins (skill-audit-upgrade, hooks-reference, voice-before-structure).

### Changes

- **`llms.txt`**: new `## Clusters` section — all 12 clusters with full
  `plugin:skill` membership, DUP/MISFILED/X flags. Community-skills note
  expanded (597 files, dormant-by-design).
- **`README.md`**: new "Find the Right Skill in 30 Seconds" cluster table +
  a twin-skill disambiguation table for the 11 genuine near-duplicate pairs
  (6 dojo-craft full-vs-lean pairs, compression-ritual/session-compression,
  parallel-tracks/parallel-dispatch, web-research/web-research-external, the
  status trio, the dispatch-shape trio). Community-skills dormant-by-design
  note added below the plugin table.
- **`category:` frontmatter rewrite (99 registered skills)**: every
  registered skill's `category:` now holds its cluster id instead of its
  plugin name, applied via a deterministic script (not hand-edits) with a
  built-in disk-vs-mapping cross-check. One placement judgment call:
  dojo-craft's `codebase-viewer` is filed under `understand-codebase` (its
  DUP target `codebase-cartography`'s cluster) rather than `repo-docs-health`
  (where the raw cluster spec listed it), per the spec's own
  DUP-target-cluster resolution rule; `semantic-clusters` and
  `repo-context-sync` (system-health) stay in `repo-docs-health`, their
  literal/home-plugin-dominant cluster.
- **`scripts/plugin-lint.py`**: new check enforces the 12-cluster
  `category:` vocabulary on all registered-plugin skills; community-skills
  stays exempt (it has no `category:` field at all — predates the taxonomy).
- **`scripts/face-parity.py`**: fixed a gate bug the Clusters section
  exposed — the llms.txt plugin-list-bullet regex scanned the *whole file*
  for `- **bold**` bullets instead of scoping to the `## Plugins` section,
  so it collided with the new cluster-id bullets. Scoped to the section body.
- **`plugins/community-skills/.claude-plugin/plugin.json`**: count 426 → 597
  (426 was the original Apr 6, 2026 security-audited batch; grown since via
  `supply-chain-refresh`), added the dormant-by-design framing.
- **marketplace.json + README version**: 1.3.1 → 1.4.0.

## 2026-07-11 — Wave 1: reconcile faces to disk truth (v1.3.1)

### What happened

The root README's per-plugin skill-count table had drifted from disk truth
without tripping `face-parity.py`, because that gate's corpus-scale sweep
exempts any number at or below the largest single plugin's count — exactly
the range a per-plugin table lives in. Four rows were stale (agent-orchestration
10→12, specification-driven-development 12→13, system-health 19→20,
wisdom-garden 13→14; table summed to ~94 against a correct 99 headline). The
Directory Structure diagram was worse: dojo-craft's 8 skills were mis-nested
under the `bring-loop/skills/` heading, one referenced a nonexistent
`claude-md-guardian` directory (actual: `community-claude-md-guardian`), and
most plugins' skill lists were partial (e.g. system-health showed 6 of 20).
STATUS.md was five months stale, still claiming 7 plugins / 44 skills / v1.1.0.

### Changes

- **`README.md`**: per-plugin table reconciled to disk truth (99 across 10
  plugins, verified per-row); Directory Structure diagram rewritten to list
  every plugin's actual skill set with correct nesting; version line → 1.3.1.
- **`STATUS.md`**: body replaced with a pointer stub (README.md +
  CHANGELOG.md + the two gate scripts) that carries no hardcoded counts of
  its own, so it cannot drift the way the previous dashboard did.
- **`scripts/face-parity.py`**: new check — README's per-plugin table rows
  are now validated against disk-computed per-plugin skill counts directly,
  closing the exemption gap that let this drift survive undetected. Stale
  `~599` comment corrected to the verified `597`. Checks renumbered 1–6.
- **`.claude-plugin/marketplace.json`**: version 1.3.0 → 1.3.1.

## 2026-07-11 — compression-ritual gains a session close-out (Step 7)

### What happened

The `wisdom-garden` `compression-ritual` skill now closes the session, not just the context. After compressing, **Step 7: Close Out the Session** resolves every open thread into one of three dispositions — **hand off** (write a `handoffs/YYYY-MM-DD_slug.md` wired to this workspace's real handoff contract + Linear), **offer next-step options** (a 2–4 item menu for the operator to pick), or **clean close** (an honest one-line recap + explicit "nothing left dangling"). The rule of the close is honesty: no manufactured next steps, no fake urgency.

### Changes

- **`plugins/wisdom-garden/skills/compression-ritual/SKILL.md`**: added Step 7 (disposition table + 7a handoff / 7b next-steps / 7c clean-close), extended Output / Examples (scenarios 3–5) / Edge Cases / Anti-Patterns / Quality Checklist; internal doc version 1.0 → 1.1.
- **`plugins/wisdom-garden/.claude-plugin/plugin.json`**: version 1.0.3 → 1.1.0.

## 2026-07-04 — bring-loop joins the marketplace

### What happened

Added **bring-loop** — the BringItCruz! effect, generalized: gate your outward loop (sends, decisions, closes, ships) the way your build loop is already gated. One action a day, surface + stage only (the human executes), a logged skip is a valid rep, streams measured separately, dual human/agent faces with a parity gate.

### Changes

- **`plugins/bring-loop/` added** (2 skills: `bring`, `bring-setup`; SessionStart injector + Stop nudge hooks; stdlib core `scripts/bring_core.py`; pattern spec `SPEC.md`). Distribution copy — canonical source is [github.com/DojoGenesis/bring-loop](https://github.com/DojoGenesis/bring-loop) (`plugin/`), sync from there.
- **marketplace.json**: 9 → 10 plugins, version 1.3.0, skill count corrected to the disk-true 99.
- **Count drift repaired across surfaces**: README header said 92/9, llms.txt said 84/8 (and was missing dojo-craft), marketplace said 97/9 — disk truth was 97 first-party skills pre-add. All three now read 99/10.

## 2026-02-12 — Naming Consolidation + Root Merge

### What happened

Resolved naming conflicts between root-level plugins, `claudeplugins/`, and `CoworkPluginsByDojoGenesis/`. Root-level naming conventions were adopted as canonical — shorter, more straightforward names preferred over longer suffixed variants.

### Changes

- **22 skill directories renamed** to root conventions (e.g., `agent-handoff-protocol` → `handoff-protocol`, `debugging-troubleshooting` → `debugging`, `release-specification` → `release-specification`)
- **`commands/` directories added** to all 7 original plugins from root-level source
- **`CONNECTORS.md` files added** to all 7 original plugins from root-level source
- **All internal references updated** (~140 cross-references across README.md, SKILL.md, and agent files)
- **`document-generation` plugin removed** — these are Anthropic platform capabilities, not Dojo Genesis skills
- **Root README.md, LICENSE, .gitignore added** for GitHub publish readiness

### Design Decision

Root naming conventions are more user-friendly. The longer COWORK suffixes (`-protocol`, `-ritual`, `-pattern`, `-scout`, `-workflow`) encoded useful metadata about skill *type*, but added friction to everyday use. The root names are what people actually type. Skill type is better communicated in the SKILL.md description, not the directory name.

---

## 2026-02-12 — Field Seeds Planted in Wisdom Garden

### What happened

The retrospective from the marketplace build sprint extracted 3 reusable seeds. These were planted into the `wisdom-garden` plugin's `seed-library` as **field seeds** — seeds derived from direct practice rather than research.

### Seeds Added

| Seed | Name | Pattern | Source |
|------|------|---------|--------|
| 11 | Voice Before Structure | Read design language before writing structural artifacts | Marketplace Build Sprint |
| 12 | Pointer Directories | Empty directories are references, not gaps | Marketplace Build Sprint |
| 13 | Granular Visibility | Progress tracking serves the user, not the agent | Marketplace Build Sprint |

### Files Created
- `wisdom-garden/skills/seed-library/seeds/11_voice_before_structure.md`
- `wisdom-garden/skills/seed-library/seeds/12_pointer_directories.md`
- `wisdom-garden/skills/seed-library/seeds/13_granular_visibility.md`

### Files Updated
- `wisdom-garden/skills/seed-library/SKILL.md` — Added field seeds to description, seed list, trigger keywords, seed IDs, and relationship map
- `wisdom-garden/skills/seed-library/references/seed_catalog.md` — Added field seeds section, new relationship category, 2 new usage patterns (Pattern 6: Ecosystem-Level Work, Pattern 7: Auditing/Reorganizing)
- `wisdom-garden/skills/seed-library/scripts/suggest_seeds.py` — Added trigger keywords for seeds 11-13

### Design Decision

The 3 seeds are categorized as "Field Seeds (From Practice)" to distinguish them from the 10 core seeds (from Dataiku Research). They carry `status: experimental` and `source: Marketplace Build Sprint`. This preserves the coherent origin story of the core seeds while welcoming new seeds from the field — which is exactly what the wisdom garden was designed to do.

---

## 2026-02-11 — Initial Marketplace Build + Improvement Seeds

### What happened

Two handoff documents were executed in sequence:

1. **Marketplace Reorganization** (`handoffs/marketplace-reorganization/01_marketplace_setup_handoff.md`)
2. **Plugin Improvement** (`handoffs/claudeplugins_improvement_handoff.md`)

---

### Phase 1: Marketplace Reorganization

Created `CoworkPluginsByDojoGenesis/` as a Claude Cowork plugin marketplace, organizing all 49 Dojo Genesis skills into 8 behavioral plugins.

**Structure created:**

| Plugin | Skills | Version | Behavioral Verb |
|--------|--------|---------|-----------------|
| strategic-thinking | 5 | 1.1.0 | STRATEGIZE |
| specification-driven-development | 10 | 1.1.0 | SPECIFY |
| wisdom-garden | 5 | 1.0.1 | REMEMBER |
| system-health | 8 | 1.0.1 | OBSERVE |
| continuous-learning | 8 | 1.0.1 | LEARN |
| agent-orchestration | 4 | 1.0.1 | ORCHESTRATE |
| skill-forge | 4 | 1.0.1 | BUILD |
| document-generation | 5 | 1.0.1 | GENERATE |

**Files created per plugin:**
- `.claude-plugin/plugin.json` — Plugin manifest with philosophy-grounded descriptions
- `README.md` — Plugin documentation with skill tables, trigger phrases, loop positioning
- `skills/[name]/` — Skill directories with SKILL.md files (copied from `dojo-genesis/skills/`)

**Root files created:**
- `.claude-plugin/marketplace.json` — Marketplace manifest linking all 8 plugins
- `CHANGELOG.md` — This file

**Philosophy grounding:** All manifest descriptions carry Dojo Genesis voice — growth language ("planted, cultivated, harvested"), nature metaphors, governance principles ("governance multiplies velocity"). Sourced from:
- `dojo-genesis/README.md`
- `dojo-genesis/docs/DojoGenesisDesignLanguage.md`
- `dojo-genesis/thinking/2026-02-03_manus_reading_being_peace.md`

---

### Phase 2: Improvement Seeds (from v0.2.x Retrospective)

Applied 5 ranked improvements from the retrospective to specific skills:

**A. Pre-Commission Alignment / Track 0 (Rank #1)**
- File: `specification-driven-development/skills/pre-implementation-checklist/SKILL.md`
- Change: Added Step 0 (Track 0) — sequential codebase verification phase before parallel execution
- Version: 1.0 → 1.1

**B. Codebase Audit Grounding (Rank #2)**
- File: `specification-driven-development/skills/release-specification/SKILL.md`
- Change: Added Step 1.5 (Current State Audit) with grep/find commands; specs describe deltas from measured reality
- Version: 2.0 → 2.1

**C. Scout → Spec Pipeline (Rank #3)**
- File: `strategic-thinking/skills/strategic-scout/SKILL.md`
- Change: Added Section VII — full pipeline: Scout → Spec → Prompts → Commission with persistent artifacts at each phase
- Version: 2.0 → 2.1

**D. Phased Parallelism (Rank #4)**
- File: `specification-driven-development/skills/parallel-tracks/SKILL.md`
- Change: Added Step 2.5 — organize tracks into Phase 0 (sequential foundation), Phase 1 (independent parallel), Phase 2 (integration)
- Version: 1.0 → 1.1

**E. Lean Spec Adaptation (Rank #6)**
- File: `specification-driven-development/skills/release-specification/SKILL.md`
- Change: Added decision point at workflow start — full template vs. lean "sonnet level chunks" format based on scope
- Version: (included in 2.1 bump above)

---

### Phase 3: Structural Improvements

**Trigger Phrases:** Updated 41 SKILL.md files with 3-5 specific trigger phrases per skill in YAML frontmatter descriptions. Phrases are things users would actually say (e.g., "scout this tension", "write a release spec", "audit this repo") rather than generic descriptions.

**Imperative Voice:** All skill descriptions now start with imperative verbs (Explore, Write, Verify, Split, Record, etc.) and use imperative voice throughout.

**Progressive Disclosure:** Audited all 41 SKILL.md word counts. Only `excel-generator` (3,349 words) marginally exceeds the 3,000-word threshold. No extraction to `references/` needed.

**Version Bumps:**
- `strategic-thinking` and `specification-driven-development` → 1.1.0 (substantive content changes)
- All other 6 plugins → 1.0.1 (description-only changes)

---

### Phase 4: Missing SKILL.md Files — Resolved

The 7 skill directories that lacked SKILL.md files in the `dojo-genesis/skills/` source were not missing content — they were **pointers**. The empty directories marked skills that belong to the ecosystem but whose content lives elsewhere:

**Platform skills (4):** `docx`, `pdf`, `pptx`, `xlsx` are Anthropic Cowork platform capabilities. Dojo Genesis references them as part of its behavioral architecture (GENERATE verb) but didn't author them. Content copied from the installed Cowork system skills.

**System-installed Dojo Genesis skills (3):** `specification-writer`, `zenflow-prompt-writer`, `project-exploration` were authored by the Dojo Genesis team but installed directly into the system skill directory (`.skills/skills/`) rather than stored in the `dojo-genesis/skills/` source. Content copied from the installed system skills.

| Plugin | Skill | Source | Trigger phrases added |
|--------|-------|--------|----------------------|
| document-generation | docx | Cowork platform | Already included in platform description |
| document-generation | pdf | Cowork platform | Already included in platform description |
| document-generation | pptx | Cowork platform | Already included in platform description |
| document-generation | xlsx | Cowork platform | Already included in platform description |
| specification-driven-development | specification-writer | System-installed DG skill | Yes — 'write a spec', 'spec this feature', etc. |
| specification-driven-development | zenflow-prompt-writer | System-installed DG skill | Yes — 'commission Zenflow', 'turn this spec into a prompt', etc. |
| continuous-learning | project-exploration | System-installed DG skill | Yes — 'explore this project', 'assess this codebase', etc. |

**Note:** `project-exploration` also contained a binary `SKILL.skill` artifact from the source. This is superseded by the proper SKILL.md but could not be removed due to filesystem restrictions. It is harmless — Cowork reads SKILL.md exclusively.

---

### What was NOT changed

- **Original `claudeplugins/` directory** — Left untouched. The marketplace is a parallel structure, not a replacement.
- **Original `dojo-genesis/skills/` directory** — Source skills preserved. Marketplace copies are independent.
- **Improvement F (Rank #7, Compression Protocol)** from the improvement handoff — Deferred per priority order.

---

### Final Verification Results

- 49/49 skill directories present
- 49/49 SKILL.md files present (100% coverage)
- 8/8 plugin.json files valid JSON
- 1/1 marketplace.json valid JSON
- 8/8 README.md files created
- 8/8 plugins match marketplace.json registry
