"""v0: a template summary built straight from the facts, with no model.

It's the bar the LLM versions have to beat. By construction it never invents a number and never misses a flag, so
an LLM version is only worth having if it reads better without losing either property.

Usage: uv run python -m summariser.baseline   -> summaries/v0-template.jsonl
"""

import json

from summariser.facts import HIGH, MEDIUM, ROOT, Facts, extract, load_companies, pct, rm

SEVERITY_ORDER = {HIGH: 0, MEDIUM: 1, "low": 2}
VERDICT = {
    HIGH: "**High risk.** Review the record before engaging.",
    MEDIUM: "**Medium risk.** Usable, but check the points below.",
    "low": "**Low risk.** No red flags found in the record.",
}


def summarise(f: Facts) -> str:
    lines = [VERDICT[f.risk]]
    flags = sorted(f.flags, key=lambda fl: SEVERITY_ORDER[fl.severity])
    if flags:
        lines.append("")
        lines.extend(f"- {fl.text}" for fl in flags)
    lines.append("")
    lines.append(_snapshot(f))
    owner = f" Majority-owned by {f.parent}." if f.parent else ""
    lines.append(f"{f.industry}, {f.state}; incorporated {f.incorporated[:4]}.{owner}")
    return "\n".join(lines)


def _snapshot(f: Facts) -> str:
    if not f.financials:
        return "No financial statements on record."
    last = f.financials[-1]
    pat = last["profit_after_tax"]
    result = f"net profit {rm(pat)}" if pat >= 0 else f"net loss {rm(-pat)}"
    text = f"FY{last['year']}: revenue {rm(last['revenue'])}, {result} ({pct(last['net_margin'])} margin)"
    if len(f.financials) >= 2 and f.financials[-2]["revenue"] > 0:
        change = last["revenue"] / f.financials[-2]["revenue"] - 1
        text += f", revenue {'up' if change >= 0 else 'down'} {pct(abs(change))} on FY{f.financials[-2]['year']}"
    return text + "."


def main() -> None:
    out = ROOT / "summaries" / "v0-template.jsonl"
    rows = [{"registrationNumber": r["registrationNumber"], "summary": summarise(extract(r))} for r in load_companies()]
    out.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(f"wrote {len(rows)} summaries to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
