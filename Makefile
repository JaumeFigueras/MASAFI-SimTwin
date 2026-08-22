# Makefile for MASAFI-SimTwin
#
# Run `make` or `make help` to see the available targets.

VENV          := .venv
PYTHON        := $(VENV)/bin/python
PIP           := $(VENV)/bin/pip
PYTEST        := $(VENV)/bin/pytest

SRC_DIR       := src
TEST_DIR      := test
DOCS_DIR      := docs
DOCS_BUILD    := $(DOCS_DIR)/build
COVERAGE_DIR  := $(TEST_DIR)/coverage_reports

.DEFAULT_GOAL := help

# ----------------------------------------------------------------------------
# Help
# ----------------------------------------------------------------------------

.PHONY: help
help:  ## Show this help
	@echo "MASAFI-SimTwin — available targets:"
	@echo
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
	@echo

# ----------------------------------------------------------------------------
# Environment
# ----------------------------------------------------------------------------

.PHONY: venv
venv:  ## Create the virtualenv if it does not exist
	@test -d $(VENV) || python3 -m venv $(VENV)

.PHONY: install
install: venv  ## Install the dependencies from requirements.txt
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

# ----------------------------------------------------------------------------
# Application
# ----------------------------------------------------------------------------

.PHONY: run
run:  ## Launch the application
	PYTHONPATH=$(SRC_DIR) $(PYTHON) -m masafi_simtwin

# ----------------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------------

.PHONY: test
test:  ## Run all tests, fast (no coverage)
	QT_QPA_PLATFORM=offscreen $(PYTEST) $(TEST_DIR) -q

.PHONY: test-full
test-full:  ## Run all tests with coverage; reports in test/coverage_reports
	@mkdir -p $(COVERAGE_DIR)
	QT_QPA_PLATFORM=offscreen $(PYTEST) $(TEST_DIR) \
		--cov=$(SRC_DIR) \
		--cov-report=term-missing \
		--cov-report=html:$(COVERAGE_DIR)/html \
		--cov-report=xml:$(COVERAGE_DIR)/coverage.xml
	@echo
	@echo "HTML coverage report: $(COVERAGE_DIR)/html/index.html"

.PHONY: test-one
test-one:  ## Run a single test, e.g. make test-one T=test/foo_test.py::test_bar
	@test -n "$(T)" || { echo "Usage: make test-one T=<test path or node id>"; exit 2; }
	QT_QPA_PLATFORM=offscreen $(PYTEST) $(T) -q

# ----------------------------------------------------------------------------
# Documentation
# ----------------------------------------------------------------------------

.PHONY: docs
docs:  ## Build the HTML documentation
	@PATH="$(CURDIR)/$(VENV)/bin:$$PATH" $(MAKE) -C $(DOCS_DIR) html
	@echo
	@echo "Documentation: $(DOCS_BUILD)/html/index.html"

.PHONY: docs-strict
docs-strict:  ## Build the docs treating warnings as errors
	@PATH="$(CURDIR)/$(VENV)/bin:$$PATH" $(MAKE) -C $(DOCS_DIR) html SPHINXOPTS="-W"

.PHONY: docs-clean
docs-clean:  ## Remove the built documentation
	@PATH="$(CURDIR)/$(VENV)/bin:$$PATH" $(MAKE) -C $(DOCS_DIR) clean

# ----------------------------------------------------------------------------
# Housekeeping
# ----------------------------------------------------------------------------

.PHONY: clean
clean: docs-clean  ## Remove build artefacts, caches and coverage reports
	rm -rf $(COVERAGE_DIR) .coverage .coverage.* .pytest_cache
	find . -path ./$(VENV) -prune -o -type d -name '__pycache__' -exec rm -rf {} +
