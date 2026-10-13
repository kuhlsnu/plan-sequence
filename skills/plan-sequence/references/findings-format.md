# Findings format

`record-findings --file findings.json` takes a JSON array. Write the file with a file tool, not a shell here-string, so dashes and quotes survive.

```json
[
  {
    "id": "F1",
    "severity": "CRITICAL",
    "anchor": "Add one guard in the adjustment handler",
    "claim": "Bulk import writes stock through the model, not the handler, so negatives get in.",
    "mitigation": "Enforce the check in the model's save path as well."
  }
]
```

| Field | Rule |
|-------|------|
| `id` | `[A-Za-z0-9_.-]+`. No spaces, no parentheses. Unique across all rounds of a run. The disposition lines cite it verbatim. |
| `severity` | `CRITICAL`, `IMPORTANT` or `MINOR` |
| `anchor` | A phrase quoted from the plan, or `path:line`. The script warns when it is neither. |
| `claim` | What is wrong, as a fact |
| `mitigation` | Optional. A suggested change |

## Severity

| Severity | Means | Gate |
|----------|-------|------|
| `CRITICAL` | Following the plan as written causes a defect, data loss, a safety problem, or breaks stated intent | Needs a disposition, and an accepted citation must show a real edit |
| `IMPORTANT` | Likely to cause rework or a bug | A missing disposition warns |
| `MINOR` | Nit, style, nice-to-have | Not gated |

When unsure between two, record the higher. A dropped CRITICAL is the failure; an over-recorded IMPORTANT costs one line.

## Normalizing a reviewer's prose

Do it as a separate cheap pass (a small model, or inline), not by changing the reviewer's prompt. Keep the reviewer lean and let normalization carry the schema. Over-include on ambiguity.

Map `must-fix` to `CRITICAL` or `IMPORTANT` by consequence, and `nice-to-have` to `MINOR`. Keep any `VERIFY:` knowledge-boundary flags: record them as `IMPORTANT` findings so someone confirms the claim.
