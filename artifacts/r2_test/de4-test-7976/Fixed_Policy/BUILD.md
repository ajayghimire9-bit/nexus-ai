# de4-test-7976 (Fixed_Policy)

Decisions: {"apply_order": "source_version", "backfill_merge": "lww_tombstones", "commit_protocol": "sink_then_offsets", "dedup": "by_msg_id", "deletes": "soft_and_hard", "discount_unit": "registry_unit", "fx": "table", "fx_unknown": "error", "gap_handling": "skip", "gold_maintenance": "full_recompute", "lateness": "processing_time", "malformed": "quarantine", "partition_discovery": "dynamic", "schema_handling": "registry_typed", "snapshots": "per_tick", "ts_format": "registry_typed", "ts_parse": "utc", "txn_isolation": "read_uncommitted"}

Checks: [('runs_all_ticks', False)]
