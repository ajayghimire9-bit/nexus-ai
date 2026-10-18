"""Run the decide()-owned ContextualStrategyMemory development benchmark."""
from nexus.core.strategy_memory_decide_bench import write_artifact


def main() -> None:
    payload = write_artifact(7)
    s = payload["summary"]
    print("free_slots", payload["free_slots"])
    print("memory_dev_regret", round(s["contextual_strategy_memory"]["dev_regret"], 4))
    print("persist_dev_regret", round(s["persistent_adaptive"]["dev_regret"], 4))
    print("causal", payload["causal_memory_changes_choice"]["changed"])
    print("collision_neg", round(payload["negative_transfer_collision_memory_minus_ablated_regret"], 4))
    print("improves_dev", payload["memory_improves_dev_selection"])


if __name__ == "__main__":
    main()
