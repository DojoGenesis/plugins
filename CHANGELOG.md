# Changelog — CoworkPluginsByDojoGenesis

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
