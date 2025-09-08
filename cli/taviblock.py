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


def get_pending_session_count():
    """Get count of only pending sessions (for wait time calculation)"""
    pending = db.get_pending_sessions()
    return len(pending)


def prompt_queue_session(target_desc, remaining_time, domains, timing, profile_name, is_all=False, target_name=None):
    """Prompt user to queue a session and handle the response."""
    print(f"\n{target_desc} currently unblocked ({format_time_remaining(remaining_time)} remaining)")
    print("Would you like to queue it to unblock again after it's blocked?")
    response = input("Queue for next unblock? (yes/no): ").lower().strip()
    
    if response in ['yes', 'y']:
        session_id = db.add_unblock_session(
            domains,
            timing['duration'],
            timing['wait'],
            profile_name,
            is_all_domains=is_all,
            queued_for_domains=domains,
            target_name=target_name
        )
        print(f"Queued session (ID: {session_id}) - will start after current session ends")
        return True
    return False


def get_domains_from_sessions(sessions):
    """Extract all domains from a list of sessions into a set."""
    domains = set()
    for session in sessions:
        domains.update(session['domains'])
    return domains


def calculate_wait_for_session(profile, base_wait, session_count):
    """Calculate wait time for a new session based on profile and concurrent sessions."""
    wait_config = profile.get('wait', {})
    if isinstance(wait_config, dict):
        penalty = wait_config.get('concurrent_penalty', 0)
        return base_wait + (session_count * penalty)
    return base_wait


def find_session_with_domains(sessions, target_domains):
    """Find a session containing any of the target domains."""
    for session in sessions:
        if any(d in session['domains'] for d in target_domains):
            return session
    return None


def print_session_info(session, session_type=""):
    """Print formatted session information."""
    # Include target name if available
    target_info = f" ({session.get('target_name')})" if session.get('target_name') else ""
    prefix = f"  [{session['id']}] {session['session_type']}{target_info}:"
    print(prefix)
    
    # Show domains
    if session.get('is_all_domains'):
        print(f"    Domains: all")
    else:
        domains = session['domains'][:5]
        print(f"    Domains: {', '.join(domains)}" + 
              (" (and more)" if len(session['domains']) > 5 else ""))
    
    return prefix


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
    
    try:
        domains, all_tags = config.resolve_targets(targets, profile_name)
    except ValueError as e:
        print(f"Error: {e}")
        print("Available targets:")
        print(f"  Domains/groups: {', '.join(sorted(config.domains.keys()))}")
        sys.exit(1)
    
    if not domains:
        print("No domains to unblock")
        sys.exit(1)
    
    # Calculate timing based on pending sessions only (not running ones)
    pending_sessions = get_pending_session_count()
    timing = config.calculate_timing(profile_name, len(targets), pending_sessions, all_tags)
    
    # Show progressive penalty if applicable
    from cli import penalty
    if penalty.should_apply_penalty(profile_name, config):
        penalty_minutes = penalty.get_progressive_penalty(config)
        if penalty_minutes > 0:
            penalty_seconds = int(penalty_minutes * 60)
            print(f"Progressive penalty: +{penalty_seconds} seconds (use 'status' for details)")
    
    # Create sessions for each target (parallel sessions)
    if profile.get('all') or 'tags' in profile or 'only' in profile:
        # These profiles create a single session for all domains
        # Check if these domains are already unblocked
        active_sessions = db.get_active_sessions()
        pending_sessions = db.get_pending_sessions()
        
        active_domains = get_domains_from_sessions(active_sessions)
        pending_domains = get_domains_from_sessions(pending_sessions)
        
        # For 'all' profiles, check if there's already an 'all' session
        if profile.get('all'):
            for session in active_sessions:
                if session.get('is_all_domains'):
                    remaining = session['end_time'] - datetime.now().timestamp()
                    prompt_queue_session(
                        f"Already have an active 'all' session (ID: {session['id']})",
                        remaining, domains, timing, profile_name, is_all=True, target_name="all"
                    )
                    return
            for session in pending_sessions:
                if session.get('is_all_domains'):
                    print(f"Already have a pending 'all' session (ID: {session['id']})")
                    return
        else:
            # Check if all domains are already unblocked or pending
            all_active = all(domain in active_domains for domain in domains)
            all_pending = all(domain in pending_domains for domain in domains)
            if all_active:
                # Find the session with these domains
                matching_session = None
                for session in active_sessions:
                    if set(domains).issubset(set(session['domains'])):
                        matching_session = session
                        break
                
                if matching_session:
                    remaining = matching_session['end_time'] - datetime.now().timestamp()
                    target_desc = f"Domains tagged {', '.join(profile['tags'])}" if 'tags' in profile else f"{', '.join(profile['only'])}"
                    target_name = f"tags:{','.join(profile['tags'])}" if 'tags' in profile else f"only:{','.join(profile['only'][:2])}"
                    prompt_queue_session(target_desc, remaining, domains, timing, profile_name, target_name=target_name)
                return
            elif all_pending:
                print(f"All requested domains are already pending")
                return
        
        # Determine target name for the session
        if profile.get('all'):
            target_name = "all"
        elif 'tags' in profile:
            target_name = f"tags:{','.join(profile['tags'])}"
        else:
            target_name = f"{','.join(profile['only'][:2])}"
        
        session_id = db.add_unblock_session(
            domains,
            timing['duration'],
            timing['wait'],
            profile_name,
            is_all_domains=profile.get('all', False),
            target_name=target_name
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
        # First, get currently active and pending sessions to check for duplicates
        active_sessions = db.get_active_sessions()
        pending_sessions = db.get_pending_sessions()
        
        # Build sets of domains that are active vs pending
        active_domains = get_domains_from_sessions(active_sessions)
        pending_domains = get_domains_from_sessions(pending_sessions)
        
        session_ids = []
        already_active_targets = []
        already_pending_targets = []
        base_wait = timing['wait']
        new_session_count = 0  # Track actual new sessions for penalty calculation
        
        for target in targets:
            try:
                target_domains, _ = config.resolve_targets([target], profile_name)
            except ValueError:
                # This shouldn't happen since we validated above, but just in case
                continue
            
            # Check if any of these domains are already active or pending
            if any(domain in active_domains for domain in target_domains):
                active_session = find_session_with_domains(active_sessions, target_domains)
                if active_session:
                    remaining = active_session['end_time'] - datetime.now().timestamp()
                    if prompt_queue_session(target, remaining, target_domains, timing, profile_name, target_name=target):
                        new_session_count += 1
                    else:
                        already_active_targets.append(target)
                continue
            elif any(domain in pending_domains for domain in target_domains):
                already_pending_targets.append(target)
                continue
            
            # Add concurrent penalty based on actual new sessions
            wait = calculate_wait_for_session(profile, base_wait, new_session_count)
            
            new_session_count += 1  # Increment after calculating wait
            
            session_id = db.add_unblock_session(
                target_domains,
                timing['duration'],
                wait,
                profile_name,
                is_all_domains=False,
                target_name=target
            )
            session_ids.append((target, session_id, wait))
        
        if already_active_targets:
            print(f"Already unblocked: {', '.join(already_active_targets)}")
        
        if already_pending_targets:
            print(f"Already pending: {', '.join(already_pending_targets)}")
        
        if session_ids:
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
    queued_sessions = db.get_queued_sessions()
    
    if not active_sessions and not pending_sessions and not queued_sessions:
        print("All domains are blocked")
        return
    
    if queued_sessions:
        print("QUEUED SESSIONS (waiting for domains to be blocked again):")
        for session in queued_sessions:
            print_session_info(session)
            print(f"    Waiting for: {', '.join(session['queued_for_domains'][:3])}" +
                  (" (and more)" if len(session['queued_for_domains']) > 3 else "") + " to be blocked")
            duration_seconds = session['end_time'] - session['wait_until']
            print(f"    Duration: {format_time_remaining(duration_seconds)} once active")
        print()
    
    if pending_sessions:
        print("PENDING SESSIONS:")
        for session in pending_sessions:
            print_session_info(session)
            wait_remaining = session['wait_until'] - datetime.now().timestamp()
            print(f"    Starts in: {format_time_remaining(wait_remaining)}")
            print(f"    Duration: {format_time_remaining(session['end_time'] - session['wait_until'])}")
        print()
    
    if active_sessions:
        print("ACTIVE SESSIONS:")
        for session in active_sessions:
            print_session_info(session)
            remaining = session['end_time'] - datetime.now().timestamp()
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
    
    # Show progressive penalty status
    from cli import penalty
    penalty_status = penalty.get_penalty_status(config)
    if penalty_status:
        print(f"\nProgressive penalty:")
        print(f"  Unblocks today: {penalty_status['unblocks_today']}")
        penalty_seconds = int(penalty_status['current_penalty'] * 60)
        print(f"  Current penalty: +{penalty_seconds} seconds")
        print(f"  Resets in: {penalty_status['reset_in']}")
        print(f"  Per unblock: +{penalty_status['per_unblock']} seconds")


def find_session_by_target(target, sessions):
    """Find a session that contains domains for the given target."""
    for session in sessions:
        # Check if any of the session's domains match the target
        for domain in session['domains']:
            if target in domain or domain in target:
                return session
    return None


def cmd_cancel(config, args):
    """Cancel session(s)."""
    if args.target:
        # Check if it's a number (session ID)
        try:
            session_id = int(args.target)
            # Cancel by ID
            session = db.get_session_info(session_id)
            if not session:
                print(f"Session {session_id} not found")
                sys.exit(1)
            
            db.cancel_session(session_id)
            print(f"Cancelled session {session_id}")
        except ValueError:
            # Cancel by target name
            active = db.get_active_sessions()
            pending = db.get_pending_sessions()
            all_sessions = active + pending
            
            # Try to find a session matching the target
            session = find_session_by_target(args.target, all_sessions)
            
            if not session:
                print(f"No session found for '{args.target}'")
                sys.exit(1)
            
            db.cancel_session(session['id'])
            print(f"Cancelled session {session['id']} for {args.target}")
    else:
        # Cancel all
        active = db.get_active_sessions()
        pending = db.get_pending_sessions()
        all_sessions = active + pending
        
        if not all_sessions:
            print("No sessions to cancel")
            return
        
        for session in all_sessions:
            db.cancel_session(session['id'])
        
        print(f"Cancelled {len(all_sessions)} session(s)")


def cmd_replace(config, args):
    """Replace a pending session with new targets."""
    pending_sessions = db.get_pending_sessions()
    active_sessions = db.get_active_sessions()
    
    # Handle different ways to identify the session to replace
    session_to_replace = None
    
    # Check if it's a number (session ID) or name
    try:
        session_id = int(args.old)
        # Replace by ID - check pending first
        for session in pending_sessions:
            if session['id'] == session_id:
                session_to_replace = session
                break
        
        if not session_to_replace:
            # Check if it's active (to give better error message)
            for session in active_sessions:
                if session['id'] == session_id:
                    print(f"Cannot replace session {session_id} - already active")
                    sys.exit(1)
            
            print(f"Session {session_id} not found")
            sys.exit(1)
    except ValueError:
        # Replace by target name
        session_to_replace = find_session_by_target(args.old, pending_sessions)
        if not session_to_replace:
            # Check active sessions for better error message
            active_match = find_session_by_target(args.old, active_sessions)
            if active_match:
                print(f"Cannot replace session for '{args.old}' - already active")
                sys.exit(1)
            
            print(f"No pending session found for '{args.old}'")
            sys.exit(1)
    
    # Get the profile and timing from the original session
    profile_name = session_to_replace['session_type']
    profile = config.profiles.get(profile_name, {})
    
    # Resolve new targets
    try:
        domains, all_tags = config.resolve_targets(args.new_targets, profile_name)
    except ValueError as e:
        print(f"Error: {e}")
        print("Available targets:")
        print(f"  Domains/groups: {', '.join(sorted(config.domains.keys()))}")
        sys.exit(1)
    
    if not domains:
        print("No domains to replace with")
        sys.exit(1)
    
    # Calculate wait time from original session
    original_wait_remaining = session_to_replace['wait_until'] - datetime.now().timestamp()
    wait_minutes = max(0, original_wait_remaining / 60)  # Keep original wait time
    duration = session_to_replace['end_time'] - session_to_replace['wait_until']
    duration_minutes = duration / 60
    
    # Cancel old session
    db.cancel_session(session_to_replace['id'])
    
    # Create new session with same timing
    new_session_id = db.add_unblock_session(
        domains,
        duration_minutes,
        wait_minutes,
        profile_name,
        is_all_domains=False,
        target_name=' '.join(args.new_targets)
    )
    
    print(f"Replaced session {session_to_replace['id']} with new session {new_session_id}")
    print(f"New targets: {', '.join(args.new_targets)}")
    if wait_minutes > 0:
        print(f"Starts in: {format_time_remaining(wait_minutes * 60)}")


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
  sudo taviblock cancel 42                  # Cancel session by ID
  sudo taviblock cancel slack               # Cancel session by name
  sudo taviblock cancel                     # Cancel all sessions
  sudo taviblock replace 42 reddit         # Replace pending session 42 with reddit
  sudo taviblock replace slack gmail       # Replace pending slack with gmail
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
    # Make it accept either a number (session ID) or string (target name)
    parser_cancel.add_argument('target', nargs='?', help='Session ID or domain/group name to cancel')
    
    # replace
    parser_replace = subparsers.add_parser('replace', help='Replace a pending session')
    parser_replace.add_argument('old', help='Session ID (number) or domain/group name to replace')
    parser_replace.add_argument('new_targets', nargs='+', help='New domains/groups to unblock')
    
    # daemon
    parser_daemon = subparsers.add_parser('daemon', help='Control daemon')
    parser_daemon.add_argument('action', choices=['start', 'stop', 'restart', 'logs'])
    
    # Check if we should use default profile
    default_profile = config.get_default_profile()
    if default_profile and len(sys.argv) > 1:
        # Get all valid commands (profiles + built-in commands)
        valid_commands = config.get_profile_names() + ['status', 'cancel', 'replace', 'daemon']
        
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
        cmd_cancel(config, args)
    elif args.command == 'replace':
        cmd_replace(config, args)
    elif args.command == 'daemon':
        cmd_daemon(args)
    else:
        # It's a profile command
        targets = getattr(args, 'targets', [])
        cmd_profile(config, args.command, targets)


if __name__ == '__main__':
    main()