PYTHON ?= python3

.PHONY: check test-python test-lean build-lean validate-lean-proofs validate-experiment-math validate-bootstrap validate-registries validate-citations validate-pica-mapping validate-pica-normalized validate-pica-atlas validate-theorem-track paper-build

check: validate-bootstrap validate-registries validate-citations validate-pica-mapping validate-pica-normalized validate-pica-atlas validate-theorem-track validate-experiment-math test-python test-lean validate-lean-proofs

test-python:
	$(PYTHON) -m pytest

build-lean:
	lake build

test-lean: build-lean
	lake env lean -DwarningAsError=true tests/lean/MathReview.lean
	lake env lean -DwarningAsError=true tests/lean/Strengthening.lean

validate-lean-proofs: build-lean
	$(PYTHON) scripts/validate_lean_proofs.py

validate-experiment-math:
	$(PYTHON) scripts/validate_experiment_math.py

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
