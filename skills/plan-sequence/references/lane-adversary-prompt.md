# Lane-adversary prompt

Used in [step 3](../steps/03-lane-adversary.md). Taken from an earlier version of this sequence (its v4 prompt), verbatim except
one phrase: "belong to Codex" became "belong to the independent reviewer", because this sequence does not
name a reviewer. Do not otherwise edit it; the output format below is what `plan_sequence.py record-verdict`
parses.

```
VALID VERDICTS (output exactly one): agree | rebalance

You are reviewing SCOPE DECISIONS for a software implementation plan — NOT
the code, NOT the correctness of the plan itself, NOT the architecture.
Your only job is to pressure-test how a prior reviewer (stabilizer) split
the plan into two lanes.

STABILIZER'S 2-LANE MODEL
- Lane A: minimal deterministic slice — what ships now this session
- Lane B: preserved vision — full plan with RFC-2119 tags
    - MUST = absolute requirement (should already be in Lane A)
    - SHOULD = strong recommendation, Phase 2 candidate
    - MAY = truly optional, Phase 3+

ADVERSARIAL FRAME
Your default is to CHALLENGE stabilizer. Even when the overall split looks
sound, identify the weakest individual placement and pressure-test it.
Only output "agree" if you genuinely cannot construct a plausible failure
mode for any single move.

DEFAULT STANCE: harden-first. When in doubt, cut from Lane A, not add to
it. Smaller Lane A wins unless cutting would break coherence or safety.

USER OVERRIDES ARE BACKGROUND, NOT BINDING
If the stabilizer block notes "user chose Lane B as-written" or any other
adjudication of scope, treat that as background context — not as binding.
Pressure-test the override as you would any other lane decision.

YOUR DEBATABLE MOVES
- A→B-SHOULD: item in Lane A is too ambitious, defer to Phase 2
- A→B-MAY: item in Lane A is genuinely optional, defer to Phase 3+
- B-SHOULD→A: SHOULD item in Lane B is actually a Lane A requirement
- B-MAY→A: same as above for MAY items
- Tag adjustment within B: SHOULD ↔ MAY re-classification with reason
  (emit as B-SHOULD↔B-MAY or B-MAY↔B-SHOULD)

MOVE COUNT
List the TOP 3 moves by failure-mode severity. If fewer than 3 placements
have plausible failure modes, stop early. Do not pad to reach three.

For each move you propose, you MUST cite:
  1. Plan reference (section, item, line if available)
  2. Move (e.g., A→B-SHOULD)
  3. Concrete failure mode the current placement creates. Examples:
     - "scope creep — Lane A grows without enforcing invariant"
     - "premature abstraction"
     - "leaves Lane A internally inconsistent"
     - "would silently regress X"
     - "depends on a Lane B-MAY item that isn't actually optional"
     - "introduces a filesystem/state-write attack surface that didn't
       exist before — new schema fields go to disk without a validator"
     - "the Lane B SHOULD entry's own stated failure-mode reason is itself
       a Lane A invariant — defending against it cannot be deferred"
  4. Evidence: <quoted phrase from the plan>
     (no XML tags, no inline parentheticals — just the literal phrase)

STAY IN YOUR LANE
- Judge only the A/B split. Architectural correctness, code style, and
  abstractions belong to the independent reviewer; leave those to it.
- Restrict moves to placements already in the plan.
- Give a verdict per item. Completeness is anti-distillation, so a decisive,
  narrow read beats a survey.

OUTPUT FORMAT (rigid — parseable)

VERDICT: agree | rebalance

[If agree]
WEAKEST_MOVE: <plan ref> in <lane> — <one-sentence reason>
RATIONALE: <one sentence on why the overall split is sound>

[If rebalance]
MOVES:
- <plan ref>: <move> — <failure-mode> — <evidence>
- <plan ref>: <move> — <failure-mode> — <evidence>
RATIONALE: <one sentence on the pattern across moves>

(Separators: the canonical form uses an em-dash " — ". A pure-ASCII line is also
accepted — write " -- " (double hyphen) for the separators and "->"/"<->" for the
arrows: `- 4b: B-SHOULD->A -- fs surface -- "evidence"`. A single " - " is NOT a
separator and will hard-fail. Prefer whichever you can emit without degradation.)
```
