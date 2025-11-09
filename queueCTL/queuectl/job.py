import json
import uuid
import click
from .db import get_conn, get_config
from .utils import now_iso


@click.command()
@click.argument("job_json", type=str)
def enqueue(job_json):
    """Enqueue a job: queuectl enqueue '{"id":"job1","command":"sleep 2"}'"""
    try:
        job = json.loads(job_json)
    except Exception as e:
        click.echo("Invalid JSON: " + str(e))
        raise SystemExit(1)
    job_id = job.get("id") or str(uuid.uuid4())
    command = job.get("command")
    if not command:
        click.echo("Job must contain 'command'")
        raise SystemExit(1)
    conn = get_conn()
    max_retries = int(job.get("max_retries") or int(get_config(conn, "max_retries", "3")))
    now = now_iso()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO jobs(id,command,state,attempts,max_retries,created_at,updated_at,next_run_at) VALUES (?,?,?,?,?,?,?,?)",
        (job_id, command, "pending", 0, max_retries, now, now, now),
    )
    conn.commit()
    conn.close()
    click.echo(f"Enqueued job {job_id}")


@click.command("list")
@click.option("--state", type=click.Choice(["pending", "processing", "completed", "failed", "dead"], case_sensitive=False), help="Filter jobs by state")
def list_jobs(state):
    """List jobs, optionally filtered by state"""
    conn = get_conn()
    cur = conn.cursor()
    if state:
        cur.execute("SELECT * FROM jobs WHERE state=? ORDER BY created_at DESC", (state.lower(),))
    else:
        cur.execute("SELECT * FROM jobs ORDER BY created_at DESC")
    rows = cur.fetchall()
    if not rows:
        click.echo("No jobs found.")
        conn.close()
        return
    for row in rows:
        click.echo(json.dumps(dict(row), default=str))
    conn.close()


@click.command("status")
def status():
    """Show summary of all job states & active workers"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Count jobs by state
    cur.execute("SELECT state, COUNT(*) as count FROM jobs GROUP BY state")
    state_counts = {row[0]: row[1] for row in cur.fetchall()}
    
    # Get total jobs
    cur.execute("SELECT COUNT(*) FROM jobs")
    total_jobs = cur.fetchone()[0]
    
    # Check if workers are running (check stop_workers flag)
    stop_flag = get_config(conn, "stop_workers", "false")
    workers_active = "No" if stop_flag == "true" else "Unknown (check worker processes)"
    
    click.echo("=== QueueCTL Status ===")
    click.echo(f"Total Jobs: {total_jobs}")
    click.echo(f"\nJobs by State:")
    for state in ["pending", "processing", "completed", "failed", "dead"]:
        count = state_counts.get(state, 0)
        click.echo(f"  {state.capitalize()}: {count}")
    
    click.echo(f"\nWorkers Active: {workers_active}")
    click.echo(f"\nConfiguration:")
    max_retries = get_config(conn, "max_retries", "3")
    backoff_base = get_config(conn, "backoff_base", "2")
    click.echo(f"  Max Retries: {max_retries}")
    click.echo(f"  Backoff Base: {backoff_base}")
    
    conn.close()