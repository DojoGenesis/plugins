---
name: file-management
model: sonnet
description: Produces a documented directory structure plan — tree layout diagram, naming convention decision, and organizational philosophy — applying patterns such as feature-domain grouping, temporal prefixes for dated artifacts, numbered directories for ordered sequences, and pointer READMEs for navigating large trees. Use when: "organize this project structure", "plan a file layout", "design a directory hierarchy", "improve folder organization", "create a project structure".
category: skill-forge

inputs:
  - name: project_description
    type: string
    description: Description of the project or codebase to organize
    required: true
  - name: constraints
    type: string
    description: Naming or organizational constraints to apply
    required: false
outputs:
  - name: directory_plan
    type: string
    description: Documented directory structure plan with tree layout diagram, naming convention decision, and organizational philosophy
---

# File Management & Organization Skill

## Philosophy

Directory structure is architecture. A well-organized repository communicates intent at a glance — a new contributor or an agent reading the tree can predict where to find things before opening a single file. Poor structure forces everyone who touches the codebase to hold the entire layout in memory, increasing cognitive load and error rates.

This skill applies when structure is unclear, inconsistent, or growing organically without a plan. It does not impose a single "right" layout — it selects the pattern that fits the project's dominant access pattern, then applies consistent naming so the structure is self-documenting.

## When to Use

- "Organize this project structure" / "plan a file layout" / "design a directory hierarchy"
- "Improve folder organization" / "create a project structure"
- A new repository is being initialized and needs a coherent layout from the start
- An existing project has grown organically and navigation is becoming painful
- A monorepo or multi-service system needs a consistent cross-service pattern

Do NOT apply unprompted to a working project where the user asked for a feature — reorganizing without invitation adds risk and context-switch cost.

## Best Practices

- **Match the pattern to the project, not the reverse.** If none of the three core patterns fits, ask one clarifying question about the dominant access pattern ("read by humans or code?") before adapting.
- **Scope changes to what hurts.** For existing projects with inconsistent but functional structure, target the 1–2 most disruptive inconsistencies rather than a full rewrite.
- **Apply one naming convention end-to-end.** Mixing kebab-case directories with snake_case files within the same layer signals inconsistency to both developers and agents.
- **Temporal prefixes belong on dated artifacts only.** Do not apply `YYYY-MM-DD_` to files that are evergreen; it obscures them in listings without adding value.
- **Pointer READMEs are navigation, not documentation.** A root README in a deep directory tree should name each subdirectory in one line — nothing more. Full documentation belongs in dedicated docs/.

## I. Recommended Patterns

These are flexible patterns that can be adapted to different environments.

### 1. The Generic Web Application

This is a good starting point for many web applications.

```
/
├── public/             # Static assets (images, fonts, etc.)
├── src/                # Source code
│   ├── api/            # Backend API handlers/controllers
│   ├── components/     # Reusable UI components
│   ├── lib/            # Shared libraries, utilities, and helpers
│   ├── pages/          # Page-level components (if using a framework like Next.js)
│   ├── services/       # Business logic and external API clients
│   └── styles/         # Global styles
├── tests/              # Tests
├── .env                # Environment variables
├── .gitignore
├── package.json
└── README.md
```

### 2. The AROMA-style Contemplative Repository

This pattern is optimized for knowledge bases and contemplative practice repositories.

```
/
├── seeds/              # Reusable patterns of thinking
├── thinking/           # Philosophical reflections and insights
├── conversations/      # Summaries of key discussions
├── docs/               # Formal documentation (specifications, retrospectives)
├── SKILLS/             # Reusable workflow skills
├── prompts/            # Prompts for other agents (e.g., implementation agents)
├── .gitignore
└── README.md
```

### 3. The Go Backend Service

A common structure for a Go backend service.

```
/
├── cmd/                # Main application entry points
│   └── api/            # The main API server
├── internal/           # Private application and library code
│   ├── handlers/       # HTTP request handlers
│   ├── models/         # Database models
│   └── store/          # Database access layer
├── pkg/                # Public library code (if any)
├── .gitignore
├── go.mod
└── README.md
```

---

## II. Naming Conventions

Apply one of these consistently across the project:

- **kebab-case** (`my-component.js`) — preferred for web projects and knowledge bases
- **snake_case** (`my_component.py`) — preferred for Python and data projects
- **PascalCase** (`MyComponent.tsx`) — reserved for class files and React components only; do not apply to directories

**Temporal prefix pattern** — prefix dated artifacts with `YYYY-MM-DD_` so they sort chronologically without a separate timestamp field:

```
docs/
├── 2026-01-15_architecture-decision.md
├── 2026-03-02_retrospective.md
└── 2026-04-07_migration-plan.md
```

**Numbered directory pattern** — prefix ordered sequences with two-digit numbers so directory listing reflects intended execution order:

```
phases/
├── 01_discovery/
├── 02_design/
└── 03_implementation/
```

**Pointer README pattern** — place a short `README.md` at the root of any directory with 5+ subdirectories. The README names each subdirectory's purpose in one line. This is the only README that belongs in a skill-adjacent directory; it is navigation, not documentation.

## Output

-   A directory layout diagram (tree format) showing the proposed structure with inline comments explaining each directory's purpose
-   A naming convention decision (kebab-case, snake_case, or PascalCase) with the rationale for the choice
-   Optional: a short prose summary of the organizational philosophy for inclusion in the project's README or ARCHITECTURE.md

## Examples

**Scenario 1:** "I'm starting a new Next.js app, how should I organize it?" → Produce the Generic Web Application layout from Section I, adapted with a `pages/` directory and a `hooks/` directory under `src/`, plus a recommendation to use kebab-case for file names.

**Before (disorganized):**
```
/
├── index.js
├── helpers.js
├── UserForm.js
├── api_client.js
├── styles.css
└── tests.js
```

**After (organized):**
```
/
├── src/
│   ├── components/   # Reusable UI — UserForm.js
│   ├── lib/          # Shared utilities — helpers.js, api_client.js
│   └── styles/       # Global styles — styles.css
├── tests/            # All test files — tests.js
└── index.js          # Entry point only
```

**Scenario 2:** "Help me restructure this knowledge base — we have seeds, retrospectives, and skill files all mixed in one folder" → Produce the AROMA-style pattern, map the existing files to the new directories, apply temporal prefix to dated docs, and add a pointer README at the root.

**Before (mixed):**
```
/
├── skill-creation.md
├── retro-jan.md
├── retro-march.md
├── seed-focus-theorem.md
└── architecture-notes.md
```

**After (structured with temporal prefixes and pointer README):**
```
/
├── README.md                          # Pointer: one line per subdirectory
├── skills/
│   └── skill-creation/SKILL.md
├── seeds/
│   └── seed-focus-theorem.md
└── docs/
    ├── 2026-01-10_retrospective.md
    ├── 2026-03-15_retrospective.md
    └── 2026-04-01_architecture-notes.md
```

## Edge Cases

-   **Existing project with inconsistent but functional structure:** Do not impose a full reorganization unless the user explicitly asks for one. Instead, identify the 1–2 most disruptive inconsistencies and propose targeted fixes only.
-   **Project type not covered by the three patterns:** Ask one clarifying question about the dominant access pattern (e.g., "is this primarily read by humans or by code?") and adapt the closest matching pattern.
-   **Monorepo with multiple services:** Apply the Go Backend or Web Application pattern per service; add a top-level `services/` or `apps/` directory rather than flattening everything.

## Anti-Patterns

-   **Imposing structure before understanding the project:** Recommending a layout without first knowing the tech stack and team size produces a structure that fits the pattern, not the project.
-   **Nesting by file type instead of feature:** Grouping all controllers in one directory and all models in another couples unrelated features and makes feature-level changes harder to scope.
-   **Reorganizing a working project unprompted:** If the user asked for a new feature, not a file audit, applying this skill without invitation adds risk and context-switch cost.

## Quality Checklist

Before delivering a directory plan, confirm:

- [ ] The dominant access pattern (human navigation vs. code import) was identified before choosing a layout
- [ ] One naming convention is applied consistently — no mixing within a layer
- [ ] Every top-level directory has a one-line purpose comment in the tree diagram
- [ ] Temporal prefixes are applied only to genuinely dated artifacts
- [ ] A pointer README is recommended for any directory with 5+ subdirectories
- [ ] For existing projects: only the highest-friction inconsistencies are targeted, not a full rewrite

## Related Skills

- `skill-maintenance` — for renaming and reconciling an existing skills directory structure
- `process-extraction` — for capturing and formalizing the layout decision itself as a repeatable workflow
- `skill-creation` — includes canonical skill directory structure (`SKILL.md`, `scripts/`, `references/`, `templates/`)
