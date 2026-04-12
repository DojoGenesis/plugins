# Cowork Plugins by Dojo Genesis

**84 skills that make autonomous software development actually work.**

AI agents are powerful but chaotic. They hallucinate requirements, forget context between sessions, skip verification, and produce work that needs rework. The problem isn't intelligence — it's discipline.

These plugins encode the discipline. 8 behavioral plugins, 84 first-party skills — from strategic scouting to specification writing to structured retrospectives. Every skill exists because we needed it while shipping real software with autonomous agents. And then needed it again.

**84 first-party skills. 40-50% timeline reduction. 77 hours saved through pre-flight verification alone.**

## The Philosophy

Most plugin marketplaces optimize for quantity. We optimize for quality.

These aren't "10 AI prompts for productivity." These are battle-tested workflows from actually shipping software with autonomous agents—retrospectives that surfaced patterns, specifications that prevented rewrites, scouting sessions that saved weeks of misdirected effort.

**Every skill here exists because we needed it. And then needed it again.**

## Plugins

| Plugin | Verb | Skills | What it does |
|--------|------|--------|--------------|
| [strategic-thinking](plugins/strategic-thinking/) | STRATEGIZE | 6 | Scout tensions before committing to solutions. Position products, design multi-surface strategies, bridge vision to execution with iterative refinement. |
| [specification-driven-development](plugins/specification-driven-development/) | SPECIFY | 12 | Write specs grounded in codebase reality, not wishful thinking. Transform them into implementation prompts, commission parallel tracks, verify alignment before handoff. |
| [wisdom-garden](plugins/wisdom-garden/) | REMEMBER | 13 | Compress session context into lasting memory. Reflect on patterns as seeds, elevate proven seeds into reusable skills. Knowledge is cultivated, not just stored. |
| [system-health](plugins/system-health/) | OBSERVE | 19 | Audit ecosystem health, map semantic clusters across codebases, track documentation drift, sync repo context. You cannot improve what you do not observe. |
| [continuous-learning](plugins/continuous-learning/) | LEARN | 13 | Harvest sprint learnings through structured retrospectives. Research deeply and widely, diagnose systematically, explore new projects with curiosity as compass. |
| [agent-orchestration](plugins/agent-orchestration/) | ORCHESTRATE | 10 | Handoffs are sacred relays, not tosses over the wall. Clean context preservation, shared workspace navigation, peer teaching, decision propagation across living documents. |
| [skill-forge](plugins/skill-forge/) | BUILD | 9 | The meta-layer—skills about making skills. Create, maintain, audit, and evolve the reusable patterns that power every other plugin. |
| [pretext-pdf](plugins/pretext-pdf/) | PUBLISH | 2 | Export structured documents to print-quality PDF using the Pretext layout engine. Zero-reflow typography, adaptive pagination, auto table of contents. |

## What Makes This Different

**Most AI productivity tools:**
- Give you fish (single-use prompts)
- Optimize for speed over understanding
- Treat errors as failures, not feedback
- Assume one-size-fits-all workflows

**These plugins:**
- Teach you to fish (transferable patterns)
- Optimize for understanding over extraction
- Treat errors as data (debug systematically, retrospect honestly)
- Adapt to your context (skills are templates, not scripts)

## Quick Start

Each plugin is self-contained with:

- `README.md` — Overview, philosophy, skill table, trigger phrases
- `CONNECTORS.md` — External service integrations (MCPs, APIs, data sources)
- `agents/` — Agent persona definitions for specialized work
- `commands/` — Command-line interfaces and keyboard shortcuts
- `skills/` — Full workflow definitions (SKILL.md files with progressive disclosure)

**Fastest path to value:**

1. Start with `strategic-thinking:scout` when facing a decision with no obvious answer
2. Use `specification-driven-development:release-specification` before commissioning autonomous agents
3. Run `continuous-learning:retro` after every major release to harvest learnings
4. Apply `wisdom-garden:compression-ritual` at the end of long sessions to preserve context
5. Lean on `system-health:health-audit` when codebases feel brittle or documentation drifts

## The Use Cases

**Strategic work:**
- Should we build native mobile or invest in web-first? → `strategic-thinking:product-positioning`
- We have a vision but no clear path → `strategic-thinking:scout` + `strategic-thinking:iterative-scouting`
- Designing a product across desktop, mobile, web → `strategic-thinking:multi-surface-strategy`

**Specification and planning:**
- Writing a release spec for an autonomous agent → `specification-driven-development:release-specification`
- Frontend spec grounded in existing backend → `specification-driven-development:frontend-from-backend`
- Splitting a large project into parallel tracks → `specification-driven-development:parallel-tracks`
- Verifying spec is ready for handoff → `specification-driven-development:pre-implementation-checklist`

**Memory and context:**
- Long conversation getting unwieldy → `wisdom-garden:compression-ritual`
- Capturing a learning for future reference → `wisdom-garden:memory-garden`
- Formalizing a repeated workflow → `wisdom-garden:seed-extraction` → `skill-forge:skill-creation`

**System health:**
- New codebase, need to understand it → `system-health:repo-status` + `system-health:semantic-clusters`
- Documentation feels stale → `system-health:documentation-audit`
- Need full health audit before major work → `system-health:health-audit`

**Learning and debugging:**
- Something broke, need systematic diagnosis → `continuous-learning:debug`
- Researching a decision → `continuous-learning:deep-research` or `continuous-learning:wide-research`
- Post-sprint reflection → `continuous-learning:retro`
- Exploring a new project → `continuous-learning:project-exploration`

**Agent coordination:**
- Handing off work between agents → `agent-orchestration:handoff-protocol`
- Teaching another agent → `agent-orchestration:agent-teaching`
- Decision needs to propagate through docs → `agent-orchestration:decision-propagation`
- Navigating shared workspace → `agent-orchestration:workspace-navigation`

## The Reality Check

These plugins won't make you ship faster on day one.

They'll make you ship *better*—which compounds into shipping faster, with less rework, and more learning preserved.

If you're optimizing for throughput over understanding, these aren't for you.
If you're building for the long term, cultivating patterns that scale, and treating governance as an investment rather than overhead—welcome home.

## Origin

Built by Dojo Genesis at Tres Pies Design.

These plugins encode patterns discovered through practice—retrospectives that surfaced friction, specifications that prevented rewrites, scouting sessions that reframed stuck decisions, and the daily work of building software with autonomous agents.

**No silver bullets. Just better attention.**

## Versioning

Current version: **1.2.0**

We follow semantic versioning with a cultivation mindset:
- **Patch** (1.1.x): Bug fixes, typo corrections, minor clarifications
- **Minor** (1.x.0): New skills, enhanced workflows, backward-compatible improvements
- **Major** (x.0.0): Breaking changes, major restructuring, philosophical shifts

See [CHANGELOG.md](CHANGELOG.md) for version history.

## Contributing

Found a pattern worth sharing? A skill that could be clearer? A workflow that needs a better name?

Open a PR. These plugins grow through use—yours, ours, everyone's.

## License

Apache 2.0 — see [LICENSE](LICENSE).

Cultivate. Harvest. Share. Repeat.
