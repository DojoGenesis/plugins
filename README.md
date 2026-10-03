# Dojo Genesis: protocol suite and plugins for Claude Code

**Give your agents genius-level protocol.**

Plugins and mods for Claude Code that put the right model on each job, keep context small, and don't call work done until a check passes.

Genius-level protocol and inexpensive inference go together. Claude Code without protocol is messy, costly and inaccurate: every subagent quietly inherits your most expensive model, files get read whole, and "done" gets written before anything ran. Each plugin here makes one of those things stop being true by a mechanism (a hook, a pinned agent, a workflow, a report), not by advice alone.

---

## Install

```
/plugin marketplace add DojoGenesis/plugins
/plugin install dojo-suite@dojo-genesis
```

Or pick one at a time, e.g. `/plugin install dojo-gates@dojo-genesis`.

`dojo-suite` installs the eight plugins below and adds nothing of its own: no skills, agents, commands or hooks, so it adds no always-on weight. The marketplace id is `dojo-genesis`; the source repo is `DojoGenesis/plugins`.

**Mods are early access.** Enable function hooks with `export CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` (or add it under `env` in `~/.claude/settings.json`), then install dojo-meter. The classic hooks, skills, agents and commands in every plugin work without that flag; the mods add the live band, status and routing that only the engine can do.

---

## The suite

<!-- suite-table:begin -->
| Plugin | Job | Skills | Also ships | Tier |
|--------|-----|--------|------------|------|
| [dojo-suite](plugins/dojo-suite/) | All eight Dojo suite plugins in one install: protocol, gates, router, meter, verify, flow, doctor and settle. Adds no skills, agents or hooks of its own. | 0 | 8 dependencies | bundle |
| [dojo-protocol](plugins/dojo-protocol/) | The Dojo Protocol for Claude Code: ten rules at session start, a scout→contract→build→verify spine, and role agents pinned to the right model. | 5 | 4 agents, 1 hook | classic |
| [dojo-gates](plugins/dojo-gates/) | Deterministic guards for the mistakes that waste a day: blanket staging, rewriting pushed commits, printing secrets, oversized reads, silent probes. | 1 | 10 guards | classic |
| [dojo-router](plugins/dojo-router/) | No subagent silently inherits your most expensive model. Warns or blocks unpinned dispatches; the mod routes them by role. | 1 | 2 hooks | classic + mod (early access) |
| [dojo-meter](plugins/dojo-meter/) | See what each turn, agent and model costs, and how big your context is: a cost report from your transcripts, and a live band with the mod. | 0 | 2 commands | classic + mod (early access) |
| [dojo-verify](plugins/dojo-verify/) | "Done" means a check ran and passed in this session. Flags claims of success with no evidence behind them. | 1 | 1 hook | classic + mod (early access) |
| [dojo-flow](plugins/dojo-flow/) | Parallel builds that stay independent: a contract gate, scouts on small models, builders in the middle, judges at the ends, and a scorecard that counts returns. | 1 | 2 commands, 2 workflows | workflows |
| [dojo-doctor](plugins/dojo-doctor/) | Find the hooks and settings that fail or cost you silently: broken interpreters, noisy injections, always-on token weight, flags that are off. | 1 | 1 command | classic |
| [dojo-settle](plugins/dojo-settle/) | Settle claims with evidence: pre-registered experiments, with/without baselines and decision gates before anything becomes a number. | 3 | none | classic |
<!-- suite-table:end -->

Tiers: **classic** means hooks, skills, agents, commands and scripts that work on any account. **classic + mod** adds a function-hook mod (early access), which is a `hooks/register.ts` file; the plugin's core value works with it off. **workflows** means Claude Code workflow scripts. **bundle** means the plugin only lists dependencies.

Every hook checks the same kill switches, in order: `DOJO_OFF=1` turns off the whole suite, and `DOJO_<PLUGIN>_OFF=1` turns off one plugin (for example `DOJO_GATES_OFF=1`). Multi-guard plugins also take `DOJO_<PLUGIN>_SKIP=<id>,<id>`.

The ten rules behind the suite are in [dojo-protocol/PROTOCOL.md](plugins/dojo-protocol/PROTOCOL.md); that file is the only copy. The method page at [dojogenesis.com/method](https://dojogenesis.com/method) pairs each rule with the plugin that enforces it.

### What is measured, and what is not

The counts in this README, and the always-on description weight of each plugin, are generated from the files on disk; `scripts/face-parity.py` fails if this README, `llms.txt` or `marketplace.json` drift from them, and the figures are published with their method and date at [dojogenesis.com/proof](https://dojogenesis.com/proof). Whether the protocol changes your results, with and without it, is not yet measured: `dojo-settle` ships eval scaffolds and a way to pre-register a bet, and nobody has run them in this release. Everything was tested with Claude Code 2.1.286.

---

## Library

The practice skills that were here before the suite, kept as they were. Nothing was removed from them: the same `plugin:skill` names work. Install any of them as `<plugin>@dojo-genesis`, for example `/plugin install strategic-thinking@dojo-genesis`.

9 library plugins and 97 library skills. Skills are structured scaffolds for strategy, specs, orchestration, review and memory; they guide an agent through a decision rather than documenting it.

| Plugin | Verb | Skills | What it does |
|--------|------|--------|--------------|
| [strategic-thinking](plugins/strategic-thinking/) | STRATEGIZE | 6 | Scout tensions before committing: product positioning, iterative scouting, multi-surface strategy, adversarial review, strategic-to-tactical workflow. |
| [specification-driven-development](plugins/specification-driven-development/) | SPECIFY | 13 | Spec writing grounded in codebase reality: release specs, parallel tracks, frontend-from-backend, implementation prompts, pre-commission alignment. |
| [agent-orchestration](plugins/agent-orchestration/) | ORCHESTRATE | 12 | Multi-agent coordination: parallel dispatch, delegation playbooks, handoff protocols, decision propagation. Handoffs are sacred relays, not tosses over the wall. |
| [continuous-learning](plugins/continuous-learning/) | LEARN | 13 | Research modes (deep/wide/web), project exploration, synthesis, retrospectives, era architecture, codebase cartography, TLDR code analysis. |
| [skill-forge](plugins/skill-forge/) | BUILD | 9 | The meta-layer — skills about making skills. Create, maintain, audit, batch-normalize community skills, build MCP servers. |
| [system-health](plugins/system-health/) | OBSERVE | 20 | Audit repository health: documentation audit, health audit, observability dashboard, repo status, semantic clusters, supply chain refresh, budget guard. |
| [wisdom-garden](plugins/wisdom-garden/) | REMEMBER | 14 | Compress session context into lasting memory: compression ritual, memory garden, seed extraction, system prompt archaeology, session continuity ledger. |
| [pretext-pdf](plugins/pretext-pdf/) | PUBLISH | 2 | Export structured documents to print-quality PDF using the Pretext layout engine. Zero-reflow typography, adaptive pagination, auto table of contents. |
| [dojo-craft](plugins/dojo-craft/) | CRAFT | 8 | The practitioner's workbench — strategic thinking, codebase intelligence, memory curation, and project governance as composable workflows. |

## Companions

Two small plugins that gate the outward loop (sends, decisions, closes) the way the suite gates the build loop. They share one `bring/` queue and are independent of the suite.

| Plugin | Verb | Skills | What it does |
|--------|------|--------|--------------|
| [bring-loop](plugins/bring-loop/) | BRING | 2 | Gate your outward loop like your build loop: one send/decision/close a day, staged by the agent, executed by you, measured in honest separate streams. |
| [kata-harness](plugins/kata-harness/) | ROLL | 2 | Roll the bring queue one tick at a time: bounded, self-terminating sessions (reps or minutes) over the same `bring/` queue — one bring surfaced per tick, staged by the agent, executed by you. Rolling forward is not failure. |

---

## Find the Right Skill in 30 Seconds

Plugins are how skills ship; **clusters are how they behave.** 12 clusters
cross-cut the library, companion and suite plugins — skills grouped by what
they *do*, not which directory holds them. Every registered skill's `category:` frontmatter is
one of these 12 ids (enforced by `scripts/plugin-lint.py`); see the full
`plugin:skill` roster with DUP/MISFILED/X flags in [llms.txt](llms.txt).

A cluster is a *lens*, not a filing system: membership lives in a skill's
`category:` metadata, and skills are **never** physically moved between plugins
to match a cluster — that would change the `plugin:skill` invoke name and break
callers. The `misfiled`/`dup` notes below are descriptive, not a to-do list.

| Cluster | Use when you need to... | Home plugin(s) |
|---|---|---|
| **scout-position** | map a decision landscape before committing | strategic-thinking (+1 dojo-craft dup), dojo-protocol |
| **specify-commission** | turn a decision into a spec and agent-ready prompts | specification-driven-development (+1 misfiled), dojo-protocol |
| **dispatch-coordinate** | plan or run multi-agent parallel work, hand off cleanly | agent-orchestration, dojo-protocol, dojo-router, dojo-flow |
| **remember-continue** | capture an insight or wrap up a session into memory | wisdom-garden (+1 dojo-craft dup) |
| **seed-lifecycle** | extract, catalog, or elevate a reusable pattern | wisdom-garden (+1 dojo-craft dup) |
| **system-prompt-intel** | ingest or reverse-engineer another agent's system prompt | wisdom-garden |
| **repo-docs-health** | audit a repo's health, docs, or CLAUDE.md hierarchy | system-health (+2 dojo-craft dups, +1 misfiled), dojo-protocol |
| **agent-telemetry** | watch agent cost, behavior, or tool-call traces | system-health, dojo-doctor |
| **learn-research** | research a question or retro a sprint | continuous-learning, dojo-settle |
| **understand-codebase** | get oriented in an unfamiliar codebase | continuous-learning (+1 dojo-craft dup) |
| **forge** | build, maintain, or normalize a skill or MCP server | skill-forge (+2 misfiled, +2 span from other plugins) |
| **govern-publish** | record a decision, scaffold a project, export a PDF, gate an outward send, run a bounded roll, guard a tool call, check evidence | dojo-craft, pretext-pdf, bring-loop, kata-harness, dojo-gates, dojo-verify, dojo-settle |

### Twin Skills — Which One Do I Want?

The clustering pass surfaced genuine near-duplicates. Same intent, different
weight or angle — here's the boundary for each:

| Pair | Boundary |
|---|---|
| `strategic-thinking:strategic-scout` vs `dojo-craft:scout-writer` | Same output shape (tension → routes → recommendation). strategic-scout is the flagship, wired into the full scout→spec→prompts→commission pipeline; scout-writer is the single-file lean variant for a fast, self-contained scout with no pipeline scaffolding. |
| `system-health:convergence-gate` vs `dojo-craft:convergence-checker` | convergence-checker is a quick RED/YELLOW/GREEN triage (dirty files, sessions, open items). convergence-gate is the full structured 7-phase remediation *session* you run once the checker (or the drift detector) fires. Checker diagnoses; gate treats. |
| `system-health:claude-md-guardian` vs `dojo-craft:community-claude-md-guardian` | Both audit CLAUDE.md for conflicts and staleness. claude-md-guardian can additionally install a PreToolUse hook to *enforce* the ruleset going forward; community-claude-md-guardian is the audit-report-only lean variant with no enforcement mechanism. |
| `continuous-learning:codebase-cartography` vs `dojo-craft:codebase-viewer` | Near-identical output (directory roles, entry points, dependency graph, "here be dragons"). codebase-cartography is canonical (adds a defined reading-order output); codebase-viewer is the lean single-file variant for use inside dojo-craft's self-contained workbench. |
| `wisdom-garden:memory-garden` vs `dojo-craft:memory-curator` | memory-garden *writes* one new structured entry (daily/curated/archive tier) from a conversation insight. memory-curator *maintains* the existing index — prune, dedupe, search, keep MEMORY.md under 200 lines. Garden plants; curator tends. |
| `wisdom-garden:seed-extraction` vs `dojo-craft:seed-curator` | seed-extraction produces one seed file (trigger + evidence + application) from an experience. seed-curator bundles the fuller lifecycle — plant, harvest, search, elevate to skill — in dojo-craft's single-file style. |
| `wisdom-garden:compression-ritual` vs `wisdom-garden:session-compression` | session-compression is the routine end-of-session wrap-up (decisions, changes, context into the memory garden). compression-ritual is the heavier treatment for a long conversation — multiple artifact types plus a dated compression log. |
| `specification-driven-development:parallel-tracks` vs `agent-orchestration:parallel-dispatch` | parallel-tracks *plans* the split — phased structure, track specs, integration contracts, wiring gate — before any agent runs. parallel-dispatch *executes* it — actually dispatches the agents with file manifests and independent verification. Spec-side vs execution-side of the same split. |
| `continuous-learning:web-research` vs `continuous-learning:web-research-external` | web-research is general fact-finding/verification via Brave Search + web_fetch, output as a Research Summary. web-research-external is scoped to library/API/framework lookups, output as an implementation-ready handoff. |
| `system-health:repo-status` vs `status-template` vs `status-writing` | repo-status is the first full snapshot of an unfamiliar repo (exploration-heavy: filesystem + clusters + importance ranking). status-template is the formal 10-section schema itself, when you want that exact structure. status-writing is the routine "update our STATUS.md" once the document already exists. |
| `agent-orchestration:agent-dispatch-playbook` vs `orchestration-pattern-selector` vs `maestro-orchestration` | orchestration-pattern-selector decides *which* orchestration pattern fits, via an 11-signal matrix — use it first when unsure. agent-dispatch-playbook plans the mechanics (isolation, count, sequencing, models) once you know you're doing a parallel dispatch. maestro-orchestration *is* one specific pattern — a single conductor decomposing and dispatching to specialists — invoke it directly when that shape is already the right fit. |

---

## Directory Structure

```
plugins/
├── dojo-suite/                   plugin.json only: depends on the eight plugins below
├── dojo-protocol/                skills, agents, hooks, output style, evals, PROTOCOL.md
├── dojo-gates/                   skills, hooks (the guards), evals
├── dojo-router/                  skills, hooks, mod (hooks/register.ts)
├── dojo-meter/                   commands, scripts, mod (hooks/register.ts)
├── dojo-verify/                  skills, hooks, mod (hooks/register.ts)
├── dojo-flow/                    skills, commands, workflows, scripts
├── dojo-doctor/                  skills, commands, scripts
├── dojo-settle/                  skills, scripts, templates
├── agent-orchestration/
│   ├── README.md
│   ├── CONNECTORS.md
│   ├── agents/
│   ├── commands/
│   ├── hooks/
│   └── skills/                   (12)
│       ├── agent-dispatch-playbook/SKILL.md
│       ├── agent-teaching/SKILL.md
│       ├── async-agent-dispatch/SKILL.md
│       ├── audit-sweep-dispatch/SKILL.md
│       ├── decision-propagation/SKILL.md
│       ├── granular-visibility/SKILL.md
│       ├── handoff-protocol/SKILL.md
│       ├── maestro-orchestration/SKILL.md
│       ├── orchestration-pattern-selector/SKILL.md
│       ├── parallel-dispatch/SKILL.md
│       ├── workflow-router/SKILL.md
│       └── workspace-navigation/SKILL.md
├── continuous-learning/skills/   (13) — codebase-cartography, debugging, design-system-selector,
│                                      era-architecture, figma-to-code, patient-learning-protocol,
│                                      project-exploration, research-modes, research-synthesis,
│                                      retrospective, tldr-code-analysis, web-research, web-research-external
├── skill-forge/skills/           (9)  — batch-normalize-and-package, file-management, mcp-cloudflare-builder,
│                                      mcp-server-builder, normalize-community-skill, process-extraction,
│                                      scan-community-repos, skill-creation, skill-maintenance
├── specification-driven-development/skills/  (13) — codebase-audit-grounding, context-ingestion,
│                                      frontend-from-backend, gap-audit-then-fix, implementation-prompt,
│                                      parallel-tracks, planning-with-files, pre-commission-alignment,
│                                      pre-implementation-checklist, release-specification,
│                                      spec-constellation-to-prompt-suite, specification-writer, zenflow-prompt-writer
├── strategic-thinking/skills/    (6)  — adversarial-reviewer, iterative-scouting, multi-surface-strategy,
│                                      product-positioning, strategic-scout, strategic-to-tactical-workflow
├── system-health/skills/         (20) — agent-performance-report, budget-guard, build-sweep, claude-md-guardian,
│                                      convergence-gate, documentation-audit, health-audit, hooks-reference,
│                                      mcp-builder, observability-dashboard, observability-dashboard-spec,
│                                      pointer-directories, repo-context-sync, repo-status, semantic-clusters,
│                                      skill-audit-upgrade, status-template, status-writing, supply-chain-refresh,
│                                      tool-intercept-logger
├── wisdom-garden/skills/         (14) — analyze-agent-behavior, build-intelligence-map, compression-ritual,
│                                      continuity-ledger, ingest-system-prompt, memory-garden, reflect-and-learn,
│                                      seed-extraction, seed-library, seed-to-skill-converter, session-compression,
│                                      session-lifecycle-automation, system-prompt-archaeology, voice-before-structure
├── pretext-pdf/skills/           (2)
│   ├── pdf-export/SKILL.md
│   └── pdf-typography/SKILL.md
├── dojo-craft/skills/            (8)  — the lean workbench: single-file variants of six flagship skills
│                                      (scout-writer, convergence-checker, community-claude-md-guardian,
│                                      codebase-viewer, memory-curator, seed-curator) plus two unique skills
│                                      (adr-writer, project-scaffolder)
├── bring-loop/skills/            (2)
│   ├── bring/SKILL.md
│   └── bring-setup/SKILL.md
├── kata-harness/skills/          (2)
│   ├── kata-harness/SKILL.md
│   └── kata-harness-setup/SKILL.md
```

Each plugin is a directory under `plugins/`. Only `skills/` is guaranteed; the rest are present where relevant:
- `skills/` — Full workflow definitions (SKILL.md files) — **always present**
- `README.md` — Overview, philosophy, skill table, trigger phrases
- `CONNECTORS.md` — External service integrations (MCPs, APIs, data sources)
- `agents/` — Agent persona definitions for specialized work
- `commands/` — Claude Code slash command definitions

---

## How Skills Work

Each skill is a `SKILL.md` file with YAML frontmatter:

```yaml
---
name: release-specification
model: opus            # sonnet for parsing/bulk, opus for architecture
description: Produces a release specification grounded in codebase reality. Use when "write a release spec" or "create a specification for vX.X.X".
category: specify-commission   # one of 12 cluster ids (enforced by scripts/plugin-lint.py)
inputs:
  - name: release_context
    type: string
    description: What the release should accomplish (version, goals, scope)
    required: true
outputs:
  - name: release_spec
    type: ref
    format: cas-ref
    description: The release specification document
---

# Release Specification

[Full workflow steps as markdown...]
```

Skills are **active cognitive scaffolds** — structured methodologies that guide AI agents through complex decisions, not passive documentation. They use progressive disclosure: a quick trigger gets you started, the full SKILL.md provides the complete workflow when needed.

---

## Key Commands

```bash
# List all skills by plugin
dojo list-skills

# Search skills by keyword
dojo search-skills "specification"

# Invoke a skill directly
/specification-driven-development:release-specification

# Fastest path to value
/strategic-thinking:scout                              # Facing a decision with no obvious answer
/specification-driven-development:release-specification # Before commissioning autonomous agents
/continuous-learning:retrospective                     # After every major release
/wisdom-garden:compression-ritual                      # End of long sessions
/system-health:health-audit                            # When codebases feel brittle
```

---

## Use Cases

**Strategic work**
- Decision with no obvious answer → `/strategic-thinking:scout`
- Product strategy across desktop, mobile, web → `/strategic-thinking:multi-surface-strategy`
- Stress-test a plan → `/strategic-thinking:adversarial-reviewer`

**Specification and planning**
- Release spec for autonomous agents → `/specification-driven-development:release-specification`
- Frontend spec from existing backend → `/specification-driven-development:frontend-from-backend`
- Split project into parallel agent tracks → `/specification-driven-development:parallel-tracks`
- Verify spec is ready for handoff → `/specification-driven-development:pre-implementation-checklist`

**Memory and context**
- Long conversation getting unwieldy → `/wisdom-garden:compression-ritual`
- Capture a learning for future reference → `/wisdom-garden:memory-garden`
- Formalize a repeated workflow → `/wisdom-garden:seed-extraction` → `/skill-forge:skill-creation`

**System health**
- New codebase, need to understand it → `/system-health:repo-status` + `/system-health:semantic-clusters`
- Documentation feels stale → `/system-health:documentation-audit`
- Full health audit before major work → `/system-health:health-audit`

**Learning and debugging**
- Systematic diagnosis → `/continuous-learning:debugging`
- Research a decision → `/continuous-learning:research-modes`
- Post-sprint reflection → `/continuous-learning:retrospective`

**Agent coordination**
- Handoff work between agents → `/agent-orchestration:handoff-protocol`
- Parallel agent dispatch → `/agent-orchestration:parallel-dispatch`
- Decision propagation through docs → `/agent-orchestration:decision-propagation`

---

## Requirements

- Claude Code. The suite was tested with 2.1.286; the mods need function hooks enabled (early access), nothing else does
- Dojo MCP Server, optional, for `dojo.*` tool access to the library: [DojoGenesis/mcp](https://github.com/DojoGenesis/mcp)
- No additional dependencies. Skills are markdown; the suite's hooks and scripts use the Python 3 standard library only and run on the macOS system Python 3.9

---

## Version

**2.0.0** — the Dojo protocol suite (eight plugins and the `dojo-suite` install bundle) listed first, then the library and the companions. 114 first-party skills across 20 plugins, with 12 semantic clusters as metadata; no library plugin was removed, and cluster membership never moves a skill between plugins (invoke-name stability). Counts here are checked against disk by `scripts/face-parity.py`.

Semantic versioning:
- **Patch** (x.x.1): typo fixes, minor clarifications
- **Minor** (x.1.0): new skills or plugins, backward-compatible
- **Major** (2.0.0): a new top-level shape, such as the suite becoming the front door

See [CHANGELOG.md](CHANGELOG.md) for full history.

---

## Related

- [DojoGenesis/mcp](https://github.com/DojoGenesis/mcp) — Dojo MCP Server (skill discovery, invocation, logging)
- [DojoGenesis/cli](https://github.com/DojoGenesis/cli) — Dojo CLI (plugin install, gateway bridge, `--json` one-shot)
- [DojoGenesis/gateway](https://github.com/DojoGenesis/gateway) — Agentic Gateway (skill routing, CAS, OAuth2)
- [PORTABILITY.md](PORTABILITY.md) — How to use these skills outside Claude Code

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

Built by Dojo Genesis at TresPies LLC. Every skill here exists because we needed it. And then needed it again.
