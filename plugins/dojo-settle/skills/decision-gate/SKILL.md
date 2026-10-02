---
name: decision-gate
description: Frame a bet-level decision as one sentence and up to three options, each with what you get, give up, risk and undo cost, plus the evidence it needs. Names a default only when that evidence is in hand.
model: inherit
category: govern-publish
---

# decision-gate

Turn a pile of analysis into the thing a person can actually rule on: one sentence naming the choice, at most three options priced in plain words, a line on what isn't at stake, how hard each option is to undo, and, only when the evidence supports it, a default they can veto. The analysis stays where it is as the archive. The page you write is the ask.

Use it for bet-level calls: money committed, a direction locked in, a path that's expensive to undo. Skip it for routine picks; a plain confirm is enough there.

## Steps

1. **Check it's a real gate.** Does it commit money, lock in a direction, or cost real effort to reverse? If not, ask the plain question and move on.
2. **One sentence.** State the choice. If you can't say it in one sentence, the options aren't cut cleanly; re-split them first.
3. **Up to three options.** For each: **you get**, **you give up**, **biggest risk**, **undo cost**. Spell out any shorthand; nobody should need a glossary to read their own decision. If there are more than three, merge the dominated ones and say what collapsed into what.
4. **Evidence per option.** This is the step that keeps a recommendation honest. For each option, list the evidence that would have to be true for it to be the right call, what you have in hand, and whether the status is `have` or `not yet`:

   | Option | Evidence needed | Evidence in hand | Status |
   |---|---|---|---|

   Say `not yet evidenced` wherever it's missing. Evidence means something you checked this session or a source you can name, not a feeling or a summary of one.
5. **What isn't at stake, and what's reversible.** Say what stays the same across every option so the person can stop weighing it. Mark undo cost per option; unequal undo costs often decide a choice better than more analysis.
6. **Default, only if earned.** A default may name an option only when every row of its evidence is `have`. Then frame it as "going with this unless you'd rather X". Otherwise write: `no default yet; to settle it: <the smallest experiment that would produce the missing evidence>`, and point to the `settle` skill in this plugin to run it.
7. **Ship the page inline, not the brief.** Link the source brief or ADR if there is one; don't re-paste it.
8. **Sub-picks.** If secondary choices hang under the main call, ask them afterwards with `AskUserQuestion` (or in plain text if that tool isn't available): at most four options per round. List a recommended option first only in the evidenced case from step 6; otherwise list none as recommended.
9. **Record the ruling only on plain words.** A thumbs-up, a quick "yeah", a "sounds good" or a picker click on a bet-level question is a lean, not a ruling. Treat the gate as open and ask again at a moment they can answer in words. When they do, write their words verbatim, dated, in the project's own `decisions/` or ADR directory if it has one; if it has none, put it in the session and say where.

## Page shape

```
Decision: <one sentence>

A. <option>  get: ... | give up: ... | risk: ... | undo: ...
B. <option>  ...

Evidence: <the table from step 4>
Not at stake: <what stays the same>
Default: <option and why>  OR  no default yet; to settle it: <smallest experiment>
```

## Anti-patterns

- Shipping the dense brief as the ask.
- More than three options.
- Codenames or internal shorthand instead of plain terms.
- A recommendation with a `not yet` in its evidence row.
- Logging a lean as a ruling.
- Leaving what isn't at stake for the reader to rediscover.
- Quietly leaving off the option nobody argued for; if you dropped one, name it and say why.
