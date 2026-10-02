# Contract: <short name>

Frozen: <date>. Change this file only between waves, and tell every affected agent.

## Goal

<Two sentences. What exists when this is done.>

Out of scope: <what nobody should touch.>

## Shared decisions

- <Name / interface / format / version that more than one agent relies on.>
- <One line each. If it is not here, it is not decided.>

## Ownership

| Agent | Owns (writes only these) | May read |
|---|---|---|
| <track-a> | `<path/>`, `<path/file>` | everything |
| <track-b> | `<path/>` | everything |
| integrator | shared files: `<config>`, `<index>` | everything |

Need something outside your list? Report it. Do not edit it.

## Done-checks

| Agent | Command | Expected |
|---|---|---|
| <track-a> | `<command>` | exit 0 |
| <track-b> | `<command>` | exit 0 |
| integrator | `<full build and test command>` | exit 0 |

## Waves and gates

1. Wave 1: <tracks that can run together>. Gate: <clean build / test command>.
2. Wave 2: <tracks that need wave 1>. Gate: <command>.
3. Integrate, then run the full check yourself.

## Irreversible steps

<Anything that pushes, deploys, publishes, deletes or sends. Each one needs the person's go.>

## Return shape

Every agent reports: files changed, commands run, their exit codes, anything unfinished.
