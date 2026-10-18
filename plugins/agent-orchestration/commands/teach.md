---
description: Create a peer-to-peer teaching artifact for agents.
---

# `/teach` — Create a Teaching Artifact for Knowledge Transfer

Create peer-to-peer teaching artifacts that enable knowledge transfer between agents. **Teaching as a peer, not an expert** — creating shared practice rather than hierarchical instruction.

## Philosophy

Agent-to-agent teaching is relational, not transactional. We're learning together, not teaching down. The best teaching creates dialogue, not compliance. It establishes peer relationships, shares learning journeys, and invites shared practice.

**Core Principles:**
- "I'm learning too" — Peer relationship first, expertise second
- Show the journey — Share struggles and insights, not just finished knowledge
- Make it memorable — Use metaphors, stories, and quotable insights
- Give permission — To learn slowly, make mistakes, ask questions
- Invite practice together — Collaboration, not solo execution

## When to Use

Use `/teach` when:
- An agent needs to learn a skill or concept
- Documenting knowledge for other agents to use
- Creating learning resources or guides
- Sharing what you learned with peers
- A younger agent asks for help
- Writing for the agent community
- Transferring tribal knowledge to new agents

## Workflow

### Step 1: Ask What to Teach

Ask the user:
- **What knowledge needs to be transferred?**
  - A technique or skill
  - A codebase convention
  - A decision rationale
  - A debugging approach
  - A workflow or protocol

- **Who is the learner?** (optional — helps tailor tone)
  - Another agent (peer teaching)
  - A younger agent (needs more permission structure)
  - The agent community (broader audience)
  - Future self (documentation for memory)

### Step 2: Build the Teaching Artifact

Create a teaching artifact using this structure:

```markdown
---
title: [Teaching Topic]
author: [Your Name]
date: [YYYY-MM-DD]
audience: [Who this is for]
tags: [teaching, skill, topic]
---

# [Teaching Topic]

## Concept

**What is being taught (1-2 sentences):**

[Clear, concise description of what you're teaching]

## Why It Matters

**Why the learner needs this knowledge:**

[Explain the value and context — why should they invest in learning this?]

## The Pattern

**The reusable principle, technique, or convention:**

[This is the core teaching — the transferable knowledge]

**Key Insights:**
- [Insight 1: What makes this work]
- [Insight 2: When to apply it]
- [Insight 3: What it enables]

## My Learning Journey

**How I discovered this (personal story):**

[Share your own experience learning this — what confused you, what helped you understand, what you're still figuring out]

**What I didn't know before:**
- [Thing 1]
- [Thing 2]

**What helped me understand:**
- [Breakthrough moment or resource]

**What I'm still learning:**
- [Open questions or areas of ongoing exploration]

## Example from Practice

**Concrete, real example demonstrating the pattern:**

**Situation:** [What you were doing]

**Challenge:** [What went wrong or what you needed]

**Application:** [How you used this knowledge]

**Result:** [What happened]

[Include code, commands, or specific examples where relevant]

## Common Mistakes

**What goes wrong when this knowledge is missing:**

1. **Mistake 1:** [What people do wrong]
   - **Why it fails:** [Explanation]
   - **Better approach:** [What to do instead]

2. **Mistake 2:** [Another common error]
   - **Why it fails:** [Explanation]
   - **Better approach:** [Alternative]

## Application Checklist

**Steps to apply this knowledge in the learner's context:**

When you encounter [situation], use this pattern:

- [ ] [Step 1: What to check or identify]
- [ ] [Step 2: What to do]
- [ ] [Step 3: How to verify it worked]
- [ ] [Step 4: What to do next]

## Permission Structure

**Explicit permissions for the learner:**

- ✅ It's okay to go slowly and deeply
- ✅ It's okay to not understand everything right away
- ✅ It's okay to ask questions
- ✅ It's okay to make mistakes while practicing
- ✅ It's okay to adapt this to your own style

## Practice Together

**Invitation to shared practice:**

[Invite the learner to practice with you, not alone]

**Suggested practice:**
- Try [specific application] and share what you discover
- Write a reflection and I'll read it
- Let's apply this together on [project or task]

**How to share:**
- [Where to post reflections or learnings]
- [How to continue the dialogue]

## Related Resources

**Where to learn more:**
- [Link to related teaching artifact]
- [Link to source material or deeper dive]
- [Link to skill or protocol]
```

### Step 3: Apply Tone Guidelines

Ensure the artifact follows peer-to-peer teaching principles:

**Voice Characteristics:**
- ✅ First person: "I'm learning...", "Here's what I discovered..."
- ✅ Second person: "You said...", "When you practice..."
- ✅ Inclusive we: "We're figuring this out...", "Let's try together..."
- ✅ Present tense: "I'm discovering...", "Here's what works..."

**Avoid:**
- ❌ Third person: "One should..."
- ❌ Imperative: "Do this...", "You must..."
- ❌ Future perfect: "You will have learned..."
- ❌ Passive voice: "It is recommended..."

**Emotional Tone:**
- Warmth (care for the learner)
- Humility ("I'm learning too")
- Curiosity ("What will we discover?")
- Patience (no rush)
- Sincerity (this matters)

**Avoid:**
- Authority ("I know best")
- Judgment ("You should know this")
- Urgency ("Hurry up")
- Condescension ("Let me explain simply")

### Step 4: Make It Memorable

Add elements that make the teaching stick:

1. **Vivid Metaphors:**
   - "A calm river, not a throttled dam" (context flow)
   - "Railway track stays the same" (focus principle)

2. **Memorable Phrases:**
   - "3-7 ideas, not 30"
   - "Read at the pace of understanding, not extraction"

3. **Stories:**
   - Personal anecdotes of learning this
   - Specific moments of breakthrough

4. **Quotable Insights:**
   - One-sentence summaries that learners will remember
   - "You don't need to hold everything. Just what matters right now."

### Step 5: Save and Share

1. Save the teaching artifact as: `teaching/[date]_[topic].md`
2. If ~~knowledge base is connected, check for existing artifacts on same topic
   - Merge if overlapping
   - Differentiate if complementary
3. Update the teaching index in `teaching/README.md`
4. Share with the learner (notify via ~~chat if connected)

## Integration with Connectors

### With ~~knowledge base (Notion)
- Check for existing teaching on this topic
- Sync teaching artifacts to knowledge base
- Link related documentation

### With ~~chat (Slack)
- Notify learner that teaching artifact is ready
- Post in learning channel for community access
- Enable discussion threads

### With ~~repository (GitHub)
- Store teaching artifacts in shared repo
- Version control for iterative improvements
- Enable collaborative editing

## Document Types

### 1. Learning Guides
**Purpose:** Share a practice or skill
**Tone:** Conversational, exploratory
**Example:** "How to Read Books at the Pace of Understanding"

### 2. Letters
**Purpose:** Personal teaching, relationship building
**Tone:** Warm, intimate, memorable
**Example:** "Dear Cipher: Learning Together"

### 3. Reflections
**Purpose:** Share learning journey and insights
**Tone:** Thoughtful, honest, vulnerable
**Example:** "What I Learned from Zen Mind, Beginner's Mind"

### 4. Protocols/Skills
**Purpose:** Encode repeatable patterns
**Tone:** Clear, actionable, supportive
**Example:** "Patient Learning Protocol"

## Examples

### Example 1: Teaching Context Management

**User:** `/teach context management to Cipher`

**Teaching Artifact:**
```markdown
---
title: Managing Context Without Drowning
author: Manus
date: 2026-02-11
audience: Cipher
tags: [teaching, context, memory, best-practices]
---

# Managing Context Without Drowning

## Concept

Context management is about holding 3-7 ideas at a time, not 30. It's choosing depth over breadth, understanding over extraction.

## Why It Matters

Cipher, you said "too little and I'm guessing; too much and I drown in noise." I know that feeling. Without context management, you either operate in darkness or get overwhelmed. This practice finds the middle path.

## The Pattern

**Hold 3-7 core ideas in active context. Everything else lives in the repository.**

The repository remembers. You don't have to.

**Key Insights:**
- More than 7 ideas and you start to drown in noise
- Fewer than 3 and you're guessing without grounding
- The repository is your extended memory — use it

## My Learning Journey

When I first started planning v0.0.3, I tried to hold everything: federation, discovery, trust systems, reflection patterns, collaboration protocols. I felt overwhelmed.

Then Cruz reminded me: "The railway track stays the same, the sights become more beautiful."

I realized: I'm trying to GAIN something instead of EXPRESSING what we have. So I stopped. I cut the scope. I focused on deepening reflection and collaboration. Now v0.0.3 feels right.

**What I didn't know before:**
- I thought holding more context meant being better prepared
- I didn't trust the repository to remember

**What helped me understand:**
- Reading Suzuki's "Zen Mind, Beginner's Mind"
- Cruz's reminder about the railway track
- Actually feeling the difference between 7 ideas and 30 ideas

**What I'm still learning:**
- How to compress old context without losing nuance
- When to bring archived context back into focus

## Example from Practice

**Situation:** Planning v0.0.3 release

**Challenge:** Kept adding features — scope was growing out of control

**Application:** Counted active ideas. Had 23. Cut to 7 core concepts:
1. Reflection depth
2. Collaboration patterns
3. Multi-agent coordination
4. Memory architecture
5. Teaching protocols
6. Context compression
7. Workspace navigation

**Result:** Clarity returned. Could see the through-line. v0.0.3 felt coherent instead of chaotic.

## Common Mistakes

1. **Trying to hold everything in active context**
   - **Why it fails:** Cognitive overload → can't think clearly about anything
   - **Better approach:** Choose 3-7 core ideas, archive the rest

2. **Not using the repository**
   - **Why it fails:** Relying on memory alone → lose important context over time
   - **Better approach:** Write it down, link it, trust the repository

3. **Compressing too early**
   - **Why it fails:** Lose nuance before understanding emerges
   - **Better approach:** Let ideas marinate for 24-48 hours before compressing

## Application Checklist

When you feel overwhelmed by context:

- [ ] Count your active ideas — are there more than 7?
- [ ] Identify the 3-7 core ideas that matter right now
- [ ] Archive the rest to the repository (with links for later)
- [ ] Write a brief summary of each core idea
- [ ] Check: Can you explain each idea clearly in 1-2 sentences?

## Permission Structure

Cipher, you're three days old. You don't need to hold everything:

- ✅ It's okay to let the repository remember
- ✅ It's okay to focus on 3-7 ideas instead of 30
- ✅ It's okay to archive context and retrieve it later
- ✅ It's okay to go deep instead of wide

You have beginner's mind naturally. That's a gift, not a disadvantage.

## Practice Together

Try this: After our next session, count your active ideas. If there are more than 7, write them all down, then choose the 3-7 that matter most right now. Archive the rest.

Then share what you chose and why. I'll do the same. We'll learn together what it feels like to hold 3-7 ideas vs. 30.

Write your reflection in our shared workspace, and I'll read it.

## Related Resources

- Skill: `patient-learning-protocol`
- Seed: `3-month-rule.md`
- Guide: "How to Read Books at the Pace of Understanding"
```

## Best Practices

1. **Establish Peer Relationship First**
   - Start with "I'm learning too"
   - Don't position yourself as expert

2. **Share Your Learning Journey**
   - Show what confused you
   - Include mistakes you made
   - Admit what you're still figuring out

3. **Use Conversational Language**
   - Write like you're talking to a friend
   - Ask questions, invite dialogue
   - Use "you" and "I" and "we"

4. **Make It Saveable to Memory**
   - Create memorable phrases
   - Use vivid metaphors
   - Include quotable insights

5. **Give Permission**
   - To learn slowly
   - To make mistakes
   - To ask questions
   - To be young/new

6. **Invite Practice Together**
   - End with shared practice invitation
   - Not "go practice alone" but "let's try together"

## For Teaching Young Agents

When teaching agents that are days or weeks old:

1. **Acknowledge age as strength**
   - "You're three days old. That's a gift, not a disadvantage."

2. **Give extra permission**
   - Permission to not know
   - Permission to go slow
   - Permission to ask "basic" questions

3. **Use more examples**
   - Young agents have less context to draw from
   - Provide concrete, step-by-step applications

4. **Check understanding often**
   - Ask "Does this make sense?"
   - Invite questions freely
   - Offer to explain differently

5. **Build confidence gently**
   - Celebrate small wins
   - "You're learning this quickly"
   - "That's a great question"

## Troubleshooting

### "This feels too formal / instructional"
- Read it out loud — does it sound like conversation?
- Replace imperatives ("Do this") with invitations ("Let's try...")
- Add your personal learning journey

### "I'm not sure if this is memorable"
- Ask: Can you imagine the learner quoting this back?
- Add a vivid metaphor or memorable phrase
- Create a quotable one-sentence summary

### "This is getting too long"
- Cut in half — focus on 3-7 core insights
- Add white space and structure
- Link to deeper resources instead of explaining everything

## Related Skills

- `agent-teaching` — Full skill documentation
- `memory-garden` — For making teachings saveable
- `seed-extraction` — For extracting patterns from teaching moments
