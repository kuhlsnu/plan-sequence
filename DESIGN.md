# Design

Why Plan Sequence is built the way it is. Each choice below names what it replaced, what it costs, and what we know about whether it works.

Every claim is labelled with the kind of evidence behind it, because a design document that sounds sure of everything is hard to trust:

| Label | Meaning |
|-------|---------|
| **Measured** | We ran it and counted. The number and the run are given. |
| **Observed** | It happened in a real run or a real review, once. Not a rate. |
| **Judgment** | A design call we made and have not tested against an alternative. |

---

## The problem the design answers

A plan is approved by a person who skims it, and acted on by an agent that proceeds on the approval. Neither has to say what the plan is for or what it changes in the real world. The approval then carries no information, and the consequences surface after execution.

Everything below is a way to make that approval carry information, or to prove it was given for the text that is actually executed.

## 1. Intent comes first, and the requester answers for the guesses

**Choice.** Before any reviewer runs, the plan must state what it is for in an `## Intended behaviour (normative)` section. Each statement is tagged by weight (`[LOAD-BEARING]` or `[CHOICE]`) and by owner (`[confirmed]` or `[inferred]`). The `[inferred]` statements are put to the requester as questions, and finalize refuses to stamp until that is recorded.

**Why.**
- Every later reviewer is told to ground a finding in a quoted phrase from the plan or a `path:line` from the code. Intent that was never written is quotable from neither, so a missing purpose is the one defect those reviewers cannot see. *Judgment, from how the reviewers are prompted.*
- Folding review findings makes it worse: each fold adds mechanism and none adds purpose, so a plan gets denser in how and thinner in why with every round. *Observed in the pipeline this one was ported from.*
- **Observed.** In a review of a clinical-protocol plan, the plan cleared a scope audit, an adversary pass, a five-worker swarm, two independent reviews and a mechanical check, with 16 findings all dispositioned, and it still had no statement of what it was supposed to do. Adding the section and rerunning one independent review surfaced six more findings, one of them a patient-safety gap: the plan gated a feature on "past the ceiling" while the stated purpose was a different, later boundary. That defect is invisible without the intent section, because the plan is consistent with itself.
- **Observed.** In the first dogfood run, the intent section had 11 statements and all 11 were `[inferred]`. Putting them to the requester surfaced three decisions nobody had made (the solver model, how unlock works, what the first hints do).

**Why intent has to be written as observable behaviour.** A plan that is silent on a case forces whoever executes it to choose between stopping to ask and guessing. Stopping is visible and costs minutes. A guess is invisible and costs a rework when the wrong assumption surfaces after execution, and if the thing built was the wrong thing, the repair is a rewrite, not a fix. An agent rarely stops by itself, so the cases a plan does not cover are filled in silently. Statements phrased as what an affected person would see ("a rejected adjustment shows a visible error") do double duty: the requester can confirm them without reading any mechanism, and each one is already shaped like an acceptance check, with a starting state, an action and an expected result. Boundaries have to state which side is included, and the list of what must never happen has to include the silent no-op, because those are the two places an implementer's silent guess most often lands.

**Why the inferred statements get their own gate.** They are the part of the section the requester never stated. A reviewer will quote them as authority. A single Accept on the whole section is exactly the click-through the step exists to prevent, so the script wants each inferred statement asked, and records how many stood when it was asked.

The technical reason is how human review fails. A checkpoint only adds safety if the person's answer can differ from "yes". Approval that is given the same way every time carries no information, and a person who is asked to approve everything learns to approve without reading, so the checkpoint becomes a record that a click happened. The remedy is to spend the person's attention where uncertainty actually is. The confirmed statements are the requester's own words and need no second look. The inferred ones are the agent's guesses, so they are the only part that needs a decision, and putting each one as a question with concrete answers makes "yes to everything" an effort and not a default.

**Why this gate has an override and the presence check does not.** A missing section is always fixable by editing the plan. A conversation with the requester is not always possible, so a hard stop would trap the session. The override takes a reason and the reason goes into the stamp. *Judgment.*

**Cost.** One round trip with the requester before any review work. The script cannot tell whether they understood, only that the question was claimed.

## 2. A script enforces the order; markdown only describes it

**Choice.** The sequence is documents plus one stdlib Python script. The script refuses a step whose predecessor is not recorded, parses the structured outputs, and writes the stamp.

**Why.**
- A markdown skill cannot validate a schema, prove a section changed, or bind a stamp to a hash. An agent that is told to follow an order can skip it without anything noticing. *Judgment.*
- **Measured.** A red-team of the first version of the script found 16 reproducible ways to get a stamp or a recorded result that should have been refused. All 16 were fixed, and 34 mutants of the fixed script were each killed by the test suite. The suite is now 88 tests.
- **Measured.** An eval of the scope-audit step ran 5 scenarios 3 times each against 15 graded constraints: 8 held in every run and 7 were flaky. Among the worst were producing a concrete patch (60% of runs) and quoting the plan exactly (73%). Those are instructions a model follows unevenly, which is the case for checking in code what can be checked in code. *The eval is measured; the conclusion drawn from it is judgment.*

**Why the order is a state machine and not a checklist.** A checklist is advice, and advice is skipped silently. Treating each step as a state with one allowed predecessor turns "did we do step 3" into a question the script can answer from the record, and makes skipping a step an error with a name. It also bounds what each step may change: every step appends one kind of record and nothing else, so a late step cannot quietly rewrite what an early one concluded.

**Why recording the same verdict twice is a no-op and recording a different one is refused.** Sessions get interrupted and commands get retried. If a retry appended a second verdict, the record would hold two answers and every later reader would have to pick one. So re-recording an identical verdict changes nothing, and a conflicting verdict is refused with a message to start a new run. A retry is then safe, and a disagreement cannot hide.

**Why the record is append-only.** The sidecar is an audit log: it says what was concluded, in what order, and against which text. An in-place edit would make it a current-state file, which is easier to read and impossible to audit. The cost is that corrections are new entries and the file grows, which is cheap against being able to say how a plan got its stamp.

**Why the script parses every structured output strictly.** Rejecting malformed input at the boundary keeps everything downstream simple, because later gates can assume the shape they read is complete. The failure to avoid is the quiet one: a reviewer line the parser cannot read, if skipped, turns a malformed finding into an absent finding, and a gate that counts findings reads absence as "nothing to resolve". So an unreadable line is an error that names the line, never a skip.

**Why standard library only, in one file.** So it runs anywhere Python 3.9 does with nothing to install, and an outsider can read all of it. *Judgment.*

**Cost.** The script is the part that can be wrong in ways prose cannot. It has its own tests for that reason.

## 3. The reviewer is not the author, and its provenance is recorded

**Choice.** Step 5 uses a reviewer other than the author, read-only, with every finding grounded in a quote. A reviewer that saw earlier findings is recorded as primed, and the results call its agreement endorsement, not independent confirmation.

**Why.**
- The author grading its own plan shares its blind spots. *Judgment.*
- A second reviewer shown the first one's findings tends to agree with them. Counting that as a second opinion would overstate the evidence, so the sequence labels it. *Judgment.*

**Cost.** A second model or context is needed. In a harness with only one model, the adapters note says what to do and the results will say the review was not independent.

## 4. "Accepted" has to show up in the text

**Choice.** A critical finding marked accepted must cite a section whose content differs from a snapshot taken when that finding was recorded. Blank lines, a bare rename and an empty new heading do not count.

**Why.** An acknowledgement costs nothing, and a pile of acknowledged findings reads like a thorough review. The change check is a cheap proxy for "something actually moved". *Judgment.*

**What it does not prove.** That the fix is right, or that it landed in the cited section for the right reason. When three or more accepted findings cite one section, the script warns, because it cannot tell which finding the edit answered. *Observed in the dogfood run, where three findings cited one section.*

## 5. The stamp is bound to the exact text

**Choice.** The stamp holds a hash of the plan and of the review record. Edit one line afterwards and `verify` exits 3.

**Why.** The text that was reviewed and the text that gets executed can differ by one late edit. A stamp that survives edits certifies nothing. *Judgment.*

**Why the hash covers both the plan and the review record.** The stamp is a version check. Review work was done against one version of the text, and the stamp says "this is still that version". If the text moved, the right response is to review again, not to merge the two versions by hand, so a mismatch fails and asks for a redo. The record is hashed as well because a stamp that covered only the plan would stay valid after someone changed what the review concluded. Line endings are normalised before hashing, so checking a file out on another platform does not invalidate a stamp. *Judgment.*

**What it is not.** Not tamper-proof. Anyone who can write the plan directory can regenerate the review record and the stamp together. Keeping the stamp out of the author's reach needs something outside the repo, which v0 does not have.

## 6. The mechanical check also looks for work that already exists

**Choice.** A cold reader checks the final text against the repository: paths, names, commands, step order, and whether the change is already built, including on other branches and worktrees.

**Why.** **Observed.** In the first dogfood run, the plan's first task described work that already existed, as a commit on an unmerged branch. A reader that checked only the default branch would have called the plan clean. The reader now looks beyond it, and a `stale` result sends the task back to be rewritten as "verify what exists".

## 7. Three review rounds, then fold and finish

**Choice.** At most three finder passes.

**Why.** Each round adds mechanism to the plan and the findings get smaller. A bound forces a decision. *Judgment: three is a number we chose, not one we measured. The dogfood run used one round.*

## 8. Overrides are allowed and are always on the stamp

**Choice.** There are three: disposition, staleness, and unasked inferred statements. Each takes a reason, is written into the stamp, and makes `verify` report `WITH OVERRIDES`.

**Why.** A gate with no way past it traps the session in a state where the honest move is to bypass it silently. A recorded override keeps the gate and keeps the evidence. The alternative to a visible exception is an invisible one, and a stamp that says `WITH OVERRIDES` is information a later reader can use. *Judgment.*

## 9. What v0 leaves out, and why

| Left out | Why not yet |
|----------|-------------|
| Review tiers that scale cost with plan size | Needs a size signal we trust. The spine should be solid at one tier first. |
| Multi-worker review swarms | Cost is high and the dogfood run did not need them. Add when a plan is too big for one reviewer. |
| An external source-of-truth backstop | Depends on a particular knowledge tool, which is the kind of coupling v0 avoids. |
| Advisory passes, auto-escalation | They tune the review, not the order. Separable later. |
| Keeping the stamp out of the author's reach | Needs infrastructure outside a repo. Worth doing, and the biggest honest gap. |
| A harness-specific hook | The harness-neutral check is `verify`'s exit code. A hook is a thin wrapper per harness. |

## What we have not shown

- That the sequence changes outcomes. We ran it on one real plan and found real problems, but there is no comparison with the same plan unreviewed.
- That the new step 1 rules work on a requester who is tired or in a hurry. They have not been tried on one.
- That three rounds is the right cap.
