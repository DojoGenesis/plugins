# Evidence rules: short cases and the claim-to-check map

Read this when a rule in SKILL.md is not clear enough to act on. The cases are composites, written without names or numbers.

## Cases, by rule

**1. A report is a claim.** A build agent finished and reported "done, typecheck clean, tests pass". The tree showed it had completed a fraction of its tasks, and one build script failed on another operating system. Reading the report told nobody that; running the gates did. Later, a quick prototype shipped its own ticked-box docs while its headline figures matched no data source. A report with no saved artifact behind it is a hypothesis.

**2. Load the real page.** A content migration passed typecheck, the full test suite, API output and row-level SQL checks. Every cover image still rendered as a grey box, because the production content-security header refused the external image host. The only check that could see it was loading the page.

**3. Empty output is not evidence.** A diagnostic wrapped in a `timeout` command printed nothing on a machine that has no such command. The silence was read as "the service is wedged", and the service was restarted, which destroyed the evidence it had been answering all along. Separately, a recursive search used a different implementation that skipped ignored folders, found a framework "nowhere", and was wrong. Run the probe against a known positive in the same invocation style first. For lists: a product endpoint returned a first page with no error, and three downstream scripts inherited the truncation. Compare the count with the reported total.

**4. A check built by the code under test.** A privacy sweep stayed green while a real leak shipped, because its fixtures were built through the library, and the library refuses to construct the one dangerous state. A later sweep with hand-forged inputs found it. Success is also never proof that a control fired: force a failure through it once.

**5. Count returns.** A fan-out harness turned an errored agent into an empty result, so a scorecard reported every lens dispatched and verified after some had died on API errors. Report three numbers, and treat a missing return as a failure until shown otherwise.

**6. A hash beats a version.** An update command printed "updated" and wrote the new version into the manifest, while a cache keyed by version kept serving the old bytes. Changed bytes need a bumped version, and every hop needs a hash.

## Claim to check

| Claim | The check | A weak substitute to avoid |
| --- | --- | --- |
| tests pass | the project's test command, output shown | reading the test file, or an earlier run before the last edit |
| typecheck / lint clean | the project's own command | running the tool on an untouched package |
| deployed | fetch the live URL, load the page, compare the served hash | the deploy command's "success" line |
| schema change is safe | run it on a copy of production's shape, read the statements it prints | a green migration unit test |
| endpoint returns everything | count against the source's total, follow pagination | one page of results |
| agent did the work | its non-empty answer plus the files it names | its own "complete" |
| a probe found nothing | the same probe on a known positive | the empty output |

## What the hook can and cannot see

The Stop hook sees the main thread's session: its edits, its commands, their results and the final message. It can show that a check ran and came back clean after the last change. It cannot show that the check was the right one, and it cannot see inside a subagent. A subagent's report reaching you is rule 1: treat it as a claim and check it yourself.
