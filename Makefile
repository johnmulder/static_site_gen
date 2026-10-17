.PHONY: check lint test coverage hooks check-package release-check build format serve clean help

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

lint: ## Run linting and type checks
	ruff check .
	ruff format --check .
	mypy static_site_gen/ tests/ scripts/

check: lint test hooks check-package ## Run all merge acceptance checks without prompts

format: ## Format code with Ruff
	ruff format static_site_gen/ tests/
	ruff check --fix static_site_gen/ tests/

test: ## Run test suite
	pytest --cov-fail-under=95

coverage: test ## Run tests with coverage report and the CI coverage floor

hooks: ## Check all tracked files with pre-commit
	pre-commit run --all-files

check-package: ## Build and exercise isolated wheel and sdist installations
	@artifact_dir=$$(mktemp -d) || exit 1; \
	trap 'rm -rf "$$artifact_dir"' EXIT; \
	python -m build --outdir "$$artifact_dir" && \
	python -m twine check --strict "$$artifact_dir"/*.whl "$$artifact_dir"/*.tar.gz && \
	python scripts/check_installed_artifacts.py "$$artifact_dir"/*.whl "$$artifact_dir"/*.tar.gz && \
	python scripts/check_source_distribution.py "$$artifact_dir"/*.tar.gz

release-check: ## Retain a verified alpha bundle from the current clean commit
	python scripts/release.py check

build: ## Build the static site
	python -m static_site_gen build

serve: ## Start local development server
	python -m static_site_gen serve

clean: ## Remove build artifacts and caches
	rm -rf site/ .mypy_cache/ .pytest_cache/ .ruff_cache/ .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
