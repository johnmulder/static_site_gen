.PHONY: lint test build format serve clean help

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

lint: ## Run linting and type checks
	ruff check static_site_gen/ tests/
	ruff format --check static_site_gen/ tests/
	mypy static_site_gen/ tests/

format: ## Format code with Ruff
	ruff format static_site_gen/ tests/
	ruff check --fix static_site_gen/ tests/

test: ## Run test suite
	pytest

coverage: ## Run tests with coverage report
	pytest --cov=static_site_gen --cov-report=term-missing

build: ## Build the static site
	python -m static_site_gen build

serve: ## Start local development server
	python -m static_site_gen serve

clean: ## Remove build artifacts and caches
	rm -rf site/ .mypy_cache/ .pytest_cache/ .ruff_cache/ .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
