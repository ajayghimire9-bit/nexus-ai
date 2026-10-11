from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ExperimentRecord:
    id: str
    created_at: str
    env_id: str
    generation: int
    architecture: dict[str, Any]
    train_config: dict[str, Any]
    mean_return: float
    std_return: float
    timesteps: int
    seed: int
    status: str
    notes: str


class ExperimentStore:
    """SQLite memory of trained-and-evaluated experiments."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._init()

    def _init(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                env_id TEXT NOT NULL,
                generation INTEGER NOT NULL,
                architecture_json TEXT NOT NULL,
                train_config_json TEXT NOT NULL,
                mean_return REAL NOT NULL,
                std_return REAL NOT NULL,
                timesteps INTEGER NOT NULL,
                seed INTEGER NOT NULL,
                status TEXT NOT NULL,
                notes TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def add(
        self,
        *,
        env_id: str,
        generation: int,
        architecture: dict[str, Any],
        train_config: dict[str, Any],
        mean_return: float,
        std_return: float,
        timesteps: int,
        seed: int,
        status: str = "evaluated",
        notes: str = "",
    ) -> ExperimentRecord:
        record = ExperimentRecord(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            env_id=env_id,
            generation=generation,
            architecture=architecture,
            train_config=train_config,
            mean_return=mean_return,
            std_return=std_return,
            timesteps=timesteps,
            seed=seed,
            status=status,
            notes=notes,
        )
        self._conn.execute(
            """
            INSERT INTO experiments (
                id, created_at, env_id, generation, architecture_json,
                train_config_json, mean_return, std_return, timesteps, seed, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.created_at,
                record.env_id,
                record.generation,
                json.dumps(record.architecture),
                json.dumps(record.train_config),
                record.mean_return,
                record.std_return,
                record.timesteps,
                record.seed,
                record.status,
                record.notes,
            ),
        )
        self._conn.commit()
        return record

    def top(self, n: int = 5) -> list[ExperimentRecord]:
        rows = self._conn.execute(
            "SELECT * FROM experiments ORDER BY mean_return DESC LIMIT ?", (n,)
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def all(self) -> list[ExperimentRecord]:
        rows = self._conn.execute("SELECT * FROM experiments ORDER BY created_at ASC").fetchall()
        return [self._row_to_record(r) for r in rows]

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ExperimentRecord:
        return ExperimentRecord(
            id=row["id"],
            created_at=row["created_at"],
            env_id=row["env_id"],
            generation=int(row["generation"]),
            architecture=json.loads(row["architecture_json"]),
            train_config=json.loads(row["train_config_json"]),
            mean_return=float(row["mean_return"]),
            std_return=float(row["std_return"]),
            timesteps=int(row["timesteps"]),
            seed=int(row["seed"]),
            status=row["status"],
            notes=row["notes"],
        )
