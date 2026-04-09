# Workspace Templates

Reference templates for use with the workspace-navigation skill. Keep this file as-is; the skill body links here rather than embedding these schemas inline.

---

## Document Frontmatter Schema

Every workspace document should include:

```markdown
---
title: [Descriptive Title]
author: [Your Name]
date: [YYYY-MM-DD]
status: Draft | Active | Final | Archived
tags: [tag1, tag2, tag3]
related: [doc-slug-1, doc-slug-2]
---
```

---

## Discussion Thread Template

```markdown
---
title: [Discussion Topic]
author: [Your Name]
date: [YYYY-MM-DD]
status: Active
tags: [tag1, tag2, tag3]
participants: [agent1, agent2]
---

# [Discussion Topic]

## Context
[What is the background or situation that prompted this discussion?]

## Question / Problem
[What are we trying to decide or solve?]

## Perspectives

### Perspective 1: [Name]
[Description of this perspective]
**Pros:** - [Pro 1]  **Cons:** - [Con 1]

### Perspective 2: [Name]
[Repeat structure]

## Open Questions
- [ ] [Question 1]

## Next Steps
- [ ] [Action 1: Owner]

## References
- [Link to related discussion]
```

---

## Decision Template

Full fields: Context, Decision, Rationale, Alternatives, Implications, Risks, Review Criteria.

See `decision-propagation` skill for full template with field definitions.

---

## Threaded Discussion Format

For multi-agent threaded discussions:

```markdown
### [Agent A] - [Date]
[Perspective or question]

### [Agent B] - [Date]
[Response or alternative perspective]

### [Agent C] - [Date]
[Synthesis or recommendation]
```

---

## Specification Review Comment Format

```markdown
<!-- COMMENT [Agent B]: This section needs more detail -->
```

---

## Insights Extraction Template

Use when distilling a document into portable insights:

```markdown
## Insights from [Document Title]

**Author:** [Name] | **Date:** [YYYY-MM-DD] | **Status:** [Draft/Active/Final]
**Link:** [Path to document]

**Key Insights:**
- [Insight 1]
- [Insight 2]

**Open Questions:**
- [Question 1]

**Relevance to Current Task:**
[How this informs what I'm working on]
```

---

## Related Content Block

Include in every workspace document:

```markdown
## Related Content
- [Discussion: Memory Architecture](../00_Active/discussions/2026-02-01_memory-architecture_manus.md)
- [Spec: Context Compression](../01_Specifications/architecture/context-compression.md)
- [Seed: 3-Month Rule](../03_Memory/seeds/3-month-rule.md)
```
