"""Postgres connection + schema.

Everything -- metadata and the actual file bytes (original pattern, PDF,
thumbnail) -- lives in this one database. That's deliberate: a free
Postgres host like Neon keeps your data safe independently of whatever
happens to the app server's own disk (which on a free hosting plan can
be wiped on redeploy), the same way the other apps built for this GitHub
account (Home Kitchen, the tax assistant, the gardening app) all keep
their data in a database rather than on the server's local disk.
"""

from __future__ import annotations

import psycopg
from psycopg.rows import dict_row

SCHEMA = """
CREATE TABLE IF NOT EXISTS patterns (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    original_filename TEXT NOT NULL,
    original_ext TEXT NOT NULL,
    original_bytes BYTEA NOT NULL,
    pdf_bytes BYTEA,
    thumbnail_bytes BYTEA,
    layer_names TEXT NOT NULL DEFAULT '[]',
    shape_count INTEGER,
    canvas_w_mm REAL,
    canvas_h_mm REAL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def get_connection(database_url: str) -> psycopg.Connection:
    conn = psycopg.connect(database_url, row_factory=dict_row, autocommit=False)
    return conn


def init_db(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA)
    conn.commit()
