# Step 3: Lane adversary

A fresh reviewer pressure-tests stabilizer's Lane A / Lane B split. Its only job is the split: not the code, not the architecture.

## Run it

1. Build the prompt into a file with the script, so you never retype the plan or the prompt:

   ```
   python plan_sequence.py build-prompt plan.md adversary --audit audit.md --out adversary_prompt.txt
   ```

   It writes these parts, in this order:
   - **Preamble:** "You are a single-pass review agent. You already have everything you need in this prompt, so work only from the text provided below. Apply the prompt that follows VERBATIM and produce ONLY the rigid output format it defines (VERDICT / MOVES / RATIONALE): no preamble, no commentary, no closing summary."
   - **The prompt** in [lane-adversary-prompt.md](../references/lane-adversary-prompt.md), unedited.
   - **The plan body,** then the stabilizer audit under a `## Stabilizer Lane Assignments` heading.
2. Give it to a context that has not seen this conversation: a subagent, a separate CLI call, a person. A model reviewing a split it just produced rubber-stamps it.
3. Hand the reviewer the **file path**, not the text, and have it write its answer to an output file itself. Keep that file as the verdict; do not retype or retouch it, because arrows and dashes degrade. Relayed output can also be altered in transit: one run saw `<pk>` come back as `&lt;pk&gt;` through a notification. `record-verdict` warns when the text contains HTML entities, so compare with the reviewer's own file before recording.

## Record it

```
python plan_sequence.py record-verdict plan.md --file adversary.txt
```

The script rejects, and you must re-run the adversary or fix the transport for:

- anything not starting `VERDICT: agree|rebalance`
- `agree` without `WEAKEST_MOVE:` and `RATIONALE:`
- `rebalance` with no parseable moves (a failed review, not a pass)
- a move type outside `A→B-SHOULD`, `A→B-MAY`, `B-SHOULD→A`, `B-MAY→A`, `B-SHOULD↔B-MAY`, `B-MAY↔B-SHOULD`
- a bare ` - ` between the three fields (` — ` and ` -- ` both work; `->` and `<->` are accepted for the arrows)

Recording is idempotent per run: replaying the same text is a no-op, and different text is refused. To redo it, start a new run with `init`. MOVES lines must come before `RATIONALE:`; a move after it is an error.

## Reading the result

- `agree` is a valid pass. The weakest move is still recorded.
- `rebalance` moves are proposals. Nothing moves until the requester decides in step 4.
