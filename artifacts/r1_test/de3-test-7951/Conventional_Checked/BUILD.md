# de3-test-7951 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "source_version", "backfill_merge": "insert_if_absent", "commit_protocol": "transactional", "dedup": "by_msg_id", "deletes": "hard_only", "fx": "none", "gap_handling": "wait_contiguous", "gold_maintenance": "delta_no_retract", "lateness": "watermark", "malformed": "quarantine", "partition_discovery": "static_initial", "schema_handling": "registry_typed", "snapshots": "none", "ts_format": "registry_typed", "ts_parse": "utc", "txn_isolation": "read_committed"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
