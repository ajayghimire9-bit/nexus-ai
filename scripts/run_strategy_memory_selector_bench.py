"""Run the retrieved-mean / gated strategy-memory development benchmark."""
from nexus.core.strategy_memory_selector_bench import write_artifact


def main() -> None:
    payload = write_artifact(7)
    print("success", payload["development_success"], payload["successful_selector"])
    for name in ("persistent_adaptive", "memory_combined_ucb", "memory_combined_retrieved", "memory_combined_gated"):
        row = payload["summary"][name]
        print(
            name,
            "devFF",
            round(row["development"]["first_free_regret"], 4),
            "shFF",
            round(row["shifted"]["first_free_regret"], 4),
        )


if __name__ == "__main__":
    main()
