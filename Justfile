set shell := ["bash", "-euo", "pipefail", "-c"]

default: setup

# Install the dependencies on your machine (add your own with `uv add`).
setup:
    uv sync --locked

# Start the viewer at http://localhost:${APP_PORT:-8000}, and wait until it's up.
up:
    docker compose up -d --wait
    @echo "Viewer: http://localhost:${APP_PORT:-8000}"

# Stop the viewer.
down:
    docker compose down -v

# Check the viewer's code (app/) with Ruff and Pyrefly.
lint:
    uv run ruff check
    uv run ruff format --check
    uv run pyrefly check

# --- My solution (see CASE_STUDY.md) ---

# Run the evaluator's tests.
test:
    uv run pytest -q summariser

# v0: template summaries from facts, no model.
baseline:
    uv run python -m summariser.baseline

# Generate an LLM version (v1-raw or v2-grounded). Needs LLM_BASE_URL, LLM_API_KEY, LLM_MODEL.
generate version *args:
    uv run python -m summariser.generate {{version}} {{args}}

# Score one or more summary files, e.g. `just evaluate summaries/v1-raw.jsonl summaries/v2-grounded.jsonl`.
evaluate *files:
    uv run python -m summariser.evaluate {{files}}

# Blind side-by-side review of two versions (then `just unblind`).
review a b:
    uv run python -m summariser.blind_review {{a}} {{b}}

unblind:
    uv run python -m summariser.blind_review --unblind
