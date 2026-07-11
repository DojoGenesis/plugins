---
name: compression-ritual
model: sonnet
description: Produces markdown memory artifacts (conversation summaries, seed files, philosophical reflections, doc updates) and a dated compression log by distilling a long conversation into its essential decisions and learnings. For the lighter, routine end-of-session wrap-up, use `session-compression` instead — this skill is for a long conversation that needs the fuller multi-artifact treatment. Use when: "compress this context", "distill this conversation", "create a memory artifact", "condense this history", "extract key wisdom before handoff".
category: remember-continue

inputs:
  - name: conversation_context
    type: string
    description: The long conversation or session context to compress into memory artifacts
    required: true
outputs:
  - name: memory_artifacts
    type: ref
    format: cas-ref
    description: Markdown memory artifacts (conversation summaries, seed files, philosophical reflections, doc updates) and dated compression log
---

# Context Compression Ritual Skill

**Version:** 1.1  
**Created:** 2026-02-04  
**Updated:** 2026-07-11 — added Step 7: Close Out the Session (handoff / next-step options / clean close)  
**Author:** Manus AI  
**Purpose:** To provide a mindful, repeatable ritual for compressing long conversation histories into smaller, more potent memory artifacts — and to close the session cleanly, so that wisdom is preserved, context overload is prevented, and no carry-forward work is silently lost.

---

## I. The Philosophy: The Art of Letting Go

An agent's context window is like a working memory. It is finite and precious. To fill it with raw, unprocessed history is to invite distraction and confusion. The Context Compression Ritual is the **Art of Letting Go**—a conscious practice of choosing what is essential to keep and what can be respectfully released.

This is not a destructive act, but a creative one. We are not deleting history; we are distilling it. We transform the raw material of conversation into the refined artifacts of wisdom: philosophical reflections, key decisions, and reusable seeds of practice. This ritual ensures that our memory remains potent and relevant, a source of clarity rather than noise.

---

## II. When to Use This Skill

-   **After a long and complex conversation:** (e.g., more than 20-30 turns).
-   **At the end of a major work session or sprint.**
-   **When the context feels "heavy" or "noisy."**
-   **Before handing off a project to another agent.**
-   As a regular, scheduled practice (e.g., end of day) to maintain cognitive hygiene.

---

## III. The Compression Workflow

### Step 1: Signal the Intent

Announce the intention to perform the ritual. This frames the activity as a deliberate and mindful practice.

**Example:** "This has been a long and fruitful conversation. To preserve the wisdom we've generated, I will now perform the Context Compression Ritual."

### Step 2: Review the Transcript

Read through the recent conversation history with a specific intention: to identify the moments of significance. Look for:

-   **Key Decisions:** Moments where a choice was made that altered the course of the project.
-   **Profound Insights:** "Aha!" moments, new understandings, or philosophical reflections.
-   **Actionable Learnings:** Concrete lessons that should inform future behavior.
-   **Reusable Patterns:** Ideas or workflows that could be generalized into seeds or skills.
-   **Unresolved Questions:** Important questions that were raised but not yet answered.

### Step 3: Choose the Right Vessel

For each significant moment identified, determine the appropriate "vessel" to hold its essence. Not all wisdom takes the same form.

| Artifact Type | Location | Purpose |
| :--- | :--- | :--- |
| **Philosophical Reflection** | `thinking/` | To explore the "why" behind our work, the deeper meanings and patterns. |
| **Conversation Summary** | `conversations/` | To document the key decisions and outcomes of a specific discussion. |
| **Dojo Seed** | `seeds/` | To capture a reusable pattern of thinking or problem-solving. |
| **Documentation Update** | `docs/` or `README.md` | To integrate a key decision or learning into the project's official record. |

### Step 4: Write the Artifacts

Create the new markdown files in their appropriate locations. Write with the intention of distillation—capture the essence, not the raw transcript. Link between artifacts where appropriate (e.g., a reflection might reference a specific conversation summary).

### Step 5: Create a Compression Log (Optional but Recommended)

Create a log file that documents what was compressed and where it was stored. This provides a meta-record of the compression itself.

**Example:** `thinking/2026-02-04_compression_log.md`

### Step 6: Commit to AROMA

Commit the new artifacts to the repository with a clear commit message.

**Commit Message Convention:**
`feat(memory): Compress conversation from [Date]`

### Step 7: Close Out the Session

Compression preserves what *happened*; close-out decides what happens *next*. The ritual is not finished until every open thread has a disposition. Before ending, resolve the session into one of three — and never leave it dangling with unstated carry-forward.

| Disposition | Choose when | Produce |
| :--- | :--- | :--- |
| **Hand off** | Work remains for a later session, a different machine, or another person | a handoff note (+ a tracked task/issue if a person must act) |
| **Next-step options** | Natural pause; clear continuations exist but nothing needs a formal handoff | A 2–4 item menu, one line each, for the operator to pick |
| **Clean close** | The thread is complete and nothing is pending | A one-line recap + an explicit "nothing left dangling" + an honest sign-off |

These are **not exclusive** — a session may write a handoff *and* offer next steps. Choose every disposition that applies, then end.

**7a. Carry-forward work → write a handoff.**
If work remains that a later session, a different machine, or another person must pick up, write a handoff so it is not silently lost — using whatever handoff or task mechanism your workspace already has. Follow the workspace's convention; do not invent a competing format.

-   **If your workspace defines a handoff format or registry, use it** (a `handoffs/` directory, an issue tracker, a ticket queue — check the project's conventions).
-   **Otherwise, write a dated note** (e.g. `handoffs/YYYY-MM-DD_short-slug.md`) with a clear body: `## Why` · `## Do this` · `## Verify` · `## Rollback`. Name who or what picks it up next, and how urgent it is.
-   For a richer package (objective, required-context file list, definition-of-done, constraints), invoke the `handoff-protocol` skill and land its output as the handoff body.
-   Mirror anything a person must act on into your task tracker (create or update the issue), so it stays visible outside this session.

**7b. No handoff, but clear continuations → offer next-step options.**
When the thread is at a natural pause with obvious next moves but nothing that must be *formally* handed off, present a short menu — 2 to 4 concrete options, one line each, each a real action the operator could pick — and stop. Let them choose the direction rather than assuming it.

**7c. Nothing pending → close cleanly.**
When the thread is genuinely complete and nothing is carried forward, close **neatly, politely, and honestly**: name what was accomplished in a sentence, confirm explicitly that nothing is left dangling, and sign off. Honesty is the rule of the close — do not manufacture next steps, invent urgency, or pad the ending to seem busy. If it is done, say it is done. A clean, quiet close is the natural completion of the Art of Letting Go.

---

## IV. Compression Log Template

```markdown
# Compression Log: [Date]

**Source:** Conversation history from [Start Time] to [End Time]
**Purpose:** To distill key insights and reduce context window load.

---

## Artifacts Created

| Type | Path | Description |
| :--- | :--- | :--- |
| **Reflection** | `thinking/[...].md` | [A summary of the philosophical reflection.] |
| **Seed** | `seeds/[...].md` | [The name and purpose of the new seed.] |
| **Decision** | `conversations/[...].md` | [The key decision that was documented.] |
| **Doc Update** | `docs/[...].md` | [The documentation that was updated.] |

---

## Key Insights Preserved

-   [Insight 1]
-   [Insight 2]

## Context Released

-   [e.g., Raw conversational turns, intermediate steps, dead-end explorations]
```

---

## V. Best Practices

-   **Be Ruthless, But Respectful:** The goal is to reduce noise, but do so with care. Don't discard something that might be important later.
-   **Favor Wisdom Over Data:** Prioritize the "why" and the "how" over the raw "what."
-   **Link, Don't Repeat:** If a concept is already documented, link to it rather than rewriting it.
-   **The Shorter, The Better:** A compressed artifact should be significantly shorter than the source conversation.
-   **Perform the Ritual Regularly:** The more frequently you do this, the less daunting it becomes.

---

## Output

- One or more markdown files written to their appropriate locations (`thinking/`, `conversations/`, `seeds/`, or `docs/`)
- A compression log at `thinking/YYYY-MM-DD_compression_log.md` documenting what was compressed, what was retained, and what was released
- A git commit with message `feat(memory): Compress conversation from [Date]`
- **A session disposition (Step 7):** a handoff at `handoffs/YYYY-MM-DD_slug.md` for carry-forward work, a short next-step options menu, and/or a clean honest sign-off — whichever apply

## Examples

**Scenario 1:** User says "compress this context — we've been going for 40 turns" → ritual identifies 2 decisions, 1 seed, and 1 philosophical insight, writes 3 files, creates a compression log, and commits all artifacts.

**Scenario 2:** User says "extract key wisdom before we hand this off" → ritual reads the conversation, writes a `conversations/handoff-summary.md` with key decisions and unresolved questions, and one new seed file, then commits.

**Scenario 3 (close-out — hand off):** Session ends with a migration half-finished that a later session must complete → ritual compresses as usual, then in Step 7 writes a dated `handoffs/…` note with `Why`/`Do this`/`Verify`/`Rollback`, opens a tracked issue for it, and closes by naming the handoff.

**Scenario 4 (close-out — next steps):** Session reaches a natural pause; nothing must be formally handed off → ritual compresses, then offers a 2–4 item menu ("(a) wire the new endpoint into the gateway, (b) write tests for the parser, (c) draft the ADR") and stops for the operator to choose.

**Scenario 5 (close-out — clean close):** A short, fully-resolved session → ritual notes compression is optional, and closes neatly and honestly: one-line recap, an explicit "nothing is left dangling," and a brief sign-off. No invented next steps.

## Edge Cases

- If the conversation is fewer than 20 turns, note that compression is optional and ask whether the user wants to proceed anyway.
- If a compression log already exists for today's date, append to it rather than creating a duplicate.
- If it is unclear whether work should be handed off, default to **writing the handoff** — an unclaimed thread is cheaper to close later than a dropped one is to recover. When genuinely nothing carries forward, prefer the clean close over inventing a handoff.
- If your workspace enforces a specific handoff-authoring path (a write guard, a registration script, a required tool), follow it rather than writing the file directly — check the project's conventions before authoring the handoff.

## Anti-Patterns

- Skipping the compression log — without the log, there is no record of what was released, making the compression irreversible and opaque.
- Writing raw transcript excerpts into the artifact files — compression means distillation to essence, not copy-paste of conversation turns.
- Ending the session with no disposition — leaving carry-forward work unstated so it is silently lost is the failure Step 7 exists to prevent.
- Manufacturing next steps or fake urgency at the close — if the thread is done, an honest clean close is correct; padding it to seem busy is dishonest and adds noise.

---

## Quality Checklist

Before closing the ritual, verify:

- [ ] Every artifact has been placed in the correct vessel (`thinking/`, `conversations/`, `seeds/`, or `docs/`)
- [ ] Each artifact is a distillation (shorter than the source; no raw transcript blocks)
- [ ] The compression log exists for today's date and lists every artifact created
- [ ] The compression log includes a "Context Released" section naming what was let go
- [ ] All artifacts are linked to one another where relevant (reflection → conversation, seed → reflection)
- [ ] The git commit has been made with message `feat(memory): Compress conversation from [Date]`
- [ ] The resulting context (if continuing) is meaningfully shorter and cleaner than before the ritual
- [ ] **Step 7 disposition is set:** carry-forward work has a handoff (in your workspace's format, with a tracked task if a person must act), or next-step options were offered, or the session was closed cleanly — and no open thread was left dangling
- [ ] Any close-out that claims "done" is honest — no invented next steps, no manufactured urgency

---

## Related Skills

- `session-compression` — applies compression to a structured memory garden; use after compression-ritual when working inside a Dojo memory path
- `seed-extraction` — extract a reusable pattern from the session; pairs with compression-ritual when a seed candidate is identified during review
- `session-lifecycle-automation` — automates the session-end trigger so the compression ritual fires without manual invocation
- `continuity-ledger` — deposits decisions and open items across sessions; complements the compression log
