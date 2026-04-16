---
name: project-scaffolder
description: "Bootstrap project structure from proven templates: phases, tracks, decisions, artifacts, commissions directories with README stubs and initial ADR-000 template."
triggers:
  - "scaffold project"
  - "bootstrap project"
  - "init project structure"
  - "create project dirs"
  - "new project"
version: "1.0.0"
model: sonnet
---

# Project Scaffolder

Bootstraps project directory structures from proven templates. Creates the skeleton — directories, READMEs, initial docs — so projects start with good bones.

## Workflow

### 1. TEMPLATE
Select template based on project type:

**go-service:**
```
cmd/{name}/main.go
internal/
pkg/
docs/
decisions/
  000-template.md
Makefile
.goreleaser.yaml
.gitignore
README.md
CLAUDE.md
```

**fullstack:**
```
frontend/
  src/
  package.json
backend/
  cmd/
  internal/
docs/
decisions/
  000-template.md
docker-compose.yml
README.md
CLAUDE.md
```

**orchestration:**
```
phases/
specs/
scouts/
decisions/
  000-template.md
commissions/
contracts/
docs/
STATUS.md
ARCHITECTURE.md
VISION.md
README.md
CLAUDE.md
```

**plugin:**
```
.claude-plugin/
  plugin.json
skills/
agents/
commands/
hooks/
  hooks.json
README.md
```

**minimal:**
```
docs/
decisions/
  000-template.md
README.md
CLAUDE.md
```

### 2. CUSTOMIZE
Gather project metadata:
- Project name (required)
- One-line description (required)
- Primary language (inferred from template, can override)
- Repository URL (optional)
- Author / organization (optional)

### 3. CREATE
Generate directory structure:
- Create all directories from template
- Add README.md stub in each directory explaining its purpose (1-3 sentences)
- Never overwrite existing files — skip with warning
- Never generate source code files — scaffold structure only

### 4. ADR
Write `decisions/000-template.md`:
```markdown
# ADR-NNN: [Short Title]

**Date:** YYYY-MM-DD
**Status:** Proposed | Accepted | Superseded by ADR-NNN
**Affects:** [list repos and/or contracts affected]

## Context
What is the situation that calls for a decision?

## Decision
What is the decision that was made?

## Consequences
What are the positive and negative consequences?

## Propagation
- [ ] [document/repo 1]
- [ ] STATUS.md updated
```

### 5. CLAUDE
Generate initial CLAUDE.md:
- Project overview section with name and description
- Conventions section (language-specific defaults from template)
- Debugging protocol stub
- Git rules section (conventional commits, build before commit)
- Active projects section (empty, to be filled)

### 6. STATUS
Generate initial STATUS.md:
- Project metadata (name, version: 0.1.0, status: initialized)
- Architecture section (empty, to be filled)
- Test status section (no tests yet)
- Open items section (empty)

### 7. GIT
Initialize version control:
- `git init` if not already in a git repo
- Generate .gitignore appropriate to the primary language
- Do NOT create initial commit — let the user review first

### 8. REPORT
Output summary:
- Directories created: N
- Files created: N
- Files skipped (already existed): N
- Next steps guidance (e.g., "Write your first ADR", "Add a go.mod", "Configure your CI")

## Anti-patterns
- Never generate source code — this is structure, not implementation
- Never commit on behalf of the user — they review first
- Never overwrite existing files — scaffold is additive only
- Never add dependencies — the scaffold has zero runtime requirements
