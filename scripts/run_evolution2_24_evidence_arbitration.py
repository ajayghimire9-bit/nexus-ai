"""Recorded-source E2.24 development proxy audit, no simulator collection."""
from nexus.evolution2.evidence_arbitration_bench import write_artifact

if __name__ == "__main__":
    result = write_artifact()
    print("complete", result["declared_complete"])
    for name, phases in result.get("summary", {}).items():
        print(name, {p: round(r["first_free_regret"],6) for p,r in phases.items()})
