"""The viewer: shows each company's record next to the summaries your system wrote. It only reads files."""

import re
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

ROOT = Path(__file__).resolve().parent.parent
COMPANIES = ROOT / "data" / "companies.jsonl"
SUMMARIES = ROOT / "summaries"


class Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class FormerName(Model):
    name: str
    changed_on: str


class Profile(Model):
    company_name: str
    status: str
    company_type: str
    incorporation_date: str
    industry: str
    state: str
    nature_of_business: str
    share_capital: int
    former_names: list[FormerName]


class Director(Model):
    name: str
    designation: str
    appointed_on: str


class Shareholder(Model):
    type: Literal["company", "individual"]
    name: str
    percentage: float
    registration_number: str | None = None
    incorporated_in: str | None = None


class Relationships(Model):
    directors: list[Director]
    shareholders: list[Shareholder]


class Audit(Model):
    firm: str
    opinion: str


class FinancialYear(Model):
    financial_year: int
    financial_year_end: str
    audit: Audit
    statements: dict[str, int]
    ratios_and_metrics: dict[str, dict[str, float | None]]


class Financials(Model):
    years: list[FinancialYear]


class Case(Model):
    case_number: str
    role: Literal["plaintiff", "defendant"]
    case_type: str
    court: str
    filed_on: str
    status: str
    claim_amount: float


class Litigation(Model):
    cases: list[Case]


class Company(Model):
    registration_number: str
    profile: Profile
    relationships: Relationships
    financials: Financials
    litigation: Litigation


class CompanyListItem(Model):
    registration_number: str
    company_name: str
    industry: str
    state: str


class SummaryLine(Model):
    registration_number: str
    summary: str


class SummaryVersion(Model):
    summaries: dict[str, str]
    invalid_lines: list[int]


app = FastAPI(title="Company summaries viewer")


def load_companies() -> list[Company]:
    lines = COMPANIES.read_text(encoding="utf-8").splitlines()
    return [Company.model_validate_json(line) for line in lines if line.strip()]


@app.get("/api/companies")
def list_companies() -> list[CompanyListItem]:
    return [
        CompanyListItem(
            registration_number=c.registration_number,
            company_name=c.profile.company_name,
            industry=c.profile.industry,
            state=c.profile.state,
        )
        for c in load_companies()
    ]


@app.get("/api/companies/{registration_number}")
def get_company(registration_number: str) -> Company:
    for company in load_companies():
        if company.registration_number == registration_number:
            return company
    raise HTTPException(404, f"No company {registration_number}")


@app.get("/api/summaries")
def list_versions() -> list[str]:
    return sorted(p.stem for p in SUMMARIES.glob("*.jsonl"))


@app.get("/api/summaries/{version}")
def get_version(version: str) -> SummaryVersion:
    path = SUMMARIES / f"{version}.jsonl"
    if not re.fullmatch(r"[A-Za-z0-9._-]+", version) or not path.is_file():
        raise HTTPException(404, f"No summaries/{version}.jsonl")
    summaries: dict[str, str] = {}
    invalid_lines: list[int] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = SummaryLine.model_validate_json(line)
        except ValidationError:
            invalid_lines.append(number)
            continue
        summaries[row.registration_number] = row.summary
    return SummaryVersion(summaries=summaries, invalid_lines=invalid_lines)


app.mount("/", StaticFiles(directory=ROOT / "app" / "static", html=True), name="static")
