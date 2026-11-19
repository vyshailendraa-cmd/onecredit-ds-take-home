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
