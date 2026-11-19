# Changelog

Versions use CalVer with the role prefix: `ds-vYYYY.MM`, or `ds-vYYYY.MM.N` for a second release in the same month.
Each version is a git tag. A copy made with "Use this template" carries no tags, so the version you took is in
`ASSESSMENT_VERSION`. A retired version is no longer sent to new candidates.

## ds-v2026.11

Status: active.

- First Data Scientist take-home: build, experiment with and evaluate a system that summarises company records for a
  team vetting suppliers and partners, then write it up as a case study.
- Data: records for 50 synthetic companies (profile, directors and shareholders, up to three financial years with
  statements and ratios, court cases). People and audit firms have placeholder names (`Director 1`, `Audit Firm 3`).
- README: what to submit and how it's scored up front, a mock of the company page, a flowchart of the pieces, and the
  free-tier limits explained, 6 to 8 hours. Records are as of 31 December 2025. Solutions are in Python.
- Viewer (renders headings, lists and tables in summaries): a small FastAPI backend and one HTML page, run with Docker Compose, that shows each record next to the
  candidate's summaries and compares two versions side by side.
- Models: any free LLM API (the brief links awesome-free-llm-apis); a paid key is the candidate's choice and doesn't
  affect scoring. Candidates may use a sample of the 50 companies.
- Submission: a public copy, linked in a submission form along with the candidate's résumé.
