#!/usr/bin/env python3
"""Progressive penalty system for taviblock"""

import json
from datetime import datetime, time, timedelta
from cli import db


def get_daily_stats():
    """Get unblock statistics for today"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Get last reset time
    cursor.execute("SELECT value FROM global_state WHERE key = 'penalty_last_reset'")
    row = cursor.fetchone()
    
    now = datetime.now()
    today_4am = datetime.combine(now.date(), time(4, 0))
    if now.hour < 4:
        today_4am -= timedelta(days=1)
    
    last_reset = today_4am.timestamp()
    
    if row:
        stored_reset = float(row['value'])
        if stored_reset > last_reset:
            last_reset = stored_reset
    
    # Count unblocks since last reset
    cursor.execute("""
        SELECT COUNT(*) as count 
        FROM unblock_sessions 
        WHERE created_at > ?
    """, (last_reset,))
    
    count = cursor.fetchone()['count']
    conn.close()
    
    return {
        'count': count,
        'last_reset': last_reset,
        'next_reset': (today_4am + timedelta(days=1)).timestamp()
    }


def update_penalty_reset():
    """Update the last penalty reset time"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    now = datetime.now()
    cursor.execute("""
        INSERT OR REPLACE INTO global_state (key, value)
        VALUES ('penalty_last_reset', ?)
    """, (str(now.timestamp()),))
    
    conn.commit()
    conn.close()


def get_progressive_penalty(config):
    """Calculate the current progressive penalty in minutes"""
    penalty_config = config.data.get('progressive_penalty', {})
    
    if not penalty_config.get('enabled', False):
        return 0
    
    stats = get_daily_stats()
    
    # Check if we need to reset
    now = datetime.now()
    if now.timestamp() > stats['next_reset']:
        update_penalty_reset()
        return 0
    
    # Calculate penalty
    per_unblock_seconds = penalty_config.get('per_unblock', 10)
    penalty_seconds = stats['count'] * per_unblock_seconds
    
    # Convert to minutes
    return penalty_seconds / 60


def should_apply_penalty(profile_name, config):
    """Check if penalty should apply to this profile"""
    penalty_config = config.data.get('progressive_penalty', {})
    
    if not penalty_config.get('enabled', False):
        return False
    
    exclude_profiles = penalty_config.get('exclude_profiles', [])
    return profile_name not in exclude_profiles


def get_penalty_status(config):
    """Get human-readable penalty status"""
    penalty_config = config.data.get('progressive_penalty', {})
    
    if not penalty_config.get('enabled', False):
        return None
    
    stats = get_daily_stats()
    penalty_minutes = get_progressive_penalty(config)
    
    # Time until next reset
    next_reset = datetime.fromtimestamp(stats['next_reset'])
    now = datetime.now()
    time_until_reset = next_reset - now
    hours = int(time_until_reset.total_seconds() / 3600)
    minutes = int((time_until_reset.total_seconds() % 3600) / 60)
    
    return {
        'unblocks_today': stats['count'],
        'current_penalty': penalty_minutes,
        'reset_in': f"{hours}h {minutes}m",
        'per_unblock': penalty_config.get('per_unblock', 10)
    }