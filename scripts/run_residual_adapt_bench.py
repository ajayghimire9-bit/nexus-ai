"""Run residual selection / adaptation development benchmark."""
from nexus.core.residual_adapt_bench import write_artifact


def main() -> None:
    payload = write_artifact(7)
    print("success", payload["decision"]["development_success"])
    print("causal", payload["causal"])
    for name, row in payload["summary"].items():
        print(name, "dev_regret", round(row["development"]["regret"], 5), "arms", row["development"]["arms"])


if __name__ == "__main__":
    main()
