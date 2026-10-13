# Cold-reader prompt

Used in [step 7](../steps/07-mechanical-check.md). Give it to a fresh context that has not seen the plan's authoring, with read access to the repository. Fill in the two paths.

It is read-only on purpose: the reader reports and never edits. It also looks at unmerged branches and other worktrees, because that is where work the plan describes as to-do tends to already exist.

```
Do a READ-ONLY mechanical check of an implementation plan against a repository. Do not edit,
create or delete any file anywhere; use only read tools and read-only git commands (log, show,
status, ls-files, grep, branch; never checkout, reset, stash or commit). Do not run the test suite.

Plan file: <path to the plan>
Repository: <path to the repository>
There may also be task worktrees and unmerged branches; read them too, but another session may own them.

Check, with file:line or commit evidence for each result:
1. EXISTING FILES: every file the plan says already exists really exists.
2. NAMES THE PLAN RELIES ON: functions, classes, fields, routes and interpreters the plan names
   exist and have the shape the plan assumes.
3. TEST COMMAND: the test and verification commands in the plan match how this project runs them
   (look at its CLAUDE.md, README, manage.py or package scripts).
4. STEP ORDER: each task only uses things earlier tasks create; list any dependency out of order.
5. FILES THE PLAN CREATES: which do not exist yet (a WARN, not a failure) and which already exist.
6. ALREADY IMPLEMENTED: is any of the described change already present on the current branch, on
   any other branch, or in any worktree? Name where. This is the staleness check.

Output format, nothing else: one line per numbered check as `N. CLEAN|WARN|FAIL|STALE - evidence`,
then `RESULT: clean|warn|fail|stale` using the most severe result, then `NOTE:` one sentence naming
the most important thing. Be exact. If you cannot verify something, say so; do not guess.
```

## Mapping the result to `record-check`

| Result | Record | Then |
|--------|--------|------|
| `clean` | `clean` | Finalize |
| `warn` | `warn` | Note it; finalize |
| `fail` | `fail` | Fix with a targeted edit, re-run this prompt |
| `stale` | `stale` | Rewrite the task as verify-existing, re-run this prompt on the new text |
