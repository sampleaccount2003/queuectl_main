import threading
import time
import subprocess
import datetime
import click
from .db import get_conn, get_config, set_config
from .utils import now_iso

stop_event = threading.Event()

def update_job_state(conn, job_id, state, last_error=None, next_run_at=None, expected_state=None):
    """Update job state and related fields.
    If expected_state is provided, only update if current state matches (for safety)."""
    cur = conn.cursor()
    now = now_iso()
    if last_error is not None and next_run_at is not None:
        if expected_state:
            cur.execute(
                "UPDATE jobs SET state=?, attempts=attempts+1, updated_at=?, last_error=?, next_run_at=? WHERE id=? AND state=?",
                (state, now, last_error, next_run_at, job_id, expected_state)
            )
        else:
            cur.execute(
                "UPDATE jobs SET state=?, attempts=attempts+1, updated_at=?, last_error=?, next_run_at=? WHERE id=?",
                (state, now, last_error, next_run_at, job_id)
            )
    elif last_error is not None:
        if expected_state:
            cur.execute(
                "UPDATE jobs SET state=?, attempts=attempts+1, updated_at=?, last_error=?, next_run_at=? WHERE id=? AND state=?",
                (state, now, last_error, next_run_at, job_id, expected_state)
            )
        else:
            cur.execute(
                "UPDATE jobs SET state=?, attempts=attempts+1, updated_at=?, last_error=?, next_run_at=? WHERE id=?",
                (state, now, last_error, next_run_at, job_id)
            )
    else:
        if expected_state:
            cur.execute(
                "UPDATE jobs SET state=?, updated_at=? WHERE id=? AND state=?",
                (state, now, job_id, expected_state)
            )
        else:
            cur.execute(
                "UPDATE jobs SET state=?, updated_at=? WHERE id=?",
                (state, now, job_id)
            )
    conn.commit()

def pick_job_and_lock(conn):
    """Pick a pending job and lock it by setting state to processing.
    Uses an atomic UPDATE to prevent race conditions."""
    cur = conn.cursor()
    now = now_iso()
    
    # Begin a transaction to ensure atomicity
    cur.execute("BEGIN IMMEDIATE")
    try:
        # First, find a candidate job
        cur.execute("""
            SELECT id, command, attempts, max_retries 
            FROM jobs 
            WHERE state='pending' 
            AND (next_run_at IS NULL OR next_run_at <= ?)
            ORDER BY created_at ASC
            LIMIT 1
        """, (now,))
        row = cur.fetchone()
        
        if row:
            job_id = row['id']
            # Atomically try to lock it by updating state to processing
            # This will only succeed if the job is still in 'pending' state
            cur.execute("""
                UPDATE jobs 
                SET state='processing', updated_at=?
                WHERE id=? AND state='pending'
            """, (now, job_id))
            
            # If we successfully updated the job, commit and return it
            if cur.rowcount > 0:
                conn.commit()
                return dict(row)
            else:
                # Another worker got it first
                conn.commit()
                return None
        else:
            # No jobs available
            conn.commit()
            return None
    except Exception as e:
        conn.rollback()
        raise

def worker_loop(worker_id, backoff_base):
    """Main worker loop that processes jobs"""
    click.echo(f"[worker {worker_id}] started")
    while not stop_event.is_set():
        conn = get_conn()
        stop_flag = get_config(conn, "stop_workers", "false")
        if stop_flag == "true":
            click.echo(f"[worker {worker_id}] stop flag set, exiting")
            conn.close()
            break
        
        job = pick_job_and_lock(conn)
        if not job:
            conn.close()
            time.sleep(1)  # Wait before checking again
            continue
        
        job_id = job['id']
        command = job['command']
        attempts = job['attempts']
        max_retries = job['max_retries']
        
        click.echo(f"[worker {worker_id}] processing job {job_id}: {command}")
        
        try:
            # Execute the command
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                # Success
                click.echo(f"[worker {worker_id}] job {job_id} completed successfully")
                update_job_state(conn, job_id, "completed", expected_state="processing")
            else:
                # Failed
                error_msg = result.stderr or result.stdout or "Command failed"
                click.echo(f"[worker {worker_id}] job {job_id} failed: {error_msg[:100]}")
                if attempts < max_retries:
                    delay = (backoff_base ** attempts)
                    next_run = (datetime.datetime.utcnow() + datetime.timedelta(seconds=delay)).replace(microsecond=0).isoformat() + "Z"
                    update_job_state(conn, job_id, "pending", last_error=error_msg[:500], next_run_at=next_run, expected_state="processing")
                else:
                    update_job_state(conn, job_id, "dead", last_error=error_msg[:500], next_run_at=None, expected_state="processing")
                    click.echo(f"[worker {worker_id}] job {job_id} moved to DLQ (dead)")
        except subprocess.TimeoutExpired:
            click.echo(f"[worker {worker_id}] job {job_id} timed out.")
            if attempts < max_retries:
                delay = (backoff_base ** attempts)
                next_run = (datetime.datetime.utcnow() + datetime.timedelta(seconds=delay)).replace(microsecond=0).isoformat() + "Z"
                update_job_state(conn, job_id, "pending", last_error="timeout", next_run_at=next_run, expected_state="processing")
            else:
                update_job_state(conn, job_id, "dead", last_error="timeout", next_run_at=None, expected_state="processing")
        except Exception as e:
            click.echo(f"[worker {worker_id}] unexpected error for job {job_id}: {e}")
            if attempts < max_retries:
                delay = (backoff_base ** attempts)
                next_run = (datetime.datetime.utcnow() + datetime.timedelta(seconds=delay)).replace(microsecond=0).isoformat() + "Z"
                update_job_state(conn, job_id, "pending", last_error=str(e), next_run_at=next_run, expected_state="processing")
            else:
                update_job_state(conn, job_id, "dead", last_error=str(e), next_run_at=None, expected_state="processing")
        
        conn.close()
    
    click.echo(f"[worker {worker_id}] exiting.")


@click.group()
def worker():
    """Worker control commands"""
    pass


@worker.command("start")
@click.option("--count", default=1, help="Number of worker threads to start")
def start(count):
    conn = get_conn()
    backoff_base = int(get_config(conn, "backoff_base", "2"))
    set_config(conn, "stop_workers", "false")
    stop_event.clear()
    threads = []
    for i in range(count):
        t = threading.Thread(target=worker_loop, args=(i + 1, backoff_base), daemon=True)
        threads.append(t)
        t.start()
    click.echo(f"Started {count} worker(s). Press Ctrl-C to stop.")
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        click.echo("Keyboard interrupt — requesting graceful shutdown")
        stop_event.set()
        with get_conn() as c:
            set_config(c, "stop_workers", "true")
        for t in threads:
            t.join()
        click.echo("All workers stopped.")


@worker.command("stop")
def stop():
    conn = get_conn()
    set_config(conn, "stop_workers", "true")
    stop_event.set()
    click.echo("Requested workers to stop (config flag set)")
