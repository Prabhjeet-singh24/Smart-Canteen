"""SQLite helpers: connection handling and schema creation."""
import sqlite3
from pathlib import Path

from flask import current_app, g

from models import SCHEMA


def connect(path):
    """Open a standalone connection (used by scripts and by get_db)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_schema(conn):
    conn.executescript(SCHEMA)
    conn.commit()
