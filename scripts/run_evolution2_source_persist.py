"""Gated source-array persist entry. Refuses while unauthorized."""
from __future__ import annotations

import argparse

from nexus.evolution2 import source_persist_request as lock


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-cap", type=int, required=True)
    args = parser.parse_args(argv)
    lock.dispatch(args.env_cap)


if __name__ == "__main__":
    main()
