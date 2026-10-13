# ruff: noqa: F811
"""The inferred intent statements are the unagreed part of a plan: the run must record whether they were asked."""

from __future__ import annotations

from test_plan_sequence import (  # noqa: F401  (env is a pytest fixture)
    CRIT,
    PLAN,
    VERDICT_AGREE,
    env,
    findings_json,
    fold_and_dispose,
    ps,
)

ALL_CONFIRMED = PLAN.replace("[CHOICE][inferred]", "[CHOICE][confirmed]")


def test_standing_inferred_statements_warn_until_recorded_as_asked(env, capsys):
    plan, run, *_ = env
    run("init", plan)
    run("intent", plan, "--surface", "approved")
    out = capsys.readouterr().out
    assert "1 [inferred] statement(s) still stand" in out
    assert "/open-questions" in out


def test_inferred_asked_silences_the_warning(env, capsys):
    plan, run, *_ = env
    run("init", plan)
    run("intent", plan, "--surface", "approved", "--inferred-asked")
    assert "still stand" not in capsys.readouterr().out


def test_no_inferred_statements_means_nothing_to_ask(env, capsys):
    plan, run, *_ = env
    plan.write_text(ALL_CONFIRMED, encoding="utf-8")
    run("init", plan)
    run("intent", plan, "--surface", "approved")
    assert "still stand" not in capsys.readouterr().out


def test_asked_can_be_added_later_without_resetting_the_surface(env):
    plan, run, *_ = env
    run("init", plan)
    run("intent", plan, "--surface", "approved")
    run("intent", plan, "--inferred-asked")
    blocks = [
        b["data"]
        for b in ps.load_blocks(ps.sidecar_path(plan))
        if b["kind"] == "intent"
    ]
    assert [(d["surface"], d["inferred_asked"]) for d in blocks] == [
        ("approved", False),
        ("approved", True),
    ]


def test_rerunning_without_flags_does_not_downgrade_a_recorded_ask(env):
    plan, run, *_ = env
    run("init", plan)
    run("intent", plan, "--surface", "approved", "--inferred-asked")
    run("intent", plan)
    blocks = [
        b["data"]
        for b in ps.load_blocks(ps.sidecar_path(plan))
        if b["kind"] == "intent"
    ]
    assert len(blocks) == 1 and blocks[0]["inferred_asked"] is True


def _results(plan):
    return plan.read_text(encoding="utf-8") + ps.sidecar_path(plan).read_text(
        encoding="utf-8"
    )


def _ready_to_finalize(plan, run, write, tmp, asked=False):
    """Everything but finalize, with the intent step recorded without --inferred-asked by default."""
    run("init", plan)
    run("intent", plan, "--surface", "approved", *(["--inferred-asked"] * asked))
    run("record-verdict", plan, "--file", write("v.txt", VERDICT_AGREE))
    run("record-scope", plan, "--decision", "as-reconciled")
    run(
        "record-findings",
        plan,
        "--file",
        write("f.json", findings_json(CRIT)),
        "--reviewer",
        "other-model",
    )
    fold_and_dispose(plan)
    run("check-disposition", plan)
    run("record-check", plan, "--result", "clean")


def test_finalize_refuses_while_inferred_statements_stand_unasked(env, capsys):
    plan, run, write, tmp = env
    _ready_to_finalize(plan, run, write, tmp)
    run("finalize", plan, expect=1)
    assert "were not put to the requester" in capsys.readouterr().out
    assert not ps.stamp_path(plan).exists()


def test_override_inferred_stamps_with_the_reason_and_says_no(env):
    plan, run, write, tmp = env
    _ready_to_finalize(plan, run, write, tmp)
    run("finalize", plan, "--override-inferred", "requester unreachable")
    stamp = ps.stamp_path(plan).read_text(encoding="utf-8")
    assert "requester unreachable" in stamp
    assert "(1 standing)" in stamp
    assert "put to the requester: NO (1 standing)" in _results(plan)


def test_retagging_the_inferred_statements_clears_the_gate(env):
    """The requester confirmed the premise: nothing inferred stands, so nothing needs asking."""
    plan, run, write, tmp = env
    _ready_to_finalize(plan, run, write, tmp)
    plan.write_text(
        plan.read_text(encoding="utf-8").replace(
            "[CHOICE][inferred]", "[CHOICE][confirmed]"
        ),
        encoding="utf-8",
    )
    run("record-check", plan, "--result", "clean")
    run("finalize", plan)
    assert "put to the requester" not in _results(plan)
    assert "0 open); surface" in _results(plan)


def test_results_say_when_inferred_statements_were_asked(env):
    plan, run, write, tmp = env
    _ready_to_finalize(plan, run, write, tmp, asked=True)
    run("finalize", plan)
    assert "inferred statements put to the requester: yes" in _results(plan)


def test_a_later_surface_change_keeps_the_recorded_ask(env):
    plan, run, *_ = env
    run("init", plan)
    run("intent", plan, "--surface", "approved", "--inferred-asked")
    run("intent", plan, "--surface", "annotated")
    last = [
        b["data"]
        for b in ps.load_blocks(ps.sidecar_path(plan))
        if b["kind"] == "intent"
    ][-1]
    assert (last["surface"], last["inferred_asked"]) == ("annotated", True)


def test_results_carry_no_note_when_nothing_is_inferred(env):
    plan, run, write, tmp = env
    plan.write_text(ALL_CONFIRMED, encoding="utf-8")
    _ready_to_finalize(plan, run, write, tmp)
    run("finalize", plan)
    assert "put to the requester" not in _results(plan)


def test_a_run_recorded_before_the_flag_existed_reads_as_not_asked(env):
    """An in-flight run whose intent block has no inferred_asked key reads as not asked, with no crash."""
    plan, run, write, tmp = env
    _ready_to_finalize(plan, run, write, tmp)
    sidecar = ps.sidecar_path(plan)
    text = sidecar.read_text(encoding="utf-8")
    assert '"inferred_asked": false' in text
    sidecar.write_text(
        text.replace(',\n  "inferred_asked": false', ""), encoding="utf-8"
    )
    run("finalize", plan, expect=1)  # a missing key reads as not asked
    run("finalize", plan, "--override-inferred", "predates the flag")
    assert "put to the requester: NO (1 standing)" in _results(plan)


LATE = "- [CHOICE][inferred] A late premise the author added after the ask."


def _add_a_late_inferred_statement(plan, run):
    """Edit the plan after the ask, then re-run the mechanical check on the new text."""
    plan.write_text(
        plan.read_text(encoding="utf-8").replace(
            "- [CHOICE][inferred] The guard lives in the adjustment handler.",
            "- [CHOICE][inferred] The guard lives in the adjustment handler.\n" + LATE,
        ),
        encoding="utf-8",
    )
    run("record-check", plan, "--result", "clean")


def test_an_inferred_statement_added_after_the_ask_is_refused(env, capsys):
    """Mutation: compare against the recorded flag only, ignoring the count that stood at the ask."""
    plan, run, write, tmp = env
    _ready_to_finalize(plan, run, write, tmp, asked=True)
    _add_a_late_inferred_statement(plan, run)
    run("finalize", plan, expect=1)
    out = capsys.readouterr().out
    assert "only 1 stood when the requester was asked" in out
    assert not ps.stamp_path(plan).exists()


def test_asking_again_after_the_plan_grew_clears_it(env):
    plan, run, write, tmp = env
    _ready_to_finalize(plan, run, write, tmp, asked=True)
    _add_a_late_inferred_statement(plan, run)
    run("intent", plan, "--inferred-asked")
    run("finalize", plan)
    assert "inferred statements put to the requester: yes" in _results(plan)


def test_the_re_ask_records_the_new_standing_count(env):
    plan, run, write, tmp = env
    _ready_to_finalize(plan, run, write, tmp, asked=True)
    _add_a_late_inferred_statement(plan, run)
    run("intent", plan, "--inferred-asked")
    standing = [
        b["data"]["inferred_standing"]
        for b in ps.load_blocks(ps.sidecar_path(plan))
        if b["kind"] == "intent"
    ]
    assert standing == [1, 2]


def test_passing_the_flag_again_with_nothing_new_records_nothing(env):
    """Mutation: re-record on every flagged call. A repeat with the same count is not a re-ask."""
    plan, run, *_ = env
    run("init", plan)
    run("intent", plan, "--surface", "approved", "--inferred-asked")
    run("intent", plan, "--inferred-asked")
    blocks = [b for b in ps.load_blocks(ps.sidecar_path(plan)) if b["kind"] == "intent"]
    assert len(blocks) == 1


def test_overriding_an_added_after_the_ask_statement_says_no_in_the_results(env):
    plan, run, write, tmp = env
    _ready_to_finalize(plan, run, write, tmp, asked=True)
    _add_a_late_inferred_statement(plan, run)
    run("finalize", plan, "--override-inferred", "requester left")
    assert "put to the requester: NO (2 standing)" in _results(plan)


def test_a_run_that_recorded_the_ask_before_counts_were_kept_still_covers(env):
    """An in-flight run with asked=true and no standing key reads as covering what it covered."""
    plan, run, write, tmp = env
    _ready_to_finalize(plan, run, write, tmp, asked=True)
    sidecar = ps.sidecar_path(plan)
    text = sidecar.read_text(encoding="utf-8")
    assert '"inferred_standing": 1' in text
    sidecar.write_text(
        text.replace(',\n  "inferred_standing": 1', ""), encoding="utf-8"
    )
    run("finalize", plan)
    assert "inferred statements put to the requester: yes" in _results(plan)
