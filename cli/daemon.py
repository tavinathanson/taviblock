#!/usr/bin/env python3
import time
import os
import sys
import signal
import logging
from pathlib import Path
from datetime import datetime
import subprocess
import db
from taviblock import read_config, generate_block_entries, HOSTS_PATH, BLOCKER_START, BLOCKER_END, CONFIG_FILE_DEFAULT

# Logging setup
LOG_DIR = Path("/var/log/taviblock")
LOG_DIR.mkdir(exist_ok=True, parents=True)
LOG_PATH = LOG_DIR / "daemon.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class TaviblockDaemon:
    def __init__(self):
        self.running = True
        self.config_file = CONFIG_FILE_DEFAULT
        self.notified_sessions = set()  # Track sessions we've notified about
        
        # Make daemon harder to kill - ignore common signals
        signal.signal(signal.SIGINT, signal.SIG_IGN)  # Ignore Ctrl+C
        signal.signal(signal.SIGQUIT, signal.SIG_IGN)  # Ignore Ctrl+\
        signal.signal(signal.SIGTSTP, signal.SIG_IGN)  # Ignore Ctrl+Z
        
        # Only handle SIGTERM for graceful shutdown (from launchctl)
        signal.signal(signal.SIGTERM, self.handle_signal)
        
    def handle_signal(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        
    def update_hosts_file(self, domains_to_block):
        """Update /etc/hosts with the current blocking rules."""
        try:
            # Read current hosts file
            with open(HOSTS_PATH, 'r') as f:
                lines = f.readlines()
            
            # Remove existing block section
            new_lines = []
            in_block_section = False
            for line in lines:
                if line.strip() == BLOCKER_START:
                    in_block_section = True
                    continue
                if line.strip() == BLOCKER_END:
                    in_block_section = False
                    continue
                if not in_block_section:
                    new_lines.append(line.rstrip('\n'))
            
            # Add new block section with domains to block
            if domains_to_block:
                block_entries = generate_block_entries(domains_to_block)
                new_lines.append(BLOCKER_START)
                new_lines.extend(block_entries)
                new_lines.append(BLOCKER_END)
            
            # Write back to hosts file
            with open(HOSTS_PATH, 'w') as f:
                f.write('\n'.join(new_lines) + '\n')
                
            logger.info(f"Updated hosts file with {len(domains_to_block)} blocked domains")
            
        except Exception as e:
            logger.error(f"Error updating hosts file: {e}")
    
    def get_domains_to_block(self):
        """Calculate which domains should currently be blocked."""
        # Start with all domains from config
        all_domains = set(read_config(self.config_file))
        
        # Get domains that are currently unblocked
        unblocked_domains = set(db.get_all_unblocked_domains())
        
        # Return domains that should be blocked (all minus unblocked)
        return list(all_domains - unblocked_domains)
    
    def close_chrome_tabs_for_domains(self, domains):
        """Close Chrome tabs for multiple domains using a single AppleScript call."""
        if not domains:
            return
            
        try:
            # Build the URL checking conditions
            conditions = []
            for domain in domains:
                conditions.append(f'(tabURL contains "://{domain}" or tabURL contains "://www.{domain}")')
            
            condition_string = " or ".join(conditions)
            
            script = f'''
            if application "Google Chrome" is running then
                tell application "Google Chrome"
                    repeat with w in windows
                        set tabsToClose to {{}}
                        repeat with t in tabs of w
                            set tabURL to URL of t
                            if {condition_string} then
                                set end of tabsToClose to t
                            end if
                        end repeat
                        repeat with t in tabsToClose
                            close t
                        end repeat
                    end repeat
                end tell
            end if
            '''
            subprocess.run(['osascript', '-e', script], capture_output=True)
            logger.debug(f"Closed Chrome tabs for {len(domains)} blocked domains")
        except Exception as e:
            logger.error(f"Error closing Chrome tabs: {e}")
    
    def kill_slack_if_blocked(self, blocked_domains):
        """Kill Slack application if slack.com is blocked."""
        if 'slack.com' in blocked_domains:
            try:
                # Check if Slack is running
                result = subprocess.run(['pgrep', '-x', 'Slack'], capture_output=True)
                if result.returncode == 0:
                    subprocess.run(['killall', 'Slack'])
                    logger.info("Killed Slack application (slack.com is blocked)")
            except Exception as e:
                logger.error(f"Error killing Slack: {e}")
    
    def enforce_blocks(self, blocked_domains):
        """Close browser tabs and applications for blocked domains."""
        # Close Chrome tabs for all blocked domains in one call
        self.close_chrome_tabs_for_domains(blocked_domains)
        
        # Kill specific applications
        self.kill_slack_if_blocked(blocked_domains)
    
    def check_active_chrome_tab(self, domain):
        """Check if a Chrome tab with this domain is currently active."""
        try:
            script = f'''
            tell application "Google Chrome"
                if it is running then
                    set activeURL to URL of active tab of front window
                    if activeURL contains "://{domain}" or activeURL contains "://www.{domain}" then
                        return "true"
                    end if
                end if
            end tell
            return "false"
            '''
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            return result.stdout.strip() == "true"
        except:
            return False
    
    def check_slack_frontmost(self):
        """Check if Slack is the frontmost application."""
        try:
            script = '''
            tell application "System Events"
                set frontApp to name of first application process whose frontmost is true
                if frontApp is "Slack" then
                    return "true"
                end if
            end tell
            return "false"
            '''
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            return result.stdout.strip() == "true"
        except:
            return False
    
    def send_terminal_notification(self, session_id, domains, app_type):
        """Open a terminal window with interactive notification."""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            notification_script = os.path.join(script_dir, 'open_terminal_notification.py')
            
            # Run the notification script as the logged-in user, not root
            # Get the current console user
            console_user = subprocess.run(
                ['stat', '-f', '%Su', '/dev/console'], 
                capture_output=True, text=True
            ).stdout.strip()
            
            # Use sudo to run as the console user
            subprocess.Popen([
                'sudo', '-u', console_user,
                'python3', notification_script,
                str(session_id),
                domains,
                app_type
            ])
            
            logger.info(f"Opened terminal notification for session {session_id}")
        except Exception as e:
            logger.error(f"Error opening terminal notification: {e}")
    
    def check_ending_sessions(self):
        """Check for sessions ending soon and notify if actively used."""
        active_sessions = db.get_active_sessions()
        current_time = datetime.now().timestamp()
        
        # Clean up notified sessions that have ended
        sessions_to_remove = set()
        for session_id in self.notified_sessions:
            session_exists = any(s['id'] == session_id for s in active_sessions)
            if not session_exists:
                sessions_to_remove.add(session_id)
        self.notified_sessions -= sessions_to_remove
        
        for session in active_sessions:
            time_remaining = session['end_time'] - current_time
            
            # Skip bypass sessions - they shouldn't have notifications
            if session['session_type'] == 'bypass':
                continue
            
            # Check if session ends in 60-65 seconds (give 5 second window)
            if 60 <= time_remaining <= 65 and session['id'] not in self.notified_sessions:
                # Check if any domain in this session is actively used
                for domain in session['domains']:
                    if domain == 'slack.com' and self.check_slack_frontmost():
                        self.send_terminal_notification(
                            session['id'],
                            'slack.com',
                            'slack'
                        )
                        logger.info(f"Notified about Slack closing (session {session['id']})")
                        self.notified_sessions.add(session['id'])
                        break
                    elif self.check_active_chrome_tab(domain):
                        self.send_terminal_notification(
                            session['id'],
                            domain,
                            'tab'
                        )
                        logger.info(f"Notified about {domain} tabs closing (session {session['id']})")
                        self.notified_sessions.add(session['id'])
                        break
    
    def count_chrome_tabs(self, domain):
        """Count how many Chrome tabs are open for a domain."""
        try:
            script = f'''
            tell application "Google Chrome"
                set tabCount to 0
                repeat with w in windows
                    repeat with t in tabs of w
                        set tabURL to URL of t
                        if tabURL contains "://{domain}" or tabURL contains "://www.{domain}" then
                            set tabCount to tabCount + 1
                        end if
                    end repeat
                end repeat
                return tabCount
            end tell
            '''
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            return int(result.stdout.strip())
        except:
            return 0
    
    def run(self):
        """Main daemon loop."""
        logger.info("Taviblock daemon started")
        
        # Initialize database
        db.init_db()
        
        # Main loop
        last_update = None
        while self.running:
            try:
                # Clean expired sessions
                db.clean_expired_sessions()
                
                # Get current state
                domains_to_block = self.get_domains_to_block()
                
                # Only update if something changed or it's the first run
                current_state = frozenset(domains_to_block)
                if last_update != current_state:
                    self.update_hosts_file(domains_to_block)
                    last_update = current_state
                
                # Enforce blocks by closing tabs/apps
                self.enforce_blocks(domains_to_block)
                
                # Check for sessions ending soon
                self.check_ending_sessions()
                
                # Log active sessions periodically
                active_sessions = db.get_active_sessions()
                if active_sessions:
                    logger.debug(f"Active sessions: {len(active_sessions)}")
                    for session in active_sessions:
                        remaining = session['end_time'] - datetime.now().timestamp()
                        logger.debug(f"  - {session['session_type']}: {session['domains']} ({int(remaining/60)} min remaining)")
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
            
            # Sleep for 1 second before next check
            time.sleep(1)
        
        # Restore full blocking on shutdown
        logger.info("Restoring full blocking before shutdown")
        all_domains = read_config(self.config_file)
        self.update_hosts_file(all_domains)
        logger.info("Taviblock daemon stopped")

def main():
    """Entry point for the daemon."""
    if os.geteuid() != 0:
        print("This daemon must be run as root")
        sys.exit(1)
    
    daemon = TaviblockDaemon()
    daemon.run()

if __name__ == "__main__":
    main()