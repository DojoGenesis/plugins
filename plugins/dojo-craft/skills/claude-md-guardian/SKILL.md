---
name: claude-md-guardian
version: "1.0.0"
model: sonnet
description: "Audits CLAUDE.md files for conflicts, stale rules, missing sections, and cross-file coherence. Produces a health report with auto-fix suggestions. Use when: 'check claude.md', 'audit CLAUDE.md', 'fix claude.md', 'claude md health'."
triggers:
  - "check claude.md"
  - "audit CLAUDE.md"
  - "fix claude.md"
  - "claude md health"
category: dojo-craft

inputs:
  - name: context
    type: string
    description: Trigger context — branch merge, onboarding, weekly maintenance, behavior inconsistency, or post-learning
    required: false
outputs:
  - name: health_report
    type: string
    description: CLAUDE.md health report with severity-classified findings and auto-fix suggestions
---

# CLAUDE.md Guardian Skill

## I. Philosophy

CLAUDE.md is the agent's behavioral contract. When rules drift, conflict, or accumulate without review, agent behavior becomes unpredictable in ways that are almost impossible to debug — because the symptom (agent doing the wrong thing) is far removed from the cause (contradictory rule added three sessions ago).

The guardian treats CLAUDE.md like source code: it requires validation, consistency checks, and protection against unreviewed modification. The difference is that source code fails loudly at compile time. CLAUDE.md fails silently at runtime, in production, usually at the worst moment.

Three failure modes threaten CLAUDE.md health:
1. **Conflict** — Contradictory rules across global, project, and subdirectory files. The hierarchy resolves them mechanically, but often not the way you intended.
2. **Drift** — Rules that were true when written but no longer match the codebase. Port numbers change. Tool names change. Conventions change. The rule stays.
3. **Bloat** — Accumulated rules that are redundant, vague, or unreferenced. More rules does not mean better behavior. It means more surface area for contradiction.

## II. When to Use

- After merging branches that touched CLAUDE.md independently
- When agent behavior changes unexpectedly (first suspect: CLAUDE.md conflict or stale rule)
- During periodic maintenance (weekly, or at convergence gates)
- Before onboarding a new agent or team member to verify the contract is coherent
- After applying learnings (reflect-and-learn) to verify no conflicts were introduced
- After a major refactor that changed file paths, port numbers, or tool names

Do not use this skill to write new CLAUDE.md rules. Use it to validate existing ones.

## III. Workflow

### Step 1: DISCOVER

Find all behavioral configuration files across the entire hierarchy.

Locations to check:
- `~/.claude/CLAUDE.md` — global rules applied to all projects
- `./CLAUDE.md` — project root rules
- `./<subdirectory>/CLAUDE.md` — subdirectory-specific overrides
- `./AGENTS.md` — cross-tool compatibility file (can contradict CLAUDE.md silently)
- `~/.claude/projects/<project-hash>/CLAUDE.md` — project-specific agent memory overlays

Use `glob` and `bash` to find all CLAUDE.md and AGENTS.md files recursively. Report the full list before proceeding.

### Step 2: PARSE

Extract all discrete rules from each file.

A "rule" is any imperative statement: "Always do X", "Never do Y", "Use X instead of Y", "Run X before Z." Section headers and commentary are not rules. Specific, actionable directives are rules.

Normalize the phrasing across files to detect semantic equivalents and contradictions. Two rules that say the same thing in different words are redundancies. Two rules that say opposite things are conflicts.

Tag each rule with:
- Source file
- Rule category (convention, debugging, build, git, project-specific)
- Last modified date (if determinable from git history)

### Step 3: CONFLICT

Detect contradictions between files.

A contradiction is when two rules — from different files in the same hierarchy — give opposing instructions for the same situation.

Examples of contradictions:
- Global: "Use port 8080 for gateway" vs. Project: "Gateway default port is 7340"
- Global: "Use Go conventions by default" vs. Subdirectory: "Use TypeScript conventions for all backend work"
- Project: "Never use on: directives in Svelte" vs. Subdirectory: "Use standard Svelte event syntax"

For each conflict:
- Name the two rules verbatim
- Name the source files for each
- Classify intent: is the subdirectory rule an intentional override, or an accidental contradiction?
- Recommend: which rule should win? Should the loser be deleted, annotated with "OVERRIDE:", or promoted?

### Step 4: STALENESS

Check rules against current codebase state.

Staleness patterns:
- **Dead paths:** Rule references a file, directory, or tool that no longer exists. Check with `glob` and `bash`.
- **Outdated ports/URLs:** Rule names a specific port or URL. Cross-reference with `wrangler.toml`, `settings.json`, `.env`, and config files.
- **Superseded tools:** Rule references a deprecated library, CLI command, or convention. Check `go.mod`, `package.json`, and recent commits.
- **Wrong version numbers:** Rule references a specific version that is no longer current.
- **Abandoned patterns:** Rule describes a pattern that was replaced but the rule was not removed.

For each stale rule:
- Quote the rule
- Name the specific evidence of staleness (e.g., "port 8080 appears nowhere in the codebase; gateway uses 7340 per settings.json")
- Recommend: update with current value, remove, or verify manually

### Step 5: COMPLETENESS

Check for missing standard sections.

A project-level CLAUDE.md should contain at minimum:
- [ ] Project overview (language, purpose, primary repos)
- [ ] Key conventions (language-specific, framework-specific)
- [ ] Debugging protocol (where to check first, what to avoid)
- [ ] Git rules (force push policy, commit conventions, sub-repo handling)
- [ ] Testing gate (build and test commands, when to run them)

A subdirectory CLAUDE.md that overrides the project CLAUDE.md should clearly mark its overrides.

Report which sections are missing and whether their absence is a risk.

### Step 6: COHERENCE

Cross-reference with project metadata files.

Check these for consistency with CLAUDE.md rules:
- `go.mod` — module name, Go version, dependency list
- `package.json` — project name, scripts, dependencies
- `Makefile` — build targets and commands
- `wrangler.toml` / `wrangler.jsonc` — deployment config
- `.goreleaser.yaml` — release binary naming and config

Incoherence examples:
- CLAUDE.md says "run `make test`" but Makefile has no `test` target
- CLAUDE.md references `DojoGenesis/mcp` but go.mod imports `mcp-by-dojo-genesis`
- CLAUDE.md says port 8080 but wrangler.toml binds to 7340

### Step 7: REPORT

Produce a health report with severity-classified findings.

Severity levels:
- **CRITICAL** — Active contradiction that will cause agent misbehavior today. Fix immediately.
- **WARNING** — Stale rule or coherence mismatch that will cause confusion. Fix soon.
- **INFO** — Redundancy or completeness gap. Fix opportunistically.

Report format:
```
# CLAUDE.md Health Report
**Date:** YYYY-MM-DD
**Files audited:** N
**Total rules found:** N

## Summary
- Critical: N
- Warning: N
- Info: N

## Critical Findings
[Each finding with: rule quoted, source file, evidence, recommended fix]

## Warning Findings
[...]

## Info Findings
[...]

## Auto-Fix Candidates
[Findings safe to apply automatically — stale ports, dead paths, obvious redundancies]

## Manual Review Required
[Findings requiring human judgment — intentional overrides, ambiguous intent]
```

### Step 8: FIX

Optionally apply auto-fixes for non-controversial issues.

Auto-fix candidates (safe to apply without confirmation):
- Update stale port numbers where the correct value is unambiguous in project config
- Remove rules that reference non-existent files (after confirming the file is genuinely gone)
- Deduplicate identical rules across files (keep in the more specific file, remove from the more general)

Do NOT auto-fix:
- Conflicts where intent is ambiguous
- Rules that might be intentional overrides
- Any deletion of a rule that could be an intentional exception

Always show the diff before applying and get confirmation for changes outside the auto-fix list.

## IV. Quality Checklist

- [ ] All CLAUDE.md and AGENTS.md files inventoried (global + project + subdirectory)
- [ ] Every conflict identified with both rules quoted and source files named
- [ ] Staleness check run against actual codebase state (not assumed)
- [ ] Coherence check includes at minimum: go.mod/package.json + config files
- [ ] Completeness check covers all five standard sections
- [ ] Report uses severity classification (CRITICAL/WARNING/INFO)
- [ ] Auto-fix candidates separated from manual review items
- [ ] If auto-fixes applied: diff shown and confirmed before writing

## V. Common Pitfalls

- **Treating all contradictions as bugs.** Subdirectory CLAUDE.md files often intentionally override project rules. Check for "OVERRIDE:" markers or contextual evidence before flagging as a conflict.
- **Staleness by assumption.** Do not assume a rule is stale because it looks old. Check the codebase. A rule about "port 8080 in development" might be intentionally different from "port 7340 in production."
- **Ignoring AGENTS.md.** Cross-tool files can contradict CLAUDE.md silently because different tools read them independently. Always include them in the inventory.
- **Over-aggressive deduplication.** Two files with similar rules may both need them — one for context, one for precedence. Removing from the wrong file creates a regression.
- **Rule count as quality metric.** A CLAUDE.md with 10 precise, current rules is healthier than one with 50 accumulated rules, half of which are stale.

## VI. Related Skills

- `convergence-checker` — Runs the broader convergence gate of which a CLAUDE.md audit is one phase
- `adr-writer` — If a CLAUDE.md conflict reveals an unrecorded architectural decision, write an ADR
- `hooks-reference` (system-health plugin) — Configure mechanical protection for CLAUDE.md files

## VII. Output

- Health report: total rule count per file, conflicts with file locations and rule text, redundancies identified, staleness candidates with evidence, completeness gaps, and severity-classified recommendations.
- Optional: list of auto-fix changes applied with diff.
- If CRITICAL findings exist: explicit statement that agent behavior may be unreliable until resolved.

## Examples

**Scenario 1:** "Agent started ignoring the no-force-push rule after last week's merge."
→ Guardian discovers that a subdirectory CLAUDE.md added for the CLI repo includes "force push is acceptable for feature branches" — an accidental contradiction with the project-level "never force push to main." Classified CRITICAL. Recommendation: add "OVERRIDE: CLI feature branches only" marker and confirm intent with the team.

**Scenario 2:** "Weekly CLAUDE.md maintenance before the Era 4 sprint."
→ Guardian finds: 3 rules referencing port 8080 (correct value is 7340 per settings.json) — WARNING; 2 identical rules in global and project CLAUDE.md — INFO; missing testing gate section in subdirectory CLAUDE.md — INFO. No critical conflicts. Auto-fixes applied for port references after confirmation. Deduplication recommendation noted for manual review.

**Scenario 3:** "Onboarding a new agent to the Gateway codebase."
→ Guardian audits all three levels of CLAUDE.md. Finds that the gateway subdirectory CLAUDE.md references `DojoGenesis/mcp` but go.mod still imports the deprecated `mcp-by-dojo-genesis` path — incoherence warning. Also finds no debugging protocol section in the subdirectory file — completeness gap. Both flagged before the agent is handed any Gateway work.

## Edge Cases

- If no project-level CLAUDE.md exists, report the absence as a CRITICAL finding — a project without a behavioral contract has undefined agent behavior by default.
- If a CLAUDE.md file is empty or has only a title, treat as effectively absent for completeness purposes.
- If the git history shows a rule was added in the last 48 hours, add a note: "recently added — may be intentional, verify before removing."

## Anti-Patterns

- **Auditing without access to actual codebase state.** A guardian that checks rules against documentation alone misses 80% of staleness. Always check against live files.
- **Skipping the coherence step.** CLAUDE.md rules that contradict the actual config are worse than no rules — they actively mislead agents.
- **Treating the guardian as a one-time run.** CLAUDE.md health degrades over time. Schedule the guardian at convergence gates, not just when behavior breaks.
- **Auto-fixing ambiguous rules.** When in doubt about intent, flag for manual review. A wrong auto-fix creates a new problem that looks like it was always there.
