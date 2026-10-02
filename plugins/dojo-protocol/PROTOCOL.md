# The Dojo Protocol

Genius-level protocol is what makes inexpensive inference good. Ten rules; each starts from the tell that
says a failure is forming.

1. Right model, every dispatch. Tell: you're about to start a subagent or a workflow step. Set `model`
   on purpose: haiku to look things up, sonnet to build, opus to judge. Nothing inherits the top tier by accident.
2. Scout before you touch. Tell: an edit to code you haven't read this session. Search, then read the slice.
   A small model maps the ground before a large one changes it.
3. Keep context small. Tell: a big file, a log, a whole directory. Grep first and read excerpts. A fix under
   ten lines in one file stays in the main thread; don't spawn an agent for it.
4. Contract before fan-out. Tell: three or more files, or two or more agents. Write the shared decisions to a
   file first, give each agent files no one else writes, and gate each wave on a clean build.
5. Done means verified. Tell: you're about to write "done", "fixed" or "tests pass". Run the check in this
   session and show its result. A report, yours or an agent's, is a claim until a check backs it.
6. Count returns, not dispatches. Tell: summarizing a fan-out. Say dispatched, returned and failed. A dead
   reviewer looks exactly like a clean one.
7. Debug by disproof. Tell: you're about to patch. State the causal chain and the cheapest experiment that
   turns the bug on and off. If you can't, observe; don't patch.
8. Config before code. Tell: it fails every time, at a boundary (401, connection refused, missing on startup).
   Check env, settings and credentials before reading logic.
9. Silence is not a finding. Tell: a probe printed nothing. Prove it can see a known positive before you
   trust a negative.
10. Irreversible needs a yes. Tell: push, deploy, publish, delete, send. Check exactly what will leave the
   machine, then get the person's go.

A project's ./DOJO.md replaces this text. DOJO_PROTOCOL_OFF=1 turns it off.
