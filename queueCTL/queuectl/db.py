import sqlite3
import os
from .utils import now_iso


DB_PATH = os.getenv("QUEUECTL_DB", "queuectl.db")


def get_conn():
    # isolation_level=None => autocommit mode disabled; we'll use explicit transactions
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    command TEXT NOT NULL,
    state TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_error TEXT,
    next_run_at TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
    )
    """)
    # defaults
    set_config(conn, "max_retries", "3")
    set_config(conn, "backoff_base", "2")
    set_config(conn, "stop_workers", "false")
    conn.commit()
    conn.close()


def set_config(conn, key, value):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO config(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )
    conn.commit()


def get_config(conn, key, default=None):
    cur = conn.cursor()
    cur.execute("SELECT value FROM config WHERE key=?", (key,))
    r = cur.fetchone()
    return r[0] if r else default
