---
description: Turns a spec into an implementation prompt. Use when commissioning.
---

# /write-prompt — Transform a Spec into an Implementation Prompt

**Argument hint:** `<path to specification file>`

Load the `implementation-prompt` skill before proceeding.

## Workflow

### Step 1: Read the Specification

Read the specification file provided by the user. If no file is provided, ask for it.

### Step 2: Transform into Implementation Prompt

Create a structured prompt with these sections:

1. **Context & Grounding** — What the agent needs to know about the project, stack, and conventions. Link to the specification. Identify 2-3 existing files as pattern references.

2. **Objective** — Single, clear sentence of what to build.

3. **Requirements** — Numbered list extracted from the spec's goals and architecture. Be ruthlessly specific. Separate into Backend and Frontend if applicable.

4. **File Manifest** — Exact files to create or modify, with purpose for each:
   - **Create:** `path/to/new_file.ts` — Purpose
   - **Modify:** `path/to/existing_file.ts` — What changes

5. **Success Criteria** — Extracted from spec, reformatted as a checklist of binary pass/fail items.

6. **Constraints & Boundaries** — What the agent must NOT do:
   - No refactoring unrelated code
   - No new dependencies without approval
   - No modifying files outside the manifest
   - Explicit scope boundaries

7. **Integration Points** — Where this work connects to other tracks or existing code.

8. **Testing Requirements** — What tests to write, what coverage to target, what scenarios to verify.

### Step 3: Assess Parallelizability

If the spec is large enough for parallel tracks (>2 weeks sequential work, 2-4 natural boundaries), suggest decomposition and offer to run `/parallel-tracks`.

### Step 4: Save

Save as `prompt_[feature]_[track].md` in the workspace.

## Critical Rules

- The prompt must be self-contained. An autonomous agent should be able to implement it without asking questions.
- Every requirement must be specific and actionable, not vague or aspirational.
- The file manifest must be complete — no files mentioned in requirements but missing from the manifest.
- Constraints must explicitly state what NOT to do, not just what to do.
- All references to specific agent tools must be generic — use "autonomous agent" or "implementation agent" instead of any product name.
