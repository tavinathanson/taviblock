#!/usr/bin/python3
import argparse
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
import json
import subprocess

from cli import db
from cli.config_loader import Config

# Path to the system hosts file on macOS
HOSTS_PATH = "/etc/hosts"
# Markers to delimit our managed block section in /etc/hosts
BLOCKER_START = "# BLOCKER START"
BLOCKER_END = "# BLOCKER END"


def require_admin():
    """Ensure the script is run as root."""
    if os.geteuid() != 0:
        print("This script must be run as root. Try running with sudo.")
        sys.exit(1)


def generate_block_entries(domains):
    """Generate hosts file entries for IPv4 and IPv6."""
    entries = []
    common_subdomains = ["www", "m", "mobile", "login", "app", "api"]

    for domain in domains:
        domain = domain.strip()
        if not domain:
            continue
        parts = domain.split(".")
        if len(parts) == 2:  # root domain
            entries.append(f"127.0.0.1 {domain}")
            entries.append(f"::1 {domain}")
            for prefix in common_subdomains:
                subdomain = f"{prefix}.{domain}"
                entries.append(f"127.0.0.1 {subdomain}")
                entries.append(f"::1 {subdomain}")
        else:
            entries.append(f"127.0.0.1 {domain}")
            entries.append(f"::1 {domain}")
    return entries


def format_time_remaining(seconds):
    """Format seconds into human-readable time."""
    if seconds < 60:
        return f"{int(seconds)} seconds"
    elif seconds <= 300:  # 5 minutes or less, show minutes and seconds
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        if secs > 0:
            return f"{minutes} minute{'s' if minutes != 1 else ''} {secs} second{'s' if secs != 1 else ''}"
        else:
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        if minutes > 0:
            return f"{hours} hour{'s' if hours != 1 else ''} {minutes} minute{'s' if minutes != 1 else ''}"
        return f"{hours} hour{'s' if hours != 1 else ''}"


def get_concurrent_session_count():
    """Get count of active and pending sessions"""
    active = db.get_active_sessions()
    pending = db.get_pending_sessions()
    return len(active) + len(pending)


def cmd_profile(config: Config, profile_name: str, targets: list = None):
    """Generic profile command handler"""
    if not config.is_valid_profile(profile_name):
        print(f"Unknown profile: {profile_name}")
        print(f"Available profiles: {', '.join(config.get_profile_names())}")
        sys.exit(1)
    
    profile = config.profiles[profile_name]
    
    # Handle profiles with cooldown (like bypass)
    if 'cooldown' in profile and profile['cooldown'] > 0:
        available, remaining = db.check_profile_cooldown(profile_name, profile['cooldown'])
        if not available:
            print(f"{profile_name} on cooldown: {format_time_remaining(remaining)} remaining")
            sys.exit(1)
    
    # Resolve what to unblock
    if not targets:
        targets = []
    
    domains, all_tags = config.resolve_targets(targets, profile_name)
    
    if not domains:
        print("No domains to unblock")
        sys.exit(1)
    
    # Calculate timing based on concurrent sessions and tags
    concurrent_sessions = get_concurrent_session_count()
    timing = config.calculate_timing(profile_name, len(targets), concurrent_sessions, all_tags)
    
    # Create sessions for each target (parallel sessions)
    if profile.get('all') or 'tags' in profile or 'only' in profile:
        # These profiles create a single session for all domains
        session_id = db.add_unblock_session(
            domains,
            timing['duration'],
            timing['wait'],
            profile_name,
            is_all_domains=profile.get('all', False)
        )
        
        print(f"{profile_name.capitalize()} session created (ID: {session_id})")
        if profile.get('all'):
            print(f"Unblocking: all")
        elif 'tags' in profile:
            print(f"Unblocking: domains tagged {', '.join(profile['tags'])}")
        else:
            print(f"Unblocking: {', '.join(profile['only'])}")
    else:
        # Create separate sessions for each target
        session_ids = []
        base_wait = timing['wait']
        
        for i, target in enumerate(targets):
            target_domains, _ = config.resolve_targets([target], profile_name)
            # Add concurrent penalty for each additional session
            wait_config = profile.get('wait', {})
            if isinstance(wait_config, dict):
                penalty = wait_config.get('concurrent_penalty', 0)
                wait = base_wait + (i * penalty)
            else:
                wait = base_wait
            
            session_id = db.add_unblock_session(
                target_domains,
                timing['duration'],
                wait,
                profile_name,
                is_all_domains=False
            )
            session_ids.append((target, session_id, wait))
        
        print(f"Created {len(session_ids)} parallel session(s):")
        for target, sid, wait in session_ids:
            print(f"  [{sid}] {target}: unblocks in {format_time_remaining(wait * 60)}")
    
    # Mark cooldown if applicable
    if 'cooldown' in profile and profile['cooldown'] > 0:
        db.set_profile_cooldown(profile_name, profile['cooldown'])
    
    print(f"\nDuration: {timing['duration']} minutes once active")


def cmd_status(config: Config, args):
    """Show current status."""
    active_sessions = db.get_active_sessions()
    pending_sessions = db.get_pending_sessions()
    
    if not active_sessions and not pending_sessions:
        print("All domains are blocked")
        return
    
    if pending_sessions:
        print("PENDING SESSIONS:")
        for session in pending_sessions:
            wait_remaining = session['wait_until'] - datetime.now().timestamp()
            print(f"  [{session['id']}] {session['session_type']}:")
            # Show "all" for sessions that unblock everything
            if session.get('is_all_domains'):
                print(f"    Domains: all")
            else:
                print(f"    Domains: {', '.join(session['domains'][:5])}" + 
                      (" (and more)" if len(session['domains']) > 5 else ""))
            print(f"    Starts in: {format_time_remaining(wait_remaining)}")
            print(f"    Duration: {format_time_remaining(session['end_time'] - session['wait_until'])}")
        print()
    
    if active_sessions:
        print("ACTIVE SESSIONS:")
        for session in active_sessions:
            remaining = session['end_time'] - datetime.now().timestamp()
            print(f"  [{session['id']}] {session['session_type']}:")
            # Show "all" for sessions that unblock everything
            if session.get('is_all_domains'):
                print(f"    Domains: all")
            else:
                print(f"    Domains: {', '.join(session['domains'][:5])}" +
                      (" (and more)" if len(session['domains']) > 5 else ""))
            print(f"    Remaining: {format_time_remaining(remaining)}")
        print()
        
        all_unblocked = db.get_all_unblocked_domains()
        print(f"Currently unblocked: {', '.join(sorted(all_unblocked)[:10])}" +
              (" (and more)" if len(all_unblocked) > 10 else ""))
    
    # Check cooldowns for profiles
    print("\nProfile cooldowns:")
    for profile_name in config.get_profile_names():
        profile = config.profiles[profile_name]
        if 'cooldown' in profile:
            available, remaining = db.check_profile_cooldown(profile_name, profile['cooldown'])
            if not available:
                print(f"  {profile_name}: {format_time_remaining(remaining)} remaining")


def cmd_cancel(args):
    """Cancel session(s)."""
    if args.session_id:
        session = db.get_session_info(args.session_id)
        if not session:
            print(f"Session {args.session_id} not found")
            sys.exit(1)
        
        db.cancel_session(args.session_id)
        print(f"Cancelled session {args.session_id}")
    else:
        active = db.get_active_sessions()
        pending = db.get_pending_sessions()
        all_sessions = active + pending
        
        if not all_sessions:
            print("No sessions to cancel")
            return
        
        for session in all_sessions:
            db.cancel_session(session['id'])
        
        print(f"Cancelled {len(all_sessions)} session(s)")


def cmd_daemon(args):
    """Control the daemon."""
    if args.action == 'start':
        result = subprocess.run(['sudo', 'launchctl', 'list'], capture_output=True, text=True)
        if 'com.taviblock.daemon' in result.stdout:
            print("Daemon already running")
        else:
            subprocess.run(['sudo', 'launchctl', 'load', '/Library/LaunchDaemons/com.taviblock.daemon.plist'])
            print("Daemon started")
    
    elif args.action == 'stop':
        subprocess.run(['sudo', 'launchctl', 'unload', '/Library/LaunchDaemons/com.taviblock.daemon.plist'])
        print("Daemon stopped")
    
    elif args.action == 'restart':
        subprocess.run(['sudo', 'launchctl', 'unload', '/Library/LaunchDaemons/com.taviblock.daemon.plist'])
        subprocess.run(['sudo', 'launchctl', 'load', '/Library/LaunchDaemons/com.taviblock.daemon.plist'])
        print("Daemon restarted")
    
    elif args.action == 'logs':
        log_path = '/var/log/taviblock/daemon.log'
        if os.path.exists(log_path):
            subprocess.run(['tail', '-f', log_path])
        else:
            print(f"Log file not found: {log_path}")


def main():
    require_admin()
    
    # Load config
    config = Config()
    
    parser = argparse.ArgumentParser(
        description="Taviblock - Domain blocking with flexible profiles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Available profiles:
{chr(10).join(f'  {name}: {p.get("description", "Custom profile")}' for name, p in config.profiles.items() if p.get('description'))}

Examples:
  sudo taviblock unblock gmail              # Unblock gmail based on profile rules
  sudo taviblock unblock gmail slack        # Multiple parallel sessions
  sudo taviblock peek                       # Quick peek at everything
  sudo taviblock bypass                     # Emergency bypass (with cooldown)
  sudo taviblock quick gmail                # Quick 30-second check
  sudo taviblock work                       # Use work profile
  sudo taviblock status                     # Show current status
  sudo taviblock cancel 42                  # Cancel specific session
  sudo taviblock cancel                     # Cancel all sessions
"""
    )
    
    # Add --config flag
    parser.add_argument('--config', help='Path to config file')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Add subparser for each profile
    for profile_name in config.get_profile_names():
        profile = config.profiles[profile_name]
        help_text = profile.get('description', f'{profile_name} profile')
        
        parser_profile = subparsers.add_parser(profile_name, help=help_text)
        
        # Some profiles take targets, some don't
        if not (profile.get('all') or profile.get('tags') or profile.get('only')):
            parser_profile.add_argument('targets', nargs='*', help='Domains or groups to unblock')
    
    # status
    parser_status = subparsers.add_parser('status', help='Show status')
    
    # cancel  
    parser_cancel = subparsers.add_parser('cancel', help='Cancel sessions')
    parser_cancel.add_argument('session_id', nargs='?', type=int, help='Session ID')
    
    # daemon
    parser_daemon = subparsers.add_parser('daemon', help='Control daemon')
    parser_daemon.add_argument('action', choices=['start', 'stop', 'restart', 'logs'])
    
    # Check if we should use default profile
    default_profile = config.get_default_profile()
    if default_profile and len(sys.argv) > 1:
        # Get all valid commands (profiles + built-in commands)
        valid_commands = config.get_profile_names() + ['status', 'cancel', 'daemon']
        
        # Check if first non-flag argument is a valid command
        first_arg_idx = 1
        while first_arg_idx < len(sys.argv) and sys.argv[first_arg_idx].startswith('--'):
            first_arg_idx += 2  # Skip flag and its value
        
        if first_arg_idx < len(sys.argv) and sys.argv[first_arg_idx] not in valid_commands:
            # First argument is not a command, use default profile
            # Insert the default profile as the command
            sys.argv.insert(first_arg_idx, default_profile)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Reload config with custom path if provided
    if args.config:
        config = Config(args.config)
    
    # Initialize database
    db.init_db()
    
    # Route to appropriate handler
    if args.command == 'status':
        cmd_status(config, args)
    elif args.command == 'cancel':
        cmd_cancel(args)
    elif args.command == 'daemon':
        cmd_daemon(args)
    else:
        # It's a profile command
        targets = getattr(args, 'targets', [])
        cmd_profile(config, args.command, targets)


if __name__ == '__main__':
    main()