# A+ Specification Template

Full template for strategic and architectural specs. Each part maps to a proportional section of the document.

---

## Part 1: Vision & Context (10-15% of document)

```markdown
# [Project Name] v[X.X.X]: [Memorable Tagline]

**Author:** [Your Name]
**Status:** [Draft | Final | Approved]
**Created:** [Date]
**Grounded In:** [What this builds on - previous versions, research, feedback]

## 1. Vision

> A single, compelling sentence that captures the essence of this release.

**The Core Insight:**
[2-3 paragraphs explaining WHY this release matters, what problem it solves, and how it advances the overall vision]

**What Makes This Different:**
[2-3 paragraphs explaining what makes this approach unique, innovative, or better than alternatives]

## 2. Goals & Success Criteria

**Primary Goals:**
1. [Specific, measurable goal]
2. [Specific, measurable goal]
3. [Specific, measurable goal]

**Success Criteria:**
- [Concrete, testable criterion]
- [Concrete, testable criterion]
- [Concrete, testable criterion]

**Non-Goals (Out of Scope):**
- [What this release explicitly does NOT include]
- [What is deferred to future versions]
```

---

## Part 2: Technical Architecture (40-50% of document)

```markdown
## 3. Technical Architecture

### 3.1 System Overview

[High-level diagram or description of how components fit together]

**Key Components:**
1. **[Component Name]** - [Purpose and responsibility]
2. **[Component Name]** - [Purpose and responsibility]
3. **[Component Name]** - [Purpose and responsibility]

### 3.2 [Feature/Component 1] - Detailed Design

**Purpose:** [What this component does and why it's needed]

**Backend Implementation (Go):**

```go
package [package_name]

type [StructName] struct {
    Field1 string `json:"field1"`
    Field2 int    `json:"field2"`
}

func (s *[StructName]) [MethodName]() error {
    return nil
}
```

**Frontend Implementation (React/TypeScript):**

```typescript
interface [InterfaceName] {
  field1: string;
  field2: number;
}

export const [ComponentName]: React.FC<Props> = ({ prop1, prop2 }) => {
  return (
    <div className="...">
      {/* JSX */}
    </div>
  );
};
```

**API Endpoints:**

| Method | Endpoint | Request | Response | Purpose |
|--------|----------|---------|----------|---------|
| POST | `/api/v1/[resource]` | `{ field: value }` | `{ id: string }` | [Description] |
| GET | `/api/v1/[resource]/:id` | - | `{ data: object }` | [Description] |

**Database Schema (if applicable):**

```sql
CREATE TABLE [table_name] (
    id TEXT PRIMARY KEY,
    field1 TEXT NOT NULL,
    field2 INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_[field] ON [table_name]([field]);
```

**Integration Points:**
- Integrates with [existing component] via [method]
- Depends on [existing service] for [functionality]
- Extends [existing pattern] from v[X.X.X]

**Performance Considerations:**
- [Specific optimization or constraint]
- [Caching strategy or database indexing]
- [Expected latency or throughput]

### 3.3 [Feature/Component 2] - Detailed Design

[Repeat structure for each major component]
```

---

## Part 3: Implementation Plan (20-25% of document)

```markdown
## 4. Implementation Plan

### 4.1 Phased Approach

**Timeline:** [X] weeks

| Phase | Duration | Focus | Deliverables |
|-------|----------|-------|--------------|
| 1 | Week 1-2 | [Focus area] | [Specific deliverables] |
| 2 | Week 3-4 | [Focus area] | [Specific deliverables] |

### 4.2 Week-by-Week Breakdown

**Week 1: [Focus]**
- [ ] Task 1: [Specific, actionable task]
- [ ] Task 2: [Specific, actionable task]

**Success Criteria:** [What "done" looks like for this week]

### 4.3 Dependencies & Prerequisites

**Required Before Starting:**
- [Prerequisite 1]
- [Prerequisite 2]

**Parallel Work:** [What can be developed simultaneously]

**Blocking Dependencies:** [What must be completed before other work can start]

### 4.4 Testing Strategy

**Unit Tests:** [Component/module to test] — Target coverage: [X]%
**Integration Tests:** [Integration point] — [Expected behavior]
**E2E Tests:** [User flow] — [Success criteria]
**Performance Tests:** [Metric] — Target: [Specific number]
**Manual QA:** [Scenario] — [Edge cases]
```

---

## Part 4: Risk & Quality (10-15% of document)

```markdown
## 5. Risk Assessment & Mitigation

| Risk | Likelihood | Impact | Mitigation Strategy |
|------|------------|--------|---------------------|
| [Risk description] | High/Med/Low | High/Med/Low | [Specific mitigation] |

## 6. Rollback & Contingency

**Feature Flags:** `[flag_name]`: Controls [feature], default: `false`

**Rollback Procedure:** 1. [Step 1] 2. [Step 2] 3. [Step 3]

**Monitoring & Alerts:** [Metric]: Alert if [condition]

## 7. Documentation & Communication

**User-Facing:** Update user guide with [new feature]; create tutorial for [workflow]
**Developer:** Update API docs; document new schema; add code examples
**Release Notes:** Prepare changelog; highlight breaking changes; include migration guide
```

---

## Part 5: Appendices (5-10% of document)

```markdown
## 8. Appendices

### 8.1 Related Work & Inspiration

- [Project/Paper]: [What we learned from it]
- [Tool/System]: [How it influenced this design]

### 8.2 Future Considerations

**v[X+1] Candidates:**
- [Feature that didn't make this release but is planned]
- [Enhancement that can build on this foundation]

### 8.3 Open Questions

- [ ] [Question that needs resolution before or during implementation]
- [ ] [Decision that can be made during development]

### 8.4 References

1. [Link to related spec]
2. [Link to research paper]
3. [Link to GitHub issue or discussion]
```
