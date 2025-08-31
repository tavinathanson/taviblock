#!/usr/bin/env python3
import time
import os
import sys
import signal
import subprocess
import logging
from pathlib import Path

LOG_DIR = Path("/var/log/taviblock")
LOG_DIR.mkdir(exist_ok=True, parents=True)
LOG_PATH = LOG_DIR / "watchdog.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class TaviblockWatchdog:
    def __init__(self):
        self.running = True
        self.daemon_path = "/Users/tavi/drive/repos/taviblock_ws/taviblock/cli/daemon.py"
        self.daemon_process = None
        
        # Ignore common signals to make watchdog harder to kill
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGQUIT, signal.SIG_IGN)
        signal.signal(signal.SIGTSTP, signal.SIG_IGN)
        
        # Only respond to SIGTERM for clean shutdown
        signal.signal(signal.SIGTERM, self.handle_signal)
        
    def handle_signal(self, signum, frame):
        logger.info(f"Watchdog received signal {signum}, shutting down...")
        self.running = False
        
    def start_daemon(self):
        """Start the main daemon process."""
        try:
            self.daemon_process = subprocess.Popen(
                [sys.executable, self.daemon_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            logger.info(f"Started daemon with PID {self.daemon_process.pid}")
            return True
        except Exception as e:
            logger.error(f"Failed to start daemon: {e}")
            return False
    
    def check_daemon_health(self):
        """Check if daemon is still running."""
        if self.daemon_process is None:
            return False
            
        # Check if process is still alive
        poll_result = self.daemon_process.poll()
        if poll_result is not None:
            logger.warning(f"Daemon died with exit code {poll_result}")
            return False
            
        # Additional check: verify process exists
        try:
            os.kill(self.daemon_process.pid, 0)
            return True
        except ProcessLookupError:
            logger.warning("Daemon process not found")
            return False
    
    def restart_daemon(self):
        """Restart the daemon if it's not running."""
        if not self.check_daemon_health():
            logger.info("Daemon is not running, restarting...")
            
            # Clean up old process if needed
            if self.daemon_process:
                try:
                    self.daemon_process.terminate()
                    self.daemon_process.wait(timeout=5)
                except:
                    try:
                        self.daemon_process.kill()
                        self.daemon_process.wait(timeout=2)
                    except:
                        pass
            
            # Start new daemon
            return self.start_daemon()
        return True
    
    def run(self):
        """Main watchdog loop."""
        logger.info("Taviblock watchdog started")
        
        # Start daemon initially
        self.start_daemon()
        
        while self.running:
            try:
                # Check and restart daemon if needed
                self.restart_daemon()
                
                # Also check if LaunchDaemon is still loaded
                result = subprocess.run(
                    ['launchctl', 'list', 'com.taviblock.daemon'],
                    capture_output=True
                )
                if result.returncode != 0:
                    logger.warning("LaunchDaemon not loaded, reloading...")
                    subprocess.run([
                        'launchctl', 'load', '-w',
                        '/Library/LaunchDaemons/com.taviblock.daemon.plist'
                    ])
                
                # Sleep before next check
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error in watchdog loop: {e}")
                time.sleep(5)
        
        # Clean shutdown
        if self.daemon_process:
            logger.info("Stopping daemon...")
            self.daemon_process.terminate()
            self.daemon_process.wait(timeout=10)
        
        logger.info("Taviblock watchdog stopped")

def main():
    if os.geteuid() != 0:
        print("This watchdog must be run as root")
        sys.exit(1)
    
    watchdog = TaviblockWatchdog()
    watchdog.run()

if __name__ == "__main__":
    main()