# Step 6: Fold and dispose

One focused pass. Its only job is to fold mitigations into the plan body and give every finding an explicit fate. Do not re-review here; the diagnosis already happened.

## 6a. Map

For every recorded finding, write one line: `<id> → §<exact body heading>: what changes there`, and decide the fate: accepted (folds into a body section), rejected (reason), or deferred (owner and trigger).

`<id>` is the exact id from the findings file. Never invent a grouped label such as `CRIT-1`; the script reports it as an unknown id.

## 6b. Fold, then write the disposition

Apply each accepted finding's change into the cited section, the section an implementer actually reads. Then add **one** section headed exactly `## Finding Disposition`, one line per finding:

```markdown
## Finding Disposition

- F1: accepted §Approach
- F2: rejected — the zero case is already covered by the repro test
- F3: deferred — dana — when the audit-log work starts
```

The grammar is strict because a line the parser skips would otherwise disappear silently:

| Rule | Why |
|------|-----|
| The id sits bare before the colon: `- F1:`, never `- F1 (note):` | The script treats any top-level bullet it cannot parse as an error |
| `accepted §<heading>`: the heading runs to the end of the line, or to a ` \| ` | Reasoning on the same line becomes part of the heading and matches nothing |
| `rejected — <reason>` and `deferred — <owner> — <trigger>` | ` — ` and ` -- ` both work |
| Exactly one `## Finding Disposition` heading | Distinguish rounds with a bold label such as `**Round 2:**`, not another heading |
| Put explanation in prose below, not in a bullet | Indented bullets and prose are ignored as continuation |

## What the gate proves

For every **CRITICAL**: a disposition exists, and an `accepted` section both exists and **differs from the baseline** captured in step 5. A citation with no real edit fails.

For **IMPORTANT**: the same checks, as warnings.

It proves a fate was declared and the cited section changed. It does not prove the change mitigates the finding. That check is yours and the next reader's.

When three or more accepted findings cite one section, `check-disposition` warns: the gate cannot show that each fix landed there, only that the section changed. Read that section against every finding that cites it.

"Changed" means the section's non-blank content differs. These do not count as a fold, and the gate says so:

- adding or removing blank lines
- renaming a heading with the same content under it
- a new heading with nothing under it

Cite a `##` or deeper heading that exists once in the plan. The title (`#`) spans the whole file and is refused. `Finding Disposition` and `Review Findings` are scaffolding and are refused too, and writing them never makes another section look edited.

If you write a pipeline marker literal such as `plan-sequence:begin` into the plan prose, nothing breaks: the plan is never scanned for markers. The sidecar is.

## Dry-run it

```
python plan_sequence.py check-disposition plan.md
```

Prints every error and warning and exits 1 on any error. Run it until it is clean.

## Deferred work

Put real not-now work under its own heading, for example `## Icebox (deferred)`, and decided-against work under `## Out of scope`. The two are different: one is a queue, the other is a record so a decision is not relitigated. Sort at authoring time, not afterwards.
