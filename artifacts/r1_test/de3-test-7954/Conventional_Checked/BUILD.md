# de3-test-7954 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "arrival", "backfill_merge": "blind_overwrite", "commit_protocol": "transactional", "dedup": "none", "deletes": "soft_and_hard", "fx": "table", "gap_handling": "skip", "gold_maintenance": "recompute_affected", "lateness": "processing_time", "malformed": "drop_silent", "partition_discovery": "dynamic", "schema_handling": "registry_typed", "snapshots": "none", "ts_format": "registry_typed", "ts_parse": "utc", "txn_isolation": "read_uncommitted"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
