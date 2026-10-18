---
description: Run a full repository health audit.
---

# /health-audit -- Run a Comprehensive Health Audit

**Argument hint:** `<repository path or URL>`

---

## Philosophy

Health is not merely the absence of bugs; it is the **presence of practices** that ensure security, sustainability, and alignment with a project's core purpose. A health audit is an act of tending -- a gardener surveying the ecosystem, not a mechanic fixing a machine. Regular audits compound quality over time. Every audit produces a permanent, dated artifact so trends are visible and progress is measurable.

---

## Workflow

### Phase 1: Grounding

**Goal:** Understand what the repository is *for* before evaluating how well it works.

1. **Locate the repository.** If `~~repository` is connected, use it to access the codebase. Otherwise, navigate to the local path provided by the user.
2. **Map the directory tree.** Identify top-level shape, key directories, and the overall project structure.
3. **Count files by type** and estimate lines of code to gauge project scale.
4. **Read foundational documents:** README, package.json / go.mod / Cargo.toml / pyproject.toml, CI configs (.github/workflows, Jenkinsfile, etc.).
5. **Identify the tech stack:** primary language, framework, runtime, infrastructure.
6. **Understand the project's purpose.** Read philosophy, architecture, or design documents if they exist. Hold this purpose as the lens for the entire audit.

### Phase 2: Health Assessment

**Goal:** Systematically evaluate the repository across 5 health dimensions.

For each dimension, assign a status:
- **GREEN** -- Healthy. Good practices in place.
- **YELLOW** -- Needs attention. Gaps exist but nothing is broken.
- **RED** -- Critical. Immediate action required.

#### Dimension 1: Critical Issues
- Is the project buildable? (`npm run build`, `go build`, `cargo build`, etc.)
- Are there critical dependency vulnerabilities? (`npm audit`, `cargo audit`, etc.)
- Is the main branch in a broken state?
- Are there missing dependencies or broken imports?

#### Dimension 2: Security
- Are secrets managed securely (not hardcoded, using vaults or env management)?
- Is sensitive data encrypted at rest and in transit?
- Are authentication and authorization implemented correctly?
- Are dependencies free of known high-severity vulnerabilities?

#### Dimension 3: Sustainability -- Testing
- Is there a testing framework configured?
- What is the approximate test coverage?
- Are tests passing in CI?
- Is the CI pipeline reliable and fast?

#### Dimension 4: Sustainability -- Technical Debt
- Are there code smells, high-complexity hotspots, or excessive duplication?
- What is the TODO/FIXME/HACK density?
- Is there dead code or unused dependencies?
- Are there manual processes that should be automated?

#### Dimension 5: Sustainability -- Documentation
- Is the README accurate, complete, and useful?
- Are inline docs and comments meaningful (not stale)?
- Do API docs exist and match the actual endpoints?
- Is there architecture documentation?

### Phase 3: Generate Actionable Tasks

**Goal:** Translate every YELLOW or RED finding into a concrete engineering task.

For each finding, produce:

| Field | Description |
|---|---|
| **Task title** | Verb-object format (e.g., "Fix frontend build failure") |
| **Priority** | P0 (do now), P1 (this sprint), P2 (next sprint), P3 (backlog) |
| **File paths** | Specific files affected |
| **Estimated effort** | Hours (e.g., "2-4 hours") |
| **Acceptance criteria** | Binary, testable condition for "done" |

If `~~project tracker` is connected, offer to create tickets directly.

### Phase 4: Produce Audit Report

**Goal:** Create a permanent, dated audit artifact.

Save the report as `docs/audits/[YYYY-MM-DD]_health_audit.md` in the target repository. The report must contain:

1. **Executive Summary** -- 3-line verdict: what is the overall health, what is the biggest risk, what is the highest-priority action.
2. **Health Dashboard** -- All 5 dimensions with status (GREEN/YELLOW/RED) and a one-line summary each.
3. **Findings** -- Grouped by dimension. Each finding has severity, description, impact, and affected files.
4. **Action Items** -- Prioritized table of all generated tasks.
5. **Trend** -- If prior audits exist in `docs/audits/`, compare current results to the most recent previous audit. Note improvements and regressions.

---

## Quality Gate

Before delivering, verify:

- [ ] All 5 health dimensions are assessed with GREEN/YELLOW/RED status
- [ ] Every YELLOW or RED finding has a corresponding actionable task
- [ ] Every task has a title, priority, file paths, effort estimate, and acceptance criteria
- [ ] The audit report is saved as a dated file in `docs/audits/`
- [ ] The executive summary is 3 lines or fewer
- [ ] If prior audits exist, a trend comparison is included
- [ ] No vague advice -- every finding points to specific files and concrete next steps

---

## Output

```
docs/audits/[YYYY-MM-DD]_health_audit.md
```
