---
description: Splits a spec into parallel tracks. Use when one agent cannot do it all.
---

# /parallel-tracks — Decompose a Spec into Independent Parallel Tracks

**Argument hint:** `<path to specification or description of large task>`

Load the `parallel-tracks` skill before proceeding.

## Workflow

### Step 1: Read the Specification

Read the specification or gather task description from the user.

### Step 2: Assess Parallelizability

Before decomposing, verify the task qualifies:

- Is this >2 weeks of sequential work? If no, advise against decomposition.
- Are there 2-4 areas with clear separation of concerns? If no, advise against decomposition.
- Would parallel execution actually reduce the timeline? If no, advise against decomposition.

If the task does not qualify, explain why and suggest proceeding sequentially.

### Step 3: Identify Track Boundaries

1. List every major component/feature in the spec
2. Group into 2-4 clusters that touch different files/directories
3. Map dependencies between clusters (which must finish before which can start)
4. Verify each track is self-contained (can be specified, implemented, and tested independently)

Common boundary types:
- **By layer:** Frontend, Backend, Database, CI/CD
- **By feature:** Authentication, Orchestration, User Interface
- **By component:** Header, Chat Area, Panels, Settings

### Step 4: Define Each Track

For each track, produce:

1. **Track name** and one-sentence purpose
2. **Dependency declaration** — What it needs from other tracks, what it provides to other tracks
3. **File manifest** — Files this track creates or modifies (MUST NOT overlap with other tracks)
4. **Integration points** — Where this track's output connects to other tracks (shared interfaces, APIs, props, state shapes)
5. **Estimated duration**
6. **Success criteria** — Independent of other tracks, binary pass/fail

### Step 5: Produce Integration Plan

Define how tracks merge:
- Merge order (which track merges first)
- Integration tests that verify the merge
- Conflict resolution strategy
- Who is the "merge coordinator" if file overlap is unavoidable

### Step 6: Save

Save as `parallel_tracks_[feature].md` in the workspace.

## Critical Rules

- Aim for 2-4 tracks, not 10. Over-parallelization creates more coordination overhead than it saves.
- Each track must be substantial (500+ lines or 3+ days of work).
- File manifests MUST NOT overlap between tracks. Two tracks modifying the same file is a merge conflict guarantee.
- Lock interfaces between tracks early. If a track needs to change an interface, communicate immediately.
- Hidden dependencies must be mapped explicitly in the planning phase.
- The integration plan is mandatory, not optional.
