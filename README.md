# DojoGenesis Plugins

**99 first-party methodology skills across 10 behavioral plugins for Claude Code and the Dojo platform.**

AI agents are powerful but chaotic. They hallucinate requirements, forget context between sessions, skip verification, and produce work that needs rework. The problem isn't intelligence — it's discipline. These plugins encode the discipline: battle-tested workflows from actually shipping software with autonomous agents.

**99 skills. 40-50% timeline reduction. 77 hours saved through pre-flight verification alone.**

---

## Quick Start

### Install via Dojo CLI

```bash
dojo plugin install DojoGenesis/plugins
```

### Install via Claude Code Marketplace

Search for **"DojoGenesis Plugins"** in the Claude Code plugin marketplace, or add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "dojo": {
      "command": "dojo",
      "args": ["mcp", "--skills-path", "/path/to/plugins"]
    }
  }
}
```

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
└── community-skills/             ← community-contributed SKILL.md files, dormant-by-design
```

Each plugin is self-contained with:
- `README.md` — Overview, philosophy, skill table, trigger phrases
- `CONNECTORS.md` — External service integrations (MCPs, APIs, data sources)
- `agents/` — Agent persona definitions for specialized work
- `commands/` — Claude Code slash command definitions
- `skills/` — Full workflow definitions (SKILL.md files)

---

## How Skills Work

Each skill is a `SKILL.md` file with YAML frontmatter:

```yaml
---
name: release-specification
plugin: specification-driven-development
version: 2.1.0
quality: A+
description: Write release specs grounded in codebase reality
model: sonnet          # sonnet for parsing/bulk, opus for architecture
triggers:
  - "write a spec for"
  - "release specification"
  - "before commissioning agents"
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

**1.3.1** — 99 first-party skills, all rated A+.

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
