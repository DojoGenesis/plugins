# DojoGenesis Plugins

**101 first-party methodology skills across 11 behavioral plugins for Claude Code and the Dojo platform.**

AI agents are powerful but chaotic. They hallucinate requirements, forget context between sessions, skip verification, and produce work that needs rework. The problem isn't intelligence — it's discipline. These plugins encode the discipline: battle-tested workflows from actually shipping software with autonomous agents.

**101 first-party methodology skills across 11 behavioral plugins — structured scaffolds for strategy, specs, orchestration, review, and memory.**

---

## Quick Start

### Install via Dojo CLI

```bash
dojo plugin install DojoGenesis/plugins
```

### Install via Claude Code Marketplace (native)

```
/plugin marketplace add DojoGenesis/plugins
/plugin install wisdom-garden@dojo-genesis
```

The marketplace id is `dojo-genesis`; the source repo is `DojoGenesis/plugins`. Install any plugin as `<plugin>@dojo-genesis` (e.g. `strategic-thinking@dojo-genesis`, `system-health@dojo-genesis`).

### Invoke a skill

Once installed, invoke any skill by name:

```
/strategic-thinking:scout
/specification-driven-development:release-specification
/wisdom-garden:compression-ritual
/system-health:health-audit
```

Or via the Dojo MCP tools: `dojo.list_skills`, `dojo.search_skills`, `dojo.invoke_skill`.

---

## Plugins

| Plugin | Verb | Skills | What it does |
|--------|------|--------|--------------|
| [agent-orchestration](plugins/agent-orchestration/) | ORCHESTRATE | 12 | Multi-agent coordination: parallel dispatch, delegation playbooks, handoff protocols, decision propagation. Handoffs are sacred relays, not tosses over the wall. |
| [continuous-learning](plugins/continuous-learning/) | LEARN | 13 | Research modes (deep/wide/web), project exploration, synthesis, retrospectives, era architecture, codebase cartography, TLDR code analysis. |
| [skill-forge](plugins/skill-forge/) | BUILD | 9 | The meta-layer — skills about making skills. Create, maintain, audit, batch-normalize community skills, build MCP servers. |
| [specification-driven-development](plugins/specification-driven-development/) | SPECIFY | 13 | Spec writing grounded in codebase reality: release specs, parallel tracks, frontend-from-backend, implementation prompts, pre-commission alignment. |
| [strategic-thinking](plugins/strategic-thinking/) | STRATEGIZE | 6 | Scout tensions before committing: product positioning, iterative scouting, multi-surface strategy, adversarial review, strategic-to-tactical workflow. |
| [system-health](plugins/system-health/) | OBSERVE | 20 | Audit ecosystem health: documentation audit, health audit, observability dashboard, repo status, semantic clusters, supply chain refresh, budget guard. |
| [wisdom-garden](plugins/wisdom-garden/) | REMEMBER | 14 | Compress session context into lasting memory: compression ritual, memory garden, seed extraction, system prompt archaeology, session continuity ledger. |
| [pretext-pdf](plugins/pretext-pdf/) | PUBLISH | 2 | Export structured documents to print-quality PDF using the Pretext layout engine. Zero-reflow typography, adaptive pagination, auto table of contents. |
| [dojo-craft](plugins/dojo-craft/) | CRAFT | 8 | The practitioner's workbench — strategic thinking, codebase intelligence, memory curation, and project governance as composable workflows. |
| [bring-loop](plugins/bring-loop/) | BRING | 2 | Gate your outward loop like your build loop: one send/decision/close a day, staged by the agent, executed by you, measured in honest separate streams. The BringItCruz! effect, generalized. |
| [kata-harness](plugins/kata-harness/) | ROLL | 2 | Roll the bring queue one tick at a time: bounded, self-terminating sessions (reps or minutes) over the same `bring/` queue — one bring surfaced per tick, staged by the agent, executed by you. Rolling forward is not failure. |

**Not in the table above:** [`plugins/community-skills/`](plugins/community-skills/)
holds 597 harvested SKILL.md files. Dormant-by-design: not a
marketplace-registered plugin, a supply — promoted individually into the
plugins above once proven, never installed wholesale.

---

## Find the Right Skill in 30 Seconds

Plugins are how skills ship; **clusters are how they behave.** 12 clusters
cross-cut the 11 plugins — skills grouped by what they *do*, not which
directory holds them. Every registered skill's `category:` frontmatter is
one of these 12 ids (enforced by `scripts/plugin-lint.py`); see the full
`plugin:skill` roster with DUP/MISFILED/X flags in [llms.txt](llms.txt).

A cluster is a *lens*, not a filing system: membership lives in a skill's
`category:` metadata, and skills are **never** physically moved between plugins
to match a cluster — that would change the `plugin:skill` invoke name and break
callers. The `misfiled`/`dup` notes below are descriptive, not a to-do list.

| Cluster | Use when you need to... | Home plugin(s) |
|---|---|---|
| **scout-position** | map a decision landscape before committing | strategic-thinking (+1 dojo-craft dup) |
| **specify-commission** | turn a decision into a spec and agent-ready prompts | specification-driven-development (+1 misfiled) |
| **dispatch-coordinate** | plan or run multi-agent parallel work, hand off cleanly | agent-orchestration |
| **remember-continue** | capture an insight or wrap up a session into memory | wisdom-garden (+1 dojo-craft dup) |
| **seed-lifecycle** | extract, catalog, or elevate a reusable pattern | wisdom-garden (+1 dojo-craft dup) |
| **system-prompt-intel** | ingest or reverse-engineer another agent's system prompt | wisdom-garden |
| **repo-docs-health** | audit a repo's health, docs, or CLAUDE.md hierarchy | system-health (+2 dojo-craft dups, +1 misfiled) |
| **agent-telemetry** | watch agent cost, behavior, or tool-call traces | system-health |
| **learn-research** | research a question or retro a sprint | continuous-learning |
| **understand-codebase** | get oriented in an unfamiliar codebase | continuous-learning (+1 dojo-craft dup) |
| **forge** | build, maintain, or normalize a skill or MCP server | skill-forge (+2 misfiled, +2 span from other plugins) |
| **govern-publish** | record a decision, scaffold a project, export a PDF, gate an outward send, run a bounded roll | dojo-craft, pretext-pdf, bring-loop, kata-harness |

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
└── community-skills/             ← community-contributed SKILL.md files, dormant-by-design
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

- Claude Code (any version) or Dojo CLI
- Dojo MCP Server for full `dojo.*` tool access: [DojoGenesis/mcp](https://github.com/DojoGenesis/mcp)
- No additional dependencies — all skills are pure markdown

---

## Version

**1.5.0** — 101 first-party skills organized into 12 semantic clusters, published as the `dojo-genesis` marketplace. Cluster membership is metadata-only; skills are never moved between plugins (invoke-name stability).

Semantic versioning:
- **Patch** (1.x.x): typo fixes, minor clarifications
- **Minor** (x.x.0): new skills, enhanced workflows, backward-compatible
- **Major** (x.0.0): breaking changes, major restructuring

See [CHANGELOG.md](CHANGELOG.md) for full history.

---

## Related

- [DojoGenesis/mcp](https://github.com/DojoGenesis/mcp) — Dojo MCP Server (skill discovery, invocation, logging)
- [DojoGenesis/cli](https://github.com/DojoGenesis/cli) — Dojo CLI (plugin install, gateway bridge, `--json` one-shot)
- [DojoGenesis/gateway](https://github.com/DojoGenesis/gateway) — Agentic Gateway (skill routing, CAS, OAuth2)
- [PORTABILITY.md](PORTABILITY.md) — How to use these skills outside the Dojo platform

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

Built by Dojo Genesis at Tres Pies Design. Every skill here exists because we needed it. And then needed it again.
