from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    original_filename TEXT NOT NULL,
    original_ext TEXT NOT NULL,
    has_pdf INTEGER NOT NULL DEFAULT 0,
    has_thumbnail INTEGER NOT NULL DEFAULT 0,
    layer_names TEXT NOT NULL DEFAULT '[]',
    shape_count INTEGER,
    canvas_w_mm REAL,
    canvas_h_mm REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def get_connection(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
