---
description: Review and curate the memory garden entries.
---

# /harvest -- Review and Curate the Memory Garden

**Argument hint:** `<optional: specific area or time period to review>`

---

## Philosophy

A garden left unattended grows wild. Harvesting is the practice of walking through your memory garden with intention -- assessing what has matured, what needs attention, and what should be composted to make room for new growth. This is not a passive review; it's active curation that keeps the garden productive and navigable.

---

## Workflow

### Step 1: Survey the Garden

Scan the workspace for all memory artifacts:

| Location | What to Look For |
|---|---|
| `seeds/` | Planted seeds -- are they being cultivated? |
| `notes/` | Daily notes -- any overdue for compression? |
| `artifacts/` | Reflections, summaries, decisions -- still relevant? |
| `compressions/` | Compression logs -- recent activity? |
| `reports/` | Previous health reports -- trends? |

If **~~knowledge base** is connected, also scan connected docs for orphaned artifacts or wisdom that should be brought into the garden.

If the user specified a time period or area, focus the survey there. Otherwise, survey the entire garden.

### Step 2: Assess Each Tier

Walk through every tier and evaluate each artifact's current placement:

#### Tier A: Raw Daily Notes (1-3 day lifespan)

For each Tier A artifact:
- **Age check:** Is it older than 3 days?
- **Seed check:** Does it contain unplanted seeds?
- **Decision check:** Are there undocumented decisions?

**Recommendations for Tier A items:**
| Condition | Action |
|---|---|
| Older than 3 days, contains seeds | Promote seeds to Tier B via `/plant`, then compress the note |
| Older than 3 days, routine activities | Compress or compost |
| Older than 7 days, any state | Overdue -- compress immediately |
| Less than 3 days old | Leave in Tier A |

#### Tier B: Curated Wisdom (permanent)

For each Tier B artifact:
- **Relevance check:** Still applicable? Not superseded by newer wisdom?
- **Accuracy check:** Still true? Has context changed?
- **Duplication check:** Does this overlap with another Tier B artifact?

**Recommendations for Tier B items:**
| Condition | Action |
|---|---|
| Still relevant and accurate | Keep, no action |
| Superseded by newer insight | Merge or compost the older version |
| Partially stale | Update the stale portions |
| Duplicated elsewhere | Consolidate into single source of truth |

#### Tier C: Compressed Archive (read-only)

For each Tier C artifact:
- **Resurrection check:** Is there a reason to surface this back to Tier B?
- **Completeness check:** Was anything missed during the original compression?

**Recommendations for Tier C items:**
| Condition | Action |
|---|---|
| No reason to revisit | Leave in archive |
| Contains insight relevant to current work | Surface relevant portion back to Tier B |

### Step 3: Apply the 3-Month Rule

For every Tier A artifact older than 3 days, make a specific recommendation:

- **Promote:** Extract valuable content to Tier B (seeds, decisions, insights)
- **Compress:** Reduce to a 1-2 sentence summary in a Tier C archive
- **Compost:** Release completely -- it won't matter in 3 months

Present each recommendation with rationale. Do not make generic suggestions like "review your notes." Every recommendation must name the specific artifact and the specific action.

### Step 4: Surface Connections

Look across the garden for patterns:

- **Seeds that relate to each other** -- Could they be merged or grouped?
- **Insights that compound** -- Does seed A + seed B = a larger pattern?
- **Patterns that repeat** -- Is the same lesson appearing multiple times? (If so, it may deserve elevation to a skill via `/elevate-seed` from skill-forge)
- **Gaps** -- Are there domains or areas with no seeds planted?

### Step 5: Produce the Garden Health Report

Write a structured report:

```markdown
# Garden Health Report: YYYY-MM-DD

---

## Garden Overview

| Tier | Total | Healthy | Needs Attention | Overdue |
|---|---|---|---|---|
| A (Raw Notes) | [N] | [N] | [N] | [N] |
| B (Curated Wisdom) | [N] | [N] | [N] | [N] |
| C (Compressed Archive) | [N] | [N] | [N] | [N] |
| **Total** | [N] | [N] | [N] | [N] |

## Recent Plantings (Last 7 Days)

- [Seed/artifact name]: [Brief description]

## Stale Items Requiring Action

| Artifact | Current Tier | Age | Recommendation |
|---|---|---|---|
| [Name] | [Tier] | [Days] | [Promote / Compress / Compost] |

## Connections Discovered

- [Pattern 1]: [Seeds/artifacts that relate]
- [Pattern 2]: [Seeds/artifacts that relate]

## Recommended Actions

1. [Specific action with specific artifact]
2. [Specific action with specific artifact]
3. [Specific action with specific artifact]

## Garden Health Verdict

**[Thriving / Healthy / Needs Attention / Overgrown]**

[1-2 sentences explaining the verdict and the single most important action to take]
```

Save to: `reports/YYYY-MM-DD_garden_health.md`

---

## Quality Gate

Before delivering, verify every item passes:

- [ ] **Every tier assessed** with specific recommendations (not generic advice)
- [ ] **3-month rule applied** to every Tier A artifact older than 3 days
- [ ] **Connections surfaced** between related seeds and artifacts
- [ ] **Health report produced** with counts, stale items, and verdict
- [ ] **Every recommendation names a specific artifact** and a specific action
- [ ] **Growth language only** -- no "store," "retrieve," "create," or "delete"

If **any check fails**, fix it before delivering.

---

## Output

The garden health report saved at:

```
reports/YYYY-MM-DD_garden_health.md
```

Plus any actions taken during the harvest (promotions, compressions, composting).
