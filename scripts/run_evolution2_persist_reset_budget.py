"""Lock the persist-versus-reset resource budget. env_cap=0. Not science."""
from __future__ import annotations

from nexus.evolution2.persist_reset_path import run_budget_verification


def main() -> None:
    payload = run_budget_verification()
    budget = payload["budget"]["real_environment"]
    print(
        budget["fresh_total"],
        payload["execution_path"]["status"],
        payload["readiness"]["scientific_execution_readiness"],
        "granted_7680=", payload["granted_7680"],
    )


if __name__ == "__main__":
    main()
