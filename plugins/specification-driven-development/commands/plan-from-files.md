---
description: Plans next steps from uploaded files. Use when you have docs to act on.
---

# /plan-from-files — Create a Plan from Uploaded Files Using Intent-Based Routing

**Argument hint:** `<planning goal — e.g., 'plan next steps from this spec', 'refactor based on this code', 'create action items from these notes'>`

Load the `context-ingestion` skill before proceeding.

## Workflow

### Step 1: Analyze Files

Read all uploaded files. For each file, catalog:
- File type (spec, code, notes, research, design doc)
- Content summary (key entities, decisions, themes)
- Key entities (functions, endpoints, decisions, constraints)

### Step 2: Detect Intent and Route

Analyze the user's request for routing signals. Apply the routing table:

| File Types & Quantity | Intent Keywords | Selected Mode |
|---|---|---|
| 1-2 files (any type) | "plan", "refactor", "next steps", "action items" | **Context Ingestion** (default) |
| Spec, requirements doc | "spec", "prompt", "implement" | Route to `/write-spec` or `/write-prompt` |
| 3+ research files | "synthesize", "research", "patterns", "compare" | **Research Synthesis** |
| Ambiguous | (default) | **Context Ingestion** |

### Step 3: Route or Execute

**If routing to another command:**
Explain the routing decision and hand off. Example: "You uploaded a spec file and asked for an implementation prompt — routing to `/write-prompt`."

**If Context Ingestion mode**, execute the 5-step workflow:

#### 3a. Ingest & Catalog
Read every file, extract structure, identify key content. Create an internal catalog document.

#### 3b. Synthesize Context
- Find patterns across files
- Extract constraints (explicit and implicit)
- Note contradictions between files — flag them, do not silently resolve
- Identify opportunities

#### 3c. Create Plan
- Define phases with estimated durations
- Specify actions grounded in files (reference file names and line numbers)
- Define concrete deliverables for each phase
- Set binary success criteria
- Identify risks and mitigations

#### 3d. Validate
- Check completeness: All phases have deliverables
- Verify grounding: All recommendations tied to specific files
- Confirm actionability: Plan can execute without additional context

#### 3e. Deliver
Save plan as `[date]_plan_[topic].md`, summarize key phases, offer refinement.

### Step 4: Explain Routing

Briefly tell the user why this mode was selected. Example: "I used context ingestion because you uploaded 2 files with a general planning request."

## Critical Rules

- Every recommendation in the plan MUST reference a specific file, function, or section from the uploads.
- Constraints found in files MUST be listed explicitly in the plan.
- If files contradict each other, call it out — do not silently resolve contradictions.
- Plans must be actionable without needing additional context beyond the uploaded files.
- The routing decision must be explained to the user.
- If the router picks the wrong mode, the user can invoke the correct command directly.
