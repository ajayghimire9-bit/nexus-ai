"""Run the E2.22 observation-conditioned memory development screen."""
from nexus.evolution2.observation_memory_bench import write_artifact


def main() -> None:
    payload = write_artifact(7)
    decision = payload["decision"]
    print("success", decision["development_success"])
    print("causal", payload["causal_observation_only"])
    for name, row in payload["summary"].items():
        print(
            name,
            "dev_ff",
            round(row["dev_first_free_regret"], 4),
            "shift_ff",
            round(row["shifted_first_free_regret"], 4),
            "dev_retr",
            row["dev_retrieves"],
            "shift_fb",
            row["shifted_fallbacks"],
        )


if __name__ == "__main__":
    main()
