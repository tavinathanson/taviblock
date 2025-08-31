#!/usr/bin/env python3
"""
Block - Streamlined domain blocking tool

Usage:
    block                         # Show status
    block gmail                   # Unblock gmail
    block gmail slack             # Unblock multiple
    block bypass                  # Emergency 5-min unblock
    block peek                    # Quick 60-second peek
    block cancel                  # Cancel all sessions
    block cancel 42               # Cancel specific session
    block daemon logs             # View logs
    block unblock gmail -w 0      # Advanced: no wait
"""

import argparse
import sys
import os
from datetime import datetime
from pathlib import Path
import subprocess

# Add cli directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db

# Constants
HOSTS_PATH = "/etc/hosts"
BLOCKER_START = "# BLOCKER START"
BLOCKER_END = "# BLOCKER END"
CONFIG_FILE_DEFAULT = str(Path(__file__).resolve().parent.parent / "config.txt")


def require_admin():
    """Ensure the script is run as root."""
    if os.geteuid() != 0:
        print("This command requires sudo. Please run: sudo block ...")
        sys.exit(1)


def read_config(config_file):
    """Read the config file and return a list of domains to block."""
    if not os.path.exists(config_file):
        print(f"Config file {config_file} does not exist.")
        sys.exit(1)
    domains = []
    with open(config_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if line.startswith('[') and line.endswith(']'):
                    continue
                domains.append(line)
    return domains


def read_config_sections(config_file):
    """Read config file and return dictionary of sections to domains."""
    sections = {}
    current_section = "default"
    sections[current_section] = []
    with open(config_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1].strip()
                if current_section not in sections:
                    sections[current_section] = []
            else:
                sections[current_section].append(line)
    return sections


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


def is_ultra_distracting(domain, sections):
    """Check if a domain is in the ultra_distracting section."""
    if 'ultra_distracting' in sections:
        return domain in sections['ultra_distracting']
    return False


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


def cmd_status(args):
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
            print(f"    Domains: {', '.join(session['domains'])}")
            print(f"    Starts in: {format_time_remaining(wait_remaining)}")
            print(f"    Duration: {format_time_remaining(session['end_time'] - session['wait_until'])}")
        print()
    
    if active_sessions:
        print("ACTIVE SESSIONS:")
        for session in active_sessions:
            remaining = session['end_time'] - datetime.now().timestamp()
            print(f"  [{session['id']}] {session['session_type']}:")
            print(f"    Domains: {', '.join(session['domains'])}")
            print(f"    Remaining: {format_time_remaining(remaining)}")
        print()
        
        all_unblocked = db.get_all_unblocked_domains()
        print(f"Currently unblocked: {', '.join(sorted(all_unblocked))}")
    
    available, remaining = db.check_bypass_cooldown()
    if not available:
        print(f"\nBypass cooldown: {format_time_remaining(remaining)} remaining")


def cmd_unblock(args, targets=None):
    """Unblock specified domains/sections."""
    if targets is None:
        targets = args.targets
        
    sections = read_config_sections(args.config)
    domains_list = read_config(args.config)
    
    # Process targets
    all_domains = set()
    for target in targets:
        target = target.strip()
        
        # Check sections
        if target in sections:
            all_domains.update(sections[target])
        elif not target.endswith('.com') and (target + '.com') in sections:
            target = target + '.com'
            all_domains.update(sections[target])
        # Check single domains
        elif target in domains_list:
            all_domains.add(target)
        elif not target.endswith('.com') and (target + '.com') in domains_list:
            all_domains.add(target + '.com')
        else:
            print(f"Warning: '{target}' not found in config")
    
    if not all_domains:
        print("No valid domains found")
        sys.exit(1)
    
    # Check if these domains are already in active or pending sessions
    active_sessions = db.get_active_sessions()
    pending_sessions = db.get_pending_sessions()
    
    # Check each domain
    for session_list, session_type in [(active_sessions, "active"), (pending_sessions, "pending")]:
        for session in session_list:
            # Check if this is an IDENTICAL session (same domains, not just overlapping)
            if set(session['domains']) == all_domains and session['session_type'] != 'bypass':
                if session_type == "active":
                    remaining = session['end_time'] - datetime.now().timestamp()
                    print(f"'{', '.join(targets)}' already unblocked in session {session['id']}")
                    print(f"Time remaining: {format_time_remaining(remaining)}")
                else:
                    wait_remaining = session['wait_until'] - datetime.now().timestamp()
                    print(f"'{', '.join(targets)}' already pending in session {session['id']}")
                    print(f"Starts in: {format_time_remaining(wait_remaining)}")
                    duration = session['end_time'] - session['wait_until']
                    print(f"Duration: {format_time_remaining(duration)}")
                return
    
    # Check session limit (default 4)
    total_sessions = len(active_sessions) + len(pending_sessions)
    session_limit = 4
    
    # Check if we should replace existing sessions
    replace_id = getattr(args, 'replace', None)
    
    if replace_id is not None:
        # Replace a specific session
        found = False
        for session in active_sessions + pending_sessions:
            if session['id'] == replace_id:
                db.cancel_session(session['id'])
                print(f"Replaced session {replace_id}")
                found = True
                break
        if not found:
            print(f"Session {replace_id} not found")
            return
    elif total_sessions >= session_limit:
        print(f"Session limit reached ({session_limit} sessions). Current sessions:")
        print()
        cmd_status(args)
        print()
        print("Options:")
        print(f"  1. Cancel a session: block cancel <id>")
        print(f"  2. Replace a session: block {' '.join(targets)} -r <id>")
        print(f"  3. Cancel all sessions: block cancel")
        return
    
    # Determine wait time
    has_ultra = any(is_ultra_distracting(d, sections) for d in all_domains)
    
    wait = getattr(args, 'wait', None)
    if wait is None:
        if len(targets) == 1:
            wait = 30 if has_ultra else 5
        else:
            wait = 30 if has_ultra else 10
    
    duration = getattr(args, 'duration', None)
    if duration is None:
        duration = 30
    
    # Create session
    session_id = db.add_unblock_session(
        list(all_domains),
        duration,
        wait,
        'multiple' if len(targets) > 1 else 'single'
    )
    
    print(f"Unblock session created (ID: {session_id})")
    print(f"Targets: {', '.join(targets)}")
    print(f"Wait: {wait} minutes")
    print(f"Duration: {duration} minutes")
    
    if wait > 0:
        print(f"\nDomains will be unblocked in {wait} minutes")
    else:
        print("\nDomains are now unblocked")


def cmd_bypass(args):
    """Emergency 5-minute unblock (once per hour)."""
    available, remaining = db.check_bypass_cooldown()
    
    if not available:
        print(f"Bypass on cooldown: {format_time_remaining(remaining)} remaining")
        sys.exit(1)
    
    all_domains = read_config(args.config)
    
    session_id = db.add_unblock_session(
        all_domains,
        5,  # 5 minutes
        0,  # No wait
        'bypass'
    )
    
    db.set_bypass_used()
    
    print(f"Bypass activated! All domains unblocked for 5 minutes")
    print(f"Session ID: {session_id}")


def cmd_peek(args):
    """Quick 60-second peek after 60-second wait."""
    all_domains = read_config(args.config)
    
    session_id = db.add_unblock_session(
        all_domains,
        1,  # 1 minute duration
        1,  # 1 minute wait
        'peek'
    )
    
    print(f"Peek session created (ID: {session_id})")
    print("All domains will be unblocked in 60 seconds for 60 seconds")


def cmd_cancel(args, session_id=None):
    """Cancel session(s)."""
    if session_id is None:
        session_id = getattr(args, 'session_id', None)
        
    if session_id:
        session = db.get_session_info(session_id)
        if not session:
            print(f"Session {session_id} not found")
            sys.exit(1)
        
        db.cancel_session(session_id)
        print(f"Cancelled session {session_id}")
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


def check_daemon_running():
    """Check if the daemon is running and start it if not."""
    result = subprocess.run(['launchctl', 'list'], capture_output=True, text=True)
    if 'com.taviblock.daemon' not in result.stdout:
        print("Warning: Block daemon not running. Starting it now...")
        subprocess.run(['launchctl', 'load', '/Library/LaunchDaemons/com.taviblock.daemon.plist'],
                      stderr=subprocess.DEVNULL)
        # Give it a moment to start
        import time
        time.sleep(2)
        
        # Check again
        result = subprocess.run(['launchctl', 'list'], capture_output=True, text=True)
        if 'com.taviblock.daemon' not in result.stdout:
            print("ERROR: Failed to start daemon. Blocking may not work correctly.")
            print("Try: sudo block daemon restart")
            return False
    return True


def main():
    require_admin()
    
    # Initialize database
    db.init_db()
    
    # Check daemon is running (except for daemon commands)
    if len(sys.argv) < 2 or (len(sys.argv) >= 2 and sys.argv[1] != 'daemon'):
        check_daemon_running()
    
    # Handle simple command patterns first
    args = sys.argv[1:]
    
    if not args:
        # No args = status
        cmd_status(argparse.Namespace(config=CONFIG_FILE_DEFAULT))
        return
    
    # Single special commands
    if len(args) == 1:
        if args[0] == 'bypass':
            cmd_bypass(argparse.Namespace(config=CONFIG_FILE_DEFAULT))
            return
        elif args[0] == 'peek':
            cmd_peek(argparse.Namespace(config=CONFIG_FILE_DEFAULT))
            return
        elif args[0] == 'status':
            cmd_status(argparse.Namespace(config=CONFIG_FILE_DEFAULT))
            return
        elif args[0] == 'cancel':
            cmd_cancel(argparse.Namespace(config=CONFIG_FILE_DEFAULT), None)
            return
    
    # Cancel with ID
    if len(args) == 2 and args[0] == 'cancel':
        try:
            session_id = int(args[1])
            cmd_cancel(argparse.Namespace(config=CONFIG_FILE_DEFAULT), session_id)
            return
        except ValueError:
            pass
    
    # Daemon commands
    if args[0] == 'daemon' and len(args) >= 2:
        cmd_daemon(argparse.Namespace(action=args[1]))
        return
    
    # Full parser for complex commands
    parser = argparse.ArgumentParser(
        description="Block - Streamlined domain blocking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  block                    # Show status
  block gmail              # Unblock gmail
  block gmail slack        # Unblock multiple
  block bypass             # Emergency 5-min unblock
  block peek               # Quick 60-second peek
  block cancel             # Cancel all sessions
  block cancel 42          # Cancel specific session
  block daemon logs        # View logs
  block unblock gmail -w 0 # Advanced: no wait
"""
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # unblock (explicit)
    parser_unblock = subparsers.add_parser('unblock', help='Unblock domains/sections')
    parser_unblock.add_argument('targets', nargs='+', help='Domains or sections to unblock')
    parser_unblock.add_argument('-w', '--wait', type=int, help='Wait time in minutes')
    parser_unblock.add_argument('-d', '--duration', type=int, help='Duration in minutes')
    parser_unblock.add_argument('-r', '--replace', type=int, metavar='ID', help='Replace specific session by ID')
    parser_unblock.add_argument('--config', default=CONFIG_FILE_DEFAULT, help='Config file path')
    parser_unblock.set_defaults(func=cmd_unblock)
    
    # status
    parser_status = subparsers.add_parser('status', help='Show status')
    parser_status.add_argument('--config', default=CONFIG_FILE_DEFAULT, help='Config file path')
    parser_status.set_defaults(func=cmd_status)
    
    # bypass
    parser_bypass = subparsers.add_parser('bypass', help='Emergency 5-min unblock')
    parser_bypass.add_argument('--config', default=CONFIG_FILE_DEFAULT, help='Config file path')
    parser_bypass.set_defaults(func=cmd_bypass)
    
    # peek
    parser_peek = subparsers.add_parser('peek', help='Quick 60-second peek')
    parser_peek.add_argument('--config', default=CONFIG_FILE_DEFAULT, help='Config file path')
    parser_peek.set_defaults(func=cmd_peek)
    
    # cancel
    parser_cancel = subparsers.add_parser('cancel', help='Cancel sessions')
    parser_cancel.add_argument('session_id', nargs='?', type=int, help='Session ID')
    parser_cancel.add_argument('--all', action='store_true', help='Cancel all')
    parser_cancel.set_defaults(func=cmd_cancel)
    
    # daemon
    parser_daemon = subparsers.add_parser('daemon', help='Control daemon')
    parser_daemon.add_argument('action', choices=['start', 'stop', 'restart', 'logs'])
    parser_daemon.set_defaults(func=cmd_daemon)
    
    # If no recognized subcommand, assume it's targets for unblock
    if args and args[0] not in ['unblock', 'status', 'bypass', 'peek', 'cancel', 'daemon']:
        # Check for -r flag with ID in simple form
        replace_id = None
        targets = []
        i = 0
        while i < len(args):
            if args[i] in ['-r', '--replace']:
                if i + 1 < len(args) and args[i + 1].isdigit():
                    replace_id = int(args[i + 1])
                    i += 2
                else:
                    print("Error: -r requires a session ID")
                    return
            else:
                targets.append(args[i])
                i += 1
        
        # Treat as unblock targets
        cmd_unblock(argparse.Namespace(config=CONFIG_FILE_DEFAULT, wait=None, duration=None, replace=replace_id), targets)
        return
    
    # Parse and execute
    parsed_args = parser.parse_args()
    if hasattr(parsed_args, 'func'):
        parsed_args.func(parsed_args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()