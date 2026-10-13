# Step 2: Stabilize

Run the `stabilizer` skill on the plan, then `stabilizer-gate` on its output. Both live in [plan-stabilizer](https://github.com/kuhlsnu/plan-stabilizer).

Capture the post-gate text: classification, Lane A items, Lane B items with `MUST`/`SHOULD`/`MAY` tags, and the flags. Step 3 takes it as input.

The statements tagged `[LOAD-BEARING]` and `[CHOICE]` in step 1 are recognised by stabilizer as `MUST` and `MAY` when auditing a scoped plan, so it audits them instead of re-deriving the split.

## Do not ask the scope question here

Stabilizer states the choice as text and the gate asks it last. In this sequence that dialog is deferred to [step 4](04-scope-decision.md), after the lane adversary has had its turn. Asking now would ask about a split the adversary is about to move.

`stabilizer-gate` closes with its own Step 6, which opens the same dialog. Skip that step here and say so in your output: run its five checks and emit the corrected audit as text. Step 4 asks the question once, on the reconciled split.

## Number the items for the adversary

The adversary cites a ref for each move, and `record-scope --item` must match that ref exactly. A plan with no numbered items makes it write prose refs that are long to type and easy to get wrong. Before saving the audit, label every Lane A and Lane B item (`A1`, `A2`, `B1`...), and add a first line to the audit: `Cite items by these labels.`

## Failure

If stabilizer or the gate errors, stop and report it. There is no recorded step for this one; the audit text is the artifact and step 3 consumes it.
