#!/bin/bash

# Install enhanced protection for taviblock daemon
# This script must be run as root

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" 
   exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Installing taviblock enhanced protection..."

# 1. Update the main daemon plist with enhanced settings
echo "Updating daemon configuration..."
cp "$SCRIPT_DIR/enhanced-daemon.plist" "/Library/LaunchDaemons/com.taviblock.daemon.plist"
chmod 644 "/Library/LaunchDaemons/com.taviblock.daemon.plist"
chown root:wheel "/Library/LaunchDaemons/com.taviblock.daemon.plist"

# 2. Install watchdog service
echo "Installing watchdog service..."
cp "$SCRIPT_DIR/com.taviblock.watchdog.plist" "/Library/LaunchDaemons/com.taviblock.watchdog.plist"
chmod 644 "/Library/LaunchDaemons/com.taviblock.watchdog.plist"
chown root:wheel "/Library/LaunchDaemons/com.taviblock.watchdog.plist"

# 3. Make scripts executable
chmod +x "$SCRIPT_DIR/cli/daemon.py"
chmod +x "$SCRIPT_DIR/cli/watchdog.py"
chmod +x "$SCRIPT_DIR/cli/process_monitor.py"

# 4. Reload services
echo "Reloading services..."
launchctl unload "/Library/LaunchDaemons/com.taviblock.daemon.plist" 2>/dev/null
launchctl unload "/Library/LaunchDaemons/com.taviblock.watchdog.plist" 2>/dev/null

launchctl load -w "/Library/LaunchDaemons/com.taviblock.daemon.plist"
launchctl load -w "/Library/LaunchDaemons/com.taviblock.watchdog.plist"

# 5. Create a cron job for additional monitoring (belt and suspenders)
echo "Setting up cron monitoring..."
CRON_CMD="*/1 * * * * /usr/bin/python3 $SCRIPT_DIR/cli/process_monitor.py >> /var/log/taviblock/cron_monitor.log 2>&1"
(crontab -l 2>/dev/null | grep -v "process_monitor.py"; echo "$CRON_CMD") | crontab -

# 6. Set up System Integrity Protection notice
echo "
================================================================
IMPORTANT: Additional Protection Steps
================================================================

To make taviblock even more resistant to bypass:

1. Enable System Integrity Protection (SIP) if not already enabled:
   - Restart your Mac and hold Command+R during startup
   - Open Terminal from Utilities menu
   - Run: csrutil enable
   - Restart

2. Consider using Parental Controls:
   - System Preferences > Users & Groups > Enable Parental Controls
   - This adds an additional layer of system-level protection

3. Remove sudo privileges from your user account:
   - Only use an admin account when absolutely necessary
   - This prevents casual 'sudo kill' commands

4. The daemon now:
   - Ignores common kill signals (SIGINT, SIGQUIT, SIGTSTP)
   - Has a watchdog process that monitors and restarts it
   - Uses launchd KeepAlive to auto-restart
   - Has a cron job as backup monitoring

To stop the daemon properly:
   sudo launchctl unload /Library/LaunchDaemons/com.taviblock.daemon.plist
   sudo launchctl unload /Library/LaunchDaemons/com.taviblock.watchdog.plist

================================================================
"

echo "Enhanced protection installed successfully!"