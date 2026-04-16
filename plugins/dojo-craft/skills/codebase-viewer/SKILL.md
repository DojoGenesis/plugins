---
name: codebase-viewer
description: "Structured codebase intelligence: directory tree with roles, entry points, dependency graph, test coverage map, and annotated 'here be dragons' warnings."
triggers:
  - "view codebase"
  - "map the code"
  - "codebase overview"
  - "show me the architecture"
  - "explore this repo"
version: "1.0.0"
model: sonnet
---

# Codebase Viewer

Produces a structured codebase map — not a file listing but an annotated architecture view with entry points, dependency flow, test coverage, and danger zones.

## Workflow

### 1. TREE
Generate directory structure (2-3 levels deep) with role annotations:
- Each directory gets a one-line role description
- Mark directories as: source, test, config, docs, build, generated, vendored
- Flag empty directories and their likely purpose
- Respect .gitignore — skip node_modules, vendor, build outputs

### 2. ENTRY
Identify entry points — where execution begins:
- `main` functions (Go, Rust, Python)
- CLI command handlers
- HTTP route registrations
- Event listeners and subscribers
- Scheduled task definitions
- Test suites (as secondary entry points)

### 3. DEPS
Map the dependency graph:
- External dependencies from go.mod / package.json / Cargo.toml / requirements.txt
- Internal package import relationships
- Circular dependency detection
- Heavyweight dependencies (large transitive dep trees)

### 4. TESTS
Scan for test coverage:
- Which packages/directories have test files
- Test-to-source ratio per directory
- Packages with zero tests (flag as risk)
- Test patterns in use (unit, integration, e2e, benchmark)

### 5. PATTERNS
Identify architectural patterns:
- Clean architecture / hexagonal / onion (ports-and-adapters)
- MVC / MVVM
- Microservice boundaries
- Monolith with internal module separation
- Event-driven / message-passing
- Repository pattern / service layer

### 6. DRAGONS
Flag areas of concern — severity-labeled:
- **CRITICAL**: Files >1000 lines, circular dependencies, hardcoded secrets
- **WARNING**: Files >500 lines, deeply nested code (>4 levels), TODO/FIXME density >5 per file
- **INFO**: No tests for package, outdated dependencies, unused imports

### 7. CONTRACTS
Identify interfaces and API boundaries:
- Go interfaces and their implementors
- HTTP API surface (routes, methods, request/response types)
- gRPC / protobuf definitions
- Event schemas
- Configuration contracts (env vars, config files)

### 8. REPORT
Produce structured codebase map as markdown:
- Header with repo name, language, size metrics
- Each section from above as a headed section
- Summary statistics table (files, lines, packages, test coverage %)

### 9. SUGGEST (optional, only if requested)
Based on findings, suggest 3 high-value improvements:
- Highest-risk dragon to address first
- Biggest test coverage gap
- Most impactful architectural improvement

## Reading Rules
- For files >50KB: use Grep to find relevant sections, then read with offset/limit
- Never read files >200KB in one shot
- Check file size with wc -c before reading large files
- Prefer targeted reads over full-file reads for analysis
