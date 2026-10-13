---
name: plan-sequence
description: "Use when an agent-written plan needs review before anyone executes it: after a plan is drafted and before implementation starts, when a plan has no stated purpose, when you want an independent reviewer's findings arbitrated instead of skimmed, or when a harness gate needs proof that a plan was reviewed and has not changed since."
---

# Plan Sequence

A fixed review sequence for a plan. It ends in a stamp that is valid only for the exact text that was reviewed.

It is the judgment half of plan review: is the scope right, does the design hold up, does it say what it is for. It does not execute the plan. A mechanical check (do the paths exist, do the commands match) is the last step.

## The sequence

| # | Step | Who acts | Blocks the stamp |
|---|------|----------|------------------|
| 1 | [Intent gate](steps/01-intent-gate.md) | you, with the requester | yes |
| 2 | [Stabilize](steps/02-stabilize.md) | `stabilizer` + `stabilizer-gate` skills | yes |
| 3 | [Lane adversary](steps/03-lane-adversary.md) | a fresh reviewer context | yes |
| 4 | [Scope decision](steps/04-scope-decision.md) | the requester | yes |
| 5 | [Independent review](steps/05-independent-review.md) | a reviewer other than you | yes |
| 6 | [Fold and dispose](steps/06-fold-and-dispose.md) | you | yes (critical findings) |
| 7 | [Mechanical check](steps/07-mechanical-check.md) | a cold reader | yes |
| 8 | [Finalize](steps/08-finalize.md) | `plan_sequence.py` | writes the stamp |

Step 1 is the one people skip, and the one the rest depends on. A person who clicks accept to reach the next step has not agreed to anything, and an agent that proceeds on that click is acting on its own guess. Step 1 makes both sides say, in plain words, what the plan is for and what it will change in the real world. Do not treat an unread accept as passing it.

Read each step file before doing that step. Order matters and is enforced: the script refuses a step whose predecessor is not recorded.

## Why a script

A markdown skill cannot validate a schema, prove a section changed, or bind a stamp to a hash. `scripts/plan_sequence.py` does those, with the standard library only. You run it; you do not hand-write the sidecar or the stamp.

```
python <skill-dir>/scripts/plan_sequence.py <command> <plan.md> [options]
```

State lives in `<plan-stem>.review.md` (audit sidecar) and `<plan-stem>.stamp.json` next to the plan. The plan itself is edited only by you, in steps 1, 6 and 7.

`python plan_sequence.py status <plan.md>` shows which steps are recorded for the current run.

`python plan_sequence.py build-prompt <plan.md> adversary|reviewer --out <file>` assembles the reviewer prompts into a file, so the plan and the prompt are never retyped. Give the reviewer the file's path.

## Rules that hold in every step

- **Do not skip or reorder.** A step that cannot run is recorded as failed, not omitted.
- **A failed step never gets a stamp.** Report the error and stop. The script's message names what to fix.
- **Editing the plan after step 7 invalidates the check.** Re-run the check on the final text, then finalize.
- **Escape hatches are recorded, not silent.** `--override-disposition`, `--override-stale` and `--override-inferred` take a reason, appear in the stamp, and `verify` reports `WITH OVERRIDES`.
- **Three finder passes at most.** After the third, fold what you have and finalize.
- **Do not run this to approve an implementation.** A stamp says the plan was reviewed, not that the work is authorized.

## Using the stamp

`python plan_sequence.py verify <plan.md>` exits 0 for a valid stamp, 1 for none, 3 for a stale or altered one. Wire that into whatever gates execution: a hook, a pre-commit check, CI. See [adapters.md](references/adapters.md).

The stamp detects staleness and out-of-order review. It is not tamper-proof: anyone who can write the plan directory can rewrite the stamp and sidecar together.

## Dependencies

- `stabilizer` and `stabilizer-gate` from [plan-stabilizer](https://github.com/kuhlsnu/plan-stabilizer) (step 2).
- Python 3.9 or newer.
- Nothing else. Reviewers are whatever you can run; see [adapters.md](references/adapters.md).
