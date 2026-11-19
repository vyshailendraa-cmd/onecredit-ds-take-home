"""Extract the facts a vetting team needs from one company record, in plain code (no model).

Everything a summary is allowed to claim comes from here, so it can be checked. Thresholds are deliberately simple
and listed in one place (THRESHOLDS) so they're easy to argue about; see DECISIONS.md.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
COMPANIES = ROOT / "data" / "companies.jsonl"
AS_OF = date(2025, 12, 31)  # records are as of this date (README)

THRESHOLDS = {
    "interest_cover_high": 1.0,  # below this, operating profit doesn't cover interest
    "interest_cover_medium": 1.5,
    "quick_ratio_medium": 0.8,
    "revenue_drop_medium": -0.20,  # year-on-year
    "new_director_window_days": 365,
    "director_turnover_share": 0.5,  # share of the board appointed within the window
    "name_change_window_days": 365,
    "young_company_years": 2,
}

HIGH, MEDIUM, LOW = "high", "medium", "low"


@dataclass(frozen=True)
class Flag:
    code: str
    severity: str
    text: str  # plain English, with the figures that justify it


@dataclass
class Facts:
    registration_number: str
    name: str
    industry: str
    state: str
    nature_of_business: str
    status: str
    incorporated: str
    age_years: int
    parent: str | None
    latest_year: int | None
    financials: list[dict[str, Any]] = field(default_factory=list)  # per year, oldest first
    litigation: dict[str, Any] = field(default_factory=dict)
    flags: list[Flag] = field(default_factory=list)
    risk: str = LOW

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_companies(path: Path = COMPANIES) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def rm(amount: float) -> str:
    """RM amounts the way a reader scans them: RM5.13m, RM690k, RM-1.08m -> 'RM-1.08m' stays signed."""
    sign = "-" if amount < 0 else ""
    a = abs(amount)
    if a >= 1_000_000:
        return f"{sign}RM{a / 1_000_000:.2f}m"
    if a >= 1_000:
        return f"{sign}RM{a / 1_000:.0f}k"
    return f"{sign}RM{a:.0f}"


def pct(ratio: float) -> str:
    return f"{ratio * 100:.1f}%"


def _days_before_as_of(iso: str) -> int:
    return (AS_OF - date.fromisoformat(iso)).days


def _year_summary(year: dict[str, Any]) -> dict[str, Any]:
    s, r = year["statements"], year["ratiosAndMetrics"]
    return {
        "year": year["financialYear"],
        "audit_opinion": year["audit"]["opinion"],
        "revenue": s["revenue"],
        "profit_after_tax": s["profitAfterTax"],
        "net_margin": r["profitability"]["netProfitMargin"],
        "operating_cash_flow": s["operatingCashFlow"],
        "total_equity": s["totalEquity"],
        "borrowings": s["borrowings"],
        "interest_cover": r["capitalStructure"]["interestCoverageRatio"],
        "quick_ratio": r["liquidityAndCashFlow"]["quickRatio"],
    }


def extract(record: dict[str, Any]) -> Facts:
    profile, rel = record["profile"], record["relationships"]
    years = sorted(record["financials"]["years"], key=lambda y: y["financialYear"])
    fin = [_year_summary(y) for y in years]
    incorporated = profile["incorporationDate"]
    corporate = [s for s in rel["shareholders"] if s["type"] == "company"]
    parent = (
        f"{corporate[0]['name']} ({corporate[0]['registrationNumber']}, {corporate[0]['percentage']:g}%)"
        if corporate
        else None
    )
    facts = Facts(
        registration_number=record["registrationNumber"],
        name=profile["companyName"],
        industry=profile["industry"],
        state=profile["state"],
        nature_of_business=profile["natureOfBusiness"],
        status=profile["status"],
        incorporated=incorporated,
        age_years=_days_before_as_of(incorporated) // 365,
        parent=parent,
        latest_year=fin[-1]["year"] if fin else None,
        financials=fin,
        litigation=_litigation(record["litigation"]["cases"]),
    )
    facts.flags = _flags(record, facts)
    facts.risk = _risk(facts.flags)
    return facts


def _litigation(cases: list[dict[str, Any]]) -> dict[str, Any]:
    against = [c for c in cases if c["role"] == "defendant"]
    pending = [c for c in against if c["status"] == "Pending"]
    return {
        "cases": len(cases),
        "as_defendant": len(against),
        "as_plaintiff": len(cases) - len(against),
        "pending_as_defendant": len(pending),
        "pending_claims_rm": sum(c["claimAmount"] for c in pending),
        "judgments_against": [c for c in against if c["status"] == "Judgment entered"],
        "winding_up_petitions": [c for c in against if c["caseType"] == "Winding-up petition"],
    }


def _flags(record: dict[str, Any], f: Facts) -> list[Flag]:
    t = THRESHOLDS
    flags: list[Flag] = []
    add = flags.append

    # Legal status and court action
    if f.status != "Active":
        add(Flag("status", HIGH, f"Company status is '{f.status}'."))
    for c in f.litigation["winding_up_petitions"]:
        severity = HIGH if c["status"] in ("Pending", "Judgment entered") else MEDIUM
        add(Flag("winding_up_petition", severity, f"Winding-up petition against it filed {c['filedOn']} ({c['status']})."))
    lit = f.litigation
    if lit["judgments_against"]:
        total = sum(c["claimAmount"] for c in lit["judgments_against"])
        add(Flag("judgment_against", HIGH, f"{len(lit['judgments_against'])} judgment(s) entered against it ({rm(total)})."))
    if lit["pending_as_defendant"]:
        add(
            Flag(
                "pending_litigation",
                MEDIUM,
                f"{lit['pending_as_defendant']} pending case(s) as defendant, claims of {rm(lit['pending_claims_rm'])}.",
            )
        )

    # Audit
    for y in f.financials:
        latest = y["year"] == f.latest_year
        if y["audit_opinion"].startswith("Disclaimer"):
            add(Flag("audit_disclaimer", HIGH if latest else MEDIUM, f"FY{y['year']} audit: disclaimer of opinion."))
        elif "going concern" in y["audit_opinion"]:
            add(Flag("going_concern", HIGH if latest else MEDIUM, f"FY{y['year']} audit: material uncertainty on going concern."))

    # Financial health
    if not f.financials:
        add(Flag("no_financials", MEDIUM, "No financial statements on record."))
    else:
        last = f.financials[-1]
        losses = [y for y in f.financials if y["profit_after_tax"] < 0]
        if last["total_equity"] < 0:
            add(Flag("negative_equity", HIGH, f"Negative equity of {rm(last['total_equity'])} in FY{last['year']}."))
        if len(losses) == len(f.financials) and len(losses) >= 2:
            add(Flag("persistent_losses", HIGH, f"Loss-making in all {len(losses)} years on record (FY{last['year']}: {rm(last['profit_after_tax'])})."))
        elif last["profit_after_tax"] < 0:
            add(Flag("loss", MEDIUM, f"Net loss of {rm(last['profit_after_tax'])} in FY{last['year']}."))
        if last["operating_cash_flow"] < 0:
            add(Flag("cash_burn", MEDIUM, f"Negative operating cash flow of {rm(last['operating_cash_flow'])} in FY{last['year']}."))
        cover = last["interest_cover"]
        if cover is not None and cover < t["interest_cover_medium"]:
            severity = HIGH if cover < t["interest_cover_high"] else MEDIUM
            add(Flag("interest_cover", severity, f"Interest cover of {cover:.2f}x in FY{last['year']}."))
        quick = last["quick_ratio"]
        if quick is not None and quick < t["quick_ratio_medium"]:
            add(Flag("liquidity", MEDIUM, f"Quick ratio of {quick:.2f} in FY{last['year']}."))
        if len(f.financials) >= 2:
            prev = f.financials[-2]
            if prev["revenue"] > 0:
                change = last["revenue"] / prev["revenue"] - 1
                if change <= t["revenue_drop_medium"]:
                    add(Flag("revenue_drop", MEDIUM, f"Revenue fell {pct(-change)} to {rm(last['revenue'])} in FY{last['year']}."))

    # People and identity
    directors = record["relationships"]["directors"]
    recent = [d for d in directors if _days_before_as_of(d["appointedOn"]) <= t["new_director_window_days"]]
    if directors and len(recent) / len(directors) >= t["director_turnover_share"]:
        add(Flag("director_turnover", MEDIUM, f"{len(recent)} of {len(directors)} directors appointed in 2025."))
    for former in record["profile"]["formerNames"]:
        if _days_before_as_of(former["changedOn"]) <= t["name_change_window_days"]:
            add(Flag("name_change", LOW, f"Renamed on {former['changedOn']} (formerly {former['name']})."))
    if f.age_years < t["young_company_years"]:
        add(Flag("young_company", LOW, f"Incorporated {f.incorporated}, under {t['young_company_years']} years old."))
    return flags


def _risk(flags: list[Flag]) -> str:
    severities = {fl.severity for fl in flags}
    if HIGH in severities:
        return HIGH
    if MEDIUM in severities:
        return MEDIUM
    return LOW


def main() -> None:
    from collections import Counter

    facts = [extract(r) for r in load_companies()]
    print(Counter(f.risk for f in facts))
    print(Counter(fl.code for f in facts for fl in f.flags).most_common())


if __name__ == "__main__":
    main()
