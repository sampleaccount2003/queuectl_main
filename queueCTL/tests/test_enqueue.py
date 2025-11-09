import os
import sqlite3
from click.testing import CliRunner
import pytest

# Adjust path to find package inside test environment if needed
DB = os.getenv('QUEUECTL_DB', os.path.join(os.path.dirname(__file__), '..', 'queuectl.db'))

def test_enqueue_creates_job(tmp_path, monkeypatch):
    # Use a temporary DB for isolation
    db_path = tmp_path / "queuectl.db"
    monkeypatch.setenv('QUEUECTL_DB', str(db_path))
    # import cli lazily
    from queuectl.cli import cli
    runner = CliRunner()
    res = runner.invoke(cli, ['enqueue', '{"id":"t_test_1","command":"echo hello"}'])
    assert res.exit_code == 0, res.output
    # verify DB has the job
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM jobs WHERE id='t_test_1'")
    assert cur.fetchone()[0] == 1
    conn.close()
