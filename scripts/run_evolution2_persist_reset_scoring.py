"""Write the E2.21 executable-scoring correction. Not science."""
from nexus.evolution2.persist_reset_scoring import write_artifact


def main() -> None:
    payload = write_artifact()
    print(payload["decision"]["verdict"], payload["decision"]["env_cap"], payload["collection"])


if __name__ == "__main__":
    main()
