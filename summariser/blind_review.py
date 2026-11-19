"""Blind side-by-side review: you judge two versions without knowing which is which.

Picks a sample (half high-risk, half not, fixed seed), shuffles which version is "A" for each company, and writes
review/blind_review.md to fill in, plus review/key.json to unblind afterwards. Score each summary on the rubric in
DECISIONS.md, *then* run `--unblind` to see which version won.

Usage: uv run python -m summariser.blind_review v1-raw v2-grounded [--n 10]
       uv run python -m summariser.blind_review --unblind
"""

import argparse
import json
import random
import re

from summariser.facts import ROOT, extract, load_companies

REVIEW = ROOT / "review"


def load(version: str) -> dict[str, str]:
    path = ROOT / "summaries" / f"{version}.jsonl"
    return {(row := json.loads(line))["registrationNumber"]: row["summary"] for line in path.read_text(encoding="utf-8").splitlines() if line}


def build(a: str, b: str, n: int) -> None:
    first, second = load(a), load(b)
    records = [r for r in load_companies() if r["registrationNumber"] in first and r["registrationNumber"] in second]
    rng = random.Random(2026)
    risky = [r for r in records if extract(r).risk == "high"]
    rest = [r for r in records if extract(r).risk != "high"]
    sample = rng.sample(risky, min(n // 2, len(risky))) + rng.sample(rest, min(n - n // 2, len(rest)))
    key, parts = {}, ["# Blind review\n\nScore each summary 1-5 on: **Correct**, **Complete (red flags)**, **Decision-ready**, **Concise**. Note anything wrong.\n"]
    for record in sample:
        reg = record["registrationNumber"]
        pair = [(a, first[reg]), (b, second[reg])]
        rng.shuffle(pair)
        key[reg] = {"A": pair[0][0], "B": pair[1][0]}
        parts.append(f"\n---\n\n## {reg} · {record['profile']['companyName']}\n")
        for label, (_, text) in zip("AB", pair, strict=True):
            parts.append(f"\n### {label}\n\n{text}\n\nCorrect: _ Complete: _ Decision-ready: _ Concise: _ Notes:\n")
    REVIEW.mkdir(exist_ok=True)
    (REVIEW / "blind_review.md").write_text("".join(parts), encoding="utf-8")
    (REVIEW / "key.json").write_text(json.dumps(key, indent=1))
    print(f"wrote review/blind_review.md ({len(sample)} companies). Don't open review/key.json until you've scored.")


SCORES = re.compile(r"### ([AB])\n.*?Correct: (\S+) Complete: (\S+) Decision-ready: (\S+) Concise: (\S+)", re.S)


def unblind() -> None:
    key = json.loads((REVIEW / "key.json").read_text())
    text = (REVIEW / "blind_review.md").read_text(encoding="utf-8")
    totals: dict[str, list[int]] = {}
    for block in text.split("\n## ")[1:]:
        reg = block.split(" ")[0]
        for label, *scores in SCORES.findall(block):
            if all(s.isdigit() for s in scores):
                totals.setdefault(key[reg][label], []).extend(int(s) for s in scores)
    for version, values in totals.items():
        print(f"{version}: mean {sum(values) / len(values):.2f} over {len(values) // 4} summaries")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("versions", nargs="*")
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--unblind", action="store_true")
    args = parser.parse_args()
    if args.unblind:
        unblind()
    else:
        build(args.versions[0], args.versions[1], args.n)


if __name__ == "__main__":
    main()
