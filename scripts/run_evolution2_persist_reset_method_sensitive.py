"""Write the E2.20 method-sensitive next-screen lock. Not science."""
from nexus.evolution2.persist_reset_method_sensitive import write_artifact


def main() -> None:
    payload = write_artifact()
    print(payload["historical_label_preserved"], payload["fresh_total_upper"], payload["collection"])


if __name__ == "__main__":
    main()
