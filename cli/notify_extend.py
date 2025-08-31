#!/usr/bin/env python3
"""
Interactive notification script for extending block sessions.
This script is called by the daemon to show a terminal popup.
"""
import sys
import os
import subprocess
import time

def main():
    if len(sys.argv) < 4:
        print("Usage: notify_extend.py <session_id> <domains> <app_type>")
        sys.exit(1)
    
    session_id = sys.argv[1]
    domains = sys.argv[2]
    app_type = sys.argv[3]  # 'tab' or 'slack'
    
    print("\n" + "="*60)
    print("⚠️  TAVIBLOCK NOTIFICATION  ⚠️")
    print("="*60)
    print()
    
    if app_type == 'slack':
        print("Slack will be CLOSED in 1 minute!")
    else:
        print(f"{domains} tabs will be CLOSED in 1 minute!")
    
    print()
    print("Choose an option to extend the session:")
    print()
    print("  [1] Extend 5 minutes")
    print("  [2] Extend 30 minutes")
    print("  [3] Let it close (do nothing)")
    print()
    
    # Set a timeout for user input
    print("You have 30 seconds to decide (default: let it close)")
    print()
    
    # Use a simple timeout mechanism
    import select
    import termios
    import tty
    
    # Save terminal settings
    old_settings = termios.tcgetattr(sys.stdin)
    
    try:
        tty.setraw(sys.stdin.fileno())
        
        # Wait for input with timeout
        ready, _, _ = select.select([sys.stdin], [], [], 30)
        
        if ready:
            choice = sys.stdin.read(1)
        else:
            choice = '3'  # Default to doing nothing
    finally:
        # Restore terminal settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    
    print()  # New line after input
    
    if choice == '1':
        print("Extending session by 5 minutes...")
        # Set environment variable to bypass active check since we already verified it
        env = os.environ.copy()
        env['TAVIBLOCK_EXTEND_FROM_NOTIFICATION'] = '1'
        subprocess.run(['sudo', '-E', 'block', 'extend', str(session_id), '5'], env=env)
        print("✓ Extended by 5 minutes")
    elif choice == '2':
        print("Extending session by 30 minutes...")
        # Set environment variable to bypass active check since we already verified it
        env = os.environ.copy()
        env['TAVIBLOCK_EXTEND_FROM_NOTIFICATION'] = '1'
        subprocess.run(['sudo', '-E', 'block', 'extend', str(session_id), '30'], env=env)
        print("✓ Extended by 30 minutes")
    else:
        print("No extension. Session will end as scheduled.")
    
    print()
    print("This window will close in 3 seconds...")
    time.sleep(3)

if __name__ == "__main__":
    main()