"""Write the independent four-role assignment audit. Not science."""
from nexus.evolution2.persist_reset_roles import write_artifact


def main() -> None:
    payload = write_artifact()
    print(payload["status"], payload["historical_exclusion_clean"], payload["h17"])


if __name__ == "__main__":
    main()
