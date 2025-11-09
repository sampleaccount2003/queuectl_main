import datetime


def now_iso():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
