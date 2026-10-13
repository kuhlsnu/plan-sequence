# Step 7: Mechanical check

The judgment steps never verify mechanics. This one does, on the text that will be stamped, so it runs **after** the fold.

## Run it

Give the final plan to a cold reader with read access to the repository: a fresh subagent, a person, or a `plan-check`-style skill if you have one. Use [cold-reader-prompt.md](../references/cold-reader-prompt.md) as the brief. It checks:

- every file the plan says already exists, does
- test commands match the project's framework
- steps are in dependency order
- imports and names the plan relies on resolve
- the change described is not already implemented

## Classify and act

| Finding | Record as | What to do |
|---------|-----------|-----------|
| Nothing wrong | `clean` | Proceed |
| Creates a file that does not exist yet; a helper nothing uses | `warn` | Note it; does not block |
| Wrong test command, missing existing file, step-order violation, unresolvable import | `fail` | Fix with a **targeted edit** (one line, not a re-fold), re-run the check, then record `clean` |
| Plan is already implemented | `stale` | Do not stamp a moot plan, and do not bare-halt either |

For `stale`, offer: **abandon** (the work is done), **rewrite** stale tasks into verify-existing steps and re-run the check, or **override** (the requester chooses to proceed; finalize needs `--override-stale <reason>` and the stamp carries it).

The cold reader must look beyond the default branch. Unmerged branches and other worktrees are where already-built work hides: in one run, task A existed only as an unmerged commit. On `stale`, name where the work lives, rewrite the task as verify-existing with the known gaps listed, and run the check again on the new text. Both results stay in the sidecar, and finalize reads the last one.

## Record

```
python plan_sequence.py record-check plan.md --result clean
python plan_sequence.py record-check plan.md --result warn --note "creates tests/new.py"
```

`fail` and `stale` require `--note`.

The result is bound to the plan's hash. Any edit afterwards, even a typo, makes finalize refuse until you check and record again. That is deliberate: the check must have read the text that is stamped.
