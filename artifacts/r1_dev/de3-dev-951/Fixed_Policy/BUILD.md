# de3-dev-951 (Fixed_Policy)

Decisions: {"apply_order": "source_version", "backfill_merge": "blind_overwrite", "commit_protocol": "transactional", "dedup": "by_msg_id", "deletes": "hard_only", "fx": "none", "gap_handling": "wait_contiguous", "gold_maintenance": "recompute_affected", "lateness": "none", "malformed": "drop_silent", "partition_discovery": "static_initial", "schema_handling": "v1_strict", "snapshots": "none", "ts_format": "iso_only", "ts_parse": "text", "txn_isolation": "read_committed"}

Checks: [('runs_all_ticks', False)]
