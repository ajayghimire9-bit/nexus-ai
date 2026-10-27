# de3-val-7947 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "arrival", "backfill_merge": "insert_if_absent", "commit_protocol": "sink_then_offsets", "dedup": "by_msg_id", "deletes": "soft_and_hard", "fx": "none", "gap_handling": "skip", "gold_maintenance": "full_recompute", "lateness": "none", "malformed": "drop_silent", "partition_discovery": "static_initial", "schema_handling": "v1_lenient", "snapshots": "per_tick", "ts_format": "registry_typed", "ts_parse": "text", "txn_isolation": "read_committed"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
