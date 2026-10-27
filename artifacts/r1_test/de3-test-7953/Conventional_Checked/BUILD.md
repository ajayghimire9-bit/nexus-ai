# de3-test-7953 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "arrival", "backfill_merge": "lww_tombstones", "commit_protocol": "transactional", "dedup": "by_msg_id", "deletes": "soft_and_hard", "fx": "table", "gap_handling": "wait_contiguous", "gold_maintenance": "full_recompute", "lateness": "none", "malformed": "quarantine", "partition_discovery": "static_initial", "schema_handling": "registry_int_cast", "snapshots": "per_tick", "ts_format": "registry_typed", "ts_parse": "text", "txn_isolation": "read_uncommitted"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
