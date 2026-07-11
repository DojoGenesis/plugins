# STATUS — CoworkPluginsByDojoGenesis Repository

This file is a pointer, not a snapshot. A hand-carried count is a liability
the moment a skill is added — it keeps looking authoritative long after it
stops being true. This repo now has two live, gated sources of truth instead
of a third hand-maintained one:

- **What's here, and how many, by plugin:** [README.md](README.md) — the
  `## Plugins` table is disk-truth-gated by `scripts/face-parity.py`, which
  fails closed if any face (README, llms.txt, marketplace.json) drifts from
  the actual `plugins/*/skills/*/SKILL.md` count.
- **What changed and when:** [CHANGELOG.md](CHANGELOG.md) — dated entries,
  newest first.
- **Skill/plugin structural integrity** (missing SKILL.md, bad frontmatter,
  orphaned skills, marketplace.json consistency): run
  `python3 scripts/plugin-lint.py`.
- **Cross-face drift** (README vs llms.txt vs marketplace.json vs disk): run
  `python3 scripts/face-parity.py`.
- **Behavioral clusters** (which skills group by function, across plugin
  boundaries): see the `## Clusters` section in [llms.txt](llms.txt) and the
  "Find the right skill in 30 seconds" table in [README.md](README.md).

## Why this file has no numbers anymore

An earlier version of this file (last hand-updated 2026-02-12) carried a full
dashboard — plugin/skill/command counts, a version table, a health checklist.
Five months later it still claimed 7 plugins / 44 skills / v1.1.0 while disk
held 10 plugins / 99 skills — the snapshot outranked a `find` command in a
reader's trust for exactly as long as nobody checked it against reality.
Rather than re-audit and re-freeze a new snapshot that will just as
predictably go stale, this file is now a stub with no disk-truth claims of
its own to drift. If a rich standalone status report is needed again,
generate one fresh with `system-health:repo-status` rather than resurrecting
this file as a hand-maintained dashboard.
