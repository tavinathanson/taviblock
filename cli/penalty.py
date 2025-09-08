#!/usr/bin/env python3
"""Progressive penalty system for taviblock"""

import json
from datetime import datetime, time, timedelta
from cli import db


def get_daily_stats(config=None):
    """Get unblock statistics for today"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    now = datetime.now()
    today_4am = datetime.combine(now.date(), time(4, 0))
    if now.hour < 4:
        # If it's before 4am, we're still in "yesterday's" period
        today_4am -= timedelta(days=1)
    
    # The period we're currently in started at today_4am
    current_period_start = today_4am.timestamp()
    next_reset = (today_4am + timedelta(days=1)).timestamp()
    
    # Get excluded profiles from config
    exclude_profiles = []
    if config:
        penalty_config = config.data.get('progressive_penalty', {})
        exclude_profiles = penalty_config.get('exclude_profiles', [])
    
    # Build SQL query with proper parameter placeholders
    placeholders = ','.join('?' * len(exclude_profiles)) if exclude_profiles else ''
    exclude_clause = f"AND session_type NOT IN ({placeholders})" if exclude_profiles else ""
    
    # Count unblocks since the start of current period (excluding configured profiles)
    query = f"""
        SELECT COUNT(*) as count 
        FROM unblock_sessions 
        WHERE created_at > ? 
        AND queued_for_domains IS NULL 
        {exclude_clause}
    """
    
    params = [current_period_start] + exclude_profiles
    cursor.execute(query, params)
    
    count = cursor.fetchone()['count']
    conn.close()
    
    return {
        'count': count,
        'last_reset': current_period_start,
        'next_reset': next_reset
    }


def get_progressive_penalty(config):
    """Calculate the current progressive penalty in minutes"""
    penalty_config = config.data.get('progressive_penalty', {})
    
    if not penalty_config.get('enabled', False):
        return 0
    
    stats = get_daily_stats(config)
    
    # Calculate penalty based on unblocks in current period
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
    
    stats = get_daily_stats(config)
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