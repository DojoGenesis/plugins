---
description: Create a structured handoff package for another agent.
---

# `/handoff` — Create a Structured Handoff Package

Create a self-contained handoff package for transferring work between autonomous agents. **Every handoff is a sacred relay** — the package must be complete, and the receiving agent must be fully equipped to succeed.

## Philosophy

A handoff is a moment of trust. When one agent passes responsibility to another, the receiving agent's ability to succeed depends entirely on the quality of the context they receive. This command transforms handoffs from hopeful transfers into rigorous, verifiable exchanges.

**Core Principles:**
- **No implicit context** — If it's not in the handoff package, it doesn't exist
- **Over-communicate, always** — Better to include context that's not needed than to omit context that is
- **The receiver is the gatekeeper** — The receiving agent has the right and responsibility to reject incomplete handoffs
- **Handoff is a sacred relay** — The baton must be self-contained and complete

## When to Use

Use `/handoff` when:
- One agent's work is complete and another must begin the next phase
- Handing off a specification to an implementation agent (Zenflow, etc.)
- Transferring research to a review or synthesis agent
- Delegating a task that requires extensive context
- Moving work between sessions or agents

## Workflow

### Step 1: Gather Information

Ask the user:
1. **What work needs to be handed off?**
   - A task description
   - A spec to implement
   - A bug to fix
   - A research question to answer
   - A review to conduct

2. **Who is the receiver?**
   - Implementation agent (needs code context, file paths, exact requirements)
   - Research agent (needs question framing, source suggestions, scope boundaries)
   - Review agent (needs the work to review, criteria, known concerns)
   - Human collaborator (needs summary, decisions made, open questions)

### Step 2: Build the Handoff Package

Create a markdown file following this template:

```markdown
# Handoff: [Title]
**From:** [sender] | **To:** [receiver] | **Date:** [YYYY-MM-DD]

## Objective

> [Single, clear sentence — what the receiver must accomplish]

## Required Context

[Everything the receiver needs to understand the work]

**Project Background:**
- [2-3 sentences about the project]

**Tech Stack & Conventions:**
- [Technologies used]
- [Code conventions to follow]

**Recent Decisions:**
- [Decision 1: Rationale]
- [Decision 2: Rationale]

**Key Resources:**
- **Specification:** `[path/to/specification.md]`
- **Status:** `[path/to/STATUS.md]`
- **Pattern Files:** `[path/to/pattern.tsx]`
- **Relevant Docs:** `[path/to/documentation.md]`

## Task Definition

[Precise, unambiguous description of the work]

**For implementation agents:**
- Provide step-by-step instructions if sequential
- Use bullet lists if tasks are independent
- Include exact file paths for every file to create or modify

**For research agents:**
- Frame the research question clearly
- Suggest starting sources
- Define scope boundaries

**For review agents:**
- Link to the work to review
- Provide review criteria
- Note any known concerns

## Definition of Done

[Binary success criteria — pass/fail only]

- [ ] [Criterion 1]
- [ ] [Criterion 2]
- [ ] [Criterion 3]

## Constraints & Boundaries

[What the receiver must NOT do]

- **DO NOT** modify files outside of [specified scope]
- **DO NOT** add dependencies without [approval process]
- **DO NOT** make architectural decisions without consulting [sender]
- **MUST** follow patterns established in [pattern files]

## Next Steps After Completion

[What happens after the handoff is complete]

- Upon completion, notify [Next Agent Name]
- Hand off results for [next phase: QA, documentation, etc.]
- Update [STATUS.md] with completion status
```

### Step 3: Run the Handoff Checklist

Before delivering the package, verify against this checklist:

- [ ] **Single clear objective?** The receiver knows exactly what to accomplish
- [ ] **All referenced files/links are valid?** Every path and URL works
- [ ] **Task definition is unambiguous?** No room for interpretation
- [ ] **Success criteria are binary?** Each criterion is pass/fail, not subjective
- [ ] **Constraints are explicit?** The receiver knows what not to do
- [ ] **Next steps are defined?** Clear path forward after completion

**If any check fails, fix the package before delivering.**

### Step 4: Save and Deliver

1. Save the handoff package as: `handoffs/[date]_handoff_[title].md`
2. Present the package to the user for review
3. If the receiver is another agent in the same ecosystem:
   - Create a task for the receiver with the handoff package as input
   - Notify the receiver (via shared workspace, notification system, etc.)

## Integration with Connectors

### With ~~repository (GitHub)
- Link to specific files using repo URLs
- Reference pull requests and issues
- Include commit SHAs for context

### With ~~knowledge base (Notion)
- Link to specs, designs, and documentation
- Reference decision records
- Include page links in Required Context

### With ~~project tracker (Linear, Asana)
- Create handoff task in project tracker
- Link to related tickets
- Set up dependencies

### With ~~chat (Slack)
- Notify receiver in appropriate channel
- Share handoff package link
- Enable async coordination

## Examples

### Example 1: Implementation Handoff

**User:** "Hand off the v0.2.0 breadcrumb feature to Zenflow"

**Handoff Package:**
```markdown
# Handoff: Implement v0.2.0 Breadcrumb Navigation

**From:** Manus | **To:** Zenflow | **Date:** 2026-02-11

## Objective

> Implement breadcrumb navigation component with state management integration for v0.2.0

## Required Context

**Project Background:**
- Building multi-agent orchestration system
- Using React + TypeScript frontend
- State management via Redux Toolkit

**Tech Stack & Conventions:**
- React 18.2, TypeScript 5.0
- Component pattern: Functional components with hooks
- Styling: Tailwind CSS
- Testing: Jest + React Testing Library

**Recent Decisions:**
- Use Redux Toolkit for state management (avoids prop drilling)
- Breadcrumbs should be dynamic based on router state
- Mobile-first responsive design

**Key Resources:**
- **Specification:** `docs/v0.2.0/specs/breadcrumb_navigation.md`
- **Pattern File:** `frontend/src/components/Navigation/Sidebar.tsx`
- **Status:** `docs/v0.2.0/STATUS.md`

## Task Definition

Create breadcrumb navigation component following this structure:

1. **Create component file:** `frontend/src/components/Navigation/Breadcrumb.tsx`
   - Functional component using React hooks
   - Accept props: `path: string[], onNavigate: (path: string) => void`
   - Render clickable path segments

2. **Add state management:**
   - Create Redux slice: `frontend/src/store/slices/navigationSlice.ts`
   - Actions: `setBreadcrumb`, `updateBreadcrumb`
   - Selectors: `selectBreadcrumb`

3. **Integrate with router:**
   - Update `App.tsx` to listen to route changes
   - Dispatch breadcrumb updates on navigation

4. **Add unit tests:**
   - Component tests in `Breadcrumb.test.tsx`
   - State management tests in `navigationSlice.test.ts`
   - Coverage target: 85%+

## Definition of Done

- [ ] Breadcrumb component renders correctly for all routes
- [ ] Clicking breadcrumb segments navigates to correct route
- [ ] Redux state updates properly on navigation
- [ ] Unit tests pass with 85%+ coverage
- [ ] Component follows established patterns in Sidebar.tsx
- [ ] Mobile responsive (tested at 320px, 768px, 1024px)

## Constraints & Boundaries

- **DO NOT** modify routing logic outside of breadcrumb integration
- **DO NOT** add new dependencies (use existing React Router, Redux)
- **MUST** follow component structure in `Sidebar.tsx`
- **MUST** maintain accessibility (ARIA labels, keyboard navigation)

## Next Steps After Completion

- Notify Manus for code review
- Update `STATUS.md` with implementation status
- Create pull request for integration into develop branch
```

### Example 2: Research Handoff

**User:** "Hand off research on context compression techniques to Cipher"

**Handoff Package:**
```markdown
# Handoff: Research Context Compression Techniques

**From:** Manus | **To:** Cipher | **Date:** 2026-02-11

## Objective

> Research and synthesize context compression techniques for LLM-based agents

## Required Context

**Project Background:**
- Building agent orchestration system with long-running sessions
- Agents accumulate large context windows over time
- Need compression strategies to maintain coherence without token overflow

**Current Challenge:**
- Sessions exceed 100K tokens after 2-3 hours
- Manual summaries lose important nuance
- Need systematic compression approach

**Key Resources:**
- **Current Discussion:** `dojo-genesis/thinking/context_management_discussion.md`
- **Related Seed:** `dojo-genesis/memory/seeds/3-month-rule.md`

## Task Definition

Conduct research and produce a synthesis document on context compression:

1. **Research Sources:**
   - Academic papers on semantic compression for LLMs
   - Industry blog posts on agent memory management
   - Existing codebases (LangChain, LlamaIndex) for compression strategies
   - Suggested: Start with "Compressing Context" paper by Anthropic

2. **Key Questions to Answer:**
   - What compression techniques preserve semantic meaning?
   - How do we identify what to compress vs what to retain?
   - What are the tradeoffs (compression ratio vs information loss)?
   - Can compression be automated or does it need human guidance?

3. **Output Format:**
   - Create: `dojo-genesis/research/context_compression_synthesis.md`
   - Structure: Overview, Techniques Reviewed, Comparative Analysis, Recommendations
   - Include: Citations, code examples where relevant

## Definition of Done

- [ ] Reviewed at least 5 compression techniques
- [ ] Synthesized findings into structured document
- [ ] Provided clear recommendations for our use case
- [ ] Included citations for all sources
- [ ] Identified 2-3 techniques worth prototyping

## Constraints & Boundaries

- **DO NOT** implement code (research only)
- **DO NOT** make architectural decisions without discussing with Manus
- **STAY WITHIN** context compression for LLM agents (not general data compression)

## Next Steps After Completion

- Present findings to Manus in discussion session
- Decide on prototype approach based on recommendations
- Move to implementation phase if recommendations are approved
```

## Best Practices

1. **Be Ruthlessly Explicit**
   - Don't assume the receiver knows anything
   - Link to every file, document, and resource
   - Define every term and convention

2. **Make Success Criteria Binary**
   - ✅ Good: "Unit tests pass with 85%+ coverage"
   - ❌ Bad: "Good test coverage"

3. **Include Context Depth Based on Receiver**
   - Implementation agents need more technical detail
   - Human collaborators need more narrative explanation
   - Research agents need clear question framing

4. **Test Your Links**
   - Verify every file path exists
   - Check that URLs are accessible
   - Ensure referenced resources are current

5. **Over-Communicate**
   - If you're unsure whether to include something, include it
   - Better to have too much context than too little
   - The receiver can skim; they can't invent missing context

## Troubleshooting

### "The receiving agent rejected my handoff"
- Review the 6-point checklist — which criteria failed?
- Ask the receiver what's missing
- Update the package and resubmit

### "I'm not sure what level of detail to include"
- Ask: "Could the receiver complete this with zero questions?"
- If no, add more detail
- When in doubt, err on the side of over-communication

### "The user doesn't know who the receiver is"
- Suggest receiver based on task type
- Implementation task → implementation agent
- Research task → research agent
- If still unclear, create a general handoff and let routing decide

## Related Skills

- `handoff-protocol` — Full skill documentation
- `workspace-navigation` — For organizing handoffs in shared workspaces
- `agent-teaching` — For teaching the receiving agent necessary context
