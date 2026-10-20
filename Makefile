PYTHON ?= python3

.PHONY: help seed grounded readout check test-seed audit-seed
help:
	@printf '%s\n' 'seed       Symbolic teaching GUI' 'readout    Frozen neural GUI with learned action scorer' 'check      Verify current documentation and preserved files' 'test-seed  Relevant Seed tests; no scientific experiment reruns' 'audit-seed Verify latest saved action results without inference'

seed:
	$(PYTHON) -I -S scripts/run_learning_lab.py --allow-seed --port 8766

grounded:
	$(PYTHON) scripts/run_seed_grounded_gui.py

readout:
	PYTHONPATH=src $(PYTHON) -m nexus.seed serve --mode readout

check:
	$(PYTHON) -I -S scripts/check_repository.py

test-seed:
	PYTHONPATH=src $(PYTHON) -m pytest tests/test_seed*.py tests/test_repository_layout.py tests/test_learning_lab_sessions.py

audit-seed:
	$(PYTHON) -I -S scripts/verify_seed_surprise_readout.py
