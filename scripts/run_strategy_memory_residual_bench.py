"""Run persist vs retrieved-mean on disposable residual decide() scores."""
from nexus.core.strategy_memory_residual_bench import write_artifact


def main() -> None:
    payload = write_artifact(7)
    print("success", payload["decision"]["development_success"])
    print("ranking_shift", payload["decision"]["planner_ranking_shifts_across_tasks"])
    print("stop", payload["decision"]["stop_residual_catalogue_line"])
    for name in ("persistent_adaptive", "memory_combined_retrieved"):
        row = payload["summary"][name]
        print(name, "devFF", round(row["development"]["first_free_regret"], 4), "shFF", round(row["shifted"]["first_free_regret"], 4))


if __name__ == "__main__":
    main()
