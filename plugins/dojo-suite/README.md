# dojo-suite

All eight Dojo suite plugins in one install. It adds no skills, agents, commands or hooks of its own, so it adds no always-on weight; it only declares the eight as dependencies, and Claude Code installs them with it.

## What it installs

| Plugin | What it does |
|---|---|
| `dojo-protocol` | ten rules at session start, plus role agents pinned to the right model |
| `dojo-gates` | deterministic guards for blanket staging, rewriting pushed commits, printing secrets, oversized reads and silent probes |
| `dojo-router` | warns or blocks subagent dispatches that name no model |
| `dojo-meter` | a cost report from your transcripts |
| `dojo-verify` | flags "done" claims with no passing check behind them |
| `dojo-flow` | workflows for parallel builds and convergence audits |
| `dojo-doctor` | finds hooks and settings that fail or cost you silently |
| `dojo-settle` | pre-registered experiments and decision gates |

## Install

```
/plugin marketplace add DojoGenesis/plugins
/plugin install dojo-suite@dojo-genesis
```

Or pick one at a time, for example `/plugin install dojo-gates@dojo-genesis`.

## Turn one member off

Set the member's switch in the environment you launch Claude Code from, then start a new session:

```
export DOJO_GATES_OFF=1
```

The pattern is `DOJO_<PLUGIN>_OFF=1`. The switches that exist are `DOJO_PROTOCOL_OFF`, `DOJO_GATES_OFF`, `DOJO_ROUTER_OFF`, `DOJO_METER_OFF` and `DOJO_VERIFY_OFF`. `DOJO_OFF=1` turns off every Dojo hook at once without uninstalling anything. `dojo-flow`, `dojo-doctor` and `dojo-settle` run only when you invoke their commands or scripts, so they have no switch. Each plugin's README lists what its own switches cover.

## Remove it

The eight members are separate plugins, so remove the bundle and each member you no longer want:

```
/plugin uninstall dojo-suite@dojo-genesis
/plugin uninstall dojo-protocol@dojo-genesis
/plugin uninstall dojo-gates@dojo-genesis
/plugin uninstall dojo-router@dojo-genesis
/plugin uninstall dojo-meter@dojo-genesis
/plugin uninstall dojo-verify@dojo-genesis
/plugin uninstall dojo-flow@dojo-genesis
/plugin uninstall dojo-doctor@dojo-genesis
/plugin uninstall dojo-settle@dojo-genesis
```

## Honest limits

The mods (live status, routing and ledgers inside the engine) are early access and need function hooks enabled; the classic hooks work without them. The suite's effect on cost, speed or accuracy has not been measured. Tested with Claude Code 2.1.286.
