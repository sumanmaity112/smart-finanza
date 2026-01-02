.PHONY: provision sync run test fix-lint check-lint

# Set up development environment
provision:
	@echo "Creating virtual environment..."
	uv venv
	@echo "Installing dependencies..."
	uv sync

# Install dependencies
sync:
	@echo "Installing dependencies..."
	uv sync

# Run the dashboard
run:
	@if [ -f .env ]; then set -a && . .env && set +a; fi; uv run streamlit run src/main.py

# Run tests with coverage
test:
	uv run pytest

# Auto-format and fix linting issues
fix-lint:
	@echo "Formatting code..."
	uv run ruff format src
	@echo "Fixing linting issues..."
	uv run ruff check --fix src
	@echo "✓ Code formatted and linting issues fixed"

# Check linting without making changes
check-lint:
	uv run ruff check src
