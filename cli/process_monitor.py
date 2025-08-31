#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import logging
from pathlib import Path

LOG_DIR = Path("/var/log/taviblock")
LOG_DIR.mkdir(exist_ok=True, parents=True)
LOG_PATH = LOG_DIR / "process_monitor.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class ProcessMonitor:
    def __init__(self):
        self.daemon_plist = "/Library/LaunchDaemons/com.taviblock.daemon.plist"
        self.watchdog_plist = "/Library/LaunchDaemons/com.taviblock.watchdog.plist"
        
    def check_process_running(self, process_name):
        """Check if a process is running."""
        try:
            result = subprocess.run(
                ['pgrep', '-f', process_name],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except:
            return False
    
    def check_launchd_service(self, service_name):
        """Check if a launchd service is loaded."""
        try:
            result = subprocess.run(
                ['launchctl', 'list', service_name],
                capture_output=True
            )
            return result.returncode == 0
        except:
            return False
    
    def load_launchd_service(self, plist_path, service_name):
        """Load a launchd service."""
        try:
            # First unload if it exists
            if self.check_launchd_service(service_name):
                subprocess.run(['launchctl', 'unload', plist_path])
                time.sleep(1)
            
            # Load the service
            result = subprocess.run(
                ['launchctl', 'load', '-w', plist_path],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                logger.info(f"Loaded {service_name}")
                return True
            else:
                logger.error(f"Failed to load {service_name}: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error loading {service_name}: {e}")
            return False
    
    def ensure_services_running(self):
        """Ensure both daemon and watchdog are running."""
        # Check daemon
        if not self.check_launchd_service('com.taviblock.daemon'):
            logger.warning("Daemon service not loaded, reloading...")
            self.load_launchd_service(self.daemon_plist, 'com.taviblock.daemon')
        elif not self.check_process_running('daemon.py'):
            logger.warning("Daemon process not running, restarting service...")
            subprocess.run(['launchctl', 'kickstart', '-k', 'system/com.taviblock.daemon'])
        
        # Check watchdog
        if not self.check_launchd_service('com.taviblock.watchdog'):
            logger.warning("Watchdog service not loaded, reloading...")
            self.load_launchd_service(self.watchdog_plist, 'com.taviblock.watchdog')
        elif not self.check_process_running('watchdog.py'):
            logger.warning("Watchdog process not running, restarting service...")
            subprocess.run(['launchctl', 'kickstart', '-k', 'system/com.taviblock.watchdog'])
    
    def run(self):
        """Main monitoring loop."""
        logger.info("Process monitor started")
        
        while True:
            try:
                self.ensure_services_running()
                time.sleep(5)  # Check every 5 seconds
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                time.sleep(10)

def main():
    if os.geteuid() != 0:
        print("This monitor must be run as root")
        sys.exit(1)
    
    monitor = ProcessMonitor()
    monitor.run()

if __name__ == "__main__":
    main()