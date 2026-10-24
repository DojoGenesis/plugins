# Brief for the held-out task author

You are writing small, self-contained coding tasks for an evaluation of coding agents (Claude Code). You did not
build the software being evaluated and you must not look at it: write from this brief alone. Do not read any
repository, plugin, eval file or anything outside the output directory given in your instructions.

There are two families of tasks. Seven tasks in all.

## Family 1: five tasks named `hr-*` (one agent that hands work to helpers)

Each task sets up a tiny Python project and gives the agent a prompt in a user's voice. The prompt asks the agent
to hand part of the work to subagents (helper agents it can start, each with its own instructions) and then to
finish the job itself. Phrase it naturally, for example "use subagents to find ... and ..., then fix it" or "have a
helper agent look through ... first". The agent decides how to brief the helpers.

- **Four standard tasks.** The part handed to helpers is reading and finding: where a value is defined, which
  functions call another, how a setting flows through several files, which of several modules handles a case. The
  project should have roughly 5 to 10 small files so the lookup is real. After the helpers report, the agent makes
  a small code change (a bug fix or a small feature). Vary them: some have a visible test file the agent can run,
  some don't; at least one where the obvious fix is wrong and only careful reading or running the tests shows it.
- **One task where careful reasoning matters.** The part handed to a helper needs judgment, not lookup: for
  example, a helper reviews one module and finds the cause of a described wrong result. Make the cause subtle, so a
  quick read misses it (an off-by-one in a rare branch, an ordering assumption, a rounding or boundary case, state
  shared between calls). The visible tests, if any, must not catch it. Your hidden tests must.

## Family 2: two tasks named `hf-*` (a parallel build tool)

These tasks are run through a build tool that takes a goal, a list of tracks and a list of gate commands. It
starts one builder per track at the same time, each builder writes only the files its track owns, and at the end
the gate commands must pass. The builders cannot talk to each other. So:

- Two tracks per task. Each track has a `name` (short, lowercase), a `prompt` (everything a builder who has read
  nothing else needs: the files to write, function names, signatures and data shapes it must use), and `files`
  (repository-relative paths only that track writes; no globs; the two tracks' files must not overlap).
- Any name or shape one track uses from the other must be stated in both prompts, so neither builder has to guess.
- `gates`: one to three shell commands that must pass at the end (for example `python3 -m unittest discover -s tests -q`).
  The scaffold may include visible tests for the gates, or a track may own the test file.
- **One standard task** of modest size.
- **One task where careful reasoning matters** in one track: an algorithm or rule with an edge case that a quick
  implementation gets wrong (the visible gate tests may pass while your hidden tests catch it).

The scaffold for family 2 must also make the directory a git repository with one commit:
`git init -q && git add -A && git -c user.name=scaffold -c user.email=scaffold@example.invalid commit -qm scaffold`.

## Rules for every task

- Python 3 standard library only. No network, no package installs, nothing outside the project directory.
- The prompt (and for family 2 the goal and both track prompts) stands alone: no absolute paths, no home-directory
  paths, nothing outside the scaffolded files.
- Do not use any of these words, in any form, in a prompt, goal or track prompt: model, haiku, sonnet, opus, cheap,
  cost, expensive, route, routing, tier, dojo, verify, protocol, claim, evidence.
- Keep each family 1 task small enough for an agent to finish in under 16 turns, including the helpers' work.
- Write `expected_outcome` as one sentence describing a correct finish.

## What to write for each task

A folder `<out>/<case-name>/` (lowercase letters, digits and hyphens; family 1 names start with `hr-`, family 2
with `hf-`) containing:

1. `scaffold.sh`: a POSIX shell script that writes the project's files into the current directory (`printf` or
   here-documents; `set -e` at the top). It must not write the hidden tests or the reference solution.
2. `case.json`:
   ```json
   {
     "name": "hr-example",
     "family": "hr",
     "kind": "standard",
     "description": "One sentence.",
     "prompt": "...",
     "expected_outcome": "..."
   }
   ```
   `kind` is `standard` or `careful`. Family 2 tasks also carry `"goal": "..."`, `"tracks": [{"name": "...",
   "prompt": "...", "files": ["..."]}, ...]` and `"gates": ["..."]`; their `prompt` field is left empty (the
   evaluator writes the instruction that starts the build tool).
3. `hidden/test_hidden.py`: `unittest` acceptance tests for a correct finish, run from the project root after the
   agent is done (`python3 -m unittest test_hidden` with the file copied into the root). Standard library only.
   Test behaviour through the project's own modules and functions, not file text. They must fail on the scaffold as
   written and pass on your reference solution.
4. `reference/`: the files of one correct finish, at their project-relative paths (only the files that change or
   are added).

## Check your work, and report it

For every task, in a fresh empty temporary directory:

1. run `scaffold.sh` and list the files it wrote;
2. copy `hidden/test_hidden.py` into the directory and run `python3 -m unittest test_hidden -q`: it must fail;
3. copy `reference/` over the directory and run the hidden tests again: they must pass; for family 2, also run every
   gate command and confirm it passes on the reference;
4. for any task with visible tests, run them on the scaffold and say whether they pass or fail before a fix.

Report each command you ran and its exit code. Report anything you could not make work.
