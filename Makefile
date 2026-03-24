PYTHON ?= python3

.PHONY: check test-python build-lean validate-bootstrap validate-registries validate-citations validate-pica-mapping validate-pica-normalized validate-pica-atlas validate-theorem-track paper-build

check: validate-bootstrap validate-registries validate-citations validate-pica-mapping validate-pica-normalized validate-pica-atlas validate-theorem-track test-python build-lean

test-python:
	$(PYTHON) -m pytest

build-lean:
	lake build

validate-bootstrap:
	$(PYTHON) scripts/validate_bootstrap.py

validate-registries:
	$(PYTHON) scripts/validate_registries.py

validate-citations:
	$(PYTHON) scripts/validate_citations.py

validate-pica-mapping:
	$(PYTHON) scripts/validate_pica_mapping.py

validate-pica-normalized:
	$(PYTHON) scripts/validate_pica_normalized.py

validate-pica-atlas:
	$(PYTHON) scripts/validate_pica_atlas.py

validate-theorem-track:
	$(PYTHON) scripts/validate_theorem_track.py

paper-build:
	$(PYTHON) scripts/build_paper.py
