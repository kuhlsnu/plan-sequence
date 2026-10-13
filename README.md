# Plan Sequence

An agent hands you a plan. You skim it, it reads well, and it gets approved. Nobody checked that it says what it is for, that the scope is right, that anyone other than its author looked at it, or that the text you approved is the text that gets executed.

The gap underneath that is between what a person understands and what an agent executes. A plan arrives as pages of mechanism, the person clicks accept to reach the next step, and neither side has said what the plan is for or what it will change in the real world. The approval then carries no information.

Plan Sequence is a fixed review sequence for a plan. It ends in a stamp that is valid only for the exact text that was reviewed. A small script enforces the order, so the sequence is a gate and not a suggestion.

It is the judgment half of plan review. The last step is a mechanical check, and nothing here executes the plan.

[Install](#install) · [The sequence](#the-sequence) · [Why](#why-it-is-built-this-way) · [Run it](#run-it) · [What it does not do](#what-it-does-not-do) · [Not in v0](#not-in-v0)

---

## The sequence

| # | Step | What it catches |
|---|------|-----------------|
| 1 | **Intent gate** | Approval without understanding. The agent and the requester agree, in plain statements, on what the plan is for and what it will change in the real world, before anyone reviews the mechanism. Reviewers can only quote what is written, so unwritten purpose is invisible to them. |
| 2 | **Stabilize** | Overscoped plans. Splits the plan into what holds and what is only asserted ([plan-stabilizer](https://github.com/kuhlsnu/plan-stabilizer)). |
| 3 | **Lane adversary** | A scope split nobody pushed back on. A fresh reviewer challenges the weakest placement. |
| 4 | **Scope decision** | The agent deciding what ships on your behalf. You choose, on the reconciled split. |
| 5 | **Independent review** | The author grading its own work. A different reviewer, read-only, every finding grounded in a quote. |
| 6 | **Fold and dispose** | Findings that are acknowledged and ignored. Every critical finding gets an explicit fate, and an "accepted" fate must show a real edit. |
| 7 | **Mechanical check** | Wrong paths, wrong test commands, work that already exists. Runs on the final text. |
| 8 | **Finalize** | Skipped steps. Runs every gate and writes the stamp. |

Each step has a procedure in [`skills/plan-sequence/steps/`](skills/plan-sequence/steps).

## Why it is built this way

Four choices carry most of the design. [DESIGN.md](DESIGN.md) gives the reasoning, the cost, and what we measured or only observed for each.

- **Intent first, and the guesses get asked.** Reviewers can only quote what is written, and the statements an agent inferred are the ones nobody agreed to. Finalize refuses to stamp until they have been put to the requester.
- **A script holds the order.** A markdown skill cannot prove a step happened. In a scope-audit eval, only 8 of 15 constraints held in every run, so what can be checked in code is.
- **An accepted finding must change the text.** Acknowledgement is free. A changed section is a cheap proof that something moved, though not that it is right.
- **The stamp dies with the text.** One late edit separates what was reviewed from what runs, so any edit makes `verify` fail.

## Install

```bash
git clone https://github.com/kuhlsnu/plan-sequence
cp -r plan-sequence/skills/plan-sequence ~/.claude/skills/
```

That path is Claude Code's convention. Any harness that loads markdown skills works, and the script runs anywhere with Python 3.9 or newer. There are no dependencies beyond the standard library.

Step 2 uses `stabilizer` and `stabilizer-gate` from [plan-stabilizer](https://github.com/kuhlsnu/plan-stabilizer).

## Run it

State lives in two files next to the plan. The script does the bookkeeping; the agent does the reviewing.

```
$ plan_sequence.py init plan.md
run 20261012T181508Z-5655 started; sidecar plan.review.md
$ plan_sequence.py intent plan.md --surface approved --inferred-asked
Intent gate: present (2 load-bearing, 1 choice, 1 open)
$ plan_sequence.py record-verdict plan.md --file v.txt
verdict agree, 0 move(s) recorded
$ plan_sequence.py record-scope plan.md --decision as-reconciled
scope recorded (sequence 0): as-reconciled
$ plan_sequence.py record-findings plan.md --file f.json --reviewer second-model
round 1/3: 1 critical, 0 important, 0 minor
$ plan_sequence.py finalize plan.md
error: step not recorded for this run: check
```

Fold the finding into the plan, write the disposition, run the mechanical check, then:

```
$ plan_sequence.py record-check plan.md --result clean
$ plan_sequence.py finalize plan.md
stamp written: plan.stamp.json
$ plan_sequence.py verify plan.md
valid stamp (run 20261012T181508Z-5655, 2026-10-12T18:15:09Z)
```

Edit one line afterwards and the stamp no longer holds:

```
$ plan_sequence.py verify plan.md
stale stamp: the plan changed after review; re-run the sequence
```

`verify` exits 0 for a valid stamp, 1 for none, 3 for a stale or altered one. Wire it into a hook, a pre-commit check or CI. See [adapters](skills/plan-sequence/references/adapters.md).

## What the script enforces

A markdown skill cannot do these, so the script does.

- **Order.** Each step refuses to record until its predecessor has.
- **Schemas.** The adversary's output, the findings and the disposition lines are parsed. A line the parser cannot read is an error, never silently skipped.
- **Change proof.** A critical finding is "accepted" only if the cited section's content differs from a snapshot taken when that finding's round was recorded. Blank lines, a bare rename and an empty new heading do not count.
- **Currency.** The mechanical check is bound to the plan's hash. Edit after checking and finalize refuses.
- **Round cap.** Three finder passes, then fold and finalize.
- **Honest provenance.** A reviewer that saw earlier findings is reported as primed, and its agreement as endorsement, not independent confirmation.
- **Asked, not assumed.** Finalize refuses while `[inferred]` intent statements stand and were not recorded as put to the requester.
- **Recorded overrides.** The three escape hatches take a reason and appear in the stamp.

## What it does not do

- **It is not tamper-proof.** The stamp detects a plan that changed and a review that skipped steps. Anyone who can write the plan directory can regenerate the sidecar and stamp together.
- **It does not judge the plan.** Reviewers do. The script proves the review happened in order and was answered.
- **It cannot tell whether the requester understood.** `--surface approved` records that the intent section was shown and accepted, not that it was read. What it does is refuse to stamp a plan whose `[inferred]` statements were never recorded as put to the requester (`--inferred-asked`), unless the override and its reason are on the stamp. [Step 1](skills/plan-sequence/steps/01-intent-gate.md) says how to make the check mean something, and holding to it is the agent's job.
- **It does not prove a fix works.** It proves a fate was declared and the cited section changed.
- **It does not authorize execution.** A stamp means reviewed and unchanged.

## Not in v0

This is the spine. Left out on purpose, to be added as separable pieces once the spine is solid:

- review tiers that scale cost with plan size
- multi-worker review swarms and a reviewer-count policy
- an external source-of-truth backstop for knowledge-boundary claims
- under-extraction and mitigation-audit advisory passes
- duplication check on code the plan introduces
- auto-escalation on severe findings
- a rendered review view for the requester
- carrying deferred work into an issue tracker
- keeping the stamp out of the plan author's reach
- a ready-made hook for a specific agent harness

## License

MIT, see [LICENSE](LICENSE).
