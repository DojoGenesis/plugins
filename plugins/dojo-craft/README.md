# DojoCraft

_The lean workbench — single-file variants of six flagship skills, plus two unique skills._

## What it does

DojoCraft is the practitioner's lean workbench. Six of its eight skills are
single-file variants of flagship skills that live in other plugins — same
intent and output shape, no pipeline scaffolding, reach for these when you
want the result fast and self-contained. The other two — `adr-writer` and
`project-scaffolder` — are unique to DojoCraft; there is no flagship
elsewhere for them.

Use DojoCraft when you need to **decide well**, **document clearly**,
**keep configuration honest**, and **stay out of drift**, without pulling in
a whole plugin's worth of pipeline for a single-shot task.

## Skills

| Skill | Trigger | Description | Full version |
|-------|---------|-------------|--------------|
| `adr-writer` | "write an ADR", "architectural decision", "record a decision", "ADR for" | Produces a numbered Architecture Decision Record with context analysis, route comparison, decision rationale, consequences, and a propagation checklist | *(unique to DojoCraft)* |
| `project-scaffolder` | "scaffold project", "bootstrap project", "init project structure", "new project" | Bootstraps project structure from proven templates: phases, tracks, decisions, artifacts, commissions directories with README stubs and an initial ADR-000 template | *(unique to DojoCraft)* |
| `scout-writer` | "scout this", "strategic scout", "explore options for", "what are the routes" | Produces a scout document: identifies a tension, generates 3-5 distinct routes with tradeoffs, synthesizes a recommendation, and proposes a first action | `strategic-thinking:strategic-scout` |
| `convergence-checker` | "converge", "convergence check", "drift check", "am I drifting" | Runs a quick RED/YELLOW/GREEN triage: counts dirty files and sessions since last convergence, triages open items | `system-health:convergence-gate` |
| `community-claude-md-guardian` | "check claude.md", "audit CLAUDE.md", "fix claude.md", "claude md health" | Audits CLAUDE.md files for conflicts, stale rules, missing sections, and cross-file coherence; produces a health report with auto-fix suggestions | `system-health:claude-md-guardian` |
| `codebase-viewer` | "view codebase", "map the code", "codebase overview", "explore this repo" | Structured codebase intelligence: directory tree with roles, entry points, dependency graph, test coverage map, and annotated "here be dragons" warnings | `continuous-learning:codebase-cartography` |
| `memory-curator` | "manage memories", "curate memory", "prune memories", "memory health" | Two-tier memory management: write, update, prune, and search memories with semantic deduplication; keeps MEMORY.md under 200 lines | `wisdom-garden:memory-garden` |
| `seed-curator` | "manage seeds", "curate seeds", "harvest seed", "plant seed", "elevate seed" | Seed lifecycle management: plant new seeds from experiences, harvest insights from sessions, search the seed library, and elevate proven seeds to skills | `wisdom-garden:seed-extraction` |

The "Full version" column points at the flagship skill with the fuller
pipeline context — reach for it when the task benefits from that context;
reach for the DojoCraft variant when it doesn't and you just want the artifact.

## The Behavioral Verb

DojoCraft's behavioral verb is **CRAFT**. Where other plugins STRATEGIZE, SPECIFY, or FORGE — DojoCraft CRAFTS: deliberate, evidence-based, repeatable. Every skill in this plugin produces a persistent artifact. None of them are fire-and-forget.

## When to use

- **"We need to record this decision before we forget why we made it"** — `adr-writer` produces a numbered ADR with context and consequences
- **"I'm starting a new project and want the standard skeleton"** — `project-scaffolder` bootstraps directories, READMEs, and an ADR-000 template
- **"We have three competing approaches and no clear winner"** — `scout-writer` maps the landscape before you commit
- **"I have 20 uncommitted files and don't know where to start"** — `convergence-checker` triages the pile and gives you a status color
- **"Agent behavior changed after that merge"** — `community-claude-md-guardian` finds the contradiction across your CLAUDE.md hierarchy
- **"I need to understand this repo before I touch anything"** — `codebase-viewer` maps directory roles, entry points, and dependency flow
- **"My memory index is getting bloated and stale"** — `memory-curator` prunes and deduplicates
- **"I want to capture what just worked, fast"** — `seed-curator` plants a seed without the fuller extraction pipeline

## The Craft Loop

CRAFT → RECORD → GOVERN → CONVERGE → repeat.

Every architectural choice that lives only in someone's head is a future incident. DojoCraft externalizes the reasoning so the whole system stays legible — to future you, to agents, to collaborators.
