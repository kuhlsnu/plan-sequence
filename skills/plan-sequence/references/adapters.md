# Adapters

The sequence names roles, not products. Plug in whatever you have.

## Reviewers (steps 3, 5, 7)

| Role | Needs | Examples |
|------|-------|----------|
| Lane adversary (3) | A context that has not seen the plan's authoring. Reads text only. | A fresh subagent; a separate CLI call to any model; a person |
| Independent reviewer (5) | Read access to the plan and the repository. Read-only. A different model family from the author when you can. | A second vendor's coding CLI in a read-only sandbox; a subagent on a different model; a human reviewer |
| Cold reader (7) | Read access to the repository | A fresh subagent; a person; a plan-checking skill |

If you drive a reviewer from a script, pipe the prompt on stdin and write its output to a file. Do not pass plan text as a command-line argument: quoting layers eat backslashes and quotes, and long plans hit argument-length limits.

**Asking the requester.** Step 1 and step 4 need a real choice from a person, not a click through. In Claude Code, `AskUserQuestion` dialogs do this and `/open-questions` sweeps the `[inferred]` intent statements into them. A harness without a dialog can print the numbered questions and wait for typed answers; what matters is that the requester has to pick.

**Pin the model.** A default in your CLI config can be one your account does not support. One run exited 1 with no output file because the configured default was rejected (`400 invalid_request_error`, model not supported). Name the model explicitly, and read the first 30 seconds of the log for an error before trusting a long run.

**Launch long reviews detached, and watch for failure.** A review can outlast a tool call's time limit. Start it as an OS-detached process with its own log. Have the wrapper write a heartbeat line every 20 seconds, and watch for every terminal state, not only success: done, failed, process gone, log stale. Silence is not success.

**Ask for a durable result.** Have the CLI write its final message to a file (for Codex, `-o <file>`), and treat a missing file as a failure even when the process exits 0.

## Gating execution on the stamp

`verify` is the integration point. It prints a reason and exits:

| Exit | Meaning |
|------|---------|
| 0 | Valid stamp for the current plan and sidecar |
| 1 | No stamp |
| 3 | Stale or altered: the plan or sidecar changed after review |

Wire it wherever execution is decided.

**Pre-commit or CI.** Run `python plan_sequence.py verify docs/plans/<plan>.md` for each plan a change claims to implement.

**Agent harness hook.** A pre-tool hook on the tool that exits plan mode (or starts execution) can run `verify` against the active plan file and block on a non-zero exit. The plan's path has to come from your harness's hook input; check what yours provides. This repository ships no hook for any specific harness yet.

## What the stamp does not give you

It detects a plan that changed after review and a review that skipped steps. It does not stop someone who can write the plan directory from regenerating both files. If you need that, keep the sidecar and stamp somewhere the plan's author cannot write, and point `verify` there. That is not built yet.
