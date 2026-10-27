# de3-dev-954 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "source_version", "backfill_merge": "insert_if_absent", "commit_protocol": "offsets_first", "dedup": "none", "deletes": "soft_and_hard", "fx": "table", "gap_handling": "wait_contiguous", "gold_maintenance": "full_recompute", "lateness": "watermark", "malformed": "quarantine", "partition_discovery": "static_initial", "schema_handling": "registry_typed", "snapshots": "per_tick", "ts_format": "registry_typed", "ts_parse": "utc", "txn_isolation": "read_committed"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
