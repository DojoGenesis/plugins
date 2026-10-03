# Agent Orchestration — Connector Integration Guide

This plugin works standalone but becomes significantly more powerful when integrated with external connectors. This document describes how each connector enhances the plugin's capabilities.

---

## Connector Overview

| Category | Placeholder | Included MCP Servers | Other Options |
|----------|-------------|---------------------|---------------|
| Repository | `~~repository` | GitHub | GitLab, Bitbucket, Azure DevOps |
| Knowledge base | `~~knowledge base` | Notion | Confluence, Coda, Obsidian, Roam |
| Chat | `~~chat` | Slack | Microsoft Teams, Discord |
| Project tracker | `~~project tracker` | Linear | Asana, Jira, ClickUp, Monday.com |

---

## Repository Integration (`~~repository`)

### Default: GitHub

**Purpose:** Link handoffs, decisions, and specs to code repositories.

### Enhanced Workflows

#### With `/handoff`

**Without connector:**
- Handoff package references files by relative path
- No verification that files exist
- No link to actual code

**With ~~repository:**
- Link to specific files using repo URLs with line numbers
- Reference pull requests and issues directly
- Include commit SHAs for exact context
- Verify that referenced files exist before creating handoff

**Example:**
```markdown
## Required Context

**Pattern Files:**
- [`frontend/src/components/Navigation/Sidebar.tsx` (lines 45-120)](https://github.com/org/repo/blob/main/frontend/src/components/Navigation/Sidebar.tsx#L45-L120)
- See PR #234 for discussion on navigation patterns

**Related Issues:**
- Resolves #456 (breadcrumb navigation)
- Blocked by #123 (auth implementation)
```

#### With `/navigate-workspace`

**Enhanced capabilities:**
- Show open PRs related to active work
- Link handoffs to specific branches
- Track commit activity on specs
- Display PR status in workspace map

**Example output:**
```
## Active Work (7 items)

### Specifications (2)
- `2026-02-11_breadcrumb_spec.md` (Active)
  - PR #234: In Review (2 approvals, 1 requested change)
  - Last commit: 3 hours ago

### Handoffs (1)
- `2026-02-11_handoff_breadcrumb.md` → Zenflow (Ready)
  - Branch: feature/breadcrumb-nav
  - Status: 15 commits ahead of main
```

#### With `/propagate-decision`

**Enhanced capabilities:**
- Commit decision as atomic change with conventional commit message
- Link decision to related PRs or issues
- Tag decision in commit for traceability
- Create decision-tracking branch if needed

**Example workflow:**
1. Decision recorded: "Auth bypass for v0.2.0"
2. All documents updated
3. Single commit created:
   ```
   docs(decision): Record auth bypass for v0.2.0

   - Removes auth from v0.2.0 scope
   - Adds auth to v0.2.2 scope
   - Updates STATUS.md and master plan

   Decision-ID: DEC-001
   Closes #456
   ```

### Configuration

```json
{
  "mcpServers": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/",
      "config": {
        "defaultOrg": "your-org",
        "defaultRepo": "your-repo"
      }
    }
  }
}
```

---

## Knowledge Base Integration (`~~knowledge base`)

### Default: Notion

**Purpose:** Sync decisions, specs, and teaching artifacts to centralized knowledge base.

### Enhanced Workflows

#### With `/handoff`

**Enhanced capabilities:**
- Link to specs, designs, and documentation in Notion
- Reference decision records from knowledge base
- Include page links in Required Context
- Embed Notion pages directly in handoff

**Example:**
```markdown
## Required Context

**Core Documents:**
- [Product Spec: Breadcrumb Navigation](https://notion.so/breadcrumb-nav-spec)
- [Design System Guidelines](https://notion.so/design-system)
- [Decision Record: Navigation Architecture](https://notion.so/DEC-001)

**Related Documentation:**
- [Frontend Patterns Library](https://notion.so/frontend-patterns)
```

#### With `/teach`

**Enhanced capabilities:**
- Check for existing teaching artifacts on same topic
- Sync teaching artifacts to knowledge base automatically
- Link related documentation from knowledge base
- Build searchable teaching index in Notion

**Example workflow:**
1. Create teaching artifact: "Context Management"
2. Check Notion for existing content: Found "Memory Management Guide"
3. Merge or differentiate teaching approach
4. Sync to Notion with tags and backlinks
5. Update teaching index in Notion database

#### With `/propagate-decision`

**Enhanced capabilities:**
- Sync decision to centralized decision log
- Link to affected documentation automatically
- Update architecture diagrams in Notion
- Create decision changelog in knowledge base

**Example:**
```
Decision propagated to:
✓ Local documents (5 files updated)
✓ Notion decision log updated
✓ Architecture diagram updated
✓ Decision changelog: v0.2.0 decisions page
```

### Configuration

```json
{
  "mcpServers": {
    "notion": {
      "type": "http",
      "url": "https://mcp.notion.com/mcp",
      "config": {
        "databaseId": "your-database-id",
        "decisionsPage": "your-decisions-page-id"
      }
    }
  }
}
```

---

## Chat Integration (`~~chat`)

### Default: Slack

**Purpose:** Enable real-time notifications and async coordination between agents and teams.

### Enhanced Workflows

#### With `/handoff`

**Enhanced capabilities:**
- Notify receiver in appropriate channel when handoff is ready
- Share handoff package link in thread
- Enable async coordination and questions
- Track handoff acceptance in channel

**Example workflow:**
1. Create handoff: "Breadcrumb implementation to Zenflow"
2. Save handoff package: `handoffs/2026-02-11_breadcrumb.md`
3. Post to #engineering-handoffs:
   ```
   New handoff ready for @zenflow
   📦 Breadcrumb Navigation Implementation
   🔗 Link: workspace/handoffs/2026-02-11_breadcrumb.md
   ✅ Package verified (6/6 checklist passed)

   Reply "accept" to claim this handoff
   ```

#### With `/navigate-workspace`

**Enhanced capabilities:**
- Post workspace status to team channel
- Share workspace map in daily standup thread
- Enable workspace discussions in chat
- Notify about stale items

**Example:**
```
Weekly workspace report posted to #team-status:

📊 Workspace Health:
- 7 active items
- 2 pending handoffs
- 3 items >14 days old (needs attention)

Full map: workspace/README.md
```

#### With `/propagate-decision`

**Enhanced capabilities:**
- Announce decision in relevant channels
- Post decision summary with impact analysis
- Enable team discussion on decisions
- Track decision questions and clarifications

**Example:**
```
Posted to #architecture-decisions:

📋 New Decision: Auth Bypass for v0.2.0

**Decision:** Skip production auth; ship with debug token
**Impact:**
- ✅ Unblocks frontend immediately
- ⚠️ Temporary security degradation
- 📅 Auth moved to v0.2.2

**Affected teams:** @frontend @backend @security
**Full details:** docs/v0.2.0/decisions/DEC-001.md

React with 👍 if acknowledged, ❓ for questions
```

#### With `/teach`

**Enhanced capabilities:**
- Notify learner that teaching artifact is ready
- Post in #learning channel for community access
- Enable discussion threads on teaching content
- Build async learning community

**Example:**
```
Posted to #agent-learning:

📚 New Teaching: Context Management

@cipher, I created a teaching artifact on context management based on what I learned today. It covers the 3-7 idea threshold and when to compress context.

🔗 teaching/2026-02-11_context_management.md

Let's practice together — try it on your next task and share what you discover!
```

### Configuration

```json
{
  "mcpServers": {
    "slack": {
      "type": "http",
      "url": "https://mcp.slack.com/mcp",
      "config": {
        "channels": {
          "handoffs": "engineering-handoffs",
          "decisions": "architecture-decisions",
          "teaching": "agent-learning",
          "status": "team-status"
        }
      }
    }
  }
}
```

---

## Project Tracker Integration (`~~project tracker`)

### Default: Linear

**Purpose:** Bridge agent orchestration with human project management workflows.

### Enhanced Workflows

#### With `/handoff`

**Enhanced capabilities:**
- Create handoff task in project tracker automatically
- Link to related tickets and epics
- Set up dependencies between handoff and other work
- Track handoff progress and completion

**Example workflow:**
1. Create handoff: "Breadcrumb implementation"
2. Linear integration:
   - Creates ticket: "ENG-456: Implement breadcrumb navigation"
   - Links to epic: "Navigation Improvements"
   - Sets dependency: Blocked by ENG-123 (auth)
   - Assigns to: Zenflow
   - Attaches handoff package as description

#### With `/navigate-workspace`

**Enhanced capabilities:**
- Cross-reference workspace items with tracker tickets
- Show dependencies between workspace and external tasks
- Sync status updates bidirectionally
- Display ticket status in workspace map

**Example output:**
```
## Active Work (7 items)

### Handoffs (2)
- `2026-02-11_handoff_breadcrumb.md` → Zenflow (Ready)
  - Linear: ENG-456 (In Progress)
  - Sprint: Sprint 12
  - Points: 5

- `2026-02-09_handoff_research.md` → Cipher (Blocked)
  - Linear: ENG-445 (Blocked)
  - Blocked by: ENG-443 (In Review)
```

#### With `/propagate-decision`

**Enhanced capabilities:**
- Create tickets for each touchpoint affected by decision
- Update ticket dependencies based on scope changes
- Link tickets to decision document
- Adjust sprint planning automatically

**Example:**
```
Decision propagated to Linear:

Created tickets:
- ENG-460: Update frontend for auth bypass
- ENG-461: Defer auth implementation to v0.2.2
- ENG-462: Update integration tests

Updated dependencies:
- ENG-456 unblocked (auth no longer required)
- ENG-470 blocked (needs entity backend first)

Sprint impact:
- Sprint 12: +2 tickets (frontend work unblocked)
- Sprint 14: +3 tickets (auth implementation)
```

### Configuration

```json
{
  "mcpServers": {
    "linear": {
      "type": "http",
      "url": "https://mcp.linear.app/mcp",
      "config": {
        "teamId": "your-team-id",
        "projectId": "your-project-id",
        "labels": {
          "handoff": "handoff",
          "decision": "architectural-decision"
        }
      }
    }
  }
}
```

---

## Multi-Connector Workflows

### Example: Full-Stack Handoff

**Scenario:** Handing off a feature implementation with full traceability

**Connectors used:** ~~repository, ~~knowledge base, ~~chat, ~~project tracker

**Workflow:**
1. `/handoff feature X implementation to Zenflow`
2. Claude creates handoff package with:
   - Links to GitHub files and PRs (~~repository)
   - Links to Notion spec and design docs (~~knowledge base)
3. Saves handoff to workspace
4. Creates Linear ticket with handoff details (~~project tracker)
5. Notifies Zenflow in Slack (~~chat)
6. Agent accepts handoff:
   - Updates Linear ticket status
   - Responds in Slack thread
   - Checks out GitHub branch
7. Work progresses with status synced across all systems

### Example: Decision with Full Propagation

**Scenario:** Architectural decision affects multiple systems

**Connectors used:** ~~repository, ~~knowledge base, ~~chat, ~~project tracker

**Workflow:**
1. `/propagate-decision auth bypass for v0.2.0`
2. Claude:
   - Records decision in local docs
   - Updates all affected local documents
   - Commits changes to GitHub with tagged commit (~~repository)
   - Syncs decision to Notion decision log (~~knowledge base)
   - Creates tickets for affected work items (~~project tracker)
   - Posts decision summary to Slack (~~chat)
3. All systems reflect decision:
   - GitHub: Decision committed and tagged
   - Notion: Decision log updated
   - Linear: Tickets created/updated
   - Slack: Team notified and acknowledges

---

## Connector Setup

### Prerequisites

Each connector requires:
1. MCP server configured in `.mcp.json`
2. Authentication credentials (API keys, OAuth tokens)
3. Appropriate permissions in external system

### Minimal Configuration

```json
{
  "mcpServers": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/"
    },
    "notion": {
      "type": "http",
      "url": "https://mcp.notion.com/mcp"
    },
    "slack": {
      "type": "http",
      "url": "https://mcp.slack.com/mcp"
    },
    "linear": {
      "type": "http",
      "url": "https://mcp.linear.app/mcp"
    }
  }
}
```

### Testing Connectivity

```bash
# Test each connector
claude plugin test agent-orchestration --connector github
claude plugin test agent-orchestration --connector notion
claude plugin test agent-orchestration --connector slack
claude plugin test agent-orchestration --connector linear

# Test all connectors
claude plugin test agent-orchestration --all-connectors
```

---

## Troubleshooting

### Connector Not Found

**Symptom:** Command references `~~repository` but no integration happens

**Cause:** Connector not configured in `.mcp.json`

**Fix:** Add connector to `.mcp.json` and restart Claude

### Authentication Issues

**Symptom:** "Unauthorized" or "Permission denied" errors

**Cause:** Missing or expired credentials

**Fix:**
1. Verify API key / OAuth token is current
2. Check permissions in external system
3. Re-authenticate if needed

### Partial Integration

**Symptom:** Some features work, others don't

**Cause:** Partial permissions or incomplete configuration

**Fix:**
1. Review connector-specific configuration
2. Verify all required scopes/permissions
3. Check connector documentation for requirements

---

## Future Connectors

Potential future integrations:
- **Jira** (project tracker alternative)
- **Confluence** (knowledge base alternative)
- **Microsoft Teams** (chat alternative)
- **GitLab** (repository alternative)
- **Obsidian** (knowledge base for local-first workflows)
- **Discord** (chat alternative for communities)

---

**Last Updated:** 2026-02-11
**Maintained By:** TresPies LLC
**Status:** Active
