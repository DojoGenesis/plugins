---
name: batch-normalize-and-package
description: Orchestrate the full pipeline from community skill repos to Dojo CAS distribution. Scans repos, normalizes frontmatter, packages via dojo CLI, and generates a distribution manifest. Use when onboarding external skills at scale. Trigger phrases: "import community skills", "batch normalize skills", "package skills from repos", "onboard external skills", "run the skill supply chain".
license: Complete terms in LICENSE.txt
---

# Batch Normalize and Package

Meta-skill that orchestrates the full community-to-Dojo skill pipeline.

## I. Philosophy

Individual skill normalization is a solved problem. The hard part is orchestrating the pipeline at scale: scanning dozens of repos, triaging hundreds of files, normalizing the viable ones, packaging them into CAS, and producing a manifest that downstream consumers can trust. This skill is the assembly line foreman — it does not do the work itself but ensures every step happens in the right order with the right inputs.

## II. When to Use

- Onboarding a batch of community skills from multiple GitHub repos
- Running periodic supply chain refreshes (new skills from watched repos)
- After adding new repos to the starred/watched list
- When `dojo skill package-all` needs pre-processing (normalization) before it can succeed

Do NOT use for single-skill normalization (use `normalize-community-skill` directly) or for skills you are writing from scratch (use `skill-creation`).

## III. Workflow

This is a 6-step DAG with dependency structure:

```
Step 1: Acquire sources (parallel per repo)
    |
Step 2: Scan all sources (invokes scan-community-repos)
    |
Step 3: Filter catalog (select normalizable + ready skills)
    |
Step 4: Normalize (parallel per skill, invokes normalize-community-skill)
    |
Step 5: Package (invokes dojo skill package-all on normalized directory)
    |
Step 6: Generate distribution manifest
```

### Step 1: Acquire Sources

For each input repo:
1. If GitHub URL: shallow clone (`git clone --depth=1`) to temp directory
2. If local path: validate exists, use directly
3. If already cloned (cache hit): `git pull --ff-only` to update
4. Record: repo name, local path, acquisition timestamp

**Parallelization:** All repos can be acquired simultaneously. No dependencies.

### Step 2: Scan All Sources

Invoke `scan-community-repos` with the list of acquired paths.

**Input:** list of `{repo_name, local_path}` pairs
**Output:** JSON catalog with per-file classification (ready / normalizable / incompatible)

### Step 3: Filter Catalog

From the scan catalog, build the work queue:

| Classification | Action |
|---------------|--------|
| ready | Copy to staging directory as-is |
| normalizable | Add to normalization queue |
| incompatible | Log and skip — include in manifest as "skipped" |

**Decision criteria for "normalizable":**
- Has `name` field in frontmatter (required — cannot be inferred)
- Has `description` field (required — cannot be inferred)
- Has markdown body with at least one section heading
- File size > 100 bytes and < 50KB (too small = stub, too large = not a skill)

### Step 4: Normalize

For each skill in the normalization queue, invoke `normalize-community-skill`:

**Input:** path to the community SKILL.md
**Output:** enriched SKILL.md with Dojo-compatible frontmatter

**Parallelization:** All normalizations are independent. Run in parallel batches of 10.

**Error handling:**
- If normalization fails (malformed YAML, encoding issues): log error, mark as "failed" in manifest, continue
- If normalized skill still fails IsValid() simulation: log warning, mark as "needs-manual-review"

### Step 5: Package

Run `dojo skill package-all <staging-directory>` on the combined staging directory containing:
- Ready skills (copied as-is from Step 3)
- Normalized skills (output from Step 4)

This produces CAS entries: config blob (SkillManifest JSON) + content blob (tar archive) for each skill.

**Validation:** After packaging, verify each skill has both CAS tags:
- `skill/{name}:config` @ `{version}`
- `skill/{name}:content` @ `{version}`

### Step 6: Generate Distribution Manifest

Produce a manifest document with:

```markdown
# Skill Distribution Manifest
Generated: {timestamp}
Source repos: {count}

## Summary
- Scanned: {total_files}
- Ready (no normalization needed): {count}
- Normalized successfully: {count}
- Failed normalization: {count}
- Incompatible (skipped): {count}
- Packaged into CAS: {count}

## Packaged Skills
| Name | Source Repo | Tier | CAS Config Hash | CAS Content Hash |
|------|-----------|------|-----------------|------------------|
| ... | ... | ... | sha256:... | sha256:... |

## Skipped / Failed
| Name | Source Repo | Reason |
|------|-----------|--------|
| ... | ... | "missing name field" / "normalization error: ..." |
```

Also generate machine-readable `manifest.json`:
```json
{
  "generated": "2026-04-05T...",
  "source_repos": [...],
  "skills": [
    {
      "name": "skill-name",
      "source_repo": "org/repo",
      "tier": 2,
      "cas_config_hash": "sha256:...",
      "cas_content_hash": "sha256:...",
      "status": "packaged"
    }
  ]
}
```

## IV. Best Practices

1. **Run scan before normalize.** Never normalize blindly — the scan catalog prevents wasted effort on incompatible files.

2. **Preserve source attribution.** Every packaged skill must retain its source repo in the manifest. Provenance is non-negotiable for trust.

3. **Fail gracefully, report completely.** A single malformed skill should never abort the entire pipeline. Log it, skip it, include it in the manifest as failed, continue.

4. **Idempotent runs.** Running the pipeline twice on the same repos should produce the same CAS hashes (content-addressed storage guarantees this). Use this property for verification.

5. **Respect rate limits.** When cloning from GitHub, introduce a small delay between clones to avoid API rate limiting. Use shallow clones to minimize bandwidth.

6. **Stage before packaging.** Always copy/normalize into a clean staging directory. Never modify source repos in-place.

## V. Quality Checklist

- [ ] All source repos acquired successfully (or failures logged)
- [ ] Scan catalog generated with correct classifications
- [ ] No "normalizable" skills skipped without attempting normalization
- [ ] All normalized skills pass IsValid() simulation
- [ ] `dojo skill package-all` completes without errors
- [ ] Every packaged skill has both CAS tags (config + content)
- [ ] Distribution manifest includes ALL skills (packaged, failed, and skipped)
- [ ] manifest.json is valid JSON and parseable
- [ ] Source attribution preserved for every entry
- [ ] Pipeline is idempotent (re-run produces same hashes)
