"""Run persist vs persist+obs vs retrieved-mean development benchmark."""
from nexus.core.strategy_memory_persist_obs_bench import write_artifact


def main() -> None:
    payload = write_artifact(7)
    print("persist_obs_helps", payload["decision"]["persist_obs_helps"])
    print("stop_fakestep_line", payload["decision"]["stop_fakestep_line"])
    for name in ("persistent_adaptive", "persistent_adaptive_obs", "memory_combined_retrieved"):
        row = payload["summary"][name]
        print(name, "devFF", round(row["development"]["first_free_regret"], 4), "shFF", round(row["shifted"]["first_free_regret"], 4))


if __name__ == "__main__":
    main()
