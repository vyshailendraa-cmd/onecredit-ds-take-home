# Case study: company summaries for a vetting team

## 1. What a good summary is for this team, and why

The reader is a team vetting companies before choosing them as suppliers or partners. They're busy and
sceptical, and they're accountable for what they miss. The summary isn't a description of the company; it's a
**triage tool**: it should tell them in 30 seconds whether the full record deserves a closer look.

So, in priority order:

1. **Never miss a red flag.** A missed winding-up petition can cost far more than a clumsy sentence. A summary
   that hides one is worse than no summary, because it makes the team skip a record they should have read.
2. **Never invent or distort a figure.** If the team can't trust one number, they go back to the full record and
   the summary has saved nothing. A truncated figure ("RM674k" for 674,614) counts against it too: they can't tell
   an imprecise number from an invented one.
3. **Decision first.** The first line gives a risk level (high / medium / low) and the single main reason. I chose
   a risk level, not a recommendation such as "avoid": the decision stays with the team.
4. **Short.** Around 120 words at most, so it's read before the record, not instead of it.
5. **Plain language.** "Losses in all 3 years" rather than "negative net margin trajectory".

The order matters because the failures aren't equal. A clumsy sentence costs seconds; a missed red flag or a wrong
number costs the team's trust in every summary. That's why the first two are tested on every summary, and why the
risk level is decided by explicit rules (DECISIONS.md §2) rather than left to the model.

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

**Blind human review** (`review/blind_review.md`): 10 companies (5 high-risk), v1 and v2 shuffled as A/B. For each I
asked "which would you rather read first, and why?", wrote down anything that looked wrong, and only then unblinded.

- **I preferred v1-raw 6 times out of 10.** The reasons were all about context: it names the disputes, shows trends
  (equity falling, leverage rising, a turnaround), and adds figures like the cash cycle. v2 is safer but thinner.
- **But I noted a problem in 5 of the 10 v1 summaries, and none in v2.** Three are plain errors, confirmed against
  the records: v1 calls a 49.22% holder "majority owned" (SYN-001560), labels the net loss as the operating loss
  (SYN-001158), and rates a company with no financial statements as low risk (SYN-000333). Two are judgement
  calls: it overstates a need for outside funding, and blurs total liabilities with borrowings.
- **In one case I picked v1 even though I'd spotted its error** (the 49.22% "majority"). That's the real risk:
  richer, confident text wins the reader even when it's wrong, and the automatic checks didn't catch any of
  these five, because they're wrong *claims* built from right numbers.

So the two methods agree on safety and disagree on usefulness, which is exactly why both are needed. The next
version is clear: keep v2's grounding, and give it more checked facts to work with (trends, named disputes,
ownership stated precisely). One reviewer and ten companies is a small sample, so this is a direction, not a result.

## 4. What I'd do next, and how I'd keep improving it

1. **v3: grounded, but richer.** Add the context I preferred in v1 to the checked facts (multi-year trends,
   named disputes, exact ownership wording such as "largest shareholder" vs "majority"), and keep the rule that
   the model only uses those facts. Success means v3 matches v2 on the automatic checks and beats v1 in the blind
   review. Extend the checker to claims as well as numbers ("majority owned" requires over 50%).
   Then **ask the readers**: repeat the blind review with people from the vetting team, on more companies.
2. **Calibrate the risk rules with the team.** The thresholds in `facts.py` are my judgement. The model's
   disagreements (e.g. one year of interest cover below 1x at a two-year-old company) are a good list of edge
   cases to settle with them. Then track which flags they actually act on, and re-tune.
3. **Make the checker smarter where it's weak.** It reads "over 80%" as a rounded value rather than a bound, and
   checks flag coverage with keywords. A small labelled set of summaries would show how often each causes a false
   alarm or a miss, before deciding whether a second model as checker is worth its cost.
4. **Use the checks as a release gate.** Every new prompt or model version is scored on the same 50 companies;
   it ships only if flag recall stays at 100% and wrong numbers at 0. That's how it keeps improving without
   quietly getting worse.
5. **Add what the team would want next**, if they ask for it: a "what changed since the last review" line, and
   links from each flag to the part of the record it comes from.

## Using AI tools

I used Claude (Anthropic) throughout: to write most of the code and tests, debug the setup on my machine, check
each flagged number against the raw records, and draft this case study from the decisions and results. I ran the
generation and evaluation on my own machine with Gemini's free tier and decided what goes in. I can walk through
every part of it.
