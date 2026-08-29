# Makefile for MASAFI-SimTwin
#
# Run `make` or `make help` to see the available targets.

VENV          := .venv
PYTHON        := $(VENV)/bin/python
PIP           := $(VENV)/bin/pip
PYTEST        := $(VENV)/bin/pytest

SRC_DIR       := src
TEST_DIR      := test
TOOLS_DIR     := tools
TS_DIR        := $(SRC_DIR)/masafi_simtwin/translations
LINGUIST      := $(shell command -v linguist 2>/dev/null || echo /usr/lib/qt6/bin/linguist)
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
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
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

# PYTHONFAULTHANDLER makes the interpreter print the Python stack it died on
# when it is killed by a fatal signal.  A crash inside Qt — a signal delivered
# to an object whose C++ side has gone, most often — leaves nothing behind
# otherwise: no traceback, no exception, just "Segmentation fault".
.PHONY: run
run:  ## Launch the application
	PYTHONFAULTHANDLER=1 PYTHONPATH=$(SRC_DIR) $(PYTHON) -m masafi_simtwin

# ----------------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------------

.PHONY: test
test:  ## Run the application tests, fast (no coverage)
	QT_QPA_PLATFORM=offscreen $(PYTEST) $(TEST_DIR) -q -m "not i18n"

.PHONY: test-i18n
test-i18n:  ## Check the translation catalogues on their own
	QT_QPA_PLATFORM=offscreen $(PYTEST) $(TEST_DIR) -q -m i18n

.PHONY: test-all
test-all: test test-i18n  ## Run the application tests and the translation checks

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
# Forms
# ----------------------------------------------------------------------------

.PHONY: ui
ui:  ## Compile the Qt Designer forms into their ui_*.py modules
	$(PYTHON) $(TOOLS_DIR)/build_forms.py

.PHONY: ui-check
ui-check:  ## Fail when a form has been saved without running `make ui`
	$(PYTHON) $(TOOLS_DIR)/build_forms.py --check

.PHONY: designer
designer:  ## Open a form in Qt Designer, e.g. make designer F=about
	@test -n "$(F)" || { echo "Usage: make designer F=<form>"; exit 2; }
	$(PYTHON) $(TOOLS_DIR)/build_forms.py --designer $(F)

# ----------------------------------------------------------------------------
# Translations
# ----------------------------------------------------------------------------

.PHONY: translations
translations: ts qm  ## Extract the strings and compile the catalogues

.PHONY: ts
ts:  ## Update the .ts catalogues from the sources
	$(PYTHON) $(TOOLS_DIR)/update_translations.py --update

.PHONY: qm
qm:  ## Compile the .ts catalogues into the .qm the application loads
	$(PYTHON) $(TOOLS_DIR)/update_translations.py --release

.PHONY: linguist
linguist:  ## Open a catalogue in Qt Linguist, e.g. make linguist L=ca
	@test -n "$(L)" || { echo "Usage: make linguist L=<language>"; exit 2; }
	$(LINGUIST) $(TS_DIR)/masafi_simtwin_$(L).ts &

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
