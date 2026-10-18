"""Run the observation-aware strategy-memory development benchmark."""
from nexus.core.strategy_memory_obs_bench import write_artifact


def main() -> None:
    payload = write_artifact(7)
    d = payload["decision"]
    print("development_success", d["development_success"])
    print("combined_shifted_ff", payload["summary"]["memory_combined"]["shifted"]["first_free_regret"])
    print("persist_shifted_ff", payload["summary"]["persistent_adaptive"]["shifted"]["first_free_regret"])
    print("causal_combined_change", d["causal_combined_choice_changes"])
    print("causal_combined_better", d["causal_combined_better_on_zero"])


if __name__ == "__main__":
    main()
