"""Write the gated persist-versus-reset executor audit. Not science."""
from nexus.evolution2.persist_reset_executor import write_artifact


def main() -> None:
    payload = write_artifact()
    print(payload["status"], payload["runner_readiness"], payload["budget"]["fresh_total"])


if __name__ == "__main__":
    main()
