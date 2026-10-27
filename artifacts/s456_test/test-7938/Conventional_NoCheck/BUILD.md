# test-7938 (Conventional_NoCheck)

Outcome: COMPLETED_UNVERIFIED

Decisions: {"apply_order": "source_version", "backfill_merge": "lww_tombstones", "commit_protocol": "transactional", "dedup": "by_msg_id", "deletes": "hard_only", "fx": "table", "gold_maintenance": "recompute_affected", "lateness": "processing_time", "malformed": "quarantine", "partition_discovery": "static_initial", "schema_handling": "registry_int_cast", "snapshots": "none", "ts_format": "registry_typed", "ts_parse": "utc"}

Checks: [('runs_all_ticks', True)]
