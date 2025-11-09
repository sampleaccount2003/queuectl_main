import os
import sqlite3
from click.testing import CliRunner
import pytest

DB = os.getenv('QUEUECTL_DB', os.path.join(os.path.dirname(__file__), '..', 'queuectl.db'))

def setup_db_with_dead(tmp_path, monkeypatch):
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
    cur.execute("INSERT INTO jobs(id,command,state,attempts,max_retries,created_at,updated_at,last_error) VALUES (?,?,?,?,?,?,?,?)",
                ('dead1','/bin/false','dead',3,3,now,now,'failed too many times'))
    conn.commit()
    conn.close()
    return db_path

def test_dlq_retry(tmp_path, monkeypatch):
    db_path = setup_db_with_dead(tmp_path, monkeypatch)
    from queuectl.cli import cli
    runner = CliRunner()
    # list should show the dead job
    res = runner.invoke(cli, ['dlq', 'list'])
    assert res.exit_code == 0
    assert 'dead1' in res.output
    # retry the dead job
    res2 = runner.invoke(cli, ['dlq', 'retry', 'dead1'])
    assert res2.exit_code == 0
    # verify moved to pending
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT state, attempts FROM jobs WHERE id='dead1'")
    row = cur.fetchone()
    assert row[0] == 'pending'
    assert row[1] == 0
    conn.close()
