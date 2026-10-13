"""Behaviour added after the first real dogfood run: warnings that would have caught each friction point."""

# ruff: noqa: F811
from __future__ import annotations

from test_plan_sequence import (  # noqa: F401  (env is a pytest fixture)
    CRIT,
    VERDICT_AGREE,
    env,
    through_findings,
)

AUDIT = "STABILIZER AUDIT\nClassification: FEATURE\nLane A: the guard\n"


def test_entity_escaped_verdict_is_flagged(env, capsys):
    plan, run, write, _ = env
    run("init", plan)
    run("intent", plan)
    escaped = 'VERDICT: rebalance\nMOVES:\n- 1: A→B-MAY — f — "authors-desk-&lt;pk&gt;"\nRATIONALE: x\n'
    run("record-verdict", plan, "--file", write("v.txt", escaped))
    assert "HTML entities" in capsys.readouterr().out


def test_clean_verdict_has_no_entity_warning(env, capsys):
    plan, run, write, _ = env
    run("init", plan)
    run("intent", plan)
    run("record-verdict", plan, "--file", write("v.txt", VERDICT_AGREE))
    assert "HTML entities" not in capsys.readouterr().out


def test_long_prose_refs_are_flagged(env, capsys):
    plan, run, write, _ = env
    long_ref = "Data model, `puzzle` field, plus Lane A Rollback line"
    verdict = (
        f'VERDICT: rebalance\nMOVES:\n- {long_ref}: B-MAY→A — f — "q"\nRATIONALE: x\n'
    )
    run("init", plan)
    run("intent", plan)
    run("record-verdict", plan, "--file", write("v.txt", verdict))
    assert "number the Lane A/B items" in capsys.readouterr().out


def test_short_refs_are_not_flagged(env, capsys):
    plan, run, write, _ = env
    verdict = 'VERDICT: rebalance\nMOVES:\n- A2: A→B-MAY — f — "q"\nRATIONALE: x\n'
    run("init", plan)
    run("intent", plan)
    run("record-verdict", plan, "--file", write("v.txt", verdict))
    assert "number the Lane A/B items" not in capsys.readouterr().out


def test_reviewer_name_carrying_provenance_warns(env, capsys):
    plan, run, write, _ = env
    run("init", plan)
    run("intent", plan)
    run("record-verdict", plan, "--file", write("v.txt", VERDICT_AGREE))
    run("record-scope", plan, "--decision", "as-reconciled")
    run(
        "record-findings",
        plan,
        "--file",
        write("f.json", "[]"),
        "--reviewer",
        "codex medium, blind",
    )
    assert "name only" in capsys.readouterr().out


def test_many_findings_citing_one_section_warn(env, capsys):
    plan, run, write, tmp = env
    items = [dict(CRIT, id=f"F{n}") for n in (1, 2, 3)]
    through_findings(plan, run, write, tmp, items=items)
    text = plan.read_text(encoding="utf-8").replace(
        "Add one guard in the adjustment handler.",
        "Add one guard and a model-layer check.",
    )
    text += "\n## Finding Disposition\n\n" + "".join(
        f"- F{n}: accepted §Approach\n" for n in (1, 2, 3)
    )
    plan.write_text(text, encoding="utf-8")
    capsys.readouterr()
    run("check-disposition", plan)
    assert "3 findings (F1, F2, F3) cite §Approach" in capsys.readouterr().out


def test_two_findings_citing_one_section_do_not_warn(env, capsys):
    plan, run, write, tmp = env
    items = [dict(CRIT, id=f"F{n}") for n in (1, 2)]
    through_findings(plan, run, write, tmp, items=items)
    text = plan.read_text(encoding="utf-8").replace(
        "Add one guard in the adjustment handler.",
        "Add one guard and a model-layer check.",
    )
    text += "\n## Finding Disposition\n\n- F1: accepted §Approach\n- F2: accepted §Approach\n"
    plan.write_text(text, encoding="utf-8")
    capsys.readouterr()
    run("check-disposition", plan)
    assert "cite §Approach" not in capsys.readouterr().out


# --------------------------------------------------------------- build-prompt


def test_build_adversary_prompt_has_all_four_parts(env):
    plan, run, write, tmp = env
    audit = write("audit.md", AUDIT)
    out = tmp / "adv.txt"
    run("build-prompt", plan, "adversary", "--audit", audit, "--out", out)
    body = out.read_text(encoding="utf-8")
    assert body.startswith("You are a single-pass review agent.")
    assert "VALID VERDICTS (output exactly one): agree | rebalance" in body
    assert "Add one guard in the adjustment handler." in body
    assert body.rstrip().endswith("Lane A: the guard")
    assert body.index("## Plan") < body.index("## Stabilizer Lane Assignments")


def test_build_adversary_prompt_requires_the_audit(env):
    plan, run, write, tmp = env
    run("build-prompt", plan, "adversary", "--out", tmp / "adv.txt", expect=1)
    assert not (tmp / "adv.txt").exists()


def test_build_reviewer_prompt_is_blind_by_default(env):
    plan, run, write, tmp = env
    out = tmp / "rev.txt"
    run("build-prompt", plan, "reviewer", "--out", out)
    body = out.read_text(encoding="utf-8")
    assert "senior staff engineer" in body
    assert "State each finding as a fact grounded in a quoted phrase" in body
    assert "## Plan Under Review" in body and "Add one guard" in body
    assert "AFFIRM" not in body and "Findings to adjudicate" not in body


def test_build_reviewer_prompt_with_docket_adds_adjudication(env):
    plan, run, write, tmp = env
    docket = write("docket.md", "F1: other entry points bypass the handler")
    out = tmp / "rev2.txt"
    run("build-prompt", plan, "reviewer", "--docket", docket, "--out", out)
    body = out.read_text(encoding="utf-8")
    assert "AFFIRM" in body and "BEYOND THE DOCKET" in body
    assert "F1: other entry points bypass the handler" in body


def test_built_prompts_are_utf8_and_do_not_alter_the_plan(env):
    plan, run, write, tmp = env
    before = plan.read_bytes()
    run("build-prompt", plan, "reviewer", "--out", tmp / "rev.txt")
    assert plan.read_bytes() == before
