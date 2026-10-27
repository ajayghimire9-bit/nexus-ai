# de3-dev-953 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "arrival", "backfill_merge": "insert_if_absent", "commit_protocol": "offsets_first", "dedup": "none", "deletes": "hard_only", "fx": "table", "gap_handling": "skip", "gold_maintenance": "full_recompute", "lateness": "watermark", "malformed": "quarantine", "partition_discovery": "static_initial", "schema_handling": "registry_typed", "snapshots": "per_tick", "ts_format": "registry_typed", "ts_parse": "utc", "txn_isolation": "read_uncommitted"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
