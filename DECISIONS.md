# Decisions (working notes for the case study)

These are the calls the case study has to defend. Each says what the code currently does; change any you disagree
with before writing CASE_STUDY.md. **They score how you decided what "good" is, so these must be your calls.**

## 1. Who reads the summary, and what they need

A vetting team deciding whether a company is worth a closer look. So the summary is a **triage tool**, not a
description. Proposed definition of a good summary, in priority order:

1. **Never misses a red flag.** A missed winding-up petition costs far more than a clumsy sentence.
2. **Never invents or distorts a figure.** If the team can't trust one number, they re-read the whole record and the
   summary has saved nothing.
3. **Decision first.** First line: a risk level and the main reason.
4. **Short.** At most 120 words: read in under 30 seconds.
5. **Plain language.** "Losses in all 3 years" beats "negative net profit margin trajectory".

Your call: is this the right order? Would the team want a recommendation ("proceed / review / avoid"), or only the
facts? I went with a risk level, not a recommendation, because the decision is theirs.

## 2. What counts as a red flag (`summariser/facts.py`, `THRESHOLDS`)

| Flag | Severity | Rule |
|---|---|---|
| Status not Active (e.g. Winding up) | high | profile status |
| Winding-up petition against it | high if Pending / Judgment entered, else medium | litigation |
| Judgment entered against it | high | litigation |
| Pending cases as defendant | medium | litigation |
| Audit disclaimer / going-concern doubt | high if latest year, else medium | audit opinion |
| Negative equity | high | latest year |
| Losses in every year on record (2+ years) | high | profit after tax |
| Net loss in the latest year | medium | profit after tax |
| Negative operating cash flow | medium | latest year |
| Interest cover < 1.5x (high if < 1.0x) | medium / high | latest year |
| Quick ratio < 0.8 | medium | latest year |
| Revenue down 20%+ year on year | medium | latest two years |
| Half or more of the board appointed in 2025 | medium | directors |
| No financial statements on record | medium | financials |
| Renamed in 2025 / under 2 years old | low | profile |

Overall risk = the most severe flag. Result on the 50: **17 high, 12 medium, 21 low**.

Your call: the thresholds are judgement, not science. Defend them, or change them and rerun. The two I'd expect
questions on: interest cover 1.5x, and whether one pending case should be medium.

## 3. Facts in code, words from the model

The model never does arithmetic or decides the risk level in v2: `facts.py` does, deterministically, and the model
only writes. Reason: the two worst failures (missed flag, wrong number) are exactly what LLMs do under pressure, and
exactly what code gets right. The experiment (v1-raw vs v2-grounded) tests whether this matters.

## 4. How we know it's good: two layers

**Automatic (`summariser/evaluate.py`), on all 50:** high- and medium-flag recall, share of summaries with an
invented number, unsupported relationship claims, risk-level agreement, length. Six tests prove the checks catch
what they claim to (invented number, decimal-slip percentage, missed winding-up, a fake "same group" link between
two companies whose parents are both called "Gemilang Holdings", and that honest rounding passes).

Known limits: the checks are pattern-based. A flag mentioned in an unusual phrasing counts as missed (false alarm),
and a number that happens to equal some other figure in the record passes (missed error). Look at the per-company
CSV in `results/` for anything surprising.

**Human (blind), on 10:** `just review v1-raw v2-grounded` shuffles the two versions as A/B. Score each 1-5 on
Correct, Complete, Decision-ready, Concise, *then* `just unblind`. This is what judges usefulness, which the
automatic checks can't.

## 5. Sample and budget

All 50 companies, two LLM versions: about 200k tokens in, plus small outputs. That fits most free tiers in a day.
Run 3 companies first and read them before spending the rest.

## 6. Baseline

`v0-template` is the bar: no model, 100% flag recall, 0 invented numbers by construction. An LLM version is only
worth it if it reads better (blind review) *without* losing either property (automatic checks).
