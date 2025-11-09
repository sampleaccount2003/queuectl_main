import click
from .db import init_db
from .job import enqueue, list_jobs, status
from .worker import worker as worker_cmd
from .dlq import dlq as dlq_cmd
from .config import config as config_cmd

@click.group()
def cli():
    """QueueCTL - Background job queue system"""
    # Ensure DB + config defaults exist before any command runs
    init_db()

# Attach subcommands
cli.add_command(enqueue)
cli.add_command(list_jobs)
cli.add_command(status)
cli.add_command(worker_cmd)
cli.add_command(dlq_cmd)
cli.add_command(config_cmd)

if __name__ == "__main__":
    cli()
