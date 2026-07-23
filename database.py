"""
database.py - SQLite operations for JamSlayer V3
Stores alarm events, tracks uploads, provides aggregation queries.
"""

import sqlite3
import os
import hashlib
from datetime import datetime, timedelta
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'jamslayer.db')


def get_db_path():
    """Get database path, ensuring directory exists."""
    db_dir = os.path.dirname(DB_PATH)
    os.makedirs(db_dir, exist_ok=True)
    return DB_PATH


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize database schema."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS alarm_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device TEXT NOT NULL,
                device_raw TEXT,
                alarm_name TEXT,
                timestamp TEXT,
                date TEXT NOT NULL,
                duration_seconds INTEGER DEFAULT 0,
                priority TEXT,
                plc TEXT,
                upload_id INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_hash TEXT UNIQUE NOT NULL,
                record_count INTEGER DEFAULT 0,
                format_type TEXT,
                date_range_start TEXT,
                date_range_end TEXT,
                uploaded_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS analysis_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_json TEXT NOT NULL,
                generated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_alarm_device ON alarm_events(device);
            CREATE INDEX IF NOT EXISTS idx_alarm_date ON alarm_events(date);
            CREATE INDEX IF NOT EXISTS idx_alarm_device_date ON alarm_events(device, date);
            CREATE INDEX IF NOT EXISTS idx_upload_hash ON uploads(file_hash);
        """)


def compute_file_hash(file_content):
    """Compute SHA256 hash of file content for duplicate detection."""
    return hashlib.sha256(file_content).hexdigest()


def is_duplicate_upload(file_hash):
    """Check if a file has already been uploaded."""
    with get_connection() as conn:
        result = conn.execute(
            "SELECT id, filename FROM uploads WHERE file_hash = ?", (file_hash,)
        ).fetchone()
        return dict(result) if result else None


def record_upload(filename, file_hash, record_count, format_type, date_start=None, date_end=None):
    """Record a successful upload."""
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO uploads (filename, file_hash, record_count, format_type, date_range_start, date_range_end)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (filename, file_hash, record_count, format_type, date_start, date_end)
        )
        return cursor.lastrowid


def insert_alarm_events(events, upload_id):
    """Bulk insert alarm events."""
    with get_connection() as conn:
        conn.executemany(
            """INSERT INTO alarm_events (device, device_raw, alarm_name, timestamp, date, duration_seconds, priority, plc, upload_id)
               VALUES (:device, :device_raw, :alarm_name, :timestamp, :date, :duration_seconds, :priority, :plc, :upload_id)""",
            [{**e, 'upload_id': upload_id} for e in events]
        )


def get_daily_counts_by_device(days_back=None):
    """Get daily alarm counts per device."""
    with get_connection() as conn:
        query = "SELECT device, date, COUNT(*) as count FROM alarm_events"
        params = []
        
        if days_back:
            cutoff = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
            query += " WHERE date >= ?"
            params.append(cutoff)
        
        query += " GROUP BY device, date ORDER BY device, date"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_device_summary():
    """Get summary stats per device including PLC."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT 
                device,
                COUNT(*) as total_alarms,
                COUNT(DISTINCT date) as days_active,
                MIN(date) as first_seen,
                MAX(date) as last_seen,
                AVG(duration_seconds) as avg_duration,
                plc
            FROM alarm_events
            GROUP BY device
            ORDER BY total_alarms DESC
        """).fetchall()
        return [dict(r) for r in rows]


def get_total_stats():
    """Get overall dashboard statistics."""
    with get_connection() as conn:
        stats = {}
        row = conn.execute(
            "SELECT COUNT(DISTINCT device) as devices, COUNT(*) as total_alarms FROM alarm_events"
        ).fetchone()
        stats['total_devices'] = row['devices']
        stats['total_alarms'] = row['total_alarms']
        
        # Upload count
        row = conn.execute("SELECT COUNT(*) as count FROM uploads").fetchone()
        stats['upload_count'] = row['count']
        
        # Last upload time
        row = conn.execute("SELECT uploaded_at FROM uploads ORDER BY uploaded_at DESC LIMIT 1").fetchone()
        stats['last_upload'] = row['uploaded_at'] if row else None
        
        # Date range
        row = conn.execute(
            "SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(DISTINCT date) as active_days FROM alarm_events"
        ).fetchone()
        stats['date_range_start'] = row['min_date']
        stats['date_range_end'] = row['max_date']
        stats['active_days'] = row['active_days']
        
        return stats


def get_recent_uploads(limit=10):
    """Get recent upload history."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM uploads ORDER BY uploaded_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def save_analysis_cache(analysis_json):
    """Cache the latest analysis result."""
    with get_connection() as conn:
        conn.execute("DELETE FROM analysis_cache")
        conn.execute(
            "INSERT INTO analysis_cache (analysis_json) VALUES (?)",
            (analysis_json,)
        )


def get_analysis_cache():
    """Retrieve cached analysis."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT analysis_json, generated_at FROM analysis_cache ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def clear_all_data():
    """Clear all data (for reset functionality)."""
    with get_connection() as conn:
        conn.execute("DELETE FROM alarm_events")
        conn.execute("DELETE FROM uploads")
        conn.execute("DELETE FROM analysis_cache")


def get_device_daily_timeseries(device):
    """Get daily alarm counts for a specific device across all dates."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT date, COUNT(*) as count FROM alarm_events WHERE device = ? GROUP BY date ORDER BY date",
            (device,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_dates():
    """Get all unique dates in the dataset."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT date FROM alarm_events ORDER BY date"
        ).fetchall()
        return [r['date'] for r in rows]
