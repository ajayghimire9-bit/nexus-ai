"""Run the E2.23 cross-bundle calibration development screen."""
from nexus.evolution2.observation_memory_cross_bench import write_artifact


def main() -> None:
    payload = write_artifact(7)
    cal = payload["calibration_cross"]
    print("gate", round(cal["gate_threshold"], 4), "recall", cal["recall_at_cross_gate"], "within_recall", cal["recall_at_within_gate"])
    print("false_accept", {k: cal[k] for k in ("false_accept_far", "false_accept_zero", "false_accept_shuffled")})
    print("success", payload["decision"]["development_success"])
    for name, row in payload["summary"].items():
        print(name, "dev_ff", round(row["dev_first_free_regret"], 4), "dev_retr", row["dev_retrieves"], "shift_ff", round(row["shifted_first_free_regret"], 4))


if __name__ == "__main__":
    main()
