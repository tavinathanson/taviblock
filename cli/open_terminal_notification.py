#!/usr/bin/python3
"""
Opens a terminal window with the notification script.
Detects and uses the user's preferred terminal (iTerm2 or Terminal.app).
"""
import sys
import os
import subprocess

def check_iterm_installed():
    """Check if iTerm2 is installed."""
    try:
        subprocess.run(['osascript', '-e', 'tell application "iTerm" to version'], 
                      capture_output=True, check=True)
        return True
    except:
        return False

def open_iterm_notification(script_path, args):
    """Open notification in iTerm2."""
    applescript = f'''
    tell application "iTerm"
        create window with default profile
        tell current session of current window
            write text "python3 {script_path} {' '.join(args)}"
        end tell
    end tell
    '''
    subprocess.run(['osascript', '-e', applescript])

def open_terminal_notification(script_path, args):
    """Open notification in Terminal.app."""
    # Build the command
    cmd = f'python3 {script_path} {" ".join(args)}'
    
    applescript = f'''
    tell application "Terminal"
        do script "{cmd}"
        activate
    end tell
    '''
    subprocess.run(['osascript', '-e', applescript])

def main():
    if len(sys.argv) < 4:
        print("Usage: open_terminal_notification.py <session_id> <domains> <app_type>")
        sys.exit(1)
    
    # Get the path to notify_extend.py
    script_dir = os.path.dirname(os.path.abspath(__file__))
    notify_script = os.path.join(script_dir, 'notify_extend.py')
    
    # Pass along the arguments
    args = sys.argv[1:]
    
    # Detect and use preferred terminal
    if check_iterm_installed():
        open_iterm_notification(notify_script, args)
    else:
        open_terminal_notification(notify_script, args)

if __name__ == "__main__":
    main()