---
name: contract
description: "Use when work spans 3+ files or 2+ agents: write shared decisions, owned files and checks to a file first."
model: inherit
category: specify-commission
---

# Contract before fan-out

When several agents (or several files) move at once, the failure is rarely two of them editing the same line. It is two of them making different assumptions about something neither owns: a name, a data shape, a port, an error format. Write those decisions down before anyone starts.

Parallel tracks couple on decisions, not only on files. A contract file is where the decisions get frozen.

## Write the contract file first

Put it in the repo or a scratch directory, name it plainly (`CONTRACT.md`), and keep it short. Use `${CLAUDE_PLUGIN_ROOT}/skills/contract/contract-template.md` as a starting point. It holds:

1. **Goal** in two sentences, and what is out of scope.
2. **Decisions** that more than one agent depends on: names, interfaces, formats, versions, error shapes. One line each.
3. **Owned files** per agent: a list of paths no one else writes. Give shared files (configs, indexes, lockfiles) to exactly one owner, or to a final integrator.
4. **Done-check** per agent: the command that must pass, with the exit code you expect.
5. **Waves and gates**: what runs in parallel, and the clean build or test run that must pass before the next wave starts.

## Ownership is a practice here, not a lock

Disjoint ownership is what keeps parallel work from colliding, and you teach it by writing the lists and putting them in each brief. Nothing in this plugin enforces it. An agent with Write access can still write anywhere, so:

- Say it in the brief: "you own these files; report a need for anything else, do not edit it."
- Check it afterward: compare the changed files with the owned list before you accept a track.
- Where a mistake would be costly, remove the capability instead of warning. Give an agent a tools list that cannot do the damage; a prohibition in a prompt is not a control.

## Readiness questions (ask before fan-out)

- Can each agent finish using only its owned files plus read access to the rest?
- Is every shared decision in the contract, not in someone's head or in chat?
- Does each agent have a done-check it can run alone?
- Are the waves ordered by what depends on what, with a gate between them?
- Who integrates, and which checks do they run last?
- Is there anything irreversible in the plan (push, deploy, publish, delete)? It needs a yes from the person first.

If you cannot answer one, the contract is not ready. Fix the contract, not the agents.

## During the run

- Do not edit the contract mid-wave. If a track finds a decision is wrong, it reports; you amend the file and tell every affected agent, then continue.
- Cap concurrency to what the machine and your rate limit can carry. Some tracks need exclusive access to something (a simulator, a port, a database); do not fan out around them.
- At the gate, run the build yourself. A report that the build is clean is a claim until you have seen it.
- Close with counts: dispatched, returned, failed. See `delegate`.

Related: rule 4 in `${CLAUDE_PLUGIN_ROOT}/PROTOCOL.md`; `delegate` for the per-agent brief.
