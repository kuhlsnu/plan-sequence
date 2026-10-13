# Step 4: Scope decision

The one human input the sequence cannot derive. Ask the requester what ships now, on the **reconciled** split: stabilizer's, plus whatever the adversary moved. Never show the pre-adversary split.

## Ask

Options are forks in the work, never approve/reject and never pause/defer:

- Lane A as reconciled
- Lane A plus named Lane B promotions (name the items, not "some SHOULDs")
- A narrower slice than Lane A (name what drops)

Stay neutral. Do not mark an option recommended and do not editorialize in the descriptions. The requester is deciding, not ratifying.

If they answer with prose, take the prose as the scope, restate it in one line, and record it as `custom`. Never fall back to Lane A silently after asking.

## Record

```
python plan_sequence.py record-scope plan.md --decision as-reconciled
python plan_sequence.py record-scope plan.md --decision promote --item 4e --item 5a
python plan_sequence.py record-scope plan.md --decision narrow --note "drop the zero-quantity test"
python plan_sequence.py record-scope plan.md --decision custom --note "<their words>"
```

Each `--item` is a move ref exactly as the verdict's MOVES lines wrote it, and must name exactly one move.

Restate the chosen scope in one line in the transcript.

## Re-confirm after changes

If the fold in step 6 changes what Lane A contains, the recorded answer is stale. Ask again and record again; the highest sequence wins.
