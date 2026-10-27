# test-7931 (Conventional_NoCheck)

Outcome: COMPLETED_UNVERIFIED

Decisions: {"apply_order": "source_version", "backfill_merge": "lww_tombstones", "commit_protocol": "transactional", "dedup": "by_msg_id", "deletes": "soft_and_hard", "fx": "table", "gold_maintenance": "full_recompute", "lateness": "none", "malformed": "drop_silent", "partition_discovery": "static_initial", "schema_handling": "registry_int_cast", "snapshots": "per_tick", "ts_format": "registry_typed", "ts_parse": "text"}

Checks: [('runs_all_ticks', True)]
