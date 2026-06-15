---
name: workflow-router
model: sonnet
description: Routes user goals to the appropriate specialist agent workflow with resource allocation confirmation. Use when: the user wants to start a task but hasn't specified a workflow, asks "how should I approach this?", or needs orchestration across research → plan → build → fix stages.
category: agent-orchestration
metadata:
  version: "1.1"

inputs:
  - name: goal
    type: string
    description: User's stated goal or task description — the router will classify and route it
    required: false
outputs:
  - name: routed_workflow
    type: string
    description: Confirmation of the agent(s) dispatched and their assigned tasks, with handoff paths
---

# Workflow Router

Routes user goals to the appropriate specialist agent workflow with explicit resource allocation and confirmation before dispatch.

## Description

Classifies an incoming goal into one of four categories (Research, Plan, Build, Fix), maps it to the appropriate specialist agent(s), confirms resource allocation with the user, and dispatches. Handles the Fix workflow as a two-stage process (investigate first, then implement). Preserves context across agent handoffs using shared handoff documents. This skill is the entry point for multi-agent orchestration when the user knows what they want to accomplish but not which agent or workflow to use.

## Philosophy

The hardest moment in multi-agent work is the beginning: a goal exists but no agent is running, and the question of *which* agent to dispatch — and in what configuration — is itself a judgment call that can waste significant effort if gotten wrong.

The router exists to prevent two failure modes. The first is **premature dispatch**: launching agents before the goal is classified, so agents duplicate work or pull in opposite directions. The second is **under-resourcing**: treating a multi-phase task (research → plan → build) as a single-agent job and producing incomplete output that requires re-dispatch anyway.

The key principle is **confirm before dispatch.** An agent dispatched with ambiguous scope will spend its context budget guessing. A 30-second resource allocation conversation before dispatch is cheaper than a failed agent run and a re-brief. The router forces that conversation explicitly, so it doesn't get skipped under time pressure.

## When to Use

- User wants to start a non-trivial task without specifying a workflow
- User asks "how should I approach this?" or "what's the best way to tackle X?"
- A task requires multiple sequential agents (Research → Plan → Build)
- You need explicit resource allocation agreement before spawning agents

## Workflow

### Step 1: Classify the Goal

If the goal is not provided or is ambiguous, ask:

```
What's your primary goal for this task?

- Research — Understand/explore something (unfamiliar code, libraries, concepts)
- Plan — Design/architect a solution (implementation plans, problem decomposition)
- Build — Implement/code something (new features, components, implementation from a plan)
- Fix — Debug/fix an issue (investigate and resolve bugs, failing tests)
```

If intent is clear from context (e.g., "this test is failing" → Fix), infer without asking.

### Step 2: Check for Existing Plans

```bash
ls thoughts/shared/plans/*.md 2>/dev/null || ls docs/plans/*.md 2>/dev/null
```

- **Build goal:** Ask if implementing an existing plan; load it to avoid duplication
- **Plan goal:** Surface existing plans to prevent redundant work
- **Research / Fix:** Proceed without plan check

### Step 3: Confirm Resource Allocation

Present options and confirm before spawning:

```
How would you like to allocate resources?

- Conservative — 1-2 agents, sequential (minimal context, simple tasks)
- Balanced (recommended) — appropriate agents for the task, some parallelism
- Aggressive — max parallel agents (time-critical tasks)
- Auto — system decides based on complexity
```

Default to **Balanced** for unspecified or Auto selection.

### Step 4: Map Goal to Agent

| Goal | Primary Agent Type | Description |
|------|-------------------|-------------|
| Research | general-purpose (research mode) | Multi-source research using web and documentation tools |
| Plan | Plan | Create phased implementation plans with architectural trade-offs |
| Build | general-purpose (implementation mode) | Coding tasks, feature implementation, component creation |
| Fix | general-purpose (debug mode) → then implementation | Investigate first, implement fix after diagnosis |

**Fix workflow (two stages):**
1. Spawn debug agent to investigate: produce diagnosis and recommended fix
2. If fix requires code changes, spawn implementation agent with the diagnosis as context

### Step 5: Show Execution Summary and Confirm

```
## Execution Summary

Goal: [Research / Plan / Build / Fix]
Resource Allocation: [Conservative / Balanced / Aggressive]
Agent(s) to dispatch: [agent descriptions]

What will happen:
- [Brief description of each agent's task]
- [Expected output / deliverable and where it will be written]

Proceed? [Yes / Adjust settings]
```

Wait for confirmation before dispatching. If "Adjust settings", return to the relevant step.

### Step 6: Dispatch Agents

#### Research

```
Dispatch: general-purpose agent (research mode)

Prompt:
  Research: [topic]
  Scope: [what to investigate — libraries, APIs, patterns, concepts]
  Output: Write findings to research/[topic-slug].md and summarize key points
```

#### Plan

```
Dispatch: Plan agent

Prompt:
  Create implementation plan for: [feature/task]
  Context: [relevant codebase context, constraints, goals]
  Output: Save plan to docs/plans/[plan-slug].md with phased breakdown and trade-offs
```

#### Build

If a plan exists, summarize risks before dispatching:
- Identify any HIGH severity blockers (missing dependencies, ambiguous interfaces)
- Surface them to the user before proceeding

```
Dispatch: general-purpose agent (implementation mode)

Prompt:
  Implement: [task]
  Plan: [path to plan, if applicable]
  Constraints: [language, framework, test requirements]
  Output: Working implementation with tests passing; write handoff to handoffs/[session]/
```

#### Fix (two stages)

```
Stage 1 — Dispatch: general-purpose agent (debug mode)

Prompt:
  Investigate: [issue description]
  Symptoms: [what's failing, error messages, test output]
  Output: Diagnosis document with root cause and recommended fix path

Stage 2 — (after diagnosis) Dispatch: general-purpose agent (implementation mode)

Prompt:
  Fix: [issue as diagnosed]
  Diagnosis: [diagnosis document path]
  Output: Working fix with tests passing
```

## Handoff Preservation

Each dispatched agent should write a handoff before completing:
```
handoffs/{session-id}/{agent-type}-{timestamp}.md
```

The handoff captures: what was accomplished, what was found, decisions made, open questions, and what the next agent needs to know.

## Output

A confirmation message showing:
- Which agent(s) were dispatched
- Their assigned prompts
- Expected output locations
- Status after dispatch completes

---

## Best Practices

**Classify from the user's actual intent, not the surface wording.** "Can you look into why this test is failing?" is a Fix, not a Research. Classify by what the user needs to change, not what they literally said.

**Default to Balanced resource allocation.** Conservative is for truly trivial tasks (single file, known fix). Aggressive is for time-critical work where the user has explicitly said so. Most tasks sit in the Balanced band.

**Load existing plans before dispatching a Build agent.** A Build dispatched without a plan produces output that may conflict with prior design decisions. The 10 seconds it takes to check `thoughts/shared/plans/` can prevent a full rebuild.

**Fix is always two stages.** Never dispatch a single agent with "investigate and fix." Diagnosis and implementation are distinct cognitive tasks. Combining them produces agents that implement the first plausible hypothesis rather than the correct one.

**Write explicit handoff paths in every dispatch prompt.** Agents that don't know where to write output will either write nowhere or write somewhere the next agent won't look. Specify the path in the dispatch prompt, not as an afterthought.

**Surface HIGH blockers before dispatching Build.** If the plan has ambiguous interfaces or missing dependencies, raise them before the agent starts — not after it produces an implementation that doesn't compile.

---

## Common Pitfalls

| Pitfall | Sign | Fix |
|---------|------|-----|
| Skipping resource allocation confirmation | Dispatching immediately after classification | Always present the Execution Summary and wait for explicit confirmation |
| Merging Fix stages | Prompt says "investigate and fix" | Split into two sequential dispatches; first diagnosis, then implementation with diagnosis as input |
| Dispatching Build without checking for a plan | Agent reimplements what an existing plan already specifies | Run the plan-check step (Step 2) before every Build dispatch |
| Treating "Auto" allocation as a skip | Defaulting to maximum agents | Auto → Balanced; treat it as a preference to let the system decide, not permission to maximize |
| Omitting output paths in agent prompts | Agents write to unpredictable locations | Specify exact handoff paths in the dispatch prompt template |
| Classifying from literal wording | "Research the auth bug" dispatches a Research agent | Read intent: if the user needs something fixed, it's Fix regardless of the verb used |

---

## Examples

**Scenario 1:** User says "I want to add a dark mode toggle to the settings page."
- Classification: Build
- Step 2: Router finds `docs/plans/dark-mode.md` — loads it, surfaces one HIGH blocker (theme token naming unresolved)
- Raises blocker to user; user clarifies token convention
- Dispatches Build agent with plan path and resolved constraint
- Agent writes handoff to `handoffs/{session}/build-dark-mode.md`

**Scenario 2:** User says "The checkout flow is broken — users can't complete payment."
- Classification: Fix (two stages)
- Resource allocation: Balanced
- Stage 1: Dispatches debug agent with symptoms; agent produces `diagnosis/checkout-payment.md` with root cause identified
- Stage 2: Dispatches implementation agent with diagnosis document as context
- Both agents write handoffs; router surfaces completion status with output locations

**Scenario 3:** User asks "How should I approach this?" with no task specified.
- Router asks the four-category clarification question (Step 1)
- User answers "Plan — I need to design the new notification system"
- Step 2: No existing plan found
- Dispatches Plan agent; output saved to `docs/plans/notification-system.md`

---

## Quality Checklist

Before dispatching any agent:

- [ ] Goal is classified into exactly one category (Research / Plan / Build / Fix)
- [ ] Existing plans checked for Build goals (Step 2 completed)
- [ ] Resource allocation confirmed with user — not assumed
- [ ] Execution Summary presented and user responded "Proceed"
- [ ] Every dispatch prompt includes: task description, context, output path, constraints
- [ ] Fix goal is split into two separate dispatches (debug then implement)
- [ ] HIGH severity blockers surfaced to user before Build dispatch

After dispatch completes:

- [ ] Agent handoff files exist at the specified paths
- [ ] Confirmation message identifies all dispatched agents and their output locations
- [ ] If multi-stage (Fix or Research → Plan → Build), next stage dispatched only after prior stage output is confirmed

---

## Related Skills

- `maestro-orchestration` — use instead of or after the router when the goal requires live conductor-pattern coordination across multiple specialist agents with dependency management
- `orchestration-pattern-selector` — use when the routing decision involves choosing between parallel vs. sequential vs. swarm patterns
- `agent-dispatch-playbook` — reference for prompt engineering and model routing decisions made during Step 6 dispatch
- `handoff-protocol` — the handoff format agents should use when writing their output; ensures the next stage can consume it
- `parallel-dispatch` — for the specific case where a Research or Build goal decomposes into independent parallel tracks
