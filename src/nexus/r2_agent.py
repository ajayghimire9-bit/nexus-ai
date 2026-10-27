"""R2 build agents (NOT LOCKED). The R1 agent code (r1_agent, unchanged) is loaded as a SEPARATE module and rebound to the
R2 template (18 decisions); every arm keeps the Stage 4 proposer, localisation and caps, the R1 suite (r1_checks: Stage 4
checks + replay_conformance + ack_durability + chunk_invariance over grow_obs), scoped evidence and outcome labels.
Fixed_Policy keeps R1's src-majority options and its full-suite check (no repair search)."""
from __future__ import annotations

import importlib.util

from nexus import r1_agent as _R1A
from nexus import r2_template as RT2

_spec = importlib.util.spec_from_file_location("nexus._r2_agent_core", _R1A.__file__)
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)
M.RT = RT2
M.A.T = RT2
build = M.build
