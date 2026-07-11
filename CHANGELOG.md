# Changelog — CoworkPluginsByDojoGenesis

## 2026-07-11 — Cluster membership is metadata-only, never a physical move (v1.4.2)

### What happened

A Wave 4 was briefly implemented — physically moving `mcp-builder` and
`supply-chain-refresh` from `system-health` into `skill-forge` to match their
`forge` cluster — and then **reverted before it left this machine**, because
it is a breaking change: it renames `system-health:mcp-builder` →
`skill-forge:mcp-builder` (and the same for `supply-chain-refresh`), which
breaks every caller of the old invoke name. The forge-cluster grouping those
skills need is already fully carried by their `category: forge` metadata and
the cluster tables (added in Wave 2), so the move bought zero semantic value
at the cost of a real break. The two skills stay in `system-health`.

### The rule (now documented so it isn't re-attempted)

Cluster membership is a **lens**, expressed only through `category:` metadata
and the navigation tables — a `MISFILED` or `DUP` flag is descriptive, never a
to-do. Skills are never relocated between plugins to "fix" a cluster, because
the directory *is* the invoke name (`plugin:skill`). Recorded at the point of
temptation in `llms.txt` (`## Clusters` legend) and `README.md` (the cluster
section intro).

### Changes

- **`llms.txt`** + **`README.md`**: added the metadata-only / no-physical-move
  policy note beside the cluster flag legend.
- **marketplace.json + README version**: 1.4.1 → 1.4.2.

## 2026-07-11 — Wave 3: dedupe-in-place (v1.4.1)

### What happened

No renames, no moves — descriptions and pointers only. dojo-craft is
repositioned as the lean workbench (six single-file variants of flagship
skills elsewhere, plus two skills unique to it) rather than an undifferentiated
"practitioner's workbench," and every genuine near-duplicate pair surfaced by
the Wave 2 clustering pass now states its own boundary in its frontmatter
`description:` — the actual trigger surface skill dispatch reads, not just
the README table.

### Changes

- **`.claude-plugin/marketplace.json`**: dojo-craft's description rewritten
  to the lean-workbench framing, naming all six flagship pointers and the
  two unique skills.
- **`plugins/dojo-craft/README.md`**: rewritten — the skill table was
  showing only 4 of 8 skills and mis-named `community-claude-md-guardian` as
  `claude-md-guardian`; now lists all 8 with a "Full version" pointer column,
  and the "When to use" section covers all 8 instead of 4.
- **24 SKILL.md descriptions sharpened** with their twin's boundary + a
  "Full version: `plugin:skill`" pointer where applicable — the 6
  dojo-craft/flagship pairs (scout-writer/strategic-scout,
  convergence-checker/convergence-gate,
  community-claude-md-guardian/claude-md-guardian,
  codebase-viewer/codebase-cartography, memory-curator/memory-garden,
  seed-curator/seed-extraction), compression-ritual/session-compression,
  parallel-tracks/parallel-dispatch, web-research/web-research-external, the
  status trio (repo-status/status-template/status-writing), and the
  dispatch-shape trio (agent-dispatch-playbook/orchestration-pattern-selector/
  maestro-orchestration). All description edits verified single-line,
  under the 1024-char lint cap, no unrelated content touched.
- **marketplace.json + README version**: 1.4.0 → 1.4.1.

## 2026-07-11 — Wave 2: semantic cluster navigation layer (v1.4.0)

### What happened

Exposed 12 behavioral clusters that cross-cut the 10 plugins — a navigation
+ metadata layer on top of the existing plugin structure. No files moved.
Skills are grouped by what they *do* (scout-position, specify-commission,
dispatch-coordinate, remember-continue, seed-lifecycle, system-prompt-intel,
repo-docs-health, agent-telemetry, learn-research, understand-codebase,
forge, govern-publish), not just which plugin directory holds them —
surfacing dojo-craft's DUPs, two MISFILED skills (era-architecture,
adversarial-reviewer, figma-to-code, design-system-selector, mcp-builder,
supply-chain-refresh), and 3 skills whose function legitimately spans
plugins (skill-audit-upgrade, hooks-reference, voice-before-structure).

### Changes

- **`llms.txt`**: new `## Clusters` section — all 12 clusters with full
  `plugin:skill` membership, DUP/MISFILED/X flags. Community-skills note
  expanded (597 files, dormant-by-design).
- **`README.md`**: new "Find the Right Skill in 30 Seconds" cluster table +
  a twin-skill disambiguation table for the 11 genuine near-duplicate pairs
  (6 dojo-craft full-vs-lean pairs, compression-ritual/session-compression,
  parallel-tracks/parallel-dispatch, web-research/web-research-external, the
  status trio, the dispatch-shape trio). Community-skills dormant-by-design
  note added below the plugin table.
- **`category:` frontmatter rewrite (99 registered skills)**: every
  registered skill's `category:` now holds its cluster id instead of its
  plugin name, applied via a deterministic script (not hand-edits) with a
  built-in disk-vs-mapping cross-check. One placement judgment call:
  dojo-craft's `codebase-viewer` is filed under `understand-codebase` (its
  DUP target `codebase-cartography`'s cluster) rather than `repo-docs-health`
  (where the raw cluster spec listed it), per the spec's own
  DUP-target-cluster resolution rule; `semantic-clusters` and
  `repo-context-sync` (system-health) stay in `repo-docs-health`, their
  literal/home-plugin-dominant cluster.
- **`scripts/plugin-lint.py`**: new check enforces the 12-cluster
  `category:` vocabulary on all registered-plugin skills; community-skills
  stays exempt (it has no `category:` field at all — predates the taxonomy).
- **`scripts/face-parity.py`**: fixed a gate bug the Clusters section
  exposed — the llms.txt plugin-list-bullet regex scanned the *whole file*
  for `- **bold**` bullets instead of scoping to the `## Plugins` section,
  so it collided with the new cluster-id bullets. Scoped to the section body.
- **`plugins/community-skills/.claude-plugin/plugin.json`**: count 426 → 597
  (426 was the original Apr 6, 2026 security-audited batch; grown since via
  `supply-chain-refresh`), added the dormant-by-design framing.
- **marketplace.json + README version**: 1.3.1 → 1.4.0.

## 2026-07-11 — Wave 1: reconcile faces to disk truth (v1.3.1)

### What happened

The root README's per-plugin skill-count table had drifted from disk truth
without tripping `face-parity.py`, because that gate's corpus-scale sweep
exempts any number at or below the largest single plugin's count — exactly
the range a per-plugin table lives in. Four rows were stale (agent-orchestration
10→12, specification-driven-development 12→13, system-health 19→20,
wisdom-garden 13→14; table summed to ~94 against a correct 99 headline). The
Directory Structure diagram was worse: dojo-craft's 8 skills were mis-nested
under the `bring-loop/skills/` heading, one referenced a nonexistent
`claude-md-guardian` directory (actual: `community-claude-md-guardian`), and
most plugins' skill lists were partial (e.g. system-health showed 6 of 20).
STATUS.md was five months stale, still claiming 7 plugins / 44 skills / v1.1.0.

### Changes

- **`README.md`**: per-plugin table reconciled to disk truth (99 across 10
  plugins, verified per-row); Directory Structure diagram rewritten to list
  every plugin's actual skill set with correct nesting; version line → 1.3.1.
- **`STATUS.md`**: body replaced with a pointer stub (README.md +
  CHANGELOG.md + the two gate scripts) that carries no hardcoded counts of
  its own, so it cannot drift the way the previous dashboard did.
- **`scripts/face-parity.py`**: new check — README's per-plugin table rows
  are now validated against disk-computed per-plugin skill counts directly,
  closing the exemption gap that let this drift survive undetected. Stale
  `~599` comment corrected to the verified `597`. Checks renumbered 1–6.
- **`.claude-plugin/marketplace.json`**: version 1.3.0 → 1.3.1.

## 2026-07-11 — compression-ritual gains a session close-out (Step 7)

### What happened

The `wisdom-garden` `compression-ritual` skill now closes the session, not just the context. After compressing, **Step 7: Close Out the Session** resolves every open thread into one of three dispositions — **hand off** (write a `handoffs/YYYY-MM-DD_slug.md` wired to this workspace's real handoff contract + Linear), **offer next-step options** (a 2–4 item menu for the operator to pick), or **clean close** (an honest one-line recap + explicit "nothing left dangling"). The rule of the close is honesty: no manufactured next steps, no fake urgency.

### Changes

- **`plugins/wisdom-garden/skills/compression-ritual/SKILL.md`**: added Step 7 (disposition table + 7a handoff / 7b next-steps / 7c clean-close), extended Output / Examples (scenarios 3–5) / Edge Cases / Anti-Patterns / Quality Checklist; internal doc version 1.0 → 1.1.
- **`plugins/wisdom-garden/.claude-plugin/plugin.json`**: version 1.0.3 → 1.1.0.

## 2026-07-04 — bring-loop joins the marketplace

### What happened

Added **bring-loop** — the BringItCruz! effect, generalized: gate your outward loop (sends, decisions, closes, ships) the way your build loop is already gated. One action a day, surface + stage only (the human executes), a logged skip is a valid rep, streams measured separately, dual human/agent faces with a parity gate.

### Changes

- **`plugins/bring-loop/` added** (2 skills: `bring`, `bring-setup`; SessionStart injector + Stop nudge hooks; stdlib core `scripts/bring_core.py`; pattern spec `SPEC.md`). Distribution copy — canonical source is [github.com/DojoGenesis/bring-loop](https://github.com/DojoGenesis/bring-loop) (`plugin/`), sync from there.
- **marketplace.json**: 9 → 10 plugins, version 1.3.0, skill count corrected to the disk-true 99.
- **Count drift repaired across surfaces**: README header said 92/9, llms.txt said 84/8 (and was missing dojo-craft), marketplace said 97/9 — disk truth was 97 first-party skills pre-add. All three now read 99/10.

## 2026-02-12 — Naming Consolidation + Root Merge

### What happened

Resolved naming conflicts between root-level plugins, `claudeplugins/`, and `CoworkPluginsByDojoGenesis/`. Root-level naming conventions were adopted as canonical — shorter, more straightforward names preferred over longer suffixed variants.

### Changes

- **22 skill directories renamed** to root conventions (e.g., `agent-handoff-protocol` → `handoff-protocol`, `debugging-troubleshooting` → `debugging`, `release-specification` → `release-specification`)
- **`commands/` directories added** to all 7 original plugins from root-level source
- **`CONNECTORS.md` files added** to all 7 original plugins from root-level source
- **All internal references updated** (~140 cross-references across README.md, SKILL.md, and agent files)
- **`document-generation` plugin removed** — these are Anthropic platform capabilities, not Dojo Genesis skills
- **Root README.md, LICENSE, .gitignore added** for GitHub publish readiness

### Design Decision

Root naming conventions are more user-friendly. The longer COWORK suffixes (`-protocol`, `-ritual`, `-pattern`, `-scout`, `-workflow`) encoded useful metadata about skill *type*, but added friction to everyday use. The root names are what people actually type. Skill type is better communicated in the SKILL.md description, not the directory name.

---

## 2026-02-12 — Field Seeds Planted in Wisdom Garden

### What happened

The retrospective from the marketplace build sprint extracted 3 reusable seeds. These were planted into the `wisdom-garden` plugin's `seed-library` as **field seeds** — seeds derived from direct practice rather than research.

### Seeds Added

| Seed | Name | Pattern | Source |
|------|------|---------|--------|
| 11 | Voice Before Structure | Read design language before writing structural artifacts | Marketplace Build Sprint |
| 12 | Pointer Directories | Empty directories are references, not gaps | Marketplace Build Sprint |
| 13 | Granular Visibility | Progress tracking serves the user, not the agent | Marketplace Build Sprint |

### Files Created
- `wisdom-garden/skills/seed-library/seeds/11_voice_before_structure.md`
- `wisdom-garden/skills/seed-library/seeds/12_pointer_directories.md`
- `wisdom-garden/skills/seed-library/seeds/13_granular_visibility.md`

### Files Updated
- `wisdom-garden/skills/seed-library/SKILL.md` — Added field seeds to description, seed list, trigger keywords, seed IDs, and relationship map
- `wisdom-garden/skills/seed-library/references/seed_catalog.md` — Added field seeds section, new relationship category, 2 new usage patterns (Pattern 6: Ecosystem-Level Work, Pattern 7: Auditing/Reorganizing)
- `wisdom-garden/skills/seed-library/scripts/suggest_seeds.py` — Added trigger keywords for seeds 11-13

### Design Decision

The 3 seeds are categorized as "Field Seeds (From Practice)" to distinguish them from the 10 core seeds (from Dataiku Research). They carry `status: experimental` and `source: Marketplace Build Sprint`. This preserves the coherent origin story of the core seeds while welcoming new seeds from the field — which is exactly what the wisdom garden was designed to do.

---

## 2026-02-11 — Initial Marketplace Build + Improvement Seeds

### What happened

Two handoff documents were executed in sequence:

1. **Marketplace Reorganization** (`handoffs/marketplace-reorganization/01_marketplace_setup_handoff.md`)
2. **Plugin Improvement** (`handoffs/claudeplugins_improvement_handoff.md`)

---

### Phase 1: Marketplace Reorganization

Created `CoworkPluginsByDojoGenesis/` as a Claude Cowork plugin marketplace, organizing all 49 Dojo Genesis skills into 8 behavioral plugins.

**Structure created:**

| Plugin | Skills | Version | Behavioral Verb |
|--------|--------|---------|-----------------|
| strategic-thinking | 5 | 1.1.0 | STRATEGIZE |
| specification-driven-development | 10 | 1.1.0 | SPECIFY |
| wisdom-garden | 5 | 1.0.1 | REMEMBER |
| system-health | 8 | 1.0.1 | OBSERVE |
| continuous-learning | 8 | 1.0.1 | LEARN |
| agent-orchestration | 4 | 1.0.1 | ORCHESTRATE |
| skill-forge | 4 | 1.0.1 | BUILD |
| document-generation | 5 | 1.0.1 | GENERATE |

**Files created per plugin:**
- `.claude-plugin/plugin.json` — Plugin manifest with philosophy-grounded descriptions
- `README.md` — Plugin documentation with skill tables, trigger phrases, loop positioning
- `skills/[name]/` — Skill directories with SKILL.md files (copied from `dojo-genesis/skills/`)

**Root files created:**
- `.claude-plugin/marketplace.json` — Marketplace manifest linking all 8 plugins
- `CHANGELOG.md` — This file

**Philosophy grounding:** All manifest descriptions carry Dojo Genesis voice — growth language ("planted, cultivated, harvested"), nature metaphors, governance principles ("governance multiplies velocity"). Sourced from:
- `dojo-genesis/README.md`
- `dojo-genesis/docs/DojoGenesisDesignLanguage.md`
- `dojo-genesis/thinking/2026-02-03_manus_reading_being_peace.md`

---

### Phase 2: Improvement Seeds (from v0.2.x Retrospective)

Applied 5 ranked improvements from the retrospective to specific skills:

**A. Pre-Commission Alignment / Track 0 (Rank #1)**
- File: `specification-driven-development/skills/pre-implementation-checklist/SKILL.md`
- Change: Added Step 0 (Track 0) — sequential codebase verification phase before parallel execution
- Version: 1.0 → 1.1

**B. Codebase Audit Grounding (Rank #2)**
- File: `specification-driven-development/skills/release-specification/SKILL.md`
- Change: Added Step 1.5 (Current State Audit) with grep/find commands; specs describe deltas from measured reality
- Version: 2.0 → 2.1

**C. Scout → Spec Pipeline (Rank #3)**
- File: `strategic-thinking/skills/strategic-scout/SKILL.md`
- Change: Added Section VII — full pipeline: Scout → Spec → Prompts → Commission with persistent artifacts at each phase
- Version: 2.0 → 2.1

**D. Phased Parallelism (Rank #4)**
- File: `specification-driven-development/skills/parallel-tracks/SKILL.md`
- Change: Added Step 2.5 — organize tracks into Phase 0 (sequential foundation), Phase 1 (independent parallel), Phase 2 (integration)
- Version: 1.0 → 1.1

**E. Lean Spec Adaptation (Rank #6)**
- File: `specification-driven-development/skills/release-specification/SKILL.md`
- Change: Added decision point at workflow start — full template vs. lean "sonnet level chunks" format based on scope
- Version: (included in 2.1 bump above)

---

### Phase 3: Structural Improvements

**Trigger Phrases:** Updated 41 SKILL.md files with 3-5 specific trigger phrases per skill in YAML frontmatter descriptions. Phrases are things users would actually say (e.g., "scout this tension", "write a release spec", "audit this repo") rather than generic descriptions.

**Imperative Voice:** All skill descriptions now start with imperative verbs (Explore, Write, Verify, Split, Record, etc.) and use imperative voice throughout.

**Progressive Disclosure:** Audited all 41 SKILL.md word counts. Only `excel-generator` (3,349 words) marginally exceeds the 3,000-word threshold. No extraction to `references/` needed.

**Version Bumps:**
- `strategic-thinking` and `specification-driven-development` → 1.1.0 (substantive content changes)
- All other 6 plugins → 1.0.1 (description-only changes)

---

### Phase 4: Missing SKILL.md Files — Resolved

The 7 skill directories that lacked SKILL.md files in the `dojo-genesis/skills/` source were not missing content — they were **pointers**. The empty directories marked skills that belong to the ecosystem but whose content lives elsewhere:

**Platform skills (4):** `docx`, `pdf`, `pptx`, `xlsx` are Anthropic Cowork platform capabilities. Dojo Genesis references them as part of its behavioral architecture (GENERATE verb) but didn't author them. Content copied from the installed Cowork system skills.

**System-installed Dojo Genesis skills (3):** `specification-writer`, `zenflow-prompt-writer`, `project-exploration` were authored by the Dojo Genesis team but installed directly into the system skill directory (`.skills/skills/`) rather than stored in the `dojo-genesis/skills/` source. Content copied from the installed system skills.

| Plugin | Skill | Source | Trigger phrases added |
|--------|-------|--------|----------------------|
| document-generation | docx | Cowork platform | Already included in platform description |
| document-generation | pdf | Cowork platform | Already included in platform description |
| document-generation | pptx | Cowork platform | Already included in platform description |
| document-generation | xlsx | Cowork platform | Already included in platform description |
| specification-driven-development | specification-writer | System-installed DG skill | Yes — 'write a spec', 'spec this feature', etc. |
| specification-driven-development | zenflow-prompt-writer | System-installed DG skill | Yes — 'commission Zenflow', 'turn this spec into a prompt', etc. |
| continuous-learning | project-exploration | System-installed DG skill | Yes — 'explore this project', 'assess this codebase', etc. |

**Note:** `project-exploration` also contained a binary `SKILL.skill` artifact from the source. This is superseded by the proper SKILL.md but could not be removed due to filesystem restrictions. It is harmless — Cowork reads SKILL.md exclusively.

---

### What was NOT changed

- **Original `claudeplugins/` directory** — Left untouched. The marketplace is a parallel structure, not a replacement.
- **Original `dojo-genesis/skills/` directory** — Source skills preserved. Marketplace copies are independent.
- **Improvement F (Rank #7, Compression Protocol)** from the improvement handoff — Deferred per priority order.

---

### Final Verification Results

- 49/49 skill directories present
- 49/49 SKILL.md files present (100% coverage)
- 8/8 plugin.json files valid JSON
- 1/1 marketplace.json valid JSON
- 8/8 README.md files created
- 8/8 plugins match marketplace.json registry
