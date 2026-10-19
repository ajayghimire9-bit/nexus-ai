PYTHON ?= python3

.PHONY: help seed grounded check test-seed audit-seed
help:
	@printf '%s\n' 'seed       Open the bounded local Seed server' 'check      Verify active documentation and source paths' 'test-seed  Run source/authored-fixture tests (pytest required)' 'audit-seed Verify the incomplete saved prefix; no comparison rerun'

seed:
	$(PYTHON) -I -S scripts/run_learning_lab.py --allow-seed --port 8766

grounded:
	$(PYTHON) scripts/run_seed_grounded_gui.py

check:
	$(PYTHON) -I -S scripts/check_repository.py

test-seed:
	PYTHONPATH=src $(PYTHON) -m pytest tests/test_seed.py tests/test_repository_layout.py

audit-seed:
	$(PYTHON) -I -S scripts/verify_seed_comparison.py --allow-partial
