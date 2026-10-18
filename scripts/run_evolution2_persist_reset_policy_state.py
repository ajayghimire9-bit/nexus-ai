"""Write the E2.19 policy-state diagnostic. Not science."""
from nexus.evolution2.persist_reset_policy_state import write_artifact


def main() -> None:
    payload = write_artifact()
    decision = payload["decision"]
    print(payload["historical_label_preserved"], decision["verdict"], decision["fresh_budget_upper"])


if __name__ == "__main__":
    main()
