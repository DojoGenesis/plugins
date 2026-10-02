---
name: router
description: Use when you start a subagent or a workflow step. Set model on purpose (haiku to look things up, sonnet to build or review, opus to judge) so nothing inherits your session's model by accident.
model: inherit
category: dispatch-coordinate
---

# Router

A dispatch that names no model runs on whatever the session runs on. Name one every time. The
choice is small, and the hook below makes it a deliberate one.

## Role to model

| Role | Alias | Use it for |
|---|---|---|
| scout | `haiku` | search, read, map, summarize; anything where the answer is a lookup |
| builder | `sonnet` | write and edit code, run commands, build a slice |
| reviewer | `sonnet` | fresh-eyes review of a diff or a claim |
| judge | `opus` | adversarial review, a hard-to-undo decision, the final call |

Use aliases (`haiku`, `sonnet`, `opus`), never full model ids.

## On an Agent call

Set `model` next to `subagent_type`:

```
Agent({
  description: "Map the retry code",
  subagent_type: "Explore",
  model: "haiku",
  prompt: "Find where retries are configured. Report file:line, do not edit."
})
```

Leave `model` off only for two cases: a plugin agent (its type contains a colon, such as
`some-plugin:reviewer`) whose definition pins its own model, and `fork`, which always
inherits the parent.

## In a workflow script

Every `agent()` call sets `model` in its options object:

```js
const found = await agent('Find the config loader and report file:line.', {
  label: 'scout',
  model: 'haiku',
})
```

The workflow hook counts the `agent(` calls in the script, and in the file named by
`scriptPath`, and lists the line (and label) of each call that sets none.

## What the hooks say

- `warn` (default): one message per session per subagent type, or per script. The dispatch
  goes ahead. Next time, set `model`.
- `block`: an unpinned `general-purpose`, `Explore` or `Plan` dispatch is refused. Retry the
  call with `model` set to haiku, sonnet or opus. You do not need to ask the person first.
  A custom agent type is only warned about: its own pin can't be seen from the hook, and a
  refusal would leave no way through except overriding that pin. A workflow script with a
  missing model is refused the same way.
- Off for one session: `DOJO_ROUTER_OFF=1` (this plugin) or `DOJO_OFF=1` (the whole suite).
  Off for good: set the plugin's `mode` option to `off`.

## The mod (early access)

With function hooks enabled (`export CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`), the mod fills
`model` in for you on unpinned built-in dispatches (`general-purpose`, `Explore`, `Plan`):
`Explore` gets `explore_tier`, the rest get `default_tier`. The status line shows each
routing. It never overrides a model you named, a plugin agent, or a fork. `auto_route: false`
turns the filling off; `opus_cap` caps opus dispatches per session. The classic hooks work
the same with or without the mod, and stay quiet when the mod has already set the model.

## Limits

- A hook cannot see the model pin in a plugin agent's definition, so plugin agents are
  skipped. Custom agents are read for a pin from the project's agent folders (the session's
  folder up to the repository root) and your user agent folder, subfolders included. An agent
  passed on the command line or set by a managed policy is not found there.
- `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` and an `availableModels` policy can change any model
  after this plugin has spoken. Nothing here can see that.
- The workflow check is static. A whole options argument passed as a variable and `agent`
  used as a value (`agent.call`, `list.map(agent)`) are reported as "cannot be checked
  here". A `model` key whose value is a variable or a call counts as set, and a workflow run
  by `name` alone is not seen at all.
- Naming a model does not choose the right one. Haiku cannot do a judge's work. The router
  makes the choice deliberate; the table above is how to make it well.
