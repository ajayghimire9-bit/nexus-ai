# dev-936 (Conventional_Checked)

Outcome: COMPLETED_CHECKED

Decisions: {"apply_order": "source_version", "backfill_merge": "insert_if_absent", "commit_protocol": "sink_then_offsets", "dedup": "none", "deletes": "soft_and_hard", "fx": "table", "gold_maintenance": "full_recompute", "lateness": "watermark", "malformed": "drop_silent", "partition_discovery": "static_initial", "schema_handling": "registry_typed", "snapshots": "none", "ts_format": "iso_only", "ts_parse": "text"}

Checks: [('runs_all_ticks', True), ('schema_keys_not_null', True), ('rerun_unchanged', True), ('nonempty_outputs', True)]
