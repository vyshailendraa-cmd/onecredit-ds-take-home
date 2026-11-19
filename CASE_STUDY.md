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

Provider and model: TODO.

## 3. How I know whether it's good

| Version | High-flag recall | Medium-flag recall | Summaries with an invented number | Unsupported links | Risk matches | Median words |
|---|---|---|---|---|---|---|
| v0-template | 100% | 100% | 0% | 0 | 100% | 34 |
| v1-raw | TODO | | | | | |
| v2-grounded | TODO | | | | | |

Blind review (10 companies, 5 high-risk): TODO.

TODO: what the numbers say, two or three concrete failures you found by reading (quote them), and the limits of
the checks (DECISIONS.md §4).

## 4. What I'd do next, and how I'd keep improving it

TODO. Ideas to choose from: have the team label 50 summaries to calibrate the checks; track which flags they act
on and re-tune thresholds; add a "what changed since last review" line; a second-model checker for phrasing the
regex misses; monitor flag recall and invented-number rate on every new batch as a release gate.

## Using AI tools

TODO: say exactly what you used and for what. Draft: *I used Claude (Anthropic) to help write the code and
evaluator and to draft this document's structure. I chose the definition of "good", set the thresholds, ran the
experiments and did the blind review myself.* Edit this so it's true.
