"""Run the ContextualStrategyMemory development benchmark. Not science."""
from nexus.core.strategy_memory_bench import write_artifact


def main() -> None:
    payload = write_artifact(7)
    s = payload["summary"]
    print("memory_dev_regret", round(s["contextual_strategy_memory"]["dev_regret"], 4))
    print("persist_dev_regret", round(s["persistent_adaptive"]["dev_regret"], 4))
    print("causal", payload["causal_memory_changes_choice"]["changed"])
    print("neg_transfer", round(payload["negative_transfer_shifted_memory_minus_ablated_regret"], 4))


if __name__ == "__main__":
    main()
