"""Database access for the inventory system."""

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(db_path):
    """Open the database with foreign keys on and rows readable by column name."""
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    # SQLite ignores foreign keys unless this is switched on for every connection.
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_schema(connection):
    """Create any missing tables and indexes. Running it again keeps the data."""
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))