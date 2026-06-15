---
name: codebase-viewer
description: "Structured codebase intelligence: directory tree with roles, entry points, dependency graph, test coverage map, and annotated 'here be dragons' warnings."
triggers:
  - "view codebase"
  - "map the code"
  - "codebase overview"
  - "show me the architecture"
  - "explore this repo"
version: "1.0.1"
model: sonnet
category: dojo-craft
---

# Codebase Viewer

Produces a structured codebase map — not a file listing but an annotated architecture view with entry points, dependency flow, test coverage, and danger zones.

## Philosophy

Jumping into a new or unfamiliar codebase without a map is how hours disappear. File listings tell you what exists; this skill tells you what matters — where execution starts, where complexity accumulates, which corners have been skipped in testing, and which files will burn you. The output is a decision-ready orientation document, not a directory dump.

## When to Use

- Onboarding to a codebase you haven't touched before
- Resuming work after a long gap on a project
- Before dispatching build agents so you scout first-hand (not off a spec)
- Code review or audit where you need structural context, not just diff hungers
- Identifying where to focus refactoring or test investment
- Any time someone asks "how does this repo fit together?"

Do NOT use for repos you know intimately and just need to read a single file — this skill is oriented toward whole-codebase orientation, not targeted lookup.

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

## Common Pitfalls

- **File listing ≠ architecture map.** Don't just emit `ls -R` output. Every section should add annotation, not just enumeration.
- **Skipping the DRAGONS step.** It's tempting to stop at the pretty tree. The danger-zone audit is often the most actionable output.
- **Reading large files whole.** A 3000-line file read entirely to find one entry point wastes context. Grep for `func main` or the framework's router registration instead.
- **Marking everything CRITICAL.** Severity labels lose value if everything is red. Reserve CRITICAL for genuine hazards (hardcoded secrets, circular deps); use INFO liberally.
- **Inventing test coverage numbers.** If the tool can't count test files precisely, say "no test files found" rather than estimating a percentage.

## Example

A Go microservice repo. The skill produces:
- TREE: `cmd/server/` (entry), `internal/handler/` (HTTP layer), `internal/store/` (DB), `pkg/models/` (shared types), `docs/` (OpenAPI specs)
- ENTRY: `cmd/server/main.go` → registers HTTP router, loads config, starts listener
- DEPS: external — `chi`, `pgx`, `zap`; no circular internal imports detected
- TESTS: `internal/handler/` has tests; `internal/store/` has zero test files (flagged INFO)
- PATTERNS: Clean architecture — handler → service → store, no cross-layer imports
- DRAGONS: `internal/store/queries.go` at 1,100 lines (CRITICAL); 3 TODO comments in `internal/handler/auth.go` (INFO)

The output is a single markdown document a new contributor can read in five minutes to understand the system.

## Quality Checklist

- [ ] Tree is annotated (each directory has a role label), not a bare listing
- [ ] Entry points section names specific files and symbols, not just "main files"
- [ ] Dependency section distinguishes external vs internal imports
- [ ] Test coverage section identifies packages with zero tests
- [ ] DRAGONS section uses severity labels (CRITICAL / WARNING / INFO) and is non-empty even if all items are INFO
- [ ] Architectural pattern named explicitly (even "no clear pattern detected" is valid)
- [ ] Report section includes at least: file count, directory count, identified entry points count
- [ ] No invented metrics — if a number can't be derived from actual file reads/greps, it is omitted

## Related Skills

- `convergence-checker` — checks memory health and index freshness; useful after a codebase-viewer run reveals the local memory is stale
- `adr-writer` — once the architecture is mapped, write ADRs for the key structural decisions found
- `scout-writer` — produces targeted scouts into specific subsystems after the top-level map is done
