"""Write the persist-versus-reset pre-authorization report. Not science."""
from __future__ import annotations

from nexus.evolution2.persist_reset_planner_audit import audit_real_planner
from nexus.evolution2.persist_reset_readiness import write_artifact


def main() -> None:
    payload = write_artifact()
    planner = audit_real_planner()
    print(
        payload["readiness"]["scientific_execution_readiness"],
        payload["worksheet"]["fresh_total_environment_steps"],
        planner["status"],
        planner["scientific_dispatch"],
    )


if __name__ == "__main__":
    main()
