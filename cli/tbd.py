#!/usr/bin/python3
"""
TBD - Taviblock Quick Commands

Usage:
    sudo tbd                    # Show status
    sudo tbd gmail              # Unblock gmail 
    sudo tbd gmail slack        # Unblock multiple targets
    sudo tbd bypass             # Emergency 5-minute unblock
    sudo tbd peek               # Quick 60-second peek
    sudo tbd cancel             # Cancel all sessions
    sudo tbd cancel 42          # Cancel session 42
"""

import sys
import os
import subprocess

def main():
    # Check for root
    if os.geteuid() != 0:
        print("This command must be run with sudo")
        sys.exit(1)
    
    # Just use the taviblock command directly
    args = sys.argv[1:]
    
    if not args:
        # No arguments = show status
        subprocess.run(['taviblock', 'status'])
    
    elif args[0] == 'bypass':
        # Bypass command
        subprocess.run(['taviblock', 'bypass'])
    
    elif args[0] == 'peek':
        # Peek command
        subprocess.run(['taviblock', 'peek'])
    
    elif args[0] == 'cancel':
        # Cancel command
        if len(args) > 1:
            # Cancel specific session
            subprocess.run(['taviblock', 'cancel', args[1]])
        else:
            # Cancel all
            subprocess.run(['taviblock', 'cancel', '--all'])
    
    else:
        # Assume it's an unblock command with targets
        cmd = ['taviblock', 'unblock'] + args
        subprocess.run(cmd)

if __name__ == '__main__':
    main() 