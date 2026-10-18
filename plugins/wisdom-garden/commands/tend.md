---
description: Write a daily note and short reflection.
---

# /tend -- Daily Note and Reflection

**Argument hint:** `<optional: what you worked on today>`

---

## Philosophy

Tending is the daily practice that keeps the garden alive. A structured daily note is not busywork -- it's the soil preparation that makes future seeds possible. By ending each day with a brief, intentional reflection, you ensure that nothing important slips through the cracks, and you plant the question marks that tomorrow's work will answer.

---

## Workflow

### Step 1: Gather Today's Context

If the user provided a description of their day, use it as the starting point.

If **~~chat** is connected, pull recent activity from the relevant time period to supplement.

If **~~knowledge base** is connected (e.g., a project tracker), pull recent updates to pre-fill activities.

If neither connector is available and the user provided no description, ask:
- "What did you work on today?"
- "Were there any decisions made or insights discovered?"

### Step 2: Write the Daily Note

Create a structured daily note with all 5 sections:

```markdown
# Daily Note: YYYY-MM-DD

**Tier:** A (Raw Daily Note)
**Type:** daily-note

---

## Key Activities

- [Activity 1: brief description of what happened and what it produced]
- [Activity 2: brief description of what happened and what it produced]
- [Activity 3: brief description of what happened and what it produced]

## Decisions Made

### [Decision Title]

**Context:** [What led to this decision]
**Chosen:** [What was decided]
**Rationale:** [Why -- even 1 sentence is valuable]

## Seeds Discovered

### [Seed Name]

**Pattern:** [Brief description of the reusable insight]
**Trigger:** [When this might apply again]

> *Would you like to formally plant this seed? Use `/plant [seed name]` to cultivate it.*

## Open Questions

- [ ] [Question that needs resolution]
- [ ] [Uncertainty or ambiguity to carry forward]

## Tomorrow's Growth

- [ ] [What comes next]
- [ ] [Follow-up or continuation]
```

### Step 3: Populate Each Section

Work through the sections with the user:

**Key Activities** (required):
- Aim for 2-3 bullet points, not a full log
- Focus on what was *produced* or *decided*, not the mechanics of doing it
- Apply the 3-month rule: would this activity matter in 3 months? If no, keep it to one line

**Decisions Made** (if any):
- Even small decisions deserve 1 sentence of rationale
- If no decisions were made today, note "No significant decisions today" and move on

**Seeds Discovered** (if any):
- Look for patterns, insights, or lessons from today's work
- For each seed found, offer to formalize with `/plant`
- If no seeds are visible, that's fine -- not every day produces seeds

**Open Questions** (if any):
- Questions that emerged but weren't answered
- Uncertainties to investigate tomorrow
- These often become tomorrow's seeds

**Tomorrow's Growth** (required):
- 1-3 concrete next steps
- Frame as growth, not tasks: "Continue cultivating the auth flow" not "Work on auth"

### Step 4: Save and Confirm

Save the daily note to: `notes/YYYY-MM-DD_daily.md`

Present a brief summary:

> "Today's note is planted. [N activities], [N decisions], [N seeds discovered], [N open questions]. Your garden grows."

If seeds were discovered, remind the user they can formalize them with `/plant`.

---

## Quality Gate

Before delivering, verify every item passes:

- [ ] **All 5 sections present** (Key Activities, Decisions, Seeds, Open Questions, Tomorrow's Growth)
- [ ] **Metadata complete** (type: daily-note, tier: A, date)
- [ ] **Activities are concise** (2-3 bullets, not a full log)
- [ ] **Decisions include rationale** (even 1 sentence)
- [ ] **Seeds have pattern and trigger** (not just a vague observation)
- [ ] **Growth language throughout** -- no "store," "retrieve," "create," or "delete"

If **any check fails**, fix it before delivering.

---

## Output

The daily note saved at:

```
notes/YYYY-MM-DD_daily.md
```
