"""Community scam database (SQLite, no setup needed).

When a student confirms an offer was a scam, they report the sender
email / website. Every future analysis checks against these reports,
so the tool gets smarter the more your batch uses it.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).resolve().parent.parent / "scamdetector.db"))


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL CHECK (kind IN ('email', 'domain')),
            value TEXT NOT NULL,
            company_claimed TEXT,
            note TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_reports_value ON reports(kind, value);

        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            risk_score INTEGER NOT NULL,
            verdict TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)


def add_report(kind: str, value: str, company: str | None, note: str | None) -> int:
    with connect() as c:
        cur = c.execute(
            "INSERT INTO reports (kind, value, company_claimed, note, created_at) VALUES (?,?,?,?,?)",
            (kind, value.lower().strip(), company, (note or "")[:500],
             datetime.now(timezone.utc).isoformat()))
        return cur.lastrowid


def report_counts(emails: list[str], domains: list[str]) -> dict[str, int]:
    """Return {value: number_of_reports} for any value seen before."""
    values = [("email", e.lower()) for e in emails] + [("domain", d.lower()) for d in domains]
    if not values:
        return {}
    out = {}
    with connect() as c:
        for kind, value in values:
            n = c.execute("SELECT COUNT(*) FROM reports WHERE kind=? AND value=?",
                          (kind, value)).fetchone()[0]
            if n:
                out[value] = n
    return out


def log_analysis(score: int, verdict: str):
    """Store only the score, never the offer text (student privacy)."""
    with connect() as c:
        c.execute("INSERT INTO analyses (risk_score, verdict, created_at) VALUES (?,?,?)",
                  (score, verdict, datetime.now(timezone.utc).isoformat()))


def stats() -> dict:
    with connect() as c:
        total = c.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        scams = c.execute("SELECT COUNT(*) FROM analyses WHERE verdict='Likely scam'").fetchone()[0]
        reports = c.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
        top = c.execute("""SELECT value, COUNT(*) n FROM reports GROUP BY kind, value
                           ORDER BY n DESC LIMIT 5""").fetchall()
    return {"offers_checked": total, "scams_flagged": scams, "community_reports": reports,
            "most_reported": [{"value": r["value"], "reports": r["n"]} for r in top]}
