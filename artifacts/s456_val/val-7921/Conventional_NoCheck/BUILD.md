# val-7921 (Conventional_NoCheck)

Outcome: COMPLETED_UNVERIFIED

Decisions: {"apply_order": "arrival", "backfill_merge": "insert_if_absent", "commit_protocol": "transactional", "dedup": "by_msg_id", "deletes": "soft_and_hard", "fx": "table", "gold_maintenance": "full_recompute", "lateness": "watermark", "malformed": "drop_silent", "partition_discovery": "dynamic", "schema_handling": "registry_typed", "snapshots": "per_tick", "ts_format": "registry_typed", "ts_parse": "utc"}

Checks: [('runs_all_ticks', True)]
