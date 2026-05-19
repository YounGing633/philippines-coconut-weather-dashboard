from __future__ import annotations
from pathlib import Path
from datetime import date, datetime, timedelta, timezone
import re

MANILA_TZ = timezone(timedelta(hours=8))

def today_manila() -> date:
    return datetime.now(MANILA_TZ).date()

def parse_date(value: str | None, default: date | None = None) -> date:
    if not value:
        if default is None:
            raise ValueError('date value required')
        return default
    return datetime.strptime(str(value), '%Y-%m-%d').date()

def iso(d: date | datetime | str) -> str:
    if isinstance(d, datetime):
        return d.date().isoformat()
    if isinstance(d, date):
        return d.isoformat()
    return str(d)[:10]

def ensure_dir(p: str | Path) -> Path:
    p = Path(p)
    p.mkdir(parents=True, exist_ok=True)
    return p

def safe_id(text: str) -> str:
    return re.sub(r'[^A-Z0-9]+', '_', str(text).upper()).strip('_')

def daterange_chunks(start: date, end: date, years: int = 5):
    cur = start
    while cur <= end:
        try:
            chunk_end = cur.replace(year=cur.year + years) - timedelta(days=1)
        except ValueError:
            chunk_end = cur + timedelta(days=365 * years) - timedelta(days=1)
        if chunk_end > end:
            chunk_end = end
        yield cur, chunk_end
        cur = chunk_end + timedelta(days=1)
