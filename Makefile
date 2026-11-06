# Makefile for cncf-checks

PRIVATEER_CLI_URL  := https://raw.githubusercontent.com/privateerproj/pvtr/main
OSPS_SCANNER_URL   := https://raw.githubusercontent.com/ossf/pvtr-github-repo-scanner/main
DOWNLOAD_DIR       := download
VENV_DIR           := .venv
PYTHON             := python3
TRESTLE_WS         := trestle.ws
COMPDEF_NAME       := privateer
DOCS_DIR           := docs

.PHONY: venv install clean-venv download-privateer-data clean-download trestle-init clean-trestle build-compdef clean-compdef validate-compdef update-readme all clean help

## venv: Create a Python virtual environment and install requirements.txt
venv: $(VENV_DIR)/bin/activate

$(VENV_DIR)/bin/activate: requirements.txt
	$(PYTHON) -m venv $(VENV_DIR)
	$(VENV_DIR)/bin/pip install --upgrade pip
	$(VENV_DIR)/bin/pip install -r requirements.txt
	@touch $(VENV_DIR)/bin/activate
	@echo "Virtual environment ready. Activate with: source $(VENV_DIR)/bin/activate"

## install: Alias for venv
install: venv

## clean-venv: Remove the virtual environment
clean-venv:
	rm -rf $(VENV_DIR)

## download-privateer-data: Download upstream Privateer (pvtr) catalogs into $(DOWNLOAD_DIR)/
download-privateer-data: $(DOWNLOAD_DIR)/capability-catalog.yaml $(DOWNLOAD_DIR)/osps-baseline.yaml
	@echo "All Privateer check files downloaded to $(DOWNLOAD_DIR)/"

$(DOWNLOAD_DIR)/capability-catalog.yaml: | $(DOWNLOAD_DIR)
	@echo "Downloading capability-catalog.yaml from Privateer repository..."
	curl --silent --show-error --fail --location \
		--output $@ \
		$(PRIVATEER_CLI_URL)/.github/capability-catalog.yaml

$(DOWNLOAD_DIR)/osps-baseline.yaml: | $(DOWNLOAD_DIR)
	@echo "Downloading osps-baseline.yaml from OpenSSF scanner repository..."
	curl --silent --show-error --fail --location \
		--output $@ \
		$(OSPS_SCANNER_URL)/data/catalogs/OSPS_Baseline_latest.yaml

$(DOWNLOAD_DIR):
	mkdir -p $(DOWNLOAD_DIR)

## clean-download: Remove downloaded Privateer check files
clean-download:
	rm -rf $(DOWNLOAD_DIR)

## trestle-init: Create trestle.ws workspace directory and initialize it with trestle
trestle-init: venv
	@if [ ! -d "$(TRESTLE_WS)/.trestle" ]; then \
		mkdir -p $(TRESTLE_WS); \
		cd $(TRESTLE_WS) && ../$(VENV_DIR)/bin/trestle init; \
	fi

## clean-trestle: Remove the trestle workspace directory
clean-trestle:
	rm -rf $(TRESTLE_WS)

## build-compdef: Build the privateer OSCAL component definition directly from downloaded raw data
build-compdef: venv download-privateer-data trestle-init
	$(VENV_DIR)/bin/python scripts/build_compdef.py \
		--download-dir $(DOWNLOAD_DIR) \
		--output $(TRESTLE_WS)/component-definitions/$(COMPDEF_NAME)/component-definition.json

## clean-compdef: Remove the generated OSCAL component definition from the trestle workspace
clean-compdef:
	rm -rf $(TRESTLE_WS)/component-definitions/$(COMPDEF_NAME)

## validate-compdef: Validate the OSCAL component definition with trestle
validate-compdef: build-compdef
	cd $(TRESTLE_WS) && ../$(VENV_DIR)/bin/trestle validate --type component-definition --name $(COMPDEF_NAME)

## update-readme: Regenerate the summary chart and table in README.md
update-readme: validate-compdef
	$(VENV_DIR)/bin/python scripts/update_readme.py \
		--readme README.md \
		--compdef $(TRESTLE_WS)/component-definitions/$(COMPDEF_NAME)/component-definition.json \
		--download-dir $(DOWNLOAD_DIR) \
		--chart-out $(DOCS_DIR)/compdef-chart.png

## all: Run all steps — download data, build and validate component definition, update README
all: update-readme

## clean: Remove venv, downloaded data, trestle workspace, and generated artifacts
clean: clean-venv clean-download clean-trestle clean-compdef
	rm -rf $(DOCS_DIR)/compdef-chart.png

## help: Show this help message
help:
	@grep -E '^## ' Makefile | sed 's/^## /  /'

.DEFAULT_GOAL := help
