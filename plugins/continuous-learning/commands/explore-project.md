---
name: explore-project
description: Assesses a project's fit and entry points. Use when evaluating a repo.
argument_hint: "<project repository, docs folder, or description>"
skill: skills/project-exploration/SKILL.md
---

# /explore-project

Explore a new project or codebase to assess collaboration potential. Understand its philosophy and patterns before committing to implementation.

## Behavior

### 1. First Impressions

Read the README, project structure, and recent activity:
- What is this project? Who built it? What's its philosophy?
- What's the organizational structure? (file/folder patterns, naming conventions)
- Is this project alive? (last commit, release cadence, contributor count)

### 2. Architecture Mapping

Map the project's behavioral capabilities using a semantic-clusters approach:
- What does this project actually *do*? (capabilities, not just files)
- What architectural patterns does it follow? (MVC, plugin architecture, event-driven, etc.)
- What are the core abstractions and key dependencies?

### 3. Assess Fit

Evaluate against the user's goals:
- **Alignment:** Does this project's architecture support what the user wants to do?
- **Pattern compatibility:** Are the patterns compatible with existing work?
- **Codebase health:** Test coverage, documentation quality, code style consistency

Classify fit as:
- **GREEN** — Strong fit. Proceed with collaboration.
- **YELLOW** — Partial fit. Proceed with caution, address concerns first.
- **RED** — Poor fit. Reconsider collaboration.

Build a resonance map connecting the project's principles to existing knowledge.

### 4. Identify Entry Points

Where would a new collaborator start?
- **Most approachable** — well-documented, well-tested, clear interfaces
- **Most impactful** — where contribution adds the most value
- **Most risky** — complex, poorly documented, or tightly coupled
- **Quick wins** — small improvements that build familiarity

### 5. Produce Exploration Brief

Output:
- **Project Summary** — what it is, who built it, core philosophy
- **Architecture Snapshot** — structure, patterns, dependencies, activity
- **Fit Assessment** — GREEN/YELLOW/RED with rationale
- **Resonance Map** — connections to existing knowledge
- **Recommended Entry Points** — ranked by approachability and risk
- **Risks & Concerns** — identified risks with mitigation strategies
