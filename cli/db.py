#!/usr/bin/python3
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
            created_at REAL NOT NULL,
            is_all_domains INTEGER DEFAULT 0,  -- 1 if this session unblocks all domains
            queued_for_domains TEXT  -- JSON array of domains this is queued for (waiting for them to be blocked again)
        )
    """)
    
    # Table for profile cooldown tracking (replaces bypass_cooldown)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profile_cooldowns (
            profile_name TEXT PRIMARY KEY,
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
    
    # Add migration for existing databases
    try:
        cursor.execute("ALTER TABLE unblock_sessions ADD COLUMN is_all_domains INTEGER DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        # Column already exists
        pass
    
    try:
        cursor.execute("ALTER TABLE unblock_sessions ADD COLUMN queued_for_domains TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        # Column already exists
        pass
    
    conn.commit()
    conn.close()

def add_unblock_session(domains, duration_minutes, wait_minutes=0, session_type='single', is_all_domains=False, queued_for_domains=None):
    """Add a new unblock session."""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().timestamp()
    wait_until = now + (wait_minutes * 60) if wait_minutes > 0 else now
    end_time = wait_until + (duration_minutes * 60)
    
    cursor.execute("""
        INSERT INTO unblock_sessions (domains, start_time, end_time, wait_until, session_type, created_at, is_all_domains, queued_for_domains)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (json.dumps(domains), now, end_time, wait_until, session_type, now, 1 if is_all_domains else 0, 
          json.dumps(queued_for_domains) if queued_for_domains else None))
    
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
        WHERE wait_until > ? AND queued_for_domains IS NULL
        ORDER BY wait_until ASC
    """, (now,))
    
    sessions = []
    for row in cursor.fetchall():
        session = dict(row)
        session['domains'] = json.loads(session['domains'])
        sessions.append(session)
    
    conn.close()
    return sessions

def get_queued_sessions():
    """Get sessions that are queued (waiting for domains to be blocked again)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM unblock_sessions 
        WHERE queued_for_domains IS NOT NULL
        ORDER BY created_at ASC
    """)
    
    sessions = []
    for row in cursor.fetchall():
        session = dict(row)
        session['domains'] = json.loads(session['domains'])
        session['queued_for_domains'] = json.loads(session['queued_for_domains']) if session['queued_for_domains'] else None
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
    # Only delete sessions that have actually started (not queued ones)
    cursor.execute("DELETE FROM unblock_sessions WHERE end_time <= ? AND queued_for_domains IS NULL", (now,))
    
    conn.commit()
    conn.close()

def check_profile_cooldown(profile_name, cooldown_minutes=0):
    """Check if a profile is available (no cooldown or cooldown expired)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT last_used FROM profile_cooldowns WHERE profile_name = ?", (profile_name,))
    row = cursor.fetchone()
    
    if not row or cooldown_minutes == 0:
        conn.close()
        return True, 0
    
    last_used = row['last_used']
    now = datetime.now().timestamp()
    cooldown_seconds = cooldown_minutes * 60
    
    if now - last_used >= cooldown_seconds:
        conn.close()
        return True, 0
    else:
        remaining = int(cooldown_seconds - (now - last_used))
        conn.close()
        return False, remaining

def set_profile_cooldown(profile_name, cooldown_minutes):
    """Mark profile as used, starting the cooldown."""
    if cooldown_minutes == 0:
        return  # No cooldown to set
        
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().timestamp()
    cursor.execute("INSERT OR REPLACE INTO profile_cooldowns (profile_name, last_used) VALUES (?, ?)", 
                  (profile_name, now))
    
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

def extend_session(session_id, new_end_time):
    """Extend a session's end time."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE unblock_sessions SET end_time = ? WHERE id = ?", 
                   (new_end_time, session_id))
    
    conn.commit()
    conn.close()

def activate_queued_session(session_id, wait_minutes):
    """Convert a queued session to a regular pending session."""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().timestamp()
    new_wait_until = now + (wait_minutes * 60)
    
    # Get current session to calculate new end time
    cursor.execute("SELECT * FROM unblock_sessions WHERE id = ?", (session_id,))
    session = cursor.fetchone()
    
    if session:
        duration_seconds = session['end_time'] - session['wait_until']
        new_end_time = new_wait_until + duration_seconds
        
        # Update session to remove queued_for_domains and set new times
        cursor.execute("""
            UPDATE unblock_sessions 
            SET queued_for_domains = NULL, 
                wait_until = ?, 
                end_time = ?,
                start_time = ?
            WHERE id = ?
        """, (new_wait_until, new_end_time, now, session_id))
        
        conn.commit()
    
    conn.close()

if __name__ == "__main__":
    # Initialize the database if run directly
    init_db()
    print(f"Database initialized at {DB_PATH}")