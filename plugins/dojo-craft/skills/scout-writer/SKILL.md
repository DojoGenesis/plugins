---
name: scout-writer
version: "1.0.0"
model: sonnet
description: "Produces a scout document: identifies a tension, generates 3-5 distinct routes with tradeoffs, synthesizes a recommendation, and proposes a first action. Use when: 'scout this', 'strategic scout', 'explore options for', 'what are the routes'."
triggers:
  - "scout this"
  - "strategic scout"
  - "explore options for"
  - "what are the routes"
category: dojo-craft

inputs:
  - name: situation
    type: string
    description: The situation, tension, or decision landscape to scout
    required: true
outputs:
  - name: scout_document
    type: ref
    format: markdown
    description: Scout document with tension framing, 3-5 routes with tradeoffs, comparison table, synthesized recommendation, and first action
---

# Scout Writer Skill

## I. Philosophy

A scout does not arrive with a solution. A scout arrives with a map.

The most expensive engineering decisions are the ones made before the terrain was understood. A well-written scout document is the cheapest possible way to stress-test a direction before committing resources. It costs an hour of careful thinking and saves days or weeks of course-correction.

The scout is not neutral. The scout has a point of view — grounded in evidence, stated explicitly, open to reframe. "Here are some options" is not scouting. Scouting is: "Here is the landscape, here is what I see in it, here is where I would go and why — and here is what would change my mind."

## II. When to Use

- Before committing to an architectural direction with significant consequences
- When a team is stuck between competing legitimate approaches
- Before writing a specification — the scout produces the "why" that the spec translates into "what"
- When the question is "which direction?" not "how do we implement this direction?"
- As input to the `adr-writer` skill when the decision warrants formal recording

Do not use this skill when the direction is already decided and the question is implementation. Scouting a decided question wastes time and introduces doubt where certainty is needed.

## III. Workflow

### Step 1: TENSION

Frame the situation as a tension between competing forces — not a problem to solve, but a landscape to navigate.

A tension statement has the form: "[Force A] vs. [Force B]" with a brief explanation of why both forces are legitimate and why they pull in different directions.

Examples:
- "Velocity vs. coherence: shipping fast risks architectural drift, but slowing down to audit means missing the grant deadline."
- "Simplicity vs. extensibility: a single-file solution ships today but cannot accommodate the multi-tenant requirement arriving in Q3."
- "Build vs. buy: the existing library covers 80% of the need but the missing 20% is load-bearing."

A tension framed well reveals the routes naturally. A tension framed poorly produces routes that are all variations on one approach.

### Step 2: ROUTES

Generate 3-5 distinct approaches. Distinct means architecturally different, not just implementation variations.

For each route, produce:

| Field | Content |
|-------|---------|
| **Name** | Short label (e.g., "Route A: Minimal Wedge") |
| **Description** | What does this approach actually do? 2-4 sentences. |
| **Risk Level** | Low / Medium / High — with the specific risk named |
| **Time Estimate** | Rough order of magnitude (hours, days, weeks) |
| **Key Tradeoff** | What does this route give up to get its benefits? |
| **When it wins** | Under what conditions is this the right choice? |

Generate routes that represent genuine alternatives. If you cannot name what a route gives up, you have not understood it.

### Step 3: COMPARE

Build a route comparison table. This is the artifact that makes the scout document scannable in 30 seconds.

| Route | Description | Risk | Time | Key Tradeoff | Wins When |
|-------|-------------|------|------|-------------|-----------|
| A | ... | Low | 2d | ... | ... |
| B | ... | High | 1d | ... | ... |
| C | ... | Med | 3d | ... | ... |

The table forces honest comparison. If one route dominates on all dimensions, that is suspicious — it means the routes are not genuinely distinct, or the "losing" routes need better articulation of when they would win.

### Step 4: SYNTHESIZE

After laying out the routes, ask: can any of them be combined?

The best solutions often are not Route A or Route B — they are the part of Route A that addresses Force 1, combined with the part of Route B that addresses Force 2.

Identify synthesis opportunities:
- Which routes share underlying assumptions that make them combinable?
- Which routes address different aspects of the tension (not the same aspect from different angles)?
- What hybrid approach takes the ceiling of each route's strengths while avoiding its floor?

Synthesis is a creative act. Not every scout produces a hybrid. But looking for one forces you to understand the routes at a deeper level.

### Step 5: DECIDE

Produce a recommendation with explicit rationale.

The recommendation has four parts:

1. **Selected route (or hybrid):** Which approach? Be specific.
2. **Decisive factors:** What made this route win? Name the 2-3 factors that tipped the decision. If one factor was decisive above all others, name it.
3. **What would change this:** Under what conditions would a different route be better? This makes the recommendation conditional and honest — it tells the reader when to revisit.
4. **First concrete action:** What is the single next step that commits to this route? Naming it converts the scout from analysis to motion.

A recommendation without rationale is a guess. A recommendation without a first action is still just analysis.

### Step 6: FORMAT

Produce the scout document as structured markdown.

```
# Scout: [Topic]

**Date:** YYYY-MM-DD
**Tension:** [one sentence]

## Context

[2-3 sentences on what prompted this scout. What is the forcing function?]

## Tension

[The tension statement from Step 1 — expanded to a paragraph if needed.]

## Routes

### Route A: [Name]
[Description, risk, time, key tradeoff, when it wins]

### Route B: [Name]
[...]

### Route C: [Name]
[...]

## Comparison

[The table from Step 3]

## Synthesis

[Hybrid opportunity or note that no synthesis applies]

## Recommendation

**Selected:** [Route or hybrid]

**Decisive factors:**
- [Factor 1]
- [Factor 2]

**What would change this:** [Condition]

**First action:** [Specific next step]

## Next Steps

- If proceeding to a formal decision: invoke `adr-writer` with this scout as input
- If proceeding to specification: invoke `release-specification` or `specification-writer`
- Review point: [When to re-evaluate — date, event, or metric]
```

Save the document to `thinking/[topic]-scout.md` or the equivalent docs directory for the project.

## IV. Quality Checklist

- [ ] Tension framed as competing forces, not as a problem with one obvious solution
- [ ] 3-5 routes, each architecturally distinct
- [ ] Each route has named risk, time estimate, and key tradeoff
- [ ] Comparison table fills all columns for all routes
- [ ] Synthesis considered explicitly (even if result is "no synthesis applicable")
- [ ] Recommendation names decisive factors, not just the selected route
- [ ] First concrete action is specific and actionable
- [ ] Document saved to disk

## V. Common Pitfalls

- **Presenting routes that are not distinct.** If Routes B and C are both "use a managed service" with different providers, collapse them. The strategic choice is "managed service vs. self-hosted" — the provider is an implementation detail.
- **Recommending before all routes are laid out.** The recommendation comes after the comparison table. Anchoring the reader to a preferred route before the alternatives are presented biases the analysis.
- **No decisive factors.** "This route seems best" is not a recommendation. "This route wins because our timeline eliminates Route B and our team has no Rust experience to make Route C viable" is a recommendation.
- **Scout as substitute for decision.** The scout produces clarity, not closure. A scout that ends without a recommendation or a first action is an incomplete artifact.
- **Retrospective scouting of decided questions.** If the decision is already irreversible, write an ADR instead — not a scout. The scout is for before commitment, not after.

## VI. Output

- Scout document saved to `thinking/[topic]-scout.md`
- Recommendation with first action clearly stated
- If the scout reveals the decision warrants an ADR: explicit prompt to invoke `adr-writer`
- If the scout reveals the decision is more complex than expected: note the reframe before proceeding

## Examples

**Scenario 1:** "Scout whether to use SSE or WebSockets for the Gateway streaming interface."
→ Tension: "Protocol simplicity vs. bidirectional capability." Routes: SSE-only, WebSocket-only, SSE for server-push + REST for client-to-server, WebSocket with SSE fallback. Comparison table. Synthesis: SSE + REST is the hybrid that matches current usage patterns without the complexity of WebSocket upgrade handshake. Recommendation: SSE + REST; decisive factors: existing CLI uses REST already, server-push is 95% of traffic, WebSocket adds complexity for 5% gain.

**Scenario 2:** "Explore options for how the CLI should discover available skills."
→ Tension: "Discovery completeness vs. startup latency." Routes: filesystem scan on startup, cached manifest with TTL, on-demand load per invocation, remote registry pull. Comparison table. Synthesis: cached manifest (filesystem scan once, invalidate on file change) takes the startup speed of on-demand with the completeness of full scan. Recommendation: cached manifest + inotify invalidation. First action: add manifest file write to the existing skill-validate.sh hook.

## Edge Cases

- If the situation has only two genuine routes (binary choice), document both with full rigor and note explicitly that no third route was found after honest search. Do not invent a third route to fill the template.
- If external constraints eliminate routes before the scout begins, document those constraints in the Context section and start the routes from the remaining viable space.
- If the scout reveals that the question being asked is the wrong question, name the reframe explicitly before producing routes. A scout that maps the wrong landscape is worse than no scout.

## Anti-Patterns

- Producing routes without tradeoffs — a route without a stated cost is not an honest analysis of that route.
- Treating "more information needed" as a scout output — if you cannot characterize the routes without more information, name exactly what information is needed and from where, then pause.
- Generating routes to fill a quota — three genuine routes are better than five padded ones. Quality over count.
- Scouting as a delay tactic — if a route is clearly correct and the only question is how to implement it, say so and proceed to specification. A scout that re-derives an obvious conclusion wastes time.
