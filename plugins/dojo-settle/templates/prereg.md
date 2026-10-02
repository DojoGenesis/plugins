# Pre-registration: {{title}}

Everything above the marker line near the end of this file is the pre-registration. Write it, record its
digest with `prereg.py freeze`, and only then measure. Results go below the marker, so adding them does not
change the digest.

## 1. What is decided

<!-- One sentence naming the choice, then what changes under each outcome. If nothing changes either way, stop: this is not a question an experiment can settle. -->

{{hypothesis}}

## 2. Incumbent, measured here

<!-- The thing you would keep. A figure published elsewhere is a hypothesis until this harness reproduces it. Say how you will reproduce it. -->

{{incumbent}}

## 3. References and confound

<!-- Name every reference. Say which could fake the result. Scoring a candidate against its own output measures agreement with itself, so carry a second, independent reference and require the bar in both. -->

{{references}}

## 4. The rule and the bars

### Decision rule

<!-- A rule a stranger could apply to the numbers without asking you what you meant. -->

{{rule}}

### Numeric bars

<!-- Numbers, not adjectives. Include the null: the result that means keep the incumbent. -->

{{bar}}

## 5. What would refute the option you want

<!-- Plain terms, in advance. An empty section here is the usual leak. -->

{{refutation}}

## 6. Frozen grid and held-out tasks

### Frozen grid

<!-- Every configuration you will run. A cell added after the results is how a null becomes a win. -->

{{grid}}

### Baseline arm (without)

<!-- The same tasks with the change absent, run beside the with arm. The headline is the with-minus-without difference, not the with arm's score alone. Say how the without arm is produced. -->

{{baseline}}

### Held-out task author

<!-- Name or role of whoever wrote the test tasks and is not the person who built the thing under test. This is free text and nothing checks it. -->

{{held_out_author}}

### Task where the protocol should lose

<!-- At least one task where the thing under test should do worse than leaving it out, or do nothing. -->

{{should_lose}}

MEASUREMENTS BEGIN BELOW THIS LINE

## Results

Raw numbers per cell, including the cells that make the option you want look bad. Name every configuration
that disagreed with itself.

## Ruling applied mechanically

Paste the decision rule, then the numbers, then what the rule outputs. If the null fires, say so and keep the
incumbent.

## What outranks the ruling

The mechanism the measurement exposed on the way. Rank it above the verdict when it deserves that.

## Gaps and handicaps

What could not be tested and why. What was found broken and left alone. Any input the arms do not share.

## Digest check after write-up

Paste the `verify` output here, and the digest you recorded outside this file.
