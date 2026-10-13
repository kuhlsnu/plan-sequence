#!/usr/bin/env python3
"""plan_sequence.py: records and enforces the plan-sequence review spine.

A markdown skill cannot validate a schema, prove a section changed, or bind a
stamp to the text it reviewed. This script does, using only the standard
library. Every state change goes through a subcommand; the plan file itself is
never written. State lives in an audit sidecar next to the plan
(`<plan-stem>.review.md`) and the stamp in `<plan-stem>.stamp.json`.

The stamp is a staleness and honesty check, not a security boundary: anyone
who can write the plan directory can rewrite both files. It proves the plan
was reviewed in the order the spine requires and has not changed since.

Exit codes: 0 ok, 1 gate failed or bad input, 2 usage (argparse).
`verify` uses 0 valid, 1 no stamp, 3 stamp stale or tampered.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1
SEVERITIES = ("CRITICAL", "IMPORTANT", "MINOR")
ROUND_CAP = 3
SCAFFOLD_HEADINGS = {
    "Finding Disposition",
    "Review Findings",
    "Review pipeline results",
}
VALID_MOVES = {
    "A→B-SHOULD",
    "A→B-MAY",
    "B-SHOULD→A",
    "B-MAY→A",
    "B-SHOULD↔B-MAY",
    "B-MAY↔B-SHOULD",
}
REQUIRED_CHECKS = ("intent", "verdict", "scope", "findings", "check")


class GateError(Exception):
    """A rule of the spine was not met; message is shown to the operator verbatim."""


# ---------------------------------------------------------------- io helpers


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)


def sidecar_path(plan: Path) -> Path:
    return plan.with_name(plan.stem + ".review.md")


def stamp_path(plan: Path) -> Path:
    return plan.with_name(plan.stem + ".stamp.json")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------- sidecar blocks

_BEGIN = re.compile(r"^<!-- plan-sequence:begin kind=(\w+) run=(\S+) seq=(\d+) -->$")
_END = "<!-- plan-sequence:end -->"


def load_blocks(sidecar: Path) -> list[dict]:
    if not sidecar.exists():
        return []
    blocks: list[dict] = []
    lines = read_text(sidecar).split("\n")
    i = 0
    while i < len(lines):
        m = _BEGIN.match(lines[i])
        if not m:
            i += 1
            continue
        kind, run, seq = m.group(1), m.group(2), int(m.group(3))
        j = i + 1
        body: list[str] = []
        while j < len(lines) and lines[j] != _END:
            body.append(lines[j])
            j += 1
        raw = "\n".join(body).strip()
        raw = re.sub(r"^```json\n|\n```$", "", raw)
        blocks.append({"kind": kind, "run": run, "seq": seq, "data": json.loads(raw)})
        i = j + 1
    return blocks


def append_block(sidecar: Path, kind: str, run: str, seq: int, data: dict) -> None:
    # json.dumps escapes newlines inside strings, so LLM-authored text cannot put a marker at the start of a line.
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    head = (
        ""
        if sidecar.exists()
        else "# Plan review audit\n\nWritten by plan_sequence.py; do not edit by hand.\n"
    )
    existing = read_text(sidecar) if sidecar.exists() else head
    block = (
        f"\n<!-- plan-sequence:begin kind={kind} run={run} seq={seq} -->\n"
        f"```json\n{payload}\n```\n{_END}\n"
    )
    write_atomic(sidecar, existing.rstrip("\n") + "\n" + block)


def current_run(blocks: list[dict]) -> str:
    inits = [b for b in blocks if b["kind"] == "init"]
    if not inits:
        raise GateError("no review run started for this plan; run `init` first")
    return inits[-1]["run"]


def run_blocks(blocks: list[dict], run: str, kind: str) -> list[dict]:
    return sorted(
        (b for b in blocks if b["run"] == run and b["kind"] == kind),
        key=lambda b: b["seq"],
    )


# ------------------------------------------------------------ plan structure

_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")


def fence_mask(lines: list[str]) -> list[bool]:
    """True for every line inside (or opening/closing) a fenced code block.

    A fence closes only on the same character with at least the opening length,
    so a four-backtick fence can safely wrap a three-backtick example.
    """
    mask: list[bool] = []
    opened: tuple[str, int] | None = None
    for line in lines:
        m = _FENCE.match(line)
        if opened is None:
            if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
                opened = (m.group(1)[0], len(m.group(1)))
                mask.append(True)
            else:
                mask.append(False)
            continue
        mask.append(True)
        if (
            m
            and m.group(1)[0] == opened[0]
            and len(m.group(1)) >= opened[1]
            and not m.group(2).strip()
        ):
            opened = None
    return mask


def parse_headings(text: str) -> list[dict]:
    """Headings outside fenced code, each with its span (to the next heading of equal or higher level).

    `body` is the whole span as text. `content` is what change detection hashes: the span without its
    heading line, blank lines, or any nested scaffolding section, so writing the disposition section
    cannot make an enclosing section look edited.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    mask = fence_mask(lines)
    found: list[dict] = []
    for n, line in enumerate(lines):
        if mask[n]:
            continue
        m = _HEADING.match(line)
        if m:
            found.append(
                {"level": len(m.group(1)), "title": m.group(2).strip(), "start": n}
            )
    for idx, h in enumerate(found):
        end = len(lines)
        for nxt in found[idx + 1 :]:
            if nxt["level"] <= h["level"]:
                end = nxt["start"]
                break
        h["end"] = end
    scaffold = [
        (h["start"], h["end"]) for h in found if h["title"] in SCAFFOLD_HEADINGS
    ]
    for h in found:
        h["body"] = "\n".join(
            line.rstrip() for line in lines[h["start"] : h["end"]]
        ).strip()
        kept = [
            lines[i].rstrip()
            for i in range(h["start"] + 1, h["end"])
            if lines[i].strip() and not any(a <= i < b for a, b in scaffold)
        ]
        h["content"] = "\n".join(kept)
    return found


def section_hashes(text: str) -> dict[str, str | None]:
    """Heading title -> hash of its content; None when the title is ambiguous (repeated)."""
    out: dict[str, str | None] = {}
    for h in parse_headings(text):
        digest = sha256_text(h["content"])
        out[h["title"]] = None if h["title"] in out else digest
    return out


def section_info(text: str) -> dict[str, dict]:
    """Heading title -> {level, hash, empty}; hash is None when the title is repeated."""
    out: dict[str, dict] = {}
    for h in parse_headings(text):
        if h["title"] in out:
            out[h["title"]]["hash"] = None
            continue
        out[h["title"]] = {
            "level": h["level"],
            "hash": sha256_text(h["content"]),
            "empty": not h["content"].strip(),
        }
    return out


# --------------------------------------------------------------- intent gate

_INTENT_HEAD = re.compile(r"^intended behaviou?r\b.*\bnormative\b", re.I)
_TAG_WEIGHT = re.compile(r"\[(LOAD-BEARING|CHOICE)\]", re.I)
_TAG_OWNER = re.compile(r"\[(confirmed|inferred)\]", re.I)
_BULLET = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(.*)$")
_NEVER = re.compile(r"\bnever\b|\bmust not\b|\bno-op\b|\bsilent", re.I)


def check_intent(plan_text: str) -> dict:
    heads = [h for h in parse_headings(plan_text) if _INTENT_HEAD.match(h["title"])]
    if not heads:
        raise GateError(
            "plan has no `## Intended behaviour (normative)` section. Write it with the "
            "requester before any reviewer runs (steps/01-intent-gate.md)."
        )
    if len(heads) > 1:
        raise GateError("plan has more than one Intended behaviour (normative) section")
    lines = plan_text.replace("\r\n", "\n").split("\n")
    mask = fence_mask(lines)
    body = [
        lines[i] for i in range(heads[0]["start"] + 1, heads[0]["end"]) if not mask[i]
    ]
    load = choice = inferred = 0
    untagged: list[str] = []
    statements: list[str] = []
    for line in body:
        m = _BULLET.match(line)
        if not m:
            continue
        stmt = m.group(1)
        statements.append(stmt)
        w, o = _TAG_WEIGHT.search(stmt), _TAG_OWNER.search(stmt)
        bare = _TAG_OWNER.sub("", _TAG_WEIGHT.sub("", stmt)).strip()
        if not (w and o and bare):
            untagged.append(stmt[:100])
            continue
        if w.group(1).upper() == "LOAD-BEARING":
            load += 1
        else:
            choice += 1
        if o.group(1).lower() == "inferred":
            inferred += 1
    if not statements:
        raise GateError("Intended behaviour (normative) has no bullet statements")
    if untagged:
        shown = "; ".join(f'"{u}"' for u in untagged[:3])
        raise GateError(
            f"{len(untagged)} intent statement(s) missing a weight tag ([LOAD-BEARING]/[CHOICE]) "
            f"or an owner tag ([confirmed]/[inferred]), or have no statement text: {shown}"
        )
    warnings = []
    if not any(_NEVER.search(s) for s in statements):
        warnings.append(
            "no `what must never happen` statement found (include the silent no-op: the user "
            "acts, nothing happens, nothing is said)"
        )
    return {
        "load_bearing": load,
        "choice": choice,
        "open": inferred,
        "statements": len(statements),
        "warnings": warnings,
    }


# ------------------------------------------------------- lane adversary verdict

_SEP = re.compile(r"\s(?:—|--)\s")


def _norm_move(raw: str) -> str:
    return raw.strip().replace("<->", "↔").replace("->", "→")


def parse_verdict(raw: str) -> dict:
    text = raw.replace("\r\n", "\n").strip()
    text = re.sub(r"^```[a-z]*\n|\n```$", "", text).strip()
    lines = [ln.rstrip() for ln in text.split("\n")]
    first = next((ln for ln in lines if ln.strip()), "")
    m = re.match(r"^VERDICT:\s*(agree|rebalance)\s*$", first)
    if not m:
        raise GateError(
            f"verdict must begin `VERDICT: agree|rebalance`, got: {first[:80]!r}"
        )
    verdict = m.group(1)
    rationale = next(
        (ln.split(":", 1)[1].strip() for ln in lines if ln.startswith("RATIONALE:")), ""
    )
    if not rationale:
        raise GateError("verdict is missing a RATIONALE: line")
    if verdict == "agree":
        weakest = next(
            (
                ln.split(":", 1)[1].strip()
                for ln in lines
                if ln.startswith("WEAKEST_MOVE:")
            ),
            "",
        )
        if not weakest:
            raise GateError("an `agree` verdict must carry a WEAKEST_MOVE: line")
        return {
            "verdict": "agree",
            "moves": [],
            "weakest_move": weakest,
            "rationale": rationale,
        }
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip() == "MOVES:")
    except StopIteration:
        raise GateError("a `rebalance` verdict must carry a MOVES: block") from None
    moves = []
    tail_from = len(lines)
    for pos in range(start + 1, len(lines)):
        ln = lines[pos]
        if ln.startswith("RATIONALE:"):
            tail_from = pos
            break
        if not ln.strip():
            continue
        if not ln.lstrip().startswith("- "):
            raise GateError(
                f"unparseable MOVES line (expected `- ref: move — failure — evidence`): {ln[:80]!r}"
            )
        item = ln.lstrip()[2:]
        ref, sep, rest = item.partition(": ")
        parts = _SEP.split(" " + rest, maxsplit=2) if sep else []
        parts = [p.strip() for p in parts if p.strip()]
        if not sep or len(parts) != 3:
            raise GateError(
                "MOVES line needs `ref: move — failure-mode — evidence` with ` — ` or ` -- ` "
                f"separators (a bare ` - ` is not one): {ln[:100]!r}"
            )
        move = _norm_move(parts[0])
        if move not in VALID_MOVES:
            raise GateError(
                f"unknown move type {parts[0]!r}; allowed: {sorted(VALID_MOVES)}"
            )
        moves.append(
            {
                "ref": ref.strip(),
                "move": move,
                "failure": parts[1],
                "evidence": parts[2],
            }
        )
    stray = [ln for ln in lines[tail_from:] if ln.lstrip().startswith("- ")]
    if stray:
        raise GateError(
            f"MOVES lines must come before RATIONALE; found one after it: {stray[0][:80]!r}"
        )
    if not moves:
        raise GateError(
            "a `rebalance` verdict with zero parseable moves is a failed review, not a pass"
        )
    return {"verdict": "rebalance", "moves": moves, "rationale": rationale}


# ------------------------------------------------------------------ findings

_ID = re.compile(r"^[A-Za-z0-9_.\-]+$")
_PATH_LINE = re.compile(r"^\S+:\d+(?:[-–]\d+)?$")


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().strip("\"'`“”").lower()


def validate_findings(items: object, plan_text: str) -> tuple[list[dict], list[str]]:
    if not isinstance(items, list):
        raise GateError(
            "findings file must be a JSON array (use [] when the reviewer found nothing)"
        )
    seen: set[str] = set()
    out: list[dict] = []
    warnings: list[str] = []
    haystack = _squash(plan_text)
    for n, f in enumerate(items):
        if not isinstance(f, dict):
            raise GateError(f"finding #{n} is not an object")
        fid = str(f.get("id", ""))
        sev = str(f.get("severity", "")).upper()
        if not _ID.fullmatch(fid):
            raise GateError(
                f"finding #{n}: id {fid!r} must match [A-Za-z0-9_.-]+ (no spaces or parentheses)"
            )
        if fid in seen:
            raise GateError(f"duplicate finding id {fid}")
        seen.add(fid)
        if sev not in SEVERITIES:
            raise GateError(
                f"finding {fid}: severity must be one of {SEVERITIES}, got {f.get('severity')!r}"
            )
        anchor, claim = (
            str(f.get("anchor", "")).strip(),
            str(f.get("claim", "")).strip(),
        )
        if not anchor or not claim:
            raise GateError(f"finding {fid}: `anchor` and `claim` are required")
        if not (_squash(anchor) in haystack or _PATH_LINE.match(anchor)):
            warnings.append(
                f"{fid}: anchor is neither a phrase found in the plan nor a path:line "
                "(ungrounded findings are the ones to doubt)"
            )
        out.append(
            {
                "id": fid,
                "severity": sev,
                "anchor": anchor,
                "claim": claim,
                "mitigation": str(f.get("mitigation", "")).strip(),
            }
        )
    return out, warnings


_DISP_LINE = re.compile(
    r"^[-*]\s+(?P<id>[A-Za-z0-9_.\-]+):\s*(?P<verb>accepted|rejected|deferred)\b(?P<rest>.*)$"
)


def parse_dispositions(plan_text: str) -> tuple[dict[str, dict], list[str]]:
    """Return ({finding id: disposition}, errors). Unparseable top-level bullets are errors, never silent."""
    heads = [
        h
        for h in parse_headings(plan_text)
        if h["level"] == 2 and h["title"] == "Finding Disposition"
    ]
    if not heads:
        return {}, ["plan has no `## Finding Disposition` section"]
    if len(heads) > 1:
        return {}, [
            "more than one `## Finding Disposition` heading: use exactly one (distinguish "
            "rounds with bold sub-labels, not extra headings)"
        ]
    out: dict[str, dict] = {}
    errors: list[str] = []
    lines = plan_text.replace("\r\n", "\n").split("\n")
    mask = fence_mask(lines)
    for i in range(heads[0]["start"] + 1, heads[0]["end"]):
        line = lines[i].rstrip()
        if mask[i] or not re.match(r"^[-*]\s", line):
            continue  # fenced example, prose, or indented continuation
        m = _DISP_LINE.match(line)
        if not m:
            errors.append(
                f"unparseable disposition line (id must be bare, e.g. `- F1: accepted §Heading`): {line[:100]!r}"
            )
            continue
        fid, verb, rest = m.group("id"), m.group("verb"), m.group("rest").strip()
        if fid in out:
            errors.append(f"duplicate disposition for {fid}")
            continue
        if verb == "accepted":
            hm = re.match(r"^§\s*(?P<h>.+?)\s*(?:\|.*)?$", rest)
            if not hm:
                errors.append(
                    f"{fid}: accepted needs `§<exact heading>` (put reasoning after ` | ` or in prose below)"
                )
                continue
            out[fid] = {"verb": verb, "heading": hm.group("h")}
        elif verb == "rejected":
            reason = _SEP.split(" " + rest, maxsplit=1)
            reason = reason[1].strip() if len(reason) > 1 else ""
            if not reason:
                errors.append(
                    f"{fid}: rejected needs a reason (`- {fid}: rejected — <reason>`)"
                )
                continue
            out[fid] = {"verb": verb, "reason": reason}
        else:
            parts = [p.strip() for p in _SEP.split(" " + rest) if p.strip()]
            if len(parts) != 2:
                errors.append(f"{fid}: deferred needs `— <owner> — <trigger>`")
                continue
            out[fid] = {"verb": verb, "owner": parts[0], "trigger": parts[1]}
    return out, errors


def check_dispositions(
    findings: list[dict], baselines: dict[str, dict], plan_text: str
) -> dict:
    """Arbitrate dispositions. `baselines` maps finding id -> the section hashes taken when that finding's round was recorded."""
    disp, errors = parse_dispositions(plan_text) if findings else ({}, [])
    warnings: list[str] = []
    ids = {f["id"] for f in findings}
    info = section_info(plan_text)
    for fid in disp:
        if fid not in ids:
            errors.append(
                f"disposition for unknown finding id {fid} (use the exact recorded id)"
            )
    for f in findings:
        d = disp.get(f["id"])
        bucket = errors if f["severity"] == "CRITICAL" else warnings
        if f["severity"] == "MINOR":
            continue
        if d is None:
            bucket.append(f"{f['severity']} {f['id']} has no disposition line")
            continue
        if d["verb"] != "accepted":
            continue
        h = d["heading"]
        if h in SCAFFOLD_HEADINGS:
            bucket.append(
                f"{f['id']}: cannot cite scaffolding heading §{h}; fold into a real body section"
            )
            continue
        if h not in info:
            bucket.append(f"{f['id']}: accepted §{h} but the plan has no such heading")
            continue
        sec = info[h]
        if sec["hash"] is None:
            bucket.append(
                f"{f['id']}: §{h} is ambiguous (heading appears more than once)"
            )
            continue
        if sec["level"] == 1:
            bucket.append(
                f"{f['id']}: §{h} is the plan title and spans the whole file; cite a `##` or deeper section"
            )
            continue
        base = baselines.get(f["id"], {})
        if h in base:
            if base[h] == sec["hash"]:
                bucket.append(
                    f"{f['id']}: accepted §{h} but that section is unchanged since its review baseline"
                )
        elif sec["empty"]:
            bucket.append(
                f"{f['id']}: §{h} is a new heading with no content, so nothing was folded"
            )
        elif sec["hash"] in {v for v in base.values() if v}:
            bucket.append(
                f"{f['id']}: §{h} looks renamed: its content matches a section that already existed"
            )
    cited: dict[str, list[str]] = {}
    for fid, d in disp.items():
        if d["verb"] == "accepted" and fid in ids:
            cited.setdefault(d["heading"], []).append(fid)
    for h, fids in cited.items():
        if len(fids) >= 3:
            warnings.append(
                f"{len(fids)} findings ({', '.join(sorted(fids))}) cite §{h}: the gate shows the "
                "section changed, not that each fix landed there, so check each one"
            )
    return {"dispositions": disp, "errors": errors, "warnings": warnings}


# ------------------------------------------------------------------- commands


def _load(plan_arg: str) -> tuple[Path, str, Path, list[dict]]:
    plan = Path(plan_arg).resolve()
    if not plan.is_file():
        raise GateError(f"plan file not found: {plan}")
    sc = sidecar_path(plan)
    try:
        return plan, read_text(plan), sc, load_blocks(sc)
    except UnicodeDecodeError as e:
        raise GateError(f"plan or sidecar is not valid UTF-8: {e}") from e


_ENTITY = re.compile(r"&(?:lt|gt|amp|quot|#\d+);")


def verdict_warnings(raw: str, parsed: dict) -> list[str]:
    out: list[str] = []
    if _ENTITY.search(raw):
        out.append(
            "the output contains HTML entities (&lt; &gt; &amp;). A relay such as a notification or "
            "web view may have escaped it; compare with the file the reviewer wrote before trusting it"
        )
    long_refs = [m["ref"] for m in parsed["moves"] if len(m["ref"]) > 40]
    if long_refs:
        out.append(
            f"{len(long_refs)} move ref(s) are long prose, which makes `record-scope --item` awkward; "
            "number the Lane A/B items in the audit and ask the adversary to cite those"
        )
    return out


def _read_input(arg: str) -> str:
    return sys.stdin.read() if arg == "-" else read_text(Path(arg))


def cmd_init(a: argparse.Namespace) -> int:
    plan, text, sc, blocks = _load(a.plan)
    run = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + secrets.token_hex(2)
    )
    append_block(
        sc, "init", run, 0, {"plan_sha256": sha256_text(text), "started": now()}
    )
    stamp = stamp_path(plan)
    if stamp.exists():
        stamp.unlink()  # a re-review invalidates the previous stamp by definition
    print(f"run {run} started; sidecar {sc.name}")
    return 0


def cmd_intent(a: argparse.Namespace) -> int:
    plan, text, sc, blocks = _load(a.plan)
    run = current_run(blocks)
    res = check_intent(text)
    prior = run_blocks(blocks, run, "intent")
    last = prior[-1]["data"] if prior else {}
    # Passing only --inferred-asked must not reset a surface recorded earlier.
    surface = a.surface or last.get("surface", "not-run")
    asked = bool(a.inferred_asked or last.get("inferred_asked"))
    # What stood when the requester was asked. Passing the flag again after the plan gained more
    # [inferred] statements is a re-ask, and records the new count.
    standing = res["open"] if a.inferred_asked else last.get("inferred_standing")
    changed = (
        (a.surface and last.get("surface") != surface)
        or (asked and not last.get("inferred_asked"))
        or (a.inferred_asked and last.get("inferred_standing") != res["open"])
    )
    if not prior or changed:
        append_block(
            sc,
            "intent",
            run,
            len(prior),
            {
                **res,
                "surface": surface,
                "inferred_asked": asked,
                "inferred_standing": standing,
            },
        )
    print(
        f"Intent gate: present ({res['load_bearing']} load-bearing, {res['choice']} choice, "
        f"{res['open']} open)"
    )
    for w in res["warnings"]:
        print(f"warning: {w}")
    if res["open"] and not asked:
        print(
            f"warning: {res['open']} [inferred] statement(s) still stand and were not recorded as "
            "put to the requester. Turn each into a question with 2-4 concrete answers (in Claude "
            "Code: /open-questions), re-tag the answered ones [confirmed], then pass "
            "--inferred-asked. An inferred premise is the part of the plan nobody has agreed to."
        )
    return 0


def cmd_record_verdict(a: argparse.Namespace) -> int:
    plan, text, sc, blocks = _load(a.plan)
    run = current_run(blocks)
    raw = _read_input(a.file)
    existing = run_blocks(blocks, run, "verdict")
    if existing:
        d = existing[-1]["data"]
        if raw.strip() != d["raw"].strip():
            raise GateError(
                "a different verdict is already recorded for this run; run `init` to start over"
            )
        print(
            f"verdict already recorded for this run ({d['verdict']}, {len(d['moves'])} moves); unchanged"
        )
        return 0
    if not run_blocks(blocks, run, "intent"):
        raise GateError("intent gate has not passed for this run; run `intent` first")
    parsed = parse_verdict(raw)
    for w in verdict_warnings(raw, parsed):
        print(f"warning: {w}")
    append_block(sc, "verdict", run, 0, {**parsed, "raw": raw})
    print(f"verdict {parsed['verdict']}, {len(parsed['moves'])} move(s) recorded")
    return 0


def cmd_record_scope(a: argparse.Namespace) -> int:
    plan, text, sc, blocks = _load(a.plan)
    run = current_run(blocks)
    verdicts = run_blocks(blocks, run, "verdict")
    if not verdicts:
        raise GateError("record the lane-adversary verdict before the scope decision")
    refs = [m["ref"] for m in verdicts[-1]["data"]["moves"]]
    items = [i.strip() for i in (a.item or [])]
    if a.decision == "promote":
        if not items:
            raise GateError("`promote` needs at least one --item <move ref>")
        for ref in items:
            if refs.count(ref) != 1:
                raise GateError(
                    f"--item {ref!r} must name exactly one move in the verdict (found {refs.count(ref)})"
                )
    if a.decision in ("narrow", "custom") and not a.note:
        raise GateError(
            f"`{a.decision}` needs --note (for narrow, what drops; for custom, the requester's words)"
        )
    prior = run_blocks(blocks, run, "scope")
    seq = prior[-1]["seq"] + 1 if prior else 0
    append_block(
        sc,
        "scope",
        run,
        seq,
        {"decision": a.decision, "items": items, "note": a.note or ""},
    )
    print(f"scope recorded (sequence {seq}): {a.decision}")
    return 0


def cmd_record_findings(a: argparse.Namespace) -> int:
    plan, text, sc, blocks = _load(a.plan)
    run = current_run(blocks)
    if not run_blocks(blocks, run, "scope"):
        raise GateError("record the scope decision before running independent review")
    prior = run_blocks(blocks, run, "findings")
    if len(prior) >= ROUND_CAP:
        raise GateError(
            f"round cap reached ({ROUND_CAP} finder passes). Stop reviewing: fold what is "
            "recorded, note `Review rounds: 3 (cap reached, plan force-adopted)`, and finalize."
        )
    try:
        items = json.loads(_read_input(a.file))
    except json.JSONDecodeError as e:
        raise GateError(f"findings file is not valid JSON: {e}") from e
    findings, warnings = validate_findings(items, text)
    recorded = {f["id"] for b in prior for f in b["data"]["findings"]}
    clash = recorded & {f["id"] for f in findings}
    if clash:
        raise GateError(
            f"finding id(s) already used in an earlier round: {sorted(clash)}"
        )
    stale = sorted(set(parse_dispositions(text)[0]) & {f["id"] for f in findings})
    if stale:
        raise GateError(
            f"the plan already has disposition line(s) for {stale}: left over from an earlier review? "
            "Remove the old `## Finding Disposition` section before recording, or use new finding ids."
        )
    reused = [b["seq"] + 1 for b in prior if b["data"]["reviewer"] == a.reviewer]
    if reused and not a.primed:
        warnings.append(
            f"reviewer {a.reviewer!r} also reviewed round(s) {reused}; use a fresh context, or record this round --primed"
        )
    if re.search(r"\b(blind|primed)\b", a.reviewer, re.I):
        warnings.append(
            "--reviewer is a name only: provenance comes from the --primed flag, and the results "
            "summary adds blind or primed itself"
        )
    baseline = section_hashes(text)
    seq = len(prior)
    append_block(
        sc,
        "findings",
        run,
        seq,
        {
            "reviewer": a.reviewer,
            "primed": bool(a.primed),
            "findings": findings,
            "baseline": baseline,
            "plan_sha256": sha256_text(text),
        },
    )
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITIES}
    print(
        f"round {seq + 1}/{ROUND_CAP}: {counts['CRITICAL']} critical, {counts['IMPORTANT']} important, {counts['MINOR']} minor"
    )
    for w in warnings:
        print(f"warning: {w}")
    return 0


def _all_findings(blocks: list[dict], run: str) -> tuple[list[dict], dict[str, dict]]:
    fb = run_blocks(blocks, run, "findings")
    findings = [f for b in fb for f in b["data"]["findings"]]
    baselines = {
        f["id"]: b["data"]["baseline"] for b in fb for f in b["data"]["findings"]
    }
    return findings, baselines


def cmd_check_disposition(a: argparse.Namespace) -> int:
    plan, text, sc, blocks = _load(a.plan)
    run = current_run(blocks)
    findings, baselines = _all_findings(blocks, run)
    if not run_blocks(blocks, run, "findings"):
        raise GateError("no findings recorded for this run")
    res = check_dispositions(findings, baselines, text)
    for w in res["warnings"]:
        print(f"warning: {w}")
    for e in res["errors"]:
        print(f"error: {e}")
    print(
        f"disposition: {len(res['errors'])} error(s), {len(res['warnings'])} warning(s)"
    )
    return 1 if res["errors"] else 0


def cmd_record_check(a: argparse.Namespace) -> int:
    plan, text, sc, blocks = _load(a.plan)
    run = current_run(blocks)
    if not run_blocks(blocks, run, "findings"):
        raise GateError("record findings before the mechanical check")
    if a.result in ("fail", "stale") and not a.note:
        raise GateError(f"`{a.result}` needs --note describing what failed")
    prior = run_blocks(blocks, run, "check")
    append_block(
        sc,
        "check",
        run,
        len(prior),
        {"result": a.result, "note": a.note or "", "plan_sha256": sha256_text(text)},
    )
    print(f"mechanical check recorded: {a.result}")
    return 0


def _asked_note(open_now: int, covered: bool) -> str:
    if not open_now:
        return ""
    if covered:
        return "; inferred statements put to the requester: yes"
    return f"; inferred statements put to the requester: NO ({open_now} standing)"


def _results_markdown(
    run: str,
    blocks: list[dict],
    disp: dict,
    overrides: list[str],
    open_now: int,
    covered: bool,
) -> str:
    intent = run_blocks(blocks, run, "intent")[-1]["data"]
    verdict = run_blocks(blocks, run, "verdict")[-1]["data"]
    scope = run_blocks(blocks, run, "scope")[-1]["data"]
    fb = run_blocks(blocks, run, "findings")
    check = run_blocks(blocks, run, "check")[-1]["data"]
    findings = [f for b in fb for f in b["data"]["findings"]]
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITIES}
    verbs = [d["verb"] for d in disp["dispositions"].values()]
    lines = [
        "## Review pipeline results",
        "",
        f"- Run: `{run}`",
        f"- Intent gate: present ({intent['load_bearing']} load-bearing, {intent['choice']} choice, {open_now} open); surface: {intent['surface']}{_asked_note(open_now, covered)}",
        f"- Lane adversary: {verdict['verdict']}, {len(verdict['moves'])} move(s)",
        f"- Scope decision: {scope['decision']}"
        + (f" ({', '.join(scope['items'])})" if scope["items"] else ""),
        f"- Review rounds: {len(fb)}"
        + (" (cap reached, plan force-adopted)" if len(fb) >= ROUND_CAP else ""),
    ]
    for b in fb:
        d = b["data"]
        n = len(d["findings"])
        prov = (
            "primed (saw earlier findings: agreement is endorsement, not independent confirmation)"
            if d["primed"]
            else "blind"
        )
        lines.append(
            f"- Reviewer round {b['seq'] + 1}: {d['reviewer']}, {prov}, {n} finding(s)"
        )
    lines += [
        f"- Findings: {counts['CRITICAL']} critical, {counts['IMPORTANT']} important, {counts['MINOR']} minor",
        f"- Disposition: {verbs.count('accepted')} accepted, {verbs.count('rejected')} rejected, {verbs.count('deferred')} deferred",
        f"- Mechanical check: {check['result']}"
        + (f" ({check['note']})" if check["note"] else ""),
    ]
    for o in overrides:
        lines.append(f"- OVERRIDDEN: {o}")
    return "\n".join(lines)


def cmd_finalize(a: argparse.Namespace) -> int:
    plan, text, sc, blocks = _load(a.plan)
    run = current_run(blocks)
    failures: list[str] = []
    overrides: list[str] = []
    for kind in REQUIRED_CHECKS:
        if not run_blocks(blocks, run, kind):
            failures.append(f"step not recorded for this run: {kind}")
    if failures:
        for f in failures:
            print(f"error: {f}")
        return 1
    open_now = 0
    try:
        open_now = check_intent(text)["open"]  # still true of the text being stamped
    except GateError as e:
        failures.append(f"intent gate no longer holds: {e}")
    intent_rec = run_blocks(blocks, run, "intent")[-1]["data"]
    asked = bool(intent_rec.get("inferred_asked"))
    standing = intent_rec.get("inferred_standing")
    # A record from before the count was kept (standing None) covers what it covered.
    covered = asked and (standing is None or open_now <= standing)
    if open_now and not covered:
        if a.override_inferred:
            overrides.append(
                f"inferred intent statements not put to the requester: {a.override_inferred} "
                f"({open_now} standing)"
            )
        else:
            problem = (
                f"{open_now} [inferred] intent statement(s) stand, but only {standing} stood when "
                "the requester was asked: the rest were added after the ask"
                if asked
                else f"{open_now} [inferred] intent statement(s) stand and were not put to the "
                "requester as questions"
            )
            failures.append(
                f"{problem}: ask them (in Claude Code: /open-questions), re-tag the answered "
                "ones, run `intent --inferred-asked`, or finalize with --override-inferred <reason>"
            )
    findings, baselines = _all_findings(blocks, run)
    disp = check_dispositions(findings, baselines, text)
    if disp["errors"]:
        if a.override_disposition:
            overrides.append(
                f"disposition gate bypassed: {a.override_disposition} ({len(disp['errors'])} violation(s))"
            )
        else:
            failures += [f"disposition: {e}" for e in disp["errors"]]
    check = run_blocks(blocks, run, "check")[-1]["data"]
    if check["plan_sha256"] != sha256_text(text):
        failures.append(
            "plan changed after the mechanical check: re-run the check on the final text, then `record-check`"
        )
    if check["result"] == "fail":
        failures.append(f"mechanical check failed: {check['note']}")
    if check["result"] == "stale":
        if a.override_stale:
            overrides.append(f"staleness bypassed: {a.override_stale}")
        else:
            failures.append(
                f"plan appears already implemented ({check['note']}): abandon, rewrite to verify-existing steps, or --override-stale <reason>"
            )
    if failures:
        for f in failures:
            print(f"error: {f}")
        return 1
    for w in disp["warnings"]:
        print(f"warning: {w}")
    results = _results_markdown(run, blocks, disp, overrides, open_now, covered)
    rollup = run_blocks(blocks, run, "results")
    if not rollup or rollup[-1]["data"] != {
        "markdown": results,
        "overrides": overrides,
    }:
        append_block(
            sc,
            "results",
            run,
            len(rollup),
            {"markdown": results, "overrides": overrides},
        )
    stamp = {
        "schema": SCHEMA,
        "run": run,
        "stamped": now(),
        "plan": plan.name,
        "plan_sha256": sha256_text(text),
        "sidecar": sc.name,
        "sidecar_sha256": sha256_text(read_text(sc)),
        "overrides": overrides,
    }
    write_atomic(
        stamp_path(plan), json.dumps(stamp, indent=2, ensure_ascii=False) + "\n"
    )
    print(results)
    print(f"\nstamp written: {stamp_path(plan).name}")
    return 0


def cmd_verify(a: argparse.Namespace) -> int:
    plan = Path(a.plan).resolve()
    sp = stamp_path(plan)
    if not plan.is_file() or not sp.is_file():
        print("no stamp: this plan has not been through the review sequence")
        return 1
    sc = sidecar_path(plan)
    try:
        stamp = json.loads(read_text(sp))
        plan_hash = sha256_text(read_text(plan))
        sidecar_hash = sha256_text(read_text(sc)) if sc.is_file() else None
    except (ValueError, OSError):
        print("stale stamp: the stamp, plan or sidecar is unreadable")
        return 3
    if not isinstance(stamp, dict) or stamp.get("plan_sha256") != plan_hash:
        print("stale stamp: the plan changed after review; re-run the sequence")
        return 3
    if sidecar_hash is None or stamp.get("sidecar_sha256") != sidecar_hash:
        print("stale stamp: the audit sidecar changed or is missing")
        return 3
    print(
        f"valid stamp (run {stamp.get('run')}, {stamp.get('stamped')})"
        + (" WITH OVERRIDES" if stamp.get("overrides") else "")
    )
    return 0


REFERENCES = Path(__file__).resolve().parent.parent / "references"
ADVERSARY_PREAMBLE = (
    "You are a single-pass review agent. You already have everything you need in this prompt, so "
    "work only from the text provided below. Apply the prompt that follows VERBATIM and produce "
    "ONLY the rigid output format it defines (VERDICT / MOVES / RATIONALE): no preamble, no "
    "commentary, no closing summary."
)
REVIEWER_NOTE = (
    "The repository under review is your current working directory. Read it as needed. You are "
    "read-only: do not attempt to modify anything.\n"
    "Label each finding F1, F2, ... in order, with a severity word MUST-FIX or NICE-TO-HAVE and a "
    "grounding quote or path:line."
)


def _fences(path: Path) -> list[str]:
    found = re.findall(r"```\n(.*?)\n```", read_text(path), re.S)
    if not found:
        raise GateError(f"no fenced prompt found in {path}")
    return found


def cmd_build_prompt(a: argparse.Namespace) -> int:
    """Assemble a reviewer prompt into a file, so the controller never retypes the plan or the prompt."""
    plan, text, _sc, _blocks = _load(a.plan)
    if a.kind == "adversary":
        if not a.audit:
            raise GateError(
                "`build-prompt adversary` needs --audit <stabilizer audit file>"
            )
        body = (
            f"{ADVERSARY_PREAMBLE}\n\n{_fences(REFERENCES / 'lane-adversary-prompt.md')[0]}\n\n"
            f"## Plan\n\n{text}\n\n## Stabilizer Lane Assignments\n\n{read_text(Path(a.audit))}"
        )
    else:
        fences = _fences(REFERENCES / "reviewer-prompt.md")
        body = f"{fences[0]}\n\n{REVIEWER_NOTE}\n\n"
        if a.docket:
            body += f"{fences[1]}\n\n## Findings to adjudicate\n\n{read_text(Path(a.docket))}\n\n"
        body += f"## Plan Under Review\n\n{text}"
    out = Path(a.out)
    write_atomic(out, body)
    print(f"{a.kind} prompt written: {out} ({len(body.encode('utf-8'))} bytes)")
    return 0


def cmd_status(a: argparse.Namespace) -> int:
    plan, text, sc, blocks = _load(a.plan)
    try:
        run = current_run(blocks)
    except GateError as e:
        print(e)
        return 1
    print(f"run {run}")
    for kind in REQUIRED_CHECKS:
        n = len(run_blocks(blocks, run, kind))
        print(
            f"  {kind:<9} {'recorded' if n else 'MISSING'}"
            + (f" x{n}" if n > 1 else "")
        )
    return 0


def _reason(value: str) -> str:
    if not value.strip():
        raise argparse.ArgumentTypeError("a non-blank reason is required")
    return value.strip()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="plan_sequence", description=__doc__.split("\n\n")[0]
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name: str, fn, help_: str) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("plan", help="path to the plan markdown file")
        sp.set_defaults(fn=fn)
        return sp

    add("init", cmd_init, "start a review run (invalidates any existing stamp)")
    sp = add(
        "intent",
        cmd_intent,
        "check the Intended behaviour (normative) section and record the result",
    )
    sp.add_argument(
        "--surface",
        choices=["approved", "annotated", "deferred", "skipped"],
        help="what the requester decided when shown the section",
    )
    sp.add_argument(
        "--inferred-asked",
        action="store_true",
        help="every [inferred] statement was put to the requester as a question; those that "
        "still stand stay tagged [inferred]",
    )
    sp = add(
        "record-verdict",
        cmd_record_verdict,
        "validate and record the lane-adversary output",
    )
    sp.add_argument(
        "--file",
        required=True,
        help="file holding the adversary's raw output, or - for stdin",
    )
    sp = add("record-scope", cmd_record_scope, "record the requester's scope decision")
    sp.add_argument(
        "--decision",
        required=True,
        choices=["as-reconciled", "promote", "narrow", "custom"],
    )
    sp.add_argument(
        "--item", action="append", help="move ref promoted (repeatable; promote only)"
    )
    sp.add_argument("--note", help="one-line note; required for narrow")
    sp = add(
        "record-findings",
        cmd_record_findings,
        "validate and record one independent-review round (JSON array)",
    )
    sp.add_argument("--file", required=True)
    sp.add_argument(
        "--reviewer",
        required=True,
        help="who or what reviewed, e.g. 'codex gpt-x' or 'human: dana'",
    )
    sp.add_argument(
        "--primed",
        action="store_true",
        help="reviewer saw earlier findings before reviewing",
    )
    add(
        "check-disposition",
        cmd_check_disposition,
        "dry-run the disposition gate against the current plan",
    )
    sp = add(
        "record-check",
        cmd_record_check,
        "record the mechanical (cold-read) check on the final plan text",
    )
    sp.add_argument(
        "--result", required=True, choices=["clean", "warn", "fail", "stale"]
    )
    sp.add_argument("--note")
    sp = add("finalize", cmd_finalize, "run every gate and write the stamp")
    sp.add_argument("--override-disposition", metavar="REASON", type=_reason)
    sp.add_argument("--override-stale", metavar="REASON", type=_reason)
    sp.add_argument("--override-inferred", metavar="REASON", type=_reason)
    sp = add(
        "verify",
        cmd_verify,
        "exit 0 only when a stamp matches the current plan and sidecar",
    )
    sp = add(
        "build-prompt",
        cmd_build_prompt,
        "write an adversary or reviewer prompt file for this plan",
    )
    sp.add_argument("kind", choices=["adversary", "reviewer"])
    sp.add_argument("--out", required=True, help="where to write the assembled prompt")
    sp.add_argument("--audit", help="adversary only: the stabilizer audit file")
    sp.add_argument(
        "--docket",
        help="reviewer only: earlier findings to adjudicate (record the round --primed)",
    )
    add("status", cmd_status, "show which steps are recorded for the current run")
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except GateError as e:
        print(f"error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
