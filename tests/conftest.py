"""Session-wide blind-vault audit hook (AGENTS.md Wave 26 RULE 1)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nexus.standing_gates import install_vault_audit_hook  # noqa: E402

install_vault_audit_hook(log_path=os.environ.get("NEXUS_VAULT_AUDIT_LOG"))
