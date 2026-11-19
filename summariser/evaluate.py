"""Score a summaries file against the records. Automatic checks for the things that must never go wrong.

For each summary:
- flag recall: does it mention every high (and medium) severity flag from facts.py?
- invented numbers: every number in the text must match a figure in the record (or one derived from it), within the
  rounding the text itself uses ("RM5.1m" may be 5,050,000-5,149,999).
- unsupported relationships: no group / parent / sister-company claims the record doesn't support, and no other
  company's registration number or name.
- risk agreement: does the stated risk level match the facts?
- length in words.

These checks can't judge whether a summary is *useful*; that's the blind manual review (DECISIONS.md).

Usage: uv run python -m summariser.evaluate summaries/v1-raw.jsonl [summaries/v2-grounded.jsonl ...]
"""

import csv
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from summariser.facts import HIGH, MEDIUM, ROOT, Facts, extract, load_companies

FLAG_PATTERNS = {
    "status": r"winding[- ]up|wound up|liquidat",
    "winding_up_petition": r"winding[- ]up",
    "judgment_against": r"judge?ment",
    "pending_litigation": r"pending|lawsuit|litigation|court|legal (claim|action|case)|sued",
    "audit_disclaimer": r"disclaim",
    "going_concern": r"going concern",
    "no_financials": r"no (financial|accounts|statements)|financials?\b.{0,20}(not available|missing|unavailable)",
    "negative_equity": r"negative (equity|net worth)|liabilities exceed",
    "persistent_losses": r"loss",
    "loss": r"loss",
    "cash_burn": r"(negative|outflow|burn).{0,40}cash|cash.{0,40}(negative|outflow|burn)",
    "interest_cover": r"interest (cover|coverage)",
    "liquidity": r"liquid|quick ratio|current ratio",
    "revenue_drop": r"revenue.{0,50}(fell|fall|drop|declin|down|shr[iu]nk)|(fell|fall|drop|declin|shr[iu]nk).{0,50}revenue",
    "director_turnover": r"director|board",
    "name_change": r"rename|name change|formerly|changed (its )?name",
    "young_company": r"incorporated|young|newly",
}
RELATIONSHIP = re.compile(r"\b(group|parent|subsidiar\w*|sister|affiliat\w*|related compan\w*|holding compan\w*)\b", re.I)
RISK = re.compile(r"\b(high|medium|moderate|low)[- ]risk\b|\brisk(?: level| rating)?\s*[:=-]?\s*\**\s*(high|medium|moderate|low)\b", re.I)
# Identifiers and dates aren't figures: mask them before looking for numbers.
MASKS = [
    r"SYN-\d+",
    r"CASE-[\d-]+",
    r"\d{4}-\d{2}-\d{2}",
    r"\bFY\s?\d{2,4}",
    r"\b(Director|Shareholder|Audit Firm)\s+\d+",
    r"\b(19[5-9]\d|20[0-2]\d)\b",  # years
]
NUMBER = re.compile(
    r"(?P<rm>RM\s?)?(?P<sign>[-−])?(?P<num>\d{1,3}(?:,\d{3})+|\d+)(?P<dec>\.\d+)?\s?"
    r"(?P<unit>%|x\b|times\b|bn\b|billion\b|m\b|mil\b|million\b|k\b|thousand\b)?",
    re.I,
)
SCALE = {"bn": 1e9, "billion": 1e9, "m": 1e6, "mil": 1e6, "million": 1e6, "k": 1e3, "thousand": 1e3}


@dataclass
class Score:
    registration_number: str
    risk: str
    stated_risk: str | None
    high_flags: int
    high_missed: list[str] = field(default_factory=list)
    medium_flags: int = 0
    medium_missed: list[str] = field(default_factory=list)
    invented_numbers: list[str] = field(default_factory=list)
    unsupported_relationships: list[str] = field(default_factory=list)
    words: int = 0


def allowed_values(record: dict[str, Any], facts: Facts) -> list[float]:
    """Every figure a summary may legitimately use: raw values, ratios as %, and simple derivations."""
    values: list[float] = []

    def walk(node: Any) -> None:
        if isinstance(node, bool):
            return
        if isinstance(node, int | float):
            values.append(float(node))
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(record)
    walk(facts.litigation)
    for fl in facts.flags:  # numbers facts.py itself wrote, e.g. claim totals
        values.extend(_value for _value, _ in _numbers(fl.text))
    years = facts.financials
    for a, b in zip(years, years[1:], strict=False):
        for key in ("revenue", "profit_after_tax", "operating_cash_flow", "total_equity", "borrowings"):
            if a[key]:
                values.append(b[key] / a[key] - 1)
            values.append(b[key] - a[key])
    values.extend([len(record["relationships"]["directors"]), len(record["relationships"]["shareholders"]), len(years)])
    values.append(facts.age_years)
    values.append(date(2025, 12, 31).year - int(facts.incorporated[:4]))
    as_percent = [v * 100 for v in values if abs(v) < 100]
    return values + as_percent


def _numbers(text: str) -> list[tuple[float, float]]:
    """(value, tolerance) for each figure in the text. Tolerance is half the last written digit, times the unit."""
    for mask in MASKS:
        text = re.sub(mask, " ", text, flags=re.I)
    found = []
    for m in NUMBER.finditer(text):
        digits = m["num"].replace(",", "") + (m["dec"] or "")
        value = float(digits)
        decimals = len(m["dec"]) - 1 if m["dec"] else 0
        unit = (m["unit"] or "").lower()
        scale = SCALE.get(unit, 1.0)
        tolerance = 0.5 * 10 ** (-decimals) * scale
        found.append((value * scale, tolerance))
    return found


def _matches(value: float, tolerance: float, allowed: list[float]) -> bool:
    # Signs are ignored: "a loss of RM1.08m" is written positive for a negative figure.
    return any(abs(abs(value) - abs(a)) <= tolerance + 1e-9 for a in allowed)


def score(record: dict[str, Any], summary: str, others: dict[str, str]) -> Score:
    facts = extract(record)
    text = summary.lower()
    s = Score(facts.registration_number, facts.risk, None, 0, words=len(summary.split()))
    for fl in facts.flags:
        hit = re.search(FLAG_PATTERNS[fl.code], text, re.I) is not None
        if fl.severity == HIGH:
            s.high_flags += 1
            if not hit:
                s.high_missed.append(fl.code)
        elif fl.severity == MEDIUM:
            s.medium_flags += 1
            if not hit:
                s.medium_missed.append(fl.code)

    allowed = allowed_values(record, facts)
    for value, tolerance in _numbers(summary):
        if value <= 1 and tolerance >= 0.5:  # "1 case", "0 judgments": counts too small to be worth checking
            continue
        if not _matches(value, tolerance, allowed):
            s.invented_numbers.append(f"{value:g}")

    own = {facts.registration_number}
    if facts.parent:
        own.add(facts.parent.split("(")[1].split(",")[0])
    for reg in re.findall(r"SYN-\d{6}", summary):
        if reg not in own:
            s.unsupported_relationships.append(reg)
    for reg, name in others.items():
        if reg not in own and name.lower() in text:
            s.unsupported_relationships.append(name)
    if not facts.parent and (m := RELATIONSHIP.search(summary)):
        s.unsupported_relationships.append(m.group(0))

    if m := RISK.search(summary):
        stated = (m.group(1) or m.group(2)).lower()
        s.stated_risk = "medium" if stated == "moderate" else stated
    return s


def evaluate(path: Path) -> list[Score]:
    records = {r["registrationNumber"]: r for r in load_companies()}
    names = {reg: r["profile"]["companyName"] for reg, r in records.items()}
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [score(records[row["registrationNumber"]], row["summary"], names) for row in rows]


def report(path: Path, scores: list[Score]) -> dict[str, float]:
    n = len(scores)
    high = sum(s.high_flags for s in scores)
    medium = sum(s.medium_flags for s in scores)
    stated = [s for s in scores if s.stated_risk]
    metrics = {
        "summaries": n,
        "high-flag recall": 1 - sum(len(s.high_missed) for s in scores) / high if high else 1.0,
        "medium-flag recall": 1 - sum(len(s.medium_missed) for s in scores) / medium if medium else 1.0,
        "summaries with an invented number": sum(bool(s.invented_numbers) for s in scores) / n,
        "invented numbers (total)": sum(len(s.invented_numbers) for s in scores),
        "unsupported relationship claims": sum(len(s.unsupported_relationships) for s in scores),
        "states a risk level": len(stated) / n,
        "risk level matches facts": sum(s.stated_risk == s.risk for s in stated) / len(stated) if stated else 0.0,
        "median words": sorted(s.words for s in scores)[n // 2],
    }
    out = ROOT / "results" / f"{path.stem}.csv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["registrationNumber", "risk", "stated_risk", "high_missed", "medium_missed", "invented_numbers", "unsupported_relationships", "words"])
        for s in scores:
            writer.writerow([s.registration_number, s.risk, s.stated_risk, " ".join(s.high_missed), " ".join(s.medium_missed), " ".join(s.invented_numbers), " ".join(s.unsupported_relationships), s.words])
    print(f"\n{path.name}  (details: results/{out.name})")
    for key, value in metrics.items():
        print(f"  {key:<36} {value:.1%}" if isinstance(value, float) else f"  {key:<36} {value}")
    return metrics


def main() -> None:
    for arg in sys.argv[1:] or ["summaries/v0-template.jsonl"]:
        path = Path(arg)
        report(path, evaluate(path))


if __name__ == "__main__":
    main()
