# test-7933 (Conventional_NoCheck)

Outcome: COMPLETED_UNVERIFIED

Decisions: {"apply_order": "source_version", "backfill_merge": "lww_tombstones", "commit_protocol": "transactional", "dedup": "by_msg_id", "deletes": "soft_and_hard", "fx": "none", "gold_maintenance": "recompute_affected", "lateness": "none", "malformed": "quarantine", "partition_discovery": "dynamic", "schema_handling": "registry_typed", "snapshots": "per_tick", "ts_format": "registry_typed", "ts_parse": "text"}

Checks: [('runs_all_ticks', True)]
