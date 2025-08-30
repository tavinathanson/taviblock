#!/usr/bin/env python3
import time
import os
import sys
import signal
import logging
from pathlib import Path
from datetime import datetime
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
        signal.signal(signal.SIGTERM, self.handle_signal)
        signal.signal(signal.SIGINT, self.handle_signal)
        
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
                
                # Log active sessions periodically
                active_sessions = db.get_active_sessions()
                if active_sessions:
                    logger.debug(f"Active sessions: {len(active_sessions)}")
                    for session in active_sessions:
                        remaining = session['end_time'] - datetime.now().timestamp()
                        logger.debug(f"  - {session['session_type']}: {session['domains']} ({int(remaining/60)} min remaining)")
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
            
            # Sleep for 10 seconds before next check
            time.sleep(10)
        
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