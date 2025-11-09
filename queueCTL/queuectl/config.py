import click
from .db import get_conn, set_config, get_config

@click.group()
def config():
    """Configuration commands for queuectl"""
    pass

@config.command("set")
@click.argument("key", type=click.STRING)
@click.argument("value", type=click.STRING)
def config_set(key, value):
    """
    Set a configuration key.

    Examples:
      queuectl config set max_retries 5
      queuectl config set backoff_base 3
    """
    conn = get_conn()
    # Basic validation for known keys
    if key in ("max_retries", "backoff_base"):
        try:
            intval = int(value)
            if intval < 0:
                raise ValueError("must be >= 0")
        except Exception as e:
            click.echo(f"Invalid value for {key}: {e}")
            raise SystemExit(1)
    set_config(conn, key, value)
    click.echo(f"Set {key}={value}")

@config.command("get")
@click.argument("key", type=click.STRING)
def config_get(key):
    """Get a configuration value"""
    conn = get_conn()
    v = get_config(conn, key)
    if v is None:
        click.echo(f"{key} not set")
    else:
        click.echo(f"{key}={v}")

@config.command("list")
def config_list():
    """List all configuration keys"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT key, value FROM config ORDER BY key")
    rows = cur.fetchall()
    if not rows:
        click.echo("No configuration set.")
        return
    for k, v in rows:
        click.echo(f"{k} = {v}")
