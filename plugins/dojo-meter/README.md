# dojo-meter

See what each turn, agent and model costs, and how big your context is: a cost report from your transcripts, and a live band with the mod.

Subagents and workflow agents spend tokens you never see in the main thread. `dojo-meter` counts them:
a report you can run any time from the transcripts Claude Code already keeps, and, with the mod, a band
above the prompt that updates while the work runs.

## Install

```
/plugin marketplace add DojoGenesis/plugins
/plugin install dojo-meter@dojo-genesis
```

## What is inside

| Component | Tier | What it does |
|---|---|---|
| `commands/cost.md` | classic | `/dojo-meter:cost`: runs `scripts/cost.py` and shows its table |
| `scripts/cost.py` | classic | reads transcripts, counts tokens by model and thread, prices them from `scripts/pricing.json` |
| `scripts/pricing.json` | classic | the price table (USD per million tokens) and its source, the one place prices live |
| `hooks/register.ts` | mod (early access) | per-request ledger, the band, budget and context toasts, daily totals |
| `hooks/band.tsx` | mod | draws the band above the prompt |
| `hooks/ledger.ts` | mod | pure arithmetic: pricing, band text, fitting to the width |
| `hooks/pricing.ts` | mod | generated from `scripts/pricing.json` by `scripts/gen_pricing_ts.py`; never edit by hand |
| `scripts/gen_pricing_ts.py` | mod | regenerates `hooks/pricing.ts` and `tests/vectors.ts`; `--check` fails when they drift |
| `commands/band.md` | mod | `/dojo-meter:band on\|off\|toggle\|status`; the mod answers it, this file is the fallback |

## Classic tier: works with function hooks off

`/dojo-meter:cost` is a plain `python3` script (standard library only, Python 3.9 or newer). It is read-only.

```
/dojo-meter:cost                 this session
/dojo-meter:cost --today         since local midnight
/dojo-meter:cost --days 7        the last seven calendar days, today included
/dojo-meter:cost --session ID    one session, with its subagent files
/dojo-meter:cost --project PATH  one project (alone: all time; with --today or --days: that window)
/dojo-meter:cost --all           every transcript
/dojo-meter:cost --json          the same data as JSON
```

With no flag the command reports the session it was started from, and falls back to today when it cannot
tell which one that is.

What it prints: one row per model and thread (main thread or subagents) with requests, input, cache write,
cache read and output tokens and an estimated USD; subtotals for the main thread and the subagents; the
total by tier; the cache-read share of input-side tokens (read over input plus write plus read); and the
caveats listed below.

How it counts:

- Only lines that are an assistant message with a usage object count. Text that merely quotes such a line
  (a tool result, a progress row) does not.
- One API response is written as several lines that repeat the same usage, and a resumed session repeats
  history in another file. Lines are de-duplicated across all files on the message id (the request id when
  the id is missing), keeping the largest value of each field, so the answer does not depend on the order
  files are read.
- A line is a subagent line when its file sits in a `subagents` folder or the line is marked as a side chain.
  A response seen on the main thread anywhere counts as main thread.
- Model ids are normalised first (case, provider prefix such as `anthropic.` or `us.anthropic.`, date and
  version suffixes, bracketed tags such as a context-size tag). An id is priced only when the result equals
  an id in `scripts/pricing.json`, or equals one plus a single `-fast` or `-latest`. Nothing is priced by
  resemblance: a version number the table does not list (a point release of a known model, say), a suffix
  the table does not know such as `-preview`, or stray text after an id is a different model, so it is
  unpriced until the table gets a row for it. A `-fast` or `-latest` id is listed on a `priced as the base id:` line, and
  priced at the base id's rates.
- A model that matches nothing is shown as `unpriced`, never as zero, and its tokens are still counted. A
  dollar figure that leaves such tokens out says `(partial)` (the main thread, the subagents, the total and
  each tier are judged on their own tokens); a figure with no priced tokens behind it reads `unpriced`, even
  when the counts are zero or unusable. In `--json` that figure is `null` and the totals carry
  `unpriced_tokens` and a `partial` flag.
- Cache writes are priced at 1.25 times the input price (5-minute TTL), or 2 times when the transcript
  records that a write was 1-hour TTL.
- The report never prints a project folder name or a path.

## Mod tier: early access

Function hooks are off on many accounts. To try the mod:

```
export CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1
```

(or add it under `env` in `~/.claude/settings.json`), then start a new session. With it on, `hooks/register.ts`:

- watches every model request, subagents and workflow agents included, and keeps a ledger per thread and
  model;
- draws a band above the prompt, one line that shortens to fit the width:
  `meter  opus $a · sonnet $b ≈ $total  |  ctx <n>k (<p> percent)  |  cache <p> percent  |  today $c`.
  The tiers are the session estimate by tier, `ctx` is the input-side size of the last main-thread request
  (with its share of the context window when the window is known), `cache` is the cache-read share, and
  `today` is the day's stored total plus this session's share. `(partial)` after a figure marks it as
  partial: a model without a price was used and its tokens are left out of the dollars; a figure with no
  priced tokens reads `unpriced`;
- shows a toast at 70 and at 90 percent of `budget_usd`, each once per session (one jump past both shows
  only the 90 percent toast);
- shows a toast when the last main-thread request holds more than `context_warn_tokens` tokens, suggesting
  `/compact`, once per crossing; it arms again after the size falls below 70 percent of the threshold;
- adds the session's spend to a daily total in the plugin's own store (`day:<local date>`), and drops
  days older than 60.

`/dojo-meter:band` answers `on`, `off`, `toggle` (no argument toggles) or `status` itself, with no model
turn. It never rewrites a tool call, an agent or a request.

## Options

| Option | Default | Meaning |
|---|---|---|
| `show_band` | `true` | draw the band (mod) |
| `budget_usd` | `0` (off) | session budget in USD for the 70 and 90 percent toasts (mod). Per session: it starts again on resume |
| `context_warn_tokens` | `400000` | context size that triggers the toast (mod). `0` turns it off |

On a model with a 200,000-token window the default threshold never fires: set `context_warn_tokens`
lower there.

## Kill switches

- `DOJO_OFF=1`: the whole suite. `DOJO_METER_OFF=1`: this plugin. Either one turns the mod into a
  pass-through: no ledger, no toasts, no store writes, no band; `/dojo-meter:band` then says the band is off.
- They affect the mod only. `/dojo-meter:cost` is something you run on purpose, so it always runs.
- Options: `show_band` set to `false` hides the band only; `budget_usd` or `context_warn_tokens` set to
  `0` turns that toast off.

## Honest limits

- Every dollar figure is an estimate at list prices from `scripts/pricing.json` (see its `source` field),
  not an invoice. Subscription plans bill differently: read the figures as relative weight, not as what you pay.
- Transcripts under-record some subagent output, so subagent rows are lower bounds.
- Unknown models are shown as `unpriced`, never as zero. They are left out of the dollar totals, the band's
  session estimate and the daily total, and every figure that leaves them out says so: `(partial)` in the
  report and in the band, and a note in the budget toast.
- The only ids priced without an exact table row are a known id plus `-fast` or `-latest`, at the base id's
  list prices. If a `-fast` model is billed differently from its base id, the dollars are off by that
  difference; the report flags those ids on the `priced as the base id:` line.
- The band and the report can disagree. The mod only receives one flat cache-write count per request, so it
  prices every write at the 5-minute rate; the report reads the TTL split from the transcript and can read
  higher. The band is also its own table-priced ledger, so it can differ from the engine's own session cost.
- The band's ledger lives in the running process. After a resume or a plugin reload it starts again from
  zero, and the budget with it, while `/dojo-meter:cost` still sees the whole session.
- The daily total is best effort: two sessions finishing a turn at the same moment can lose one update.
  It uses the local date, and only priced spend goes into the dollars.
- `turn.complete` reports only the last model's usage, so the mod prices from its own per-request ledger
  and never from that.
- The toggle command is tested with the Claude Code test kit, which raises the command to the hook under
  the name `dojo-meter:band`. Whether the live engine raises it for a plugin command under that same name
  has not been checked live. If it does not, the markdown command runs instead and tells you the mod is
  not active, at the cost of one model turn.
- The mod's per-request hook runs on every model request. It keeps that work to one in-memory update and
  moves the store and toast work to the end of the main turn.
- Nothing here measures what a change of setup would change; this plugin claims no savings or benchmark figures.

## Tests

```
cd plugins/dojo-meter && python3 -m unittest discover -s tests -v
CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/dojo-meter
python3 scripts/gen_pricing_ts.py --check
```

`scripts/pricing.json` is the one price table; `hooks/pricing.ts` is generated from it because a mod cannot
import JSON. Edit the JSON, run `python3 scripts/gen_pricing_ts.py`, keep both files. A test fails when
they differ.

Tested with Claude Code 2.1.286.
