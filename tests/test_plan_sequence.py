"""Tests for plan_sequence.py. Each gate has a case that must fail, not only the happy path."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "plan-sequence"
    / "scripts"
    / "plan_sequence.py"
)
spec = importlib.util.spec_from_file_location("plan_sequence", SCRIPT)
ps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ps)

PLAN = """# Add negative-quantity guard

## Intended behaviour (normative)

- [LOAD-BEARING][confirmed] A stock adjustment below zero is rejected with a visible error.
- [CHOICE][inferred] The guard lives in the adjustment handler.
- [LOAD-BEARING][confirmed] A rejected adjustment never fails silently (no silent no-op).

## Approach

Add one guard in the adjustment handler.

## Tests

Repro: negative quantity is rejected.
"""

VERDICT_AGREE = """VERDICT: agree
WEAKEST_MOVE: Tests in Lane A -- regression coverage is thin
RATIONALE: The split is sound.
"""

VERDICT_REBALANCE = """VERDICT: rebalance
MOVES:
- 4e: A→B-SHOULD — premature abstraction — "Add one guard"
- 5a: B-MAY->A -- silent failure -- "never fails silently"
RATIONALE: Pattern across moves.
"""


@pytest.fixture
def env(tmp_path):
    plan = tmp_path / "plan.md"
    plan.write_text(PLAN, encoding="utf-8")

    def run(*argv, expect=0):
        code = ps.main([str(a) for a in argv])
        assert code == expect, f"{argv} exited {code}, expected {expect}"
        return code

    def write(name, text):
        p = tmp_path / name
        p.write_text(text, encoding="utf-8")
        return p

    return plan, run, write, tmp_path


def findings_json(*items):
    return json.dumps(list(items))


CRIT = {
    "id": "F1",
    "severity": "CRITICAL",
    "anchor": "Add one guard in the adjustment handler",
    "claim": "Other entry points bypass the handler",
    "mitigation": "guard at the model layer",
}
IMP = {
    "id": "F2",
    "severity": "IMPORTANT",
    "anchor": "Repro: negative quantity is rejected",
    "claim": "no zero case",
    "mitigation": "add zero test",
}


def through_findings(plan, run, write, tmp, verdict=VERDICT_AGREE, items=(CRIT,)):
    run("init", plan)
    run("intent", plan, "--surface", "approved", "--inferred-asked")
    run("record-verdict", plan, "--file", write("v.txt", verdict))
    run("record-scope", plan, "--decision", "as-reconciled")
    run(
        "record-findings",
        plan,
        "--file",
        write("f.json", findings_json(*items)),
        "--reviewer",
        "other-model",
    )


def fold_and_dispose(plan, accept_heading="Approach", fid="F1"):
    text = plan.read_text(encoding="utf-8")
    text = text.replace(
        "Add one guard in the adjustment handler.",
        "Add one guard in the adjustment handler and a model-layer check.",
    )
    text += f"\n## Finding Disposition\n\n- {fid}: accepted §{accept_heading}\n"
    plan.write_text(text, encoding="utf-8")


def test_happy_path_stamps_and_verifies(env):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    fold_and_dispose(plan)
    run("check-disposition", plan)
    run("record-check", plan, "--result", "clean")
    run("finalize", plan)
    run("verify", plan)
    assert ps.stamp_path(plan).exists()


def test_verify_without_stamp_is_1(env):
    plan, run, *_ = env
    run("verify", plan, expect=1)


def test_plan_edit_after_stamp_is_stale(env):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    fold_and_dispose(plan)
    run("record-check", plan, "--result", "clean")
    run("finalize", plan)
    plan.write_text(plan.read_text(encoding="utf-8") + "\nextra\n", encoding="utf-8")
    run("verify", plan, expect=3)


def test_sidecar_edit_after_stamp_is_stale(env):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    fold_and_dispose(plan)
    run("record-check", plan, "--result", "clean")
    run("finalize", plan)
    sc = ps.sidecar_path(plan)
    sc.write_text(sc.read_text(encoding="utf-8") + "\ntampered\n", encoding="utf-8")
    run("verify", plan, expect=3)


def test_init_invalidates_existing_stamp(env):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    fold_and_dispose(plan)
    run("record-check", plan, "--result", "clean")
    run("finalize", plan)
    run("init", plan)
    run("verify", plan, expect=1)


# ---------------------------------------------------------------- intent gate


def test_intent_section_missing_halts(env):
    plan, run, *_ = env
    plan.write_text("# Plan\n\n## Approach\n\nstuff\n", encoding="utf-8")
    run("init", plan)
    run("intent", plan, expect=1)


def test_untagged_intent_statement_halts(env):
    plan, run, *_ = env
    plan.write_text(PLAN.replace("[CHOICE][inferred] ", ""), encoding="utf-8")
    run("init", plan)
    run("intent", plan, expect=1)


def test_verdict_requires_intent_first(env):
    plan, run, write, _ = env
    run("init", plan)
    run("record-verdict", plan, "--file", write("v.txt", VERDICT_AGREE), expect=1)


# ----------------------------------------------------------------- verdict


@pytest.mark.parametrize(
    "bad",
    [
        "VERDICT: maybe\nRATIONALE: x\n",
        "VERDICT: agree\nRATIONALE: x\n",  # no WEAKEST_MOVE
        "VERDICT: rebalance\nMOVES:\nRATIONALE: x\n",  # zero moves
        'VERDICT: rebalance\nMOVES:\n- 1: A→B-SHOULD - single hyphen - "q"\nRATIONALE: x\n',
        'VERDICT: rebalance\nMOVES:\n- 1: A→A — f — "q"\nRATIONALE: x\n',  # unknown move
    ],
)
def test_malformed_verdicts_are_rejected(env, bad):
    plan, run, write, _ = env
    run("init", plan)
    run("intent", plan, "--inferred-asked")
    run("record-verdict", plan, "--file", write("v.txt", bad), expect=1)


def test_ascii_separators_and_arrows_accepted():
    v = ps.parse_verdict(VERDICT_REBALANCE)
    assert [m["move"] for m in v["moves"]] == ["A→B-SHOULD", "B-MAY→A"]


def test_verdict_is_idempotent_per_run(env):
    plan, run, write, _ = env
    run("init", plan)
    run("intent", plan, "--inferred-asked")
    run("record-verdict", plan, "--file", write("v.txt", VERDICT_AGREE))
    run(
        "record-verdict", plan, "--file", write("v1b.txt", VERDICT_AGREE)
    )  # same text: replay is a no-op
    blocks = ps.load_blocks(ps.sidecar_path(plan))
    assert len([b for b in blocks if b["kind"] == "verdict"]) == 1


def test_a_different_verdict_is_refused_not_silently_dropped(env):
    plan, run, write, _ = env
    run("init", plan)
    run("intent", plan, "--inferred-asked")
    run("record-verdict", plan, "--file", write("v.txt", VERDICT_AGREE))
    run("record-verdict", plan, "--file", write("v2.txt", VERDICT_REBALANCE), expect=1)


def test_moves_after_rationale_are_an_error():
    bad = 'VERDICT: rebalance\nMOVES:\n- 1: A→B-MAY — f — "q"\nRATIONALE: x\n- 2: B-MAY→A — f — "q"\n'
    with pytest.raises(ps.GateError, match="before RATIONALE"):
        ps.parse_verdict(bad)


def test_intent_surface_is_rerecorded_when_the_decision_changes(env):
    plan, run, *_ = env
    run("init", plan)
    run("intent", plan)
    run("intent", plan, "--surface", "approved")
    blocks = ps.load_blocks(ps.sidecar_path(plan))
    assert [b["data"]["surface"] for b in blocks if b["kind"] == "intent"] == [
        "not-run",
        "approved",
    ]


def test_empty_tagged_intent_bullet_and_fenced_bullets_do_not_count():
    empty = PLAN.replace(
        "A stock adjustment below zero is rejected with a visible error.", ""
    )
    with pytest.raises(ps.GateError, match="no statement text"):
        ps.check_intent(empty)
    fenced = (
        PLAN + "\n"
    )  # a fenced example inside the section must not be counted or required to be tagged
    fenced = fenced.replace(
        "\n## Approach", "\n```\n- untagged example bullet\n```\n\n## Approach"
    )
    assert ps.check_intent(fenced)["statements"] == 3


# ------------------------------------------------ gate hardening (adversarial review)


def test_leftover_disposition_from_a_previous_review_cannot_satisfy_a_new_finding(env):
    plan, run, write, tmp = env
    plan.write_text(
        PLAN
        + "\n## Finding Disposition\n\n- F1: rejected — old review, different finding\n",
        encoding="utf-8",
    )
    run("init", plan)
    run("intent", plan, "--inferred-asked")
    run("record-verdict", plan, "--file", write("v.txt", VERDICT_AGREE))
    run("record-scope", plan, "--decision", "as-reconciled")
    run(
        "record-findings",
        plan,
        "--file",
        write("f.json", findings_json(CRIT)),
        "--reviewer",
        "r",
        expect=1,
    )


def test_citing_the_plan_title_is_refused(env, capsys):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    plan.write_text(
        plan.read_text(encoding="utf-8")
        + "\n## Finding Disposition\n\n- F1: accepted §Add negative-quantity guard\n",
        encoding="utf-8",
    )
    run("check-disposition", plan, expect=1)
    assert "spans the whole file" in capsys.readouterr().out


def test_scaffolding_nested_inside_a_section_does_not_change_that_section():
    before = "# T\n\n## Approach\n\nbody\n"
    after = (
        before + "\n### Review Findings\n\n- F1 noted here\n"
    )  # nested under Approach
    assert ps.section_hashes(before)["Approach"] == ps.section_hashes(after)["Approach"]


def test_each_round_is_measured_against_its_own_baseline(env):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    text = plan.read_text(encoding="utf-8").replace(
        "Add one guard in the adjustment handler.", "Add one guard and a model check."
    )
    plan.write_text(text, encoding="utf-8")  # round-1 fold
    f2 = dict(CRIT, id="F2")
    run(
        "record-findings",
        plan,
        "--file",
        write("f2.json", findings_json(f2)),
        "--reviewer",
        "other-2",
    )
    plan.write_text(
        text
        + "\n## Finding Disposition\n\n- F1: accepted §Approach\n- F2: accepted §Approach\n",
        encoding="utf-8",
    )
    run(
        "check-disposition", plan, expect=1
    )  # F2's fold is missing: the round-1 edit must not count for it
    plan.write_text(
        plan.read_text(encoding="utf-8").replace(
            "model check.", "model check, plus audit logging."
        ),
        encoding="utf-8",
    )
    run("check-disposition", plan)


@pytest.mark.parametrize(
    "edit",
    [
        lambda t: t.replace(
            "Add one guard in the adjustment handler.",
            "Add one guard in the adjustment handler.\n\n\n",
        ),
        lambda t: t.replace("## Approach", "## Approach v2"),
        lambda t: t + "\n## Mitigation\n",
    ],
    ids=["blank-lines-only", "rename-only", "empty-new-heading"],
)
def test_cosmetic_edits_do_not_count_as_a_fold(env, edit):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    heading = (
        "Approach v2"
        if "v2" in edit(PLAN)
        else ("Mitigation" if "Mitigation" in edit(PLAN) else "Approach")
    )
    plan.write_text(
        edit(plan.read_text(encoding="utf-8"))
        + f"\n## Finding Disposition\n\n- F1: accepted §{heading}\n",
        encoding="utf-8",
    )
    run("check-disposition", plan, expect=1)


def test_a_fenced_example_disposition_does_not_dispose_a_real_finding(env):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    plan.write_text(
        plan.read_text(encoding="utf-8")
        + "\n## Finding Disposition\n\n```\n- F1: rejected — example only\n```\n",
        encoding="utf-8",
    )
    run("check-disposition", plan, expect=1)


def test_a_four_backtick_fence_hides_headings_inside_a_nested_example():
    # one bare inner fence line: a shorter fence must not close the four-backtick one
    text = "# T\n\n````md\n```\n## Hidden in example\n````\n\n## Real\n"
    assert [h["title"] for h in ps.parse_headings(text)] == ["T", "Real"]


def test_finding_id_with_a_trailing_newline_is_rejected():
    with pytest.raises(ps.GateError, match="must match"):
        ps.validate_findings([dict(CRIT, id="F1\n")], PLAN)


def test_reviewer_reuse_without_primed_warns(env, capsys):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    run(
        "record-findings",
        plan,
        "--file",
        write("f2.json", findings_json(dict(MINOR_TEMPLATE, id="M2"))),
        "--reviewer",
        "other-model",
    )
    assert "also reviewed round(s) [1]" in capsys.readouterr().out


def test_blank_override_reason_is_refused(env):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    with pytest.raises(SystemExit):
        ps.main(["finalize", str(plan), "--override-disposition", "   "])


def test_refinalize_after_fixing_the_plan_updates_the_results_block(env):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    fold_and_dispose(plan)
    run("record-check", plan, "--result", "stale", "--note", "looks implemented")
    run("finalize", plan, "--override-stale", "keeping it")
    run("record-check", plan, "--result", "clean")
    run("finalize", plan)
    last = [b for b in ps.load_blocks(ps.sidecar_path(plan)) if b["kind"] == "results"][
        -1
    ]["data"]
    assert "Mechanical check: clean" in last["markdown"] and last["overrides"] == []
    assert (
        json.loads(ps.stamp_path(plan).read_text(encoding="utf-8"))["overrides"] == []
    )
    run("verify", plan)


@pytest.mark.parametrize("content", ["not json{", "[]", ""])
def test_a_damaged_stamp_is_stale_not_a_traceback(env, content):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    fold_and_dispose(plan)
    run("record-check", plan, "--result", "clean")
    run("finalize", plan)
    ps.stamp_path(plan).write_text(content, encoding="utf-8")
    run("verify", plan, expect=3)


def test_stdin_is_read_as_utf8(env, monkeypatch):
    import io

    plan, run, write, tmp = env
    run("init", plan)
    run("intent", plan, "--inferred-asked")
    run("record-verdict", plan, "--file", write("v.txt", VERDICT_AGREE))
    run("record-scope", plan, "--decision", "as-reconciled")
    payload = json.dumps(
        [dict(CRIT, claim="Grüße — em dash →")], ensure_ascii=False
    ).encode("utf-8")
    monkeypatch.setattr(
        "sys.stdin", io.TextIOWrapper(io.BytesIO(payload), encoding="cp1252")
    )
    run("record-findings", plan, "--file", "-", "--reviewer", "r")
    blocks = ps.load_blocks(ps.sidecar_path(plan))
    assert [b for b in blocks if b["kind"] == "findings"][0]["data"]["findings"][0][
        "claim"
    ] == "Grüße — em dash →"


# ------------------------------------------------------------------- scope


def test_promote_must_name_exactly_one_move(env):
    plan, run, write, _ = env
    run("init", plan)
    run("intent", plan, "--inferred-asked")
    run("record-verdict", plan, "--file", write("v.txt", VERDICT_REBALANCE))
    run("record-scope", plan, "--decision", "promote", expect=1)
    run("record-scope", plan, "--decision", "promote", "--item", "nope", expect=1)
    run("record-scope", plan, "--decision", "promote", "--item", "4e")


def test_narrow_needs_note(env):
    plan, run, write, _ = env
    run("init", plan)
    run("intent", plan, "--inferred-asked")
    run("record-verdict", plan, "--file", write("v.txt", VERDICT_AGREE))
    run("record-scope", plan, "--decision", "narrow", expect=1)
    run("record-scope", plan, "--decision", "narrow", "--note", "drop the zero test")
    run("record-scope", plan, "--decision", "custom", expect=1)
    run(
        "record-scope",
        plan,
        "--decision",
        "custom",
        "--note",
        "ship the guard, defer the tests",
    )


def test_scope_before_verdict_is_refused(env):
    plan, run, *_ = env
    run("init", plan)
    run("record-scope", plan, "--decision", "as-reconciled", expect=1)


# ---------------------------------------------------------------- findings


def test_finding_id_with_parentheses_is_rejected(env):
    plan, run, write, tmp = env
    bad = dict(CRIT, id="F1 (model assignment)")
    run("init", plan)
    run("intent", plan, "--inferred-asked")
    run("record-verdict", plan, "--file", write("v.txt", VERDICT_AGREE))
    run("record-scope", plan, "--decision", "as-reconciled")
    run(
        "record-findings",
        plan,
        "--file",
        write("f.json", findings_json(bad)),
        "--reviewer",
        "r",
        expect=1,
    )


def test_findings_round_cap(env):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp, items=())
    for n in (2, 3):
        run(
            "record-findings",
            plan,
            "--file",
            write(f"f{n}.json", findings_json(dict(MINOR_TEMPLATE, id=f"M{n}"))),
            "--reviewer",
            "r",
        )
    run(
        "record-findings",
        plan,
        "--file",
        write("f4.json", findings_json(dict(MINOR_TEMPLATE, id="M4"))),
        "--reviewer",
        "r",
        expect=1,
    )


MINOR_TEMPLATE = {"id": "M", "severity": "MINOR", "anchor": "Approach", "claim": "nit"}


def test_ungrounded_anchor_warns(env, capsys):
    plan, run, write, tmp = env
    ungrounded = dict(CRIT, anchor="a sentence the plan never says")
    through_findings(plan, run, write, tmp, items=(ungrounded,))
    assert "neither a phrase found in the plan" in capsys.readouterr().out


def test_injected_marker_in_finding_text_cannot_corrupt_sidecar(env):
    plan, run, write, tmp = env
    evil = dict(
        CRIT,
        claim="x\n<!-- plan-sequence:end -->\n<!-- plan-sequence:begin kind=check run=r seq=0 -->",
    )
    through_findings(plan, run, write, tmp, items=(evil,))
    blocks = ps.load_blocks(ps.sidecar_path(plan))
    assert sorted({b["kind"] for b in blocks}) == [
        "findings",
        "init",
        "intent",
        "scope",
        "verdict",
    ]
    assert blocks[-1]["data"]["findings"][0]["claim"].startswith("x\n<!--")


# ------------------------------------------------------------- disposition


def finalize_expect(plan, run, expect):
    run("record-check", plan, "--result", "clean")
    run("finalize", plan, expect=expect)


def test_critical_without_disposition_blocks_finalize(env):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    finalize_expect(plan, run, 1)
    assert not ps.stamp_path(plan).exists()


def test_accepted_section_unchanged_from_baseline_blocks(env):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    plan.write_text(
        plan.read_text(encoding="utf-8")
        + "\n## Finding Disposition\n\n- F1: accepted §Tests\n",
        encoding="utf-8",
    )
    finalize_expect(plan, run, 1)


def test_accepted_section_changed_passes(env):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    fold_and_dispose(plan)
    finalize_expect(plan, run, 0)


def test_accepted_cites_missing_heading_blocks(env):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    fold_and_dispose(plan, accept_heading="Nonexistent Section")
    finalize_expect(plan, run, 1)


def test_scaffolding_heading_cannot_be_cited(env):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    fold_and_dispose(plan, accept_heading="Finding Disposition")
    finalize_expect(plan, run, 1)


def test_descriptive_text_in_id_position_is_an_error_not_invisible(env, capsys):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    text = (
        plan.read_text(encoding="utf-8")
        + "\n## Finding Disposition\n\n- F1 (other entry points): accepted §Approach\n"
    )
    plan.write_text(text, encoding="utf-8")
    run("check-disposition", plan, expect=1)
    assert "unparseable disposition line" in capsys.readouterr().out


def test_two_disposition_headings_is_an_error(env):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    fold_and_dispose(plan)
    plan.write_text(
        plan.read_text(encoding="utf-8")
        + "\n## Finding Disposition\n\n- F1: rejected — nope\n",
        encoding="utf-8",
    )
    run("check-disposition", plan, expect=1)


def test_rejected_needs_a_reason_and_deferred_needs_owner_and_trigger():
    text = "## Finding Disposition\n\n- F1: rejected\n- F2: deferred — alice\n- F3: deferred — alice — next release\n"
    disp, errors = ps.parse_dispositions(text)
    assert "F3" in disp and "F1" not in disp and "F2" not in disp
    assert len(errors) == 2


def test_important_without_disposition_only_warns(env):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp, items=(CRIT, IMP))
    fold_and_dispose(plan)
    finalize_expect(plan, run, 0)


def test_unknown_disposition_id_blocks(env):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    fold_and_dispose(plan)
    plan.write_text(
        plan.read_text(encoding="utf-8") + "- CRIT-1: rejected — invented label\n",
        encoding="utf-8",
    )
    finalize_expect(plan, run, 1)


def test_override_disposition_is_recorded_in_stamp(env):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    run("record-check", plan, "--result", "clean")
    run("finalize", plan, "--override-disposition", "owner accepted the risk")
    stamp = json.loads(ps.stamp_path(plan).read_text(encoding="utf-8"))
    assert "owner accepted the risk" in stamp["overrides"][0]
    run("verify", plan)


# --------------------------------------------------------- mechanical check


def test_plan_edit_after_mechanical_check_blocks_finalize(env):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    fold_and_dispose(plan)
    run("record-check", plan, "--result", "clean")
    plan.write_text(
        plan.read_text(encoding="utf-8") + "\nlate edit\n", encoding="utf-8"
    )
    run("finalize", plan, expect=1)


def test_stale_result_needs_explicit_override(env):
    plan, run, write, tmp = env
    through_findings(plan, run, write, tmp)
    fold_and_dispose(plan)
    run("record-check", plan, "--result", "stale", expect=1)  # note required
    run(
        "record-check",
        plan,
        "--result",
        "stale",
        "--note",
        "guard already exists in handler.py:40",
    )
    run("finalize", plan, expect=1)
    run("finalize", plan, "--override-stale", "keeping as verify-only", expect=0)


def test_finalize_lists_every_missing_step(env, capsys):
    plan, run, *_ = env
    run("init", plan)
    run("finalize", plan, expect=1)
    out = capsys.readouterr().out
    for kind in ("intent", "verdict", "scope", "findings", "check"):
        assert f"step not recorded for this run: {kind}" in out


def test_results_report_primed_reviewer_honestly(env, capsys):
    plan, run, write, tmp = env
    run("init", plan)
    run("intent", plan, "--inferred-asked")
    run("record-verdict", plan, "--file", write("v.txt", VERDICT_AGREE))
    run("record-scope", plan, "--decision", "as-reconciled")
    run(
        "record-findings",
        plan,
        "--file",
        write("f.json", "[]"),
        "--reviewer",
        "second model",
        "--primed",
    )
    run(
        "record-check",
        plan,
        "--result",
        "warn",
        "--note",
        "creates a file that does not exist yet",
    )
    run("finalize", plan)
    out = capsys.readouterr().out
    assert "agreement is endorsement, not independent confirmation" in out
    assert "Mechanical check: warn" in out
