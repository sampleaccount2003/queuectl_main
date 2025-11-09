import click
from .db import get_conn
from .utils import now_iso
import json


@click.group()
def dlq():
    """Dead Letter Queue commands"""
    pass


@dlq.command("list")
def dlq_list():
    """List all jobs in the Dead Letter Queue"""
    conn = get_conn()
    cur = conn.cursor()
    rows = cur.execute("SELECT * FROM jobs WHERE state='dead' ORDER BY updated_at").fetchall()
    if not rows:
        click.echo("No jobs in DLQ.")
        conn.close()
        return
    for r in rows:
        click.echo(json.dumps(dict(r), default=str))
    conn.close()


@dlq.command("retry")
@click.argument("job_id")
def dlq_retry(job_id):
    """Retry a job from the Dead Letter Queue"""
    conn = get_conn()
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM jobs WHERE id=? AND state='dead'", (job_id,)).fetchone()
    if not row:
        click.echo("Job not found in DLQ")
        conn.close()
        raise SystemExit(1)
    now = now_iso()
    cur.execute(
        "UPDATE jobs SET state='pending', attempts=0, updated_at=?, last_error=NULL, next_run_at=? WHERE id=?",
        (now, now, job_id),
    )
    conn.commit()
    conn.close()
    click.echo(f"Requeued {job_id} from DLQ")
