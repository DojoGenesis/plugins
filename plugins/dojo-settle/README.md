# dojo-settle

Settle claims with evidence: pre-registered experiments, with/without baselines and decision gates before anything becomes a number.

Part of the Dojo Genesis protocol suite. Tier: classic (skills and a script; no hooks, no mod).

## Install

```
/plugin marketplace add DojoGenesis/plugins
/plugin install dojo-settle@dojo-genesis
```

## What it does

Write down the rule before you look at the data, and keep a digest that shows you didn't change it afterwards. Frame a big decision as options with the evidence each one needs. Scaffold evals that compare a plugin against no plugin, and read the difference honestly.

Nothing here runs by itself. You invoke a skill, or you run the script.

## Components

| Component | Count | Files |
|---|---|---|
| Skills | 3 | `settle`, `decision-gate`, `eval-kit` |
| Scripts | 1 | `scripts/prereg.py` |
| Templates | 2 | `templates/prereg.md`, `templates/case.yaml` |
| Eval scaffolds | 2 | `evals/protocol-should-lose`, `evals/with-without-delta` |
| Hooks | 0 | none |
| Agents | 0 | none |
| Commands | 0 | none |

- `settle`: a pre-registered experiment in nine steps. Hypothesis, decision rule and numeric bar are written and digested before the first run; the held-out tasks are written by someone other than the builder; there is a with/without baseline arm and at least one task where the protocol should lose; the digest is checked again after the write-up.
- `decision-gate`: one sentence, up to three options (get, give up, risk, undo cost), the evidence each option needs, and a default only when that evidence is in hand.
- `eval-kit`: how to write a `case.yaml`, run `claude plugin eval --ablation with-without --max-cost-usd <cap> --no-publish`, confirm the plugin actually loaded, and read the with-minus-without delta.

## The script

The skills call it through `${CLAUDE_PLUGIN_ROOT}/scripts/prereg.py`. From a checkout, run it from the plugin directory:

```
python3 scripts/prereg.py create study/prereg.md --title "Window length" --rule "..." --bar "..." --refutation "..."
python3 scripts/prereg.py freeze study/prereg.md
python3 scripts/prereg.py verify study/prereg.md --expect <digest you recorded elsewhere>
```

- `create` renders `templates/prereg.md` and never overwrites. It records no hash.
- `freeze` refuses unless the marker line is present, no `{{placeholder}}` is left in the prose (HTML comments and fenced code blocks may quote one), and each of ten sections holds more than placeholders: what is decided, incumbent, references, decision rule, numeric bars, what would refute the option you want, frozen grid, baseline arm (without), held-out task author, and the task where the protocol should lose. Empty counts as nothing, and so does a body made only of placeholder words: `none`, `n/a`, `TBD`, `T.B.D.`, `TODO`, `FIXME`, `TK`, `XXX`, `...`, `??` or a lone dash, with or without list numbering, brackets, quotes, emphasis, a table pipe or a trailing `?` (`TBD?`, `1. TBD`, `(TBD)`, `**TBD**`, `| TBD | TBD |`, `TBD (fill in later)`, `- [ ] TBD`). A heading or body that sits only inside an HTML comment doesn't count either, and a comment that is opened and never closed is refused, because a renderer would hide everything after it. A `<!--` quoted in a code span or a fenced block opens nothing. It then writes `<file>.sha256` and never overwrites it. There is no `--force`; to amend, create a v2 file that cites v1's digest.
- `verify` recomputes the digest and compares. Exit 0 means the digests match, 1 means they differ or the file was refused, 2 means it couldn't run.

The digest covers every byte before the first line that is exactly `MEASUREMENTS BEGIN BELOW THIS LINE` and is not inside a fenced code block. Results go below that line without changing it. Two normalizations only: a leading byte-order mark is dropped and CRLF becomes LF, so another checkout of the same file still matches. It uses one digest over the whole pre-registration section, which includes the decision rule, rather than a digest of the rule alone.

## Kill switches

Nothing runs on its own, so there is nothing to switch off. The script is a command you type. It doesn't read `DOJO_OFF` or any other switch.

## Honest limits

- The digest shows the text above the marker is unchanged since you recorded the digest. It doesn't show the text is true, who wrote it, or when. The `.sha256` file can be rewritten together with the document, and its timestamp is your local clock. Record the digest somewhere you can't quietly rewrite (a commit, a message to your reviewer) before you run anything, then use `verify --expect`.
- The emptiness check is shallow. It catches placeholders, not weak content: a vague sentence passes. It doesn't judge whether a rule or a bar is any good.
- Comment stripping covers `<!-- -->` only. A `<style>` or `<script>` block can still hide a required section from a renderer and freeze will accept it.
- "Held-out author" is a free-text field. Nothing checks that the person named didn't build the thing under test.
- The eval scaffolds have not been run, because running them spends money. No with/without result from this plugin exists. The website's proof page lists it as not yet measured.
- Both scaffolds were written by the plugin's author, so they aren't held out. Have someone else write real prompts before reading anything into a delta.
- `claude plugin validate` does not read `case.yaml`. The unit tests check the scaffolds against the key list `eval-kit` documents; only a paid run proves a case works.
- Function hooks aren't involved, so there is no early-access path in this plugin.

## Tests and what was run

Tested with Claude Code 2.1.286. What ran: the unit tests (`cd plugins/dojo-settle && python3 -m unittest discover -s tests -v`, including under the system Python 3.9 and with a scrubbed environment), `claude plugin validate --strict`, and a scan for internal references. No eval was run.

## License

Apache-2.0.
