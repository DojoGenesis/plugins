# Wisdom Garden

_Knowledge is planted, cultivated, and harvested._

## What it does

Wisdom Garden transforms raw learning into living seed banks of reusable insight. It writes memory notes, compresses context, harvests skills from processes, and grows a personal knowledge ecosystem. Every lesson becomes a pattern others can plant.

## Skills

| Skill | Purpose |
|-------|---------|
| memory-garden | Capture insights as seeds for future retrieval |
| compression-ritual | Distill complexity into portable clarity |
| seed-extraction | Extract patterns from experience |
| seed-library | Organize seeds by domain and use |
| seed-to-skill-converter | Harvest seeds into reusable skills |
| voice-before-structure | Ground structural artifacts in project philosophy |

## When to use

- **"We keep solving the same problem"** — Plant it as a seed
- **"How do we capture what we learned?"** — Write memory notes now
- **"This pattern works everywhere"** — Harvest it into a skill
- **"Knowledge keeps walking out the door"** — Build a garden instead

## The Loop

Harvests in the REMEMBER phase: distill learning into seeds, compress wisdom, grow the skill library. Keeps the entire ecosystem nourished and retrievable.

## The garden score (mod, early access)

A weekly score for whether your memory is compounding. Compounding here means three things grow together: fewer
repeat mistakes, faster and cheaper work, and new capability. The score also checks one kind of harm: acting on
stale memory.

Run `/garden-score` to open the score in a pane. It works in the terminal and in the desktop app's Code tab.
`/garden-score text` gives the same card as plain text. Once a week, the first session after the week rolls over
works out the score, saves that week's row, and shows a toast.

| Measure | What it counts | Source |
|---|---|---|
| Repeat mistakes (proxy) | Lines added to `seed_*` and `feedback_*` files that say a known failure happened again ("fired again", "recurred", "twice", ...) | the memory repo's git history |
| Cost per session | Median cost and median turns per session | the session's own cost ledger, recorded at each turn |
| New capability | New seeds, new skills (`SKILL.md` added), and how many distinct seeds, memories and skills were used | git history, plus the reuse log |
| Stale-memory harm | Reads of a memory file that was past its `valid_until`, named a `superseded_by`, was named in another file's `supersedes`, or whose `verified` (else `as_of`, else `updated`) date was older than the age limit | the reuse log and the files' frontmatter |
| Harvest cadence | Days and sessions since the newest `compressions/compression_log_*`, and the drift ritual's offers and answers this week | the memory repo, and `~/.claude/convergence-ledger.md` |

Each figure is shown for this week against the weekly average of the four weeks before.

**The reuse log.** The mod logs every Read of a `seed_*`, `feedback_*`, `reference_*` or `project_*` file and of any
`SKILL.md`, and every Skill call. Each row holds the file's id, the time, the session and any stale flags. It is
kept in the plugin's own store for 120 days. Nothing leaves your machine.

**The compounding reading.** After four saved weeks, each measure gets a reading. The mod compares the weekly gain in
the newer half of the weeks with the older half. A newer gain at least 1.25 times the older reads `compounding`, at
most 0.75 times reads `saturating`, and anything between reads `linear`. A worse newer half reads `not improving`.
These bars are fixed in `hooks/score.ts` so they cannot be tuned after seeing the data. This is a trend reading,
not a proof. The mod is measurement only and changes nothing about how a session runs.

### Settings

| Option | Default | What it does |
|---|---|---|
| `memory_root` | empty | The folder that holds `MEMORY.md`, the seed files and `compressions/`. When empty, the mod tries `~/TresPies-AI-Orchestration` and then `~/.hermes/orchestration/trespies-memory`. |
| `stale_days` | 90 | The age limit, in days, for `verified` or `updated`. 0 turns off the age check. `valid_until` and superseded files still count. |
| `weekly_toast` | on | Score each new week at session start and show a toast. |

The mod needs function hooks turned on (`CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`). `DOJO_OFF=1` or
`GARDEN_SCORE_OFF=1` turns it off. Tested with Claude Code 2.1.305.

### Honest limits

- The repeat-mistake figure is a proxy. It counts recurrence notes someone wrote down. It does not scan transcripts
  for the same failure class, which the measurement plan asks for later.
- Cost per session is not matched by kind of task, so a week of large tasks reads as slower work.
- The reuse log starts empty when the mod is installed. Reads from before then are not counted. A backfill from
  old transcripts is planned in dojo-meter.
- A file with no `verified`, `as_of`, `updated` or `valid_until` date is never called stale. The mod does not guess
  a file's age from its modified time, because a checkout resets that time.
- The superseded check reads only the top folder of the memory repo.
- In a shallow clone, the oldest commit looks as if it added every file, so new-seed counts run high. The card says
  so when it sees one.
- Git, and so every measure from git history, needs the CLI. The desktop Code tab runs a local CLI session, so it
  works there.

### Tests

`claude plugin test plugins/wisdom-garden` runs `tests/garden-score.test.tsx`. It covers the rules, the card, the
reuse log, the session rows, the weekly toast, the off switch, and the pane drawn on both the terminal and
desktop surfaces.
