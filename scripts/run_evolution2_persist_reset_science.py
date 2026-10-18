"""Record or execute the one-run persist-versus-reset grant. No automatic retry."""
from __future__ import annotations

import argparse

from nexus.evolution2 import persist_reset_grant as grant
from nexus.evolution2 import persist_reset_science as science


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record-grant-only", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.record_grant_only == args.execute:
        raise SystemExit("choose exactly one of --record-grant-only or --execute")
    if args.record_grant_only:
        payload = science.write_protocol_artifact(grant.HUMAN_APPROVAL)
        print(payload["grant_unused"], payload["grant"]["source_commit"], payload["preflight"]["status"])
        return
    payload = science.run_authorized(grant.HUMAN_APPROVAL)
    print(payload.get("status"), payload.get("primary_label"), payload.get("env_steps"))


if __name__ == "__main__":
    main()
