# Always-on weight

Always-on weight is the text a plugin puts in the model's context in every session, before you type anything.
You pay for it on every turn, so a plugin suite that promises to keep context small has to keep its own weight
small first.

## Budget

- **The suite, all eight plugins together: under 2,000 tokens.**
- **Any other plugin in this marketplace, on its own: under 1,000 tokens.**

So the suite plus any three other plugins stays under 5,000 tokens. `scripts/release-check.sh` fails its
`always-on` row when either limit is broken.

## How it is measured

`scripts/always_on.py` adds two parts for every plugin in `.claude-plugin/marketplace.json`:

- **Listing**: skill, agent and command descriptions, read from the `Always-on:` line of
  `claude --plugin-dir plugins/NAME plugin details NAME`. Anyone can run the same command.
- **SessionStart**: what the plugin's SessionStart hooks print, run once in an empty project with an empty
  home folder. `claude plugin details` labels hooks "no model context cost", but a SessionStart hook that returns
  `additionalContext` does add to context, so it is counted here at characters divided by 3.5. dojo-protocol's
  ten rules are the only SessionStart text in a default setup. A project's own `DOJO.md` replaces them and is not
  counted.

Both are estimates, not billed usage. Run `python3 scripts/always_on.py --write` to refresh the table below.

## Current numbers

Measured on 2026-10-18 with Claude Code 2.1.302.

<!-- always-on:begin -->
| Plugin | Group | Listing | SessionStart | Always-on |
|--------|-------|--------:|-------------:|----------:|
| dojo-suite | suite | ~0 | 0 | ~0 |
| dojo-protocol | suite | ~374 | ~568 | ~942 |
| dojo-gates | suite | ~100 | 0 | ~100 |
| dojo-router | suite | ~77 | 0 | ~77 |
| dojo-meter | suite | ~82 | 0 | ~82 |
| dojo-verify | suite | ~75 | 0 | ~75 |
| dojo-flow | suite | ~207 | 0 | ~207 |
| dojo-doctor | suite | ~138 | 0 | ~138 |
| dojo-settle | suite | ~235 | 0 | ~235 |
| dojo-fleet | companion | ~59 | 0 | ~59 |
| dojo-swimlanes | companion | ~69 | 0 | ~69 |
| dojo-fixcards | companion | ~63 | 0 | ~63 |
| dojo-lanes | companion | ~50 | 0 | ~50 |
| dojo-tally | companion | ~56 | 0 | ~56 |
| dojo-brief | companion | ~50 | 0 | ~50 |
| strategic-thinking | library | ~599 | 0 | ~599 |
| specification-driven-development | library | ~897 | 0 | ~897 |
| wisdom-garden | library | ~888 | 0 | ~888 |
| system-health | library | ~894 | 0 | ~894 |
| continuous-learning | library | ~877 | 0 | ~877 |
| agent-orchestration | library | ~867 | 0 | ~867 |
| skill-forge | library | ~746 | 0 | ~746 |
| dojo-craft | library | ~621 | 0 | ~621 |
| pretext-pdf | library | ~210 | 0 | ~210 |
| bring-loop | companion | ~191 | 0 | ~191 |
| kata-harness | companion | ~132 | 0 | ~132 |

Suite together: **~1,856 tokens** (budget: under 2,000). Each other plugin: budget under 1,000. Everything in the marketplace installed at once: ~9,125 tokens.
<!-- always-on:end -->
