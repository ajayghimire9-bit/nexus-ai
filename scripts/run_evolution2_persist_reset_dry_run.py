"""Development-only persist-versus-reset dry-run entry. Not scientific dispatch."""
from __future__ import annotations

from nexus.evolution2.persist_reset_dry_run import run_development_dry_run


def main() -> None:
    payload = run_development_dry_run()
    print(payload["status"], payload["dry_run"], payload["scientific_execution"])


if __name__ == "__main__":
    main()
