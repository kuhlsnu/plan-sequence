# Step 1: Intent gate

Start the run, then check that the plan says what it is for. This blocks everything after it.

```
python plan_sequence.py init plan.md
python plan_sequence.py intent plan.md [--surface approved|annotated|deferred|skipped]
```

`init` mints a run id and deletes any existing stamp, because a re-review invalidates the old one.

## What this step is for

A person and an agent can both say yes to a plan without sharing an understanding of it. The agent has read the plan and finds it consistent with itself. The person skims it and clicks accept to get to the next step. Neither has stated what the plan is for or what will be different in the real world once it runs, so the approval carries no information, and the consequences surface after execution.

This step makes that statement, in plain words, before any review. It does two jobs:

1. **Shared understanding.** The requester reads what the plan will do for the people it affects and what it must never do, and corrects it. The agent finds out which of its premises were guesses. This is the main job.
2. **Something to review against.** Every later reviewer grounds findings in the written intent, so it has to exist as text.

If you only do the second job, you have a section that satisfies the script and an approval nobody understood.

## What the plan must contain

A section headed `## Intended behaviour (normative)`. Every bullet under it is one statement, and every statement carries two tags:

| Tag | Meaning |
|-----|---------|
| `[LOAD-BEARING]` | Purpose. Not an implementer's call. |
| `[CHOICE]` | This slice's mechanism. Open to change. |
| `[confirmed]` | The requester stated it. |
| `[inferred]` | The plan author worked it out. |

Weight and owner are independent. A capability that changes what the software does for its user is `[LOAD-BEARING]` even when the widget that expresses it is a `[CHOICE]`.

```markdown
## Intended behaviour (normative)

- [LOAD-BEARING][confirmed] A stock adjustment below zero is rejected with a visible error.
- [CHOICE][inferred] The guard lives in the adjustment handler.
- [LOAD-BEARING][confirmed] A rejected adjustment never fails silently.
```

## Why this comes first

Every later reviewer is told to ground each finding in a quoted phrase from the plan or a `path:line` from the code. Intent that was never written is quotable from neither, so a missing purpose is the one defect those reviewers cannot see. Once the section exists, every reviewer becomes an intent checker with no prompt change.

Folding makes it worse without this step: each fold adds mechanism and none adds purpose, so a plan gets denser in how and thinner in why with every round.

## What to check besides tags

- A **what must never happen** list exists and includes the silent no-op: the user acts, nothing happens, nothing is said. The script warns when no statement mentions "never", "must not", "no-op" or "silent".
- Boundaries state inclusivity (`>=` versus `<`), not just values. "32 to 34" leaves 34 unclaimed.

## If the section is missing

Stop. Write it with the requester before any reviewer runs. Do not retrofit it after review; the ordering is the point.

## Showing the requester the inferences

Show the section to the requester before it hardens, because an agent-authored premise passes the tag check and then becomes the ground every finding is quoted against. How you show it is up to the harness: a rendered page, an inline message, a dialog.

Rules for whatever you use:

- Write each statement as something an affected person would observe, not a component. "A rejected adjustment shows a visible error" can be checked by the requester. "A validator is added" cannot.
- Say what is hard to reverse. If a statement touches someone else's data, money, safety or a published artifact, say so in the statement, so the requester sees the stakes next to the behaviour.
- Ask, do not present for a click. The `[inferred]` statements are the dangerous part of the section: the agent worked them out, nobody agreed to them, and every later finding is quoted against them. Put each one to the requester as a question with 2 to 4 concrete answers and the consequence of each. A single Accept on the whole section is the failure this step exists to prevent. In Claude Code, `/open-questions` does this as multiple-choice dialogs. In another harness, use whatever makes the requester pick an answer.
- Act on each answer. A confirmed statement becomes `[confirmed]`. A statement the requester changes is rewritten, and the new wording is shown back once. One that stands as drafted stays `[inferred]`, which is allowed, because the requester read it and let it stand.
- If the requester accepts everything unchanged, ask them to restate one `[LOAD-BEARING]` statement in their own words, or to name one thing the plan must never do. An answer you cannot get is a reason to slow down, not to record `approved`.
- `approved`: the requester read the statements and let them stand. Tag them as drafted.
- `annotated`: the feedback is free text, so transcribe it into statements and show the transcription back once before tagging anything `[confirmed]`. The requester confirms your words, not your summary of theirs.
- `dismissed`, empty or no answer is never confirmation. Offer "let's see what you plan first" as an explicit option and record `deferred` only when chosen.

Pass the result as `--surface`. Once every `[inferred]` statement has been put to the requester, also pass `--inferred-asked`:

```
python plan_sequence.py intent plan.md --surface approved --inferred-asked
```

The script cannot tell reading from clicking, so the rules above are yours to hold. What it enforces is that the question was claimed:

- While `[inferred]` statements stand and `--inferred-asked` has not been passed, `intent` prints a warning.
- `finalize` refuses to write a stamp in that state. The check uses the plan's current text, so re-tagging a statement `[confirmed]` clears it.
- The flag records how many `[inferred]` statements stood when the requester was asked. A statement added after that raises the count above it and `finalize` refuses again; ask the new ones and pass `--inferred-asked` again to record the new count.
- The only way past it is `finalize --override-inferred "<reason>"`. The reason and the number standing go into the stamp, and `verify` reports `WITH OVERRIDES`.
- The final results say `inferred statements put to the requester: yes`, or `NO (N standing)` when overridden.

An override is for a requester who cannot be reached, said out loud. It is not for skipping a conversation.

`open` in the output counts `[inferred]` statements still standing. A run can be `approved` with a high `open` (the requester read the inferences and let them stand).
