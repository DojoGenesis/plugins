# dojo-router

No subagent silently inherits your most expensive model. Warns or blocks unpinned dispatches; the mod routes them by role.

A dispatch that names no model runs on whatever your session runs on. `dojo-router` notices
that moment, for subagents and for workflow steps, and either tells you (default), refuses
the dispatch, or, with the mod, fills the model in by role.

## Install

```
/plugin marketplace add DojoGenesis/plugins
/plugin install dojo-router@dojo-genesis
```

## What is inside

| Component | Tier | What it does |
|---|---|---|
| `hooks/agent_model.py` | classic | PreToolUse on `Agent` and `Task`: flags a dispatch with no model |
| `hooks/workflow_models.py` | classic | PreToolUse on `Workflow`: flags `agent()` calls in a script that set no model |
| `hooks/register.ts` | mod (early access) | fills `model` in by role, shows the routing, optional opus cap |
| `skills/router` | classic | the role table and how to set `model` on a call and in a workflow |

### Role to model

| Role | Alias |
|---|---|
| scout | `haiku` |
| builder | `sonnet` |
| reviewer | `sonnet` |
| judge | `opus` |

## Classic tier: works with function hooks off

The classic hooks are plain `python3` scripts (standard library only, Python 3.9 or newer).

- **Agent dispatches.** A call is flagged when its `subagent_type` has no `:` and is not
  `fork`, its `model` is missing, empty or `inherit`, no `CLAUDE_CODE_SUBAGENT_MODEL` or
  `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` is set, and no agent file pins a model for that name.
  Agent files are read from every `.claude/agents` folder between the session's folder and
  the repository root (the first folder holding `.git`; without a repository the climb
  continues upward), and from your user config's `agents` folder, subfolders included, matched
  on the frontmatter `name`. The nearest folder wins. The read is bounded in files and folders
  and never follows a symlinked folder. A missing `subagent_type` counts as
  `general-purpose`. The built-in `statusline-setup` agent pins its own model and is skipped.
- **Workflow scripts.** The script is read from `scriptPath` when given (the Workflow tool
  gives it precedence), else from the inline `script`. A small tokenizer skips comments,
  strings and plain template text, then checks the options object of each real `agent()`
  call for a top-level `model` key. A model written as the string `''` or `'inherit'`, or as
  `undefined`, `null` or `void 0`, counts as none. Output carries the counts (calls found,
  calls that set a model) and the line, plus the `label`, of each call that sets none. These
  are reported as "cannot be checked here", never as fine: an options argument that is not an
  object literal (a variable, a ternary, a spread argument), a `model()` method or getter, a
  computed key, and a spread that comes after an empty or `inherit` model. So is `agent` used
  as a value (`agent.call(...)`, `list.map(agent)`, an alias). Calls with an `agentType`
  containing `:` are plugin agents and are skipped. Scripts over 512 KB (a file or an inline
  script), unreadable paths and non-regular files are allowed silently. The check is linear in
  the script's size.
- **Modes.** `warn` (default) adds context for the model and a message for you, once per
  session per subagent type (once per session per script for workflows), and never decides the
  permission question. `block` refuses a dispatch it is sure about, every time, with a reason
  that says how to retry: an unpinned `general-purpose`, `Explore` or `Plan` dispatch, and a
  workflow script with a call that sets no model. A custom agent type is only warned about
  in `block` mode, because its own pin can live somewhere the hook cannot read and a refusal
  would leave no way through except overriding that pin. `off` is silent.

## Mod tier: early access

Function hooks are off on many accounts. To try the mod:

```
export CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1
```

(or add it under `env` in `~/.claude/settings.json`), then start a new session. With it on, `hooks/register.ts`:

- fills `model` in on an unpinned `Agent` call (`tool.call`), with `Explore` going to
  `explore_tier` and `general-purpose`, `Plan` and a missing type going to `default_tier`;
- backs that up for spawns that bypass the tool (`agent.spawn`), under the same exclusions
  and only for engine-provided spawns;
- shows each routing on the status line (`dojo-router: Explore -> haiku`) and clears it when
  the next turn starts;
- with `opus_cap` above 0, counts the opus dispatches the engine actually resolves, and once
  the count reaches the cap, stops routing unpinned dispatches to opus, with one toast.
  After the cap, `Explore` still goes to `explore_tier` and the other built-in types go to
  `default_tier`; a tier that is `opus` becomes `sonnet`. So a capped `Explore` is not raised
  to `default_tier`.

It never touches a call that names a model, a plugin agent (type with `:`), a fork,
`statusline-setup`, or a custom agent type. When the engine offers `general-purpose`,
`Explore` or `Plan` from a source other than `built-in` (a user or project agent of that
name, which may pin its own model), the mod leaves that name alone from then on. It stands down when `DOJO_OFF=1`,
`DOJO_ROUTER_OFF=1`, `CLAUDE_CODE_SUBAGENT_MODEL` or `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` is set.

Routing happens in `tool.call`, above the classic hook, so with the mod on the classic hook
sees the filled-in model and stays silent. In `block` mode with the mod on, nothing is blocked
because the mod has already fixed the call. That is expected.

## Options

| Option | Default | Applies to | Meaning |
|---|---|---|---|
| `mode` | `warn` | classic | `warn`, `block` or `off` |
| `default_tier` | `sonnet` | both | alias suggested or filled in for unpinned dispatches |
| `explore_tier` | `haiku` | both | alias suggested or filled in for `Explore` |
| `auto_route` | `true` | mod | fill in `model` on unpinned built-in dispatches |
| `opus_cap` | `0` (off) | mod | opus dispatches per session before unpinned dispatches stop landing on opus (`Explore` keeps `explore_tier`, the rest go to `default_tier`); independent of `auto_route` |

Options reach the classic hooks as `CLAUDE_PLUGIN_OPTION_<KEY>` and the mod through
`register(on, options)`. A value outside the allowed list falls back to the default.

## Kill switches

- `DOJO_OFF=1`: the whole suite.
- `DOJO_ROUTER_OFF=1`: this plugin, classic hooks and mod.
- `mode` set to `off`: the classic hooks only. `auto_route` set to `false`: the mod's
  routing only.

## Honest limits

- A hook cannot see the model pin in a plugin agent's definition, so plugin agents are never
  flagged or routed. Custom agent files are read for a pin as described above; an agent
  that is not found there (passed with `--agents`, set by a managed policy) is flagged with a
  note to ignore the message if its definition pins one, and is never blocked.
- The mod learns that a user or project agent has taken over a built-in name only from the
  engine's agent offers. If it has not seen such an offer, it routes by name.
- `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` and an `availableModels` policy can change any model
  after this plugin has acted, and nothing here can see that. The status line shows the
  alias the mod chose, which under such a policy may not be the model that runs.
- Routing applies `default_tier` as written. A session that runs on `haiku` can have its
  unpinned subagents raised to `sonnet`.
- The workflow check is a static read of source text, and it does not look into the value of
  a `model` key. A model given as a variable (`{ model: m }`, `{ model }`), a call
  (`{ model: pick('x') }`), an expression (`{ model: c ? 'opus' : undefined }`) or a template
  literal (even `` `inherit` ``) counts as set, and so does a literal model followed by a
  spread (`{ model: 'haiku', ...o }`), although the spread could override it. Such a call is
  not reported, so a script can pass this check and still run an agent on your session's
  model. A workflow started by `name` alone
  (`Workflow({ name: '<plugin>:<workflow>' })`) is not read, because the hook does not receive
  the file: only `script` and `scriptPath` calls are checked.
- The mod's opus counter lives in the running session's process. It resets when the plugin
  reloads (an option change) and is not a daily cap. Dispatches issued in the same message
  are counted as they resolve, so a cap can be passed by a few at once.
- Whether the engine exports a stored default for an option the person never set is
  unverified, so the hooks carry the manifest defaults themselves.
- No automated test runs the classic hooks inside the engine: the kit test harness does not
  execute `hooks.json` command hooks. The two halves are tested separately: a mod test shows
  that the rewritten input reaches the layer beneath, and a unit test shows the classic hook
  stays silent on that rewritten input.
- Nothing here measures what routing changes. There are no numbers in this plugin, and none are claimed.

## Tests

```
cd plugins/dojo-router && python3 -m unittest discover -s tests -v
CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/dojo-router
```

`evals/unpinned-dispatch-pinned/case.yaml` is a scaffold for `claude plugin eval`; it has not been run.

Tested with Claude Code 2.1.286.
