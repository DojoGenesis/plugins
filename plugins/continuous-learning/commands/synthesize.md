---
name: synthesize
description: Synthesizes research files into insights. Use when merging sources.
argument_hint: "<topic or question these files address>"
skill: skills/research-synthesis/SKILL.md
---

# /synthesize

Synthesize multiple research files into a unified, theme-based analysis with actionable recommendations. Turns raw research into coherent understanding.

## Behavior

### Phase 1: Ingest & Catalog

Read all uploaded files. For each:
- Extract metadata (author, date, key topics)
- Summarize key content
- Identify type (paper, article, notes, transcript, report)

Create an internal catalog listing all sources as a table.

### Phase 2: Cross-Reference & Find Patterns

Systematically compare across all files:

- **Convergence** — Where do sources agree? What claims have support from multiple files?
- **Divergence** — Where do sources contradict each other? These are often the most interesting insights.
- **Gaps** — What topics appear in one source but not others? What questions does no source answer?

Create a **cross-reference matrix** mapping themes to sources.

### Phase 3: Synthesize by Themes

Structure the synthesis document by **themes, NOT by individual files**. This is the cardinal rule — synthesis requires integration, not summarization.

For each theme:
- Summarize the convergent evidence
- Highlight contradictions with citations
- Provide a key insight that is not obvious from any single source

**Critical rules:**
- Organize by themes, NEVER by individual files
- Contradictions are valuable — highlight them, don't bury them
- Every claim must cite a specific source file

### Phase 4: Actionable Recommendations

Based on the synthesis, provide concrete next steps:
- Each recommendation must cite the sources that support it
- Recommendations must be concrete and implementable
- Flag recommendations where evidence is thin or contradictory

### Phase 5: Validate & Deliver

Before delivery, verify:
- [ ] All claims are supported by source files
- [ ] All major themes and contradictions are covered
- [ ] Recommendations are concrete and actionable

Save as `research/[YYYY-MM-DD]_synthesis_[topic-slug].md`.

Summarize key insights and offer to explore specific themes in more detail.

## Handoff from `/plan-from-files`

If the specification-driven-development plugin's `/plan-from-files` routes 3+ research files here, accept the handoff seamlessly. The files are already identified — begin immediately with Phase 1 (Ingest & Catalog).

## Output

Synthesis document with:
- **Topic** — what question these files address
- **Source Catalog** — table with file metadata
- **Cross-Reference Matrix** — themes mapped to sources with consensus assessment
- **Theme-Based Synthesis** — convergence, divergence, and key insights per theme
- **Actionable Recommendations** — concrete next steps with source citations and confidence levels
- **Open Questions** — gaps needing further research (suggest `/deep-research` for specific gaps)
