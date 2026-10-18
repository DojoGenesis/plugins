---
description: Map a system with semantic clusters.
---

# /map-system -- Map Behavioral Architecture Using Semantic Clusters

**Argument hint:** `<repository path, URL, or 'this project'>`

---

## Philosophy

Every codebase has two architectures: the filesystem architecture (where files live) and the behavioral architecture (what the system *does*). Most people only see the first. Semantic clusters make the second visible by grouping components under action verbs -- revealing capabilities, gaps, coupling risks, and architectural confusion that directory trees hide.

---

## Workflow

### Step 1: Inventory

**Goal:** List every significant component before clustering.

1. Walk the filesystem and identify all significant components (files, modules, packages, services).
2. For each component, record: name, location, approximate LOC, and current status.
3. If `~~repository` is connected, use it to access the codebase. Otherwise, work from the local path.

### Step 2: Assign Verbs

**Goal:** Label each component with the action verb that describes what it *does*.

Use the 13 starter verbs as the baseline vocabulary:

| Verb | Emoji | What It Means |
|---|---|---|
| CONVERSE | 🗣️ | Real-time communication with users |
| REASON | 🧠 | Thinking, planning, deciding |
| REMEMBER | 💾 | Storing and recalling knowledge |
| OBSERVE | 👁️ | Watching and reporting |
| LEARN | 📚 | Adapting based on feedback |
| ACT | 🔧 | Executing side effects |
| PROTECT | 🛡️ | Enforcing boundaries |
| CONNECT | 🔌 | Integrating externally |
| PRESENT | 🎨 | Rendering UI |
| PERSIST | 💿 | Storing data durably |
| BUILD | 🏗️ | Building, testing, shipping |
| THINK | 💭 | Meta-cognition about itself |
| ORCHESTRATE | 🎼 | Coordinating multi-step work |

**Rules:**
- Most components map to **one** verb -- pick the primary purpose.
- Some components legitimately serve **two** verbs (cross-cluster) -- note both.
- **Three or more** verbs = flag as architectural concern (doing too much).
- If a component doesn't fit any verb, it might be dead code, or you may need a **custom verb**.

**Custom verb test:** Can someone read just the verb name and guess what kinds of components belong in that cluster? If yes, it's a good verb.

### Step 3: Build Cluster Tables

**Goal:** Organize components into verb-grouped tables.

For each active verb, create a subsection:

```markdown
### [emoji] VERB -- [Short Description]
> [One sentence explaining this capability.]

| Component | Location | Status | LOC |
|-----------|----------|--------|-----|
| [Name] | [path/] | [emoji] | [~number] |

**Health:** [emoji] [one-line assessment]
**Audit Notes:** [technical details, risks -- 1-2 lines]
```

### Step 4: Identify Cross-Cluster Components

**Goal:** Surface integration points and coupling risks.

```markdown
### Cross-Cluster Components
| Component | Directory | Primary Cluster | Secondary | Notes |
|-----------|-----------|----------------|-----------|-------|
| [Name] | [path/] | [VERB] | [VERB] | [Why] |
```

Components that serve multiple clusters are where changes in one capability can break another.

### Step 5: Identify Orphans

**Goal:** Find significant code that doesn't map to any cluster.

Walk the directory tree and check: is every significant directory represented in at least one cluster?

Orphan directories signal one of three things:
1. **Dead code** that should be removed.
2. **An emerging capability** that deserves its own verb.
3. **A gap in your analysis** that needs a second look.

Document orphans explicitly. Don't sweep them under the rug.

### Step 6: Write Health Assessments

**Goal:** Rate each cluster's health.

For each cluster, write:
- **Health line:** Overall emoji + one-sentence verdict.
- **Audit Notes line:** Key constraints, risks, or technical details.

Use honest assessments: GREEN for healthy and active, YELLOW for gaps or debt, RED for broken or critical issues.

### Step 7: Save the Map

Save as `docs/audits/[YYYY-MM-DD]_behavioral_architecture_[project].md`.

---

## Quality Gate

Before delivering, verify:

- [ ] Every significant component maps to at least one cluster
- [ ] No cluster has fewer than 2 components (merge if so)
- [ ] No cluster has more than 20 components (split if so)
- [ ] Cross-cluster components are explicitly listed
- [ ] Orphan directories are documented and explained
- [ ] Each cluster has a health assessment with emoji + notes
- [ ] Custom verbs (if any) pass the "can you guess the contents?" test
- [ ] The cluster map covers both frontend and backend (if applicable)
- [ ] LOC estimates are approximate but not fictional
- [ ] The map tells a coherent story about what the system does
- [ ] 4-8 clusters for small projects, 8-15 for large ones

---

## Output

```
docs/audits/[YYYY-MM-DD]_behavioral_architecture_[project].md
```
