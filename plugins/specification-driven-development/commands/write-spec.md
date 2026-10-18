---
description: Writes a release specification. Use when starting a release.
---

# /write-spec — Write a Production-Ready Release Specification

**Argument hint:** `<feature, release, or version to specify>`

Load the `release-specification` skill before proceeding.

## Workflow

### Step 1: Gather Input

Ask the user for the feature or release to specify. Accept any of: feature name, version number, strategic brief, or vague description.

### Step 2: Gather Context

Collect as much grounding information as possible:

- **If ~~repository is connected:** Read the codebase structure, existing types, API endpoints, and recent commits.
- **If ~~project tracker is connected:** Pull related tickets, epics, and existing requirements.
- **If ~~knowledge base is connected:** Search for prior specs, design docs, and ADRs.
- **Otherwise:** Ask the user about current architecture, tech stack, existing patterns, and constraints.

### Step 3: Draft the Specification

Follow the A+ template from the `release-specification` skill. The spec MUST include all of these sections:

1. **Vision** — 2-3 sentences: what and why
2. **Goals & Success Criteria** — 3-5 measurable, binary outcomes
3. **Technical Architecture** — Production-ready TypeScript/Go/Python types, API contracts, state shapes
4. **Implementation Plan** — Ordered phases with file manifests
5. **Risk Assessment** — Likelihood x impact matrix
6. **Rollback & Contingency** — What to do when things break
7. **Documentation** — What docs need updating

### Step 4: Review with User

Present the spec and ask for feedback on scope, architecture, and timeline.

### Step 5: Save

Save as `[version]_specification_[feature].md` in the workspace.

## Critical Rules

- Every type definition must be real TypeScript/Go/Python, not pseudocode
- Every API endpoint must include method, path, request body, response body, and error cases
- Every success criterion must be binary (pass/fail, not "improved" or "better")
- Implementation phases must have explicit file manifests (which files to create/modify)
- The standard is 111/100 (A+). Good enough is not good enough.
