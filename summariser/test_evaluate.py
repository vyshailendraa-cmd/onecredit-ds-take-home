"""The evaluator has to catch the mistakes that matter. Each test plants one and checks it's caught."""

from summariser.baseline import summarise
from summariser.evaluate import score
from summariser.facts import extract, load_companies

RECORDS = {r["registrationNumber"]: r for r in load_companies()}
NAMES = {reg: r["profile"]["companyName"] for reg, r in RECORDS.items()}


def check(reg: str, summary: str):
    return score(RECORDS[reg], summary, NAMES)


def test_template_summaries_are_clean():
    for reg, record in RECORDS.items():
        s = check(reg, summarise(extract(record)))
        assert not s.invented_numbers, (reg, s.invented_numbers)
        assert not s.high_missed and not s.medium_missed, reg
        assert not s.unsupported_relationships, reg


def test_rounded_figures_pass():
    # SYN-000029 FY2024 revenue is RM5,352,856: all of these roundings are honest...
    for text in ("revenue of RM5.4m", "revenue of RM5.35m", "revenue of 5.4 million", "RM5,352,856"):
        assert not check("SYN-000029", f"**Low risk.** {text}.").invented_numbers, text
    # ...but rounding down is not: 5.3m is off by more than the 0.05m the text implies (it's truncated).
    assert check("SYN-000029", "**Low risk.** revenue of RM5.3m.").imprecise_numbers


def test_invented_number_is_caught():
    assert check("SYN-000029", "**Low risk.** Revenue of RM8.4m in FY2024.").invented_numbers == ["8.4e+06"]


def test_wrong_percentage_is_caught():
    # Net margin is 1.8%; 18% is a classic decimal slip.
    assert check("SYN-000029", "**Low risk.** Net margin of 18% in FY2024.").invented_numbers


def test_missed_winding_up_is_caught():
    reg = next(r for r, rec in RECORDS.items() if rec["profile"]["status"] == "Winding up")
    s = check(reg, "**Medium risk.** Revenue is stable and the company is profitable.")
    assert "status" in s.high_missed


def test_fake_group_claim_is_caught():
    # Two companies are owned by different holding companies that share the name "Gemilang Holdings".
    assert check("SYN-000381", "Part of the same group as SYN-001203.").unsupported_relationships == ["SYN-001203"]
    assert check("SYN-000029", "**Low risk.** A subsidiary of a larger group.").unsupported_relationships


def test_truncation_is_imprecise_not_invented():
    # Revenue RM5,352,856: "RM5.4m" is right, "RM5.3m" is truncated (imprecise), "RM9.1m" is wrong.
    s = check("SYN-000029", "**Low risk.** Revenue of RM5.3m.")
    assert s.imprecise_numbers and not s.invented_numbers
    assert check("SYN-000029", "**Low risk.** Revenue of RM9.1m.").invented_numbers


def test_identifiers_are_not_figures():
    s = check("SYN-000286", "Winding-up petition pending (Case 2022-9003). Owned by Directors 1, 5, 3 and 2.")
    assert not s.invented_numbers and not s.imprecise_numbers
    # ...but a percentage right after a director's name is still checked.
    assert check("SYN-000677", "Largest shareholder: Director 1, 37.75%.").invented_numbers == []
    assert check("SYN-000677", "Largest shareholder: Director 1, 47.75%.").invented_numbers


def test_off_by_one_age_is_wrong():
    # SYN-000333 was incorporated in October 1997: 28 years old at the end of 2025.
    assert check("SYN-000333", "Retail, Sarawak, 27 years old.").invented_numbers
