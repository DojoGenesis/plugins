---
name: supply-chain-refresh
description: Automated pipeline that refreshes the Dojo skill supply chain by pulling latest from watched repos, re-scanning, normalizing, and packaging new or updated skills into CAS. Use for periodic maintenance of the community skill library. Trigger phrases: "refresh the supply chain", "update community skills", "run skill supply chain", "sync skills from repos".
license: Complete terms in LICENSE.txt
---

# Supply Chain Refresh

Automated skill supply chain maintenance.

## I. Philosophy

A supply chain is only as good as its refresh rate. Community skills evolve — repos add new skills, fix bugs, and improve documentation. This skill runs the full scan-normalize-package pipeline on a scheduled or manual basis, producing a diff report that shows what changed since the last run.

## II. When to Use

- On a weekly schedule to keep the skill library current
- After adding new repos to the watched list
- When a community repo announces a new release
- Before publishing to OCI (Action 7) to ensure latest versions

## III. Workflow

### Step 1: Load Watched Repo List

Read the repo list from the supply chain manifest:
```
/AgenticStackOrchestration/specs/starred-repos-supply-chain/manifest.json
```

Extract `source_repos` array. Also check for any newly starred repos:
```bash
gh api user/starred --jq '.[].full_name'
```

### Step 2: Pull Latest

For each repo:
1. If already cloned: `git pull --ff-only`
2. If new: `git clone --depth=1`
3. Record: commit SHA before and after pull

### Step 3: Scan for Changes

Run `scan-community-repos` on all repo paths.
Compare new catalog against previous manifest.json:
- **New skills:** present in scan, absent in manifest
- **Updated skills:** present in both, content hash differs
- **Removed skills:** present in manifest, absent in scan

### Step 4: Normalize New/Updated Skills

For each new or updated skill:
1. Run `normalize-community-skill`
2. Copy to staging directory

### Step 5: Package

Run `dojo skill package-all` on staging directory.
Only new/updated skills will get new CAS entries (content-addressed = idempotent for unchanged content).

### Step 6: Generate Diff Report

```markdown
# Supply Chain Refresh Report
Date: {timestamp}
Previous run: {last_manifest_date}

## Changes
- New skills: {count} ({names})
- Updated skills: {count} ({names})
- Removed skills: {count} ({names})
- Unchanged: {count}

## New Skill Details
| Name | Source | Tier | CAS Hash |
|------|--------|------|----------|
```

### Step 7: Update Manifest

Overwrite `manifest.json` with new state.

## IV. Best Practices

1. **Always pull before scanning.** Stale clones produce false "unchanged" reports.
2. **Preserve the previous manifest.** Archive it as `manifest-{date}.json` before overwriting.
3. **Rate-limit git operations.** Space clones 1s apart to avoid GitHub rate limits.
4. **Log everything.** The diff report is the audit trail for what entered the skill library.

## V. Quality Checklist

- [ ] All watched repos pulled successfully (or failures logged)
- [ ] Scan catalog compared against previous manifest
- [ ] New/updated skills normalized and packaged
- [ ] Diff report generated with complete change summary
- [ ] Manifest.json updated with new state
- [ ] Previous manifest archived
