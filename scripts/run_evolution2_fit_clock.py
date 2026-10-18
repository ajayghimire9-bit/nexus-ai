"""Gated residual-MLP fit-clock entry. Refuses unauthorized caps."""
from __future__ import annotations

import argparse

from nexus.evolution2 import fit_clock as lock


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-cap", type=int, required=True)
    parser.add_argument("--n-fits", type=int, default=lock.N_FITS)
    args = parser.parse_args(argv)
    lock.dispatch(args.env_cap, args.n_fits)


if __name__ == "__main__":
    main()
