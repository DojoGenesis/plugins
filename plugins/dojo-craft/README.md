# DojoCraft

_Craft is the bridge between strategy and code._

## What it does

DojoCraft is the practitioner's workbench. It bundles the governance and intelligence workflows that keep a fast-moving codebase coherent: architectural decision records, strategic scouting, CLAUDE.md health audits, and convergence gates. These are not one-off utilities — they are repeatable disciplines that compound over time.

Use DojoCraft when you need to **decide well**, **document clearly**, **keep configuration honest**, and **stay out of drift**.

## Skills

| Skill | Trigger | Description |
|-------|---------|-------------|
| `adr-writer` | "write an ADR", "architectural decision", "record a decision", "ADR for" | Produces a numbered Architecture Decision Record with context, route comparison, rationale, consequences, and a propagation checklist |
| `scout-writer` | "scout this", "strategic scout", "explore options for", "what are the routes" | Produces a scout document: identifies a tension, generates 3-5 distinct routes with tradeoffs, synthesizes a recommendation, and proposes a first action |
| `claude-md-guardian` | "check claude.md", "audit CLAUDE.md", "fix claude.md", "claude md health" | Audits CLAUDE.md files for conflicts, stale rules, missing sections, and cross-file coherence; produces a health report with auto-fix suggestions |
| `convergence-checker` | "converge", "convergence check", "drift check", "am I drifting" | Runs a convergence gate: counts dirty files and sessions since last convergence, triages open items, and produces a RED/YELLOW/GREEN status report |

## The Behavioral Verb

DojoCraft's behavioral verb is **CRAFT**. Where other plugins STRATEGIZE, SPECIFY, or FORGE — DojoCraft CRAFTS: deliberate, evidence-based, repeatable. Every skill in this plugin produces a persistent artifact. None of them are fire-and-forget.

## When to use

- **"We need to record this decision before we forget why we made it"** — `adr-writer` produces a numbered ADR with context and consequences
- **"We have three competing approaches and no clear winner"** — `scout-writer` maps the landscape before you commit
- **"Agent behavior changed after that merge"** — `claude-md-guardian` finds the contradiction across your CLAUDE.md hierarchy
- **"I have 20 uncommitted files and don't know where to start"** — `convergence-checker` triages the pile and gives you a status color

## The Craft Loop

CRAFT → RECORD → GOVERN → CONVERGE → repeat.

Every architectural choice that lives only in someone's head is a future incident. DojoCraft externalizes the reasoning so the whole system stays legible — to future you, to agents, to collaborators.
