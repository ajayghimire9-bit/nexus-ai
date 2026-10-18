"""Source-only diagnostic; no simulator construction or neural training."""
from nexus.evolution2.planner_quality_diagnostic import write_artifact

if __name__ == "__main__":
    p = write_artifact()
    print("complete",p["declared_complete"],"screen",p["screen_pass"])
    for family,rows in p["summary"].items():
        print(family,rows)
