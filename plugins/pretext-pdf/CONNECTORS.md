# Pretext PDF — Connector Integration Guide

This plugin works standalone but integrates with external connectors for richer PDF generation.

---

## Connector Overview

| Category | Placeholder | Included MCP Servers | Other Options |
|----------|-------------|---------------------|---------------|
| Repository | `~~repository` | GitHub | GitLab, Bitbucket |
| Knowledge base | `~~knowledge base` | Notion | Confluence, Obsidian |
| File storage | `~~file storage` | Google Drive | Dropbox, S3 |
| Chat | `~~chat` | Slack | Discord, Teams |

---

## Repository Integration (`~~repository`)

### Default: GitHub

**Purpose:** Export repository files, PRs, issues, and diffs as formatted PDFs.

### Enhanced Workflows

#### With `/export-pdf`

**Without connector:**
- Export local files only
- No PR/issue context
- Manual file path specification

**With ~~repository:**
- Export PR diffs with syntax-highlighted changes
- Include issue descriptions and comments
- Batch export files from specific commits or branches
- Include commit metadata in PDF headers

---

## Knowledge Base Integration (`~~knowledge base`)

### Default: Notion

**Purpose:** Export knowledge base pages and databases as typeset PDFs.

### Enhanced Workflows

- Export Notion pages preserving heading hierarchy
- Batch export database entries with consistent formatting
- Include page metadata (author, last edited, tags)
- Cross-reference links rendered as footnotes

---

## File Storage Integration (`~~file storage`)

### Default: Google Drive

**Purpose:** Export generated PDFs to cloud storage.

### Enhanced Workflows

- Auto-upload generated PDFs to specified Drive folder
- Maintain export history with versioned filenames
- Share exported PDFs via Drive sharing links

---

## Chat Integration (`~~chat`)

### Default: Slack

**Purpose:** Export chat conversations and threads as formatted PDFs.

### Enhanced Workflows

- Export Slack threads preserving message hierarchy
- Include user avatars and timestamps
- Render code blocks with syntax highlighting
- Export channel digests as formatted reports

---

## Configuration

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
    }
  }
}
```

---

**Last Updated:** 2026-04-08
**Maintained By:** Dojo Genesis
**Status:** Active
