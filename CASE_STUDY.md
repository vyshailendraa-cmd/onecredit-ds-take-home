# Case study: company summaries for a vetting team

> Draft skeleton. Sections marked TODO need real results and your own reasoning. Write them in your own words.

## 1. What a good summary is for this team, and why

TODO (from DECISIONS.md §1). Start from the reader: a team triaging companies before a closer look, accountable
for what they miss. Then the five properties in priority order, and *why that order*: the cost of a missed red flag
vs the cost of a clumsy sentence.

## 2. What I built

- **Facts in plain code** (`summariser/facts.py`): from each record, the latest financials and 17 kinds of red flag
  (legal status, winding-up petitions, judgments, audit opinions, losses, cash burn, interest cover, liquidity,
  revenue drops, board turnover, renames). The overall risk level is the most severe flag.
- **v0-template** (`summariser/baseline.py`): summaries assembled from those facts, no model. The baseline.
- **Two LLM versions** (`summariser/generate.py`), same brief, any OpenAI-compatible free API:
  - **v1-raw**: the model gets the full record.
  - **v2-grounded**: the model also gets the pre-computed facts and the decided risk level, and is told to use only
    those figures.
- **An evaluator** (`summariser/evaluate.py`) with tests, and a **blind review** tool (`summariser/blind_review.py`).
- All model responses are cached in `cache/`, so the summaries can be re-scored without calling a model.

Provider and model: Google Gemini, `gemini-3.1-flash-lite` (free tier) through its OpenAI-compatible API,
temperature 0.2, low reasoning effort. Larger Flash models were overloaded (HTTP 503) when I ran this, so the
pipeline retries, skips and resumes; every response is cached in `cache/`.

## 3. How I know whether it's good

All 50 companies, scored automatically (`just evaluate`):

| Version | High-flag recall | Medium-flag recall | Wrong numbers | Truncated numbers | Risk level matches | Median words |
|---|---|---|---|---|---|---|
| v0-template (no model) | 100% | 100% | 0 | 0 | 100% | 34 |
| v1-raw | 96.7% | 100% | 4 (3 real, 1 false alarm; see below) | 8 | **64%** | 98 |
| v2-grounded | **100%** | **100%** | **0** | **0** | **100%** | 56 |

**Grounding is what makes the model safe.** Given only the raw record, the model:
- missed a red flag: SYN-000148's interest cover below 1x (it mentioned the losses, not that profit doesn't cover
  interest);
- got the risk level wrong in 18 of 50. It's not that the model "can't judge": without an explicit rubric it
  applies its own. It called five two-year-old, loss-making companies with negative interest cover "medium",
  three companies with **no financial statements at all** "low" (missing data read as no problems), and nine
  clean companies "medium" out of caution. Some of this is fair disagreement with my thresholds (is one year of
  interest cover below 1x really "high" for a two-year-old company?), but reading no data as low risk is not. **The team needs one consistent definition of risk, and that has to
  live in code, not in a prompt.**
- wrote ages off by one ("27 years old" for a company incorporated in October 1997);
- truncated instead of rounding ("RM674k" for 674,614; "RM52.9M" for 52,970,420). Not invented, but the team
  can't tell the difference, which is the point.

With the facts and risk level pre-computed (v2), every flag was covered, nothing was wrong or truncated, and the
summaries were 40% shorter.

**Checking the checker.** The first evaluator run reported 15 invented numbers in v1 and 1 in v2. I read every
one against the raw record: 4 were the checker's mistakes (case numbers without their `CASE-` prefix, "Directors
1, 5, 3" read as a number, a two-year change, a correct sum of two claims). I fixed those, added a test for each,
and split "wrong" from "truncated", since they're different failures. One known limit remains: "down over 80%"
(true: -82.9%) is still flagged, because the checker reads numbers as rounded values, not bounds.

Other limits: flag coverage is checked by keywords, so an unusual phrasing counts as a miss (false alarm), and a
wrong number that happens to equal another figure in the record passes (missed error). The automatic checks prove
**safety**, not **usefulness**: that's the blind review.

**Blind review** (10 companies, 5 high-risk, versions shuffled as A/B): TODO, after `just review v1-raw v2-grounded`.

## 4. What I'd do next, and how I'd keep improving it

TODO. Ideas to choose from: have the team label 50 summaries to calibrate the checks; track which flags they act
on and re-tune thresholds; add a "what changed since last review" line; a second-model checker for phrasing the
regex misses; monitor flag recall and invented-number rate on every new batch as a release gate.

## Using AI tools

TODO: say exactly what you used and for what. Draft: *I used Claude (Anthropic) to help write the code and
evaluator and to draft this document's structure. I chose the definition of "good", set the thresholds, ran the
experiments and did the blind review myself.* Edit this so it's true.
