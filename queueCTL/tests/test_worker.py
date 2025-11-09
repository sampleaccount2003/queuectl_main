import os
import sqlite3
from click.testing import CliRunner
import time

DB = os.getenv('QUEUECTL_DB', os.path.join(os.path.dirname(__file__), '..', 'queuectl.db'))

def setup_db_with_pending(tmp_path, monkeypatch):
    db_path = tmp_path / "queuectl.db"
    monkeypatch.setenv('QUEUECTL_DB', str(db_path))
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute('PRAGMA journal_mode=WAL;')
    cur.execute('''CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY, command TEXT NOT NULL, state TEXT NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0, max_retries INTEGER NOT NULL DEFAULT 3,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL, last_error TEXT, next_run_at TEXT
    )''')
    now = '2025-11-04T10:30:00Z'
    cur.execute("INSERT INTO jobs(id,command,state,attempts,max_retries,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                ('job_ok','echo hi','pending',0,1,now,now))
    conn.commit()
    conn.close()
    return db_path

def test_worker_picks_job(tmp_path, monkeypatch):
    db_path = setup_db_with_pending(tmp_path, monkeypatch)
    from queuectl.worker import pick_job_and_lock, get_conn
    conn = get_conn()
    job = pick_job_and_lock(conn)
    assert job is not None
    # after picking, job state should be processing
    cur = conn.cursor()
    cur.execute("SELECT state FROM jobs WHERE id='job_ok'")
    assert cur.fetchone()[0] == 'processing'
    conn.close()
