---
name: project-scaffolder
description: "Bootstrap project structure from proven templates: phases, tracks, decisions, artifacts, commissions directories with README stubs and initial ADR-000 template."
triggers:
  - "scaffold project"
  - "bootstrap project"
  - "init project structure"
  - "create project dirs"
  - "new project"
version: "1.0.1"
model: sonnet
category: govern-publish
---

# Project Scaffolder

Bootstraps project directory structures from proven templates. Creates the skeleton — directories, READMEs, initial docs — so projects start with good bones.

## Philosophy

How a project is organized on day one shapes how easy it is to navigate, hand off, and extend on day one hundred. Consistent skeletons mean agents and humans share a mental model without reading a map first — the `decisions/` directory always holds ADRs, `docs/` always holds specs, `internal/` always holds private packages. This skill encodes that consistency rather than letting each project invent its own layout.

## When to Use

- Starting a brand-new project or sub-project from scratch
- Formalizing a directory that grew organically and now needs structure
- Onboarding a new repository into an ecosystem that uses a standard layout
- When the user says "create a new X project" and no directory yet exists

Do NOT use to restructure an existing project with established conventions — this skill is additive only and will skip existing files, but wholesale restructuring is a different task requiring explicit migration planning.

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

## Example

User asks: "scaffold a go-service project called `billing-worker`."

The skill selects the `go-service` template, gathers: name = `billing-worker`, description = provided by user, language = Go (from template). It creates:
- `cmd/billing-worker/main.go` — stub only (not implemented)
- `internal/` with a README stub explaining it holds private packages
- `docs/` with a README stub for specs and runbooks
- `decisions/000-template.md` — the ADR template filled with `billing-worker` metadata
- `CLAUDE.md` — project overview, Go conventions, git rules
- `STATUS.md` — initialized state, version 0.1.0
- `.gitignore` — Go-appropriate (binaries, vendor, .env)

Report: 7 directories created, 9 files created, 0 skipped. Next steps: "Write your first ADR for the primary design decision. Run `go mod init` to create go.mod."

Git is initialized but no commit is made.

## Quality Checklist

- [ ] Template selected explicitly matches the project type (not defaulted to `minimal` without reason)
- [ ] Project name and description are populated in CLAUDE.md and STATUS.md — no placeholder text left
- [ ] `decisions/000-template.md` is written with correct frontmatter (date, status: Proposed)
- [ ] No source code files generated (only structure + stub docs)
- [ ] Existing files were not overwritten — any skipped files are listed in the report
- [ ] `.gitignore` is language-appropriate, not empty or generic
- [ ] Report includes directory count, file count, skipped count, and next-step guidance
- [ ] No `git commit` was run — user reviews before first commit

## Related Skills

- `adr-writer` — write the first real ADR after the scaffold is in place
- `codebase-viewer` — orient to the repo once it has content
- `community-claude-md-guardian` — validate and maintain the CLAUDE.md written during scaffolding
