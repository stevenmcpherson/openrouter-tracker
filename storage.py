"""SQLite snapshot storage — persists usage snapshots for trend history."""

import json
import sqlite3
import time
from pathlib import Path

DB_PATH = Path.home() / ".openrouter-tracker" / "usage.db"


def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            key_label TEXT NOT NULL,
            key_suffix TEXT,
            total_credits REAL,
            total_usage REAL,
            remaining REAL,
            key_limit REAL,
            key_limit_remaining REAL,
            key_usage REAL,
            usage_daily REAL,
            usage_weekly REAL,
            usage_monthly REAL,
            limit_reset TEXT,
            is_free_tier INTEGER,
            status TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON snapshots(timestamp);
        CREATE INDEX IF NOT EXISTS idx_snapshots_label ON snapshots(key_label);
    """)
    conn.commit()
    conn.close()


def save_snapshot(label, key_suffix, credits, key_info, status="ok"):
    """Insert a usage snapshot for a single key."""
    conn = get_db()
    conn.execute(
        """INSERT INTO snapshots (
            timestamp, key_label, key_suffix, total_credits, total_usage,
            remaining, key_limit, key_limit_remaining, key_usage,
            usage_daily, usage_weekly, usage_monthly, limit_reset,
            is_free_tier, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            time.time(),
            label,
            key_suffix,
            credits.get("total_credits"),
            credits.get("total_usage"),
            credits.get("remaining"),
            key_info.get("limit"),
            key_info.get("limit_remaining"),
            key_info.get("usage"),
            key_info.get("usage_daily"),
            key_info.get("usage_weekly"),
            key_info.get("usage_monthly"),
            key_info.get("limit_reset"),
            1 if key_info.get("is_free_tier") else 0,
            status,
        ),
    )
    conn.commit()
    conn.close()


def get_recent_snapshots(hours=24):
    """Return snapshots from the last N hours, grouped by key label."""
    conn = get_db()
    cutoff = time.time() - (hours * 3600)
    rows = conn.execute(
        """SELECT * FROM snapshots
           WHERE timestamp >= ?
           ORDER BY timestamp ASC""",
        (cutoff,),
    ).fetchall()
    conn.close()

    by_label = {}
    for row in rows:
        label = row["key_label"]
        if label not in by_label:
            by_label[label] = []
        by_label[label].append(dict(row))
    return by_label


def prune_old_snapshots(days=90):
    """Delete snapshots older than N days."""
    conn = get_db()
    cutoff = time.time() - (days * 86400)
    conn.execute("DELETE FROM snapshots WHERE timestamp < ?", (cutoff,))
    conn.commit()
    conn.close()
