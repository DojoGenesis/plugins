---
name: deep-research
description: Runs focused deep research. Use when one question needs depth.
argument_hint: "<research question or topic>"
skill: skills/research-modes/SKILL.md
---

# /deep-research

Conduct focused, comprehensive research on a specific topic. Produces a validated recommendation grounded in evidence.

## Behavior

### Phase 1: Define Scope

Help the user narrow from a broad topic to a specific, answerable research question.

A good research question is:
- **Answerable** — has a concrete answer, not just "it depends"
- **Bounded** — clear in/out scope
- **Actionable** — the answer informs a decision

**Bad:** "What is the best database?"
**Good:** "Which embedded database supports vector search with <100ms P95 latency for our Go backend?"

Produce a research brief with: Question, Decision it informs, Scope boundaries, Success criteria.

### Phase 2: Discover Sources

Identify 5-10 high-quality sources:
- Documentation, papers, articles, repos
- If **~~knowledge base** is connected, search internal docs first
- Prioritize: recency, authority, relevance, depth

Present sources as a table with relevance annotations.

### Phase 3: Deep Reading & Notes

For each source, extract:
- **Key claims** — what does this source argue?
- **Evidence quality** — how well-supported are the claims?
- **Relevance** — how does this inform the research question?
- **Open questions** — what doesn't this address?

Use web search and web fetch tools aggressively.

### Phase 4: Synthesis & Analysis

Cross-reference findings:
1. What are the major themes or patterns?
2. What do most sources agree on?
3. Where do sources disagree, and why?
4. What are the tradeoffs or tensions?
5. What gaps remain?

Build a recommendation grounded in evidence.

### Phase 5: Validation

Stress-test the recommendation:
- What would have to be true for this to be wrong?
- What's the strongest counterargument?
- Did I check for confirmation bias?
- Are there gaps in my reasoning?

## Output

Research brief with:
- **Question** — the research question
- **Sources Reviewed** — table with title, author, year, relevance, key contribution
- **Key Findings** — findings with evidence and confidence level
- **Synthesis** — cross-referenced analysis
- **Recommendation** — action to take with rationale, risk, and mitigation
- **Confidence Level** — High/Medium/Low with rationale
- **Open Questions** — what needs further research

## Save

Save as `research/[YYYY-MM-DD]_deep_[topic-slug].md`.
