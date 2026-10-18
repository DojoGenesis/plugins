---
description: Extract context from a repository.
---

# /sync-repo -- Sync and Extract Context from a Repository

**Argument hint:** `<repository URL or path>`

---

## Philosophy

Architectural decisions made in a vacuum are fragile. Implementation prompts written without understanding existing patterns create friction. This command embodies **grounding in reality** -- syncing with the actual codebase state before making decisions or writing specifications. It is not about reading every file, but about **surgical context extraction**: identifying what matters, syncing only those parts, and producing a context brief that enables immediate productivity.

---

## Workflow

### Step 1: Locate the Repository

**Goal:** Access the target codebase.

1. **If a URL is provided** and `~~repository` is connected: Clone or access the repository via the connected service.
2. **If a local path is provided:** Navigate to the directory and verify it is a valid project.
3. **If the path does not exist:** Ask the user to provide a valid repository URL or local path.

### Step 2: Extract Key Context

**Goal:** Build a comprehensive understanding of the codebase without reading every file.

Extract the following:

| Context Area | What to Capture |
|---|---|
| **Tech stack** | Languages, frameworks, runtimes, package managers |
| **Directory structure** | Top 3 levels of the filesystem tree |
| **Main entry points** | Application entry files, server startup, CLI commands |
| **API surface** | Routes, handlers, public functions, exported modules |
| **Data models** | Database schemas, types, interfaces, structs |
| **Test coverage** | Testing framework, test locations, approximate coverage |
| **CI/CD** | Pipeline configuration, deployment targets |
| **Dependencies** | Key dependencies from lockfile/manifest |
| **Configuration** | Environment variables, config files, feature flags |

### Step 3: Produce the Context Brief

**Goal:** Write a single markdown document that gives any reader enough context to start working in the codebase.

Structure the context brief as:

1. **Project Overview** -- What the project is, what it does, who it's for. 2-3 sentences.
2. **Tech Stack** -- Table of languages, frameworks, and key dependencies.
3. **Directory Structure** -- Annotated tree showing what each key directory contains.
4. **Entry Points** -- Where to start reading the code, how to run the project.
5. **API Surface** -- Key endpoints or public interfaces.
6. **Data Models** -- Core types, schemas, or database tables.
7. **Testing** -- How to run tests, what framework is used, approximate coverage.
8. **Build & Deploy** -- How to build, how to deploy, CI/CD pipeline overview.
9. **Key Patterns** -- Naming conventions, architectural patterns, coding style observed in the codebase.
10. **Open Questions** -- Anything unclear that would benefit from human clarification.

### Step 4: Save

Save as `[project-name]_context_brief.md` at the project root or the working directory.

---

## Quality Gate

Before delivering, verify:

- [ ] Tech stack is identified with specific versions where possible
- [ ] Directory structure covers the top 3 levels
- [ ] At least 3 entry points are documented
- [ ] API surface covers the main endpoints or public interfaces
- [ ] Key patterns reflect actual observed code, not assumptions
- [ ] Open questions are listed honestly
- [ ] The brief is sufficient for a new contributor to orient themselves

---

## Output

```
[project-name]_context_brief.md
```
