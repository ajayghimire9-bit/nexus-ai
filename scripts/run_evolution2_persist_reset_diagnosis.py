"""Write the E2.17 methodological diagnosis. Not science."""
from nexus.evolution2.persist_reset_diagnosis import write_artifact


def main() -> None:
    payload = write_artifact()
    print(payload["historical_label_preserved"], payload["proposer_choices"]["persist_reset_differed_in_any_bundle"])


if __name__ == "__main__":
    main()
