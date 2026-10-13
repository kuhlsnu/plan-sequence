# Step 8: Finalize

```
python plan_sequence.py finalize plan.md
```

Runs every gate and, only if all pass, appends a results summary to the sidecar and writes `plan.stamp.json`. The stamp holds the plan's sha256 and the sidecar's sha256 (taken after the results summary is written).

## What it checks

| Gate | Fails when |
|------|-----------|
| Steps recorded | any of intent, verdict, scope, findings, check is missing for this run |
| Intent still holds | the section was edited into an invalid state since step 1 |
| Inferred statements asked | `[inferred]` intent statements still stand and `intent --inferred-asked` was never recorded, or more stand now than when it was recorded |
| Disposition | a CRITICAL has no disposition, cites a missing or unchanged section, or any disposition line is unparseable or names an unknown id |
| Mechanical check current | the plan changed after `record-check` |
| Mechanical check result | `fail`, or `stale` without an override |

It prints every failure at once, not the first.

## Escape hatches

Each is recorded in the sidecar and the stamp, and `verify` reports `WITH OVERRIDES`:

- `--override-disposition "<reason>"` bypasses the disposition gate.
- `--override-stale "<reason>"` stamps a plan the check found already implemented.
- `--override-inferred "<reason>"` stamps a plan whose `[inferred]` intent statements were never put to the requester. The number standing is recorded with the reason.

Use them when the requester consciously accepts the gap. Never to get past a gate you could fix.

## The results summary

Generated from the recorded blocks, not typed: run id, intent counts, verdict, scope, rounds, each reviewer and whether it was blind or primed, finding counts, disposition counts, mechanical check, and any overrides. Report it to the requester as written.

## After the stamp

Edit nothing. Any change to the plan makes `verify` exit 3. A re-review starts with `init`, which deletes the stamp.

Tell the requester what the stamp means and does not: this plan was reviewed in order and is unchanged since. It does not authorize execution.
