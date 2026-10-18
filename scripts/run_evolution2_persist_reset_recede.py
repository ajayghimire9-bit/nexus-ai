"""Receding stored-obs clock. env_cap=0. Not science."""
from __future__ import annotations

from nexus.evolution2.persist_reset_recede import write_artifact


def main() -> None:
    payload = write_artifact()
    recede = payload["recede"]
    print(
        recede["n_decisions"],
        recede["wall_s"],
        recede["screen_9600_prior_s"],
        payload["granted_7680"],
        recede["twelve_arm_scientific"],
    )


if __name__ == "__main__":
    main()
