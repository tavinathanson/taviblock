#!/usr/bin/env python3
import sqlite3
import os
from datetime import datetime, timedelta
from pathlib import Path
import json

# Database location
DB_DIR = Path("/var/lib/taviblock")
DB_PATH = DB_DIR / "state.db"

def ensure_db_exists():
    """Ensure the database directory and file exist with proper permissions."""
    if not DB_DIR.exists():
        DB_DIR.mkdir(parents=True, exist_ok=True)
        os.chmod(DB_DIR, 0o755)
    
def get_connection():
    """Get a connection to the database."""
    ensure_db_exists()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database schema."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Table for active unblock sessions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS unblock_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domains TEXT NOT NULL,  -- JSON array of domains
            start_time REAL NOT NULL,
            end_time REAL NOT NULL,
            wait_until REAL,  -- When the unblock actually starts (after wait period)
            session_type TEXT NOT NULL,  -- 'single', 'multiple', 'bypass', 'peek'
            created_at REAL NOT NULL
        )
    """)
    
    # Table for bypass cooldown tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bypass_cooldown (
            id INTEGER PRIMARY KEY,
            last_used REAL NOT NULL
        )
    """)
    
    # Table for global state
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS global_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()

def add_unblock_session(domains, duration_minutes, wait_minutes=0, session_type='single'):
    """Add a new unblock session."""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().timestamp()
    wait_until = now + (wait_minutes * 60) if wait_minutes > 0 else now
    end_time = wait_until + (duration_minutes * 60)
    
    cursor.execute("""
        INSERT INTO unblock_sessions (domains, start_time, end_time, wait_until, session_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (json.dumps(domains), now, end_time, wait_until, session_type, now))
    
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return session_id

def get_active_sessions():
    """Get all currently active unblock sessions."""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().timestamp()
    
    cursor.execute("""
        SELECT * FROM unblock_sessions 
        WHERE end_time > ? AND wait_until <= ?
        ORDER BY end_time DESC
    """, (now, now))
    
    sessions = []
    for row in cursor.fetchall():
        session = dict(row)
        session['domains'] = json.loads(session['domains'])
        sessions.append(session)
    
    conn.close()
    return sessions

def get_pending_sessions():
    """Get sessions that are waiting to start."""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().timestamp()
    
    cursor.execute("""
        SELECT * FROM unblock_sessions 
        WHERE wait_until > ?
        ORDER BY wait_until ASC
    """, (now,))
    
    sessions = []
    for row in cursor.fetchall():
        session = dict(row)
        session['domains'] = json.loads(session['domains'])
        sessions.append(session)
    
    conn.close()
    return sessions

def get_all_unblocked_domains():
    """Get the union of all domains from active sessions."""
    sessions = get_active_sessions()
    all_domains = set()
    
    for session in sessions:
        all_domains.update(session['domains'])
    
    return list(all_domains)

def clean_expired_sessions():
    """Remove expired sessions from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().timestamp()
    cursor.execute("DELETE FROM unblock_sessions WHERE end_time <= ?", (now,))
    
    conn.commit()
    conn.close()

def check_bypass_cooldown():
    """Check if bypass is available (no cooldown or cooldown expired)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT last_used FROM bypass_cooldown ORDER BY last_used DESC LIMIT 1")
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return True, 0
    
    last_used = row['last_used']
    now = datetime.now().timestamp()
    cooldown_seconds = 3600  # 1 hour
    
    if now - last_used >= cooldown_seconds:
        conn.close()
        return True, 0
    else:
        remaining = int(cooldown_seconds - (now - last_used))
        conn.close()
        return False, remaining

def set_bypass_used():
    """Mark bypass as used, starting the cooldown."""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().timestamp()
    cursor.execute("INSERT OR REPLACE INTO bypass_cooldown (id, last_used) VALUES (1, ?)", (now,))
    
    conn.commit()
    conn.close()

def cancel_session(session_id):
    """Cancel a specific session."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM unblock_sessions WHERE id = ?", (session_id,))
    
    conn.commit()
    conn.close()

def get_session_info(session_id):
    """Get information about a specific session."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM unblock_sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    
    if row:
        session = dict(row)
        session['domains'] = json.loads(session['domains'])
        conn.close()
        return session
    
    conn.close()
    return None

if __name__ == "__main__":
    # Initialize the database if run directly
    init_db()
    print(f"Database initialized at {DB_PATH}")