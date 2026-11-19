"""Generate summaries with any OpenAI-compatible LLM API (Gemini, Groq, OpenRouter, ... all offer one).

Two versions, to answer one question: does grounding the model in pre-computed facts make summaries safer?
- v1-raw:      the model gets the full record and a brief.
- v2-grounded: the model also gets the facts and flags from facts.py, and is told to use only those figures.

Every response is cached in cache/<version>/<model>/<registration number>.json, keyed by the exact prompt, so
re-running never calls the model twice for the same input and reviewers can re-score without an API key.

Setup (PowerShell example, Gemini's free tier):
  $env:LLM_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
  $env:LLM_API_KEY  = "<your key>"
  $env:LLM_MODEL    = "<a model name from the provider's docs>"

Usage: uv run python -m summariser.generate v2-grounded [--ids SYN-000286,SYN-000545] [--delay 4]
"""

import argparse
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from summariser.facts import ROOT, Facts, extract, load_companies

BRIEF = """You write the summary a supplier-vetting team reads first, before deciding whether a company deserves a \
closer look. They are busy, sceptical and accountable for the decision.

Write in Markdown, at most 120 words:
1. First line: the risk level in bold (**High risk**, **Medium risk** or **Low risk**) and the single main reason.
2. Then up to 5 bullets: the red flags, most serious first. Legal status, winding-up petitions, judgments, audit \
problems, losses and cash burn come before anything else.
3. Then one line of financial snapshot for the latest year, and one line of profile (industry, state, age, owner).

Rules: never state a figure that isn't in the input. Don't speculate about causes. Don't link this company to any \
other company unless the record shows it as a shareholder. If there are no red flags, say so plainly."""

GROUNDING = """Use these pre-computed facts. They are checked; prefer them over your own arithmetic. Every flag listed \
must appear in your summary, and every number you write must come from them or the record. The risk level is \
already decided: use it."""

VERSIONS = ("v1-raw", "v2-grounded")


def prompt(version: str, record: dict[str, Any], facts: Facts) -> list[dict[str, str]]:
    user = "Company record (JSON):\n" + json.dumps(record, ensure_ascii=False)
    if version == "v2-grounded":
        grounded = {
            "risk": facts.risk,
            "flags": [{"severity": f.severity, "text": f.text} for f in facts.flags],
            "latest_financials": facts.financials[-1] if facts.financials else None,
            "parent": facts.parent,
            "age_years": facts.age_years,
        }
        user = f"{GROUNDING}\n\nFacts:\n{json.dumps(grounded, ensure_ascii=False)}\n\n{user}"
    return [{"role": "system", "content": BRIEF}, {"role": "user", "content": user}]


def call(messages: list[dict[str, str]], *, retries: int = 5) -> dict[str, Any]:
    base = os.environ["LLM_BASE_URL"].rstrip("/")
    body = json.dumps({"model": os.environ["LLM_MODEL"], "messages": messages, "temperature": 0.2}).encode()
    request = urllib.request.Request(
        f"{base}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {os.environ['LLM_API_KEY']}", "Content-Type": "application/json"},
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310 (URL comes from the user's env)
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503) and attempt < retries - 1:
                wait = 2 ** attempt * 5
                print(f"  {exc.code}, retrying in {wait}s")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("unreachable")


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text)


def generate(version: str, ids: list[str] | None, delay: float) -> Path:
    model = os.environ.get("LLM_MODEL", "unknown")
    cache_dir = ROOT / "cache" / version / _slug(model)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = ROOT / "summaries" / f"{version}.jsonl"
    existing = {}
    if out.exists():
        existing = {json.loads(line)["registrationNumber"]: line for line in out.read_text(encoding="utf-8").splitlines() if line}

    records = load_companies()
    if ids:
        records = [r for r in records if r["registrationNumber"] in ids]
    for record in records:
        reg = record["registrationNumber"]
        messages = prompt(version, record, extract(record))
        key = hashlib.sha256(json.dumps(messages).encode()).hexdigest()[:16]
        cached = cache_dir / f"{reg}.json"
        if cached.exists() and json.loads(cached.read_text())["prompt_hash"] == key:
            response = json.loads(cached.read_text())["response"]
        else:
            print(f"{version} {reg} ...")
            response = call(messages)
            cached.write_text(json.dumps({"prompt_hash": key, "model": model, "response": response}, indent=1))
            time.sleep(delay)  # stay under free-tier rate limits
        summary = response["choices"][0]["message"]["content"].strip()
        existing[reg] = json.dumps({"registrationNumber": reg, "summary": summary}, ensure_ascii=False)

    order = [r["registrationNumber"] for r in load_companies()]
    out.write_text("".join(existing[r] + "\n" for r in order if r in existing), encoding="utf-8")
    print(f"wrote {len(existing)} summaries to {out.relative_to(ROOT)}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("version", choices=VERSIONS)
    parser.add_argument("--ids", help="comma-separated registration numbers (default: all 50)")
    parser.add_argument("--delay", type=float, default=4.0, help="seconds between API calls")
    args = parser.parse_args()
    generate(args.version, args.ids.split(",") if args.ids else None, args.delay)


if __name__ == "__main__":
    main()
