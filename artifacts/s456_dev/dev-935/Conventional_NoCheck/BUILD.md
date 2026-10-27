# dev-935 (Conventional_NoCheck)

Outcome: COMPLETED_UNVERIFIED

Decisions: {"apply_order": "arrival", "backfill_merge": "insert_if_absent", "commit_protocol": "sink_then_offsets", "dedup": "by_msg_id", "deletes": "soft_and_hard", "fx": "table", "gold_maintenance": "full_recompute", "lateness": "none", "malformed": "quarantine", "partition_discovery": "dynamic", "schema_handling": "registry_typed", "snapshots": "none", "ts_format": "registry_typed", "ts_parse": "text"}

Checks: [('runs_all_ticks', True)]
