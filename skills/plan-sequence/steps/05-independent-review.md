# Step 5: Independent review

Someone other than the plan's author reviews the plan against the code and the stated intent. Findings are recorded in a rigid format so step 6 can arbitrate them.

## Choose the reviewer

Any reviewer that can read the plan and the repository and return findings: another model from a different family, a fresh subagent, a person. See [adapters.md](../references/adapters.md) for examples.

What matters:

- **Different from the author.** A same-family reviewer shares the author's blind spots.
- **Read-only.** The reviewer reads and reports; it does not edit.
- **Blind by default.** Do not show it earlier findings. If you must (a second round), pass `--primed`, and the results will say agreement there is endorsement, not independent confirmation.

## Brief it

Build its prompt into a file with `python plan_sequence.py build-prompt plan.md reviewer --out review_prompt.txt` (add `--docket <earlier findings>` for a second round, and record that round `--primed`). Give it that file and read access to the repo; the text comes from [reviewer-prompt.md](../references/reviewer-prompt.md). The prompt already carries the grounding rule: every finding quotes a phrase from the plan or cites `path:line`.

## Normalize and record

Turn the reviewer's output into a JSON array in [the findings format](../references/findings-format.md), then:

```
python plan_sequence.py record-findings plan.md --file findings.json --reviewer "name or model" [--primed]
```

Over-include on ambiguity. A dropped CRITICAL is the failure this pass exists to prevent, and a finding recorded unnecessarily costs one disposition line.

An empty array (`[]`) is a valid record: the reviewer ran and found nothing.

`--reviewer` is a name only, for example `'codex gpt-5.6-sol'`. Provenance comes from `--primed`: the results summary adds blind or primed itself, and the script warns when the name already says so.

The script warns when an anchor is neither a phrase found in the plan nor a `path:line`. Treat an ungrounded finding as the one to doubt.

Each call also snapshots every section of the plan. Step 6 compares a finding's cited section against the snapshot from the round that raised it, so **record before you fold that round's findings**. If the plan already contains the fixes when you record, the snapshot equals the final text and every `accepted` citation will fail as unchanged. A later round is measured against the plan as it stood when that round was recorded, so folding round 1 never counts for round 2.

A plan re-entering review often still carries the previous review's `## Finding Disposition`. Remove it first. The script refuses to record a finding whose id already has a disposition line, because a stale line would otherwise answer a new finding nobody read.

## Rounds

Three finder passes at most per run. The fourth `record-findings` is refused. A second pass is for verifying a fold or covering something the first missed; ids must be new each round.
