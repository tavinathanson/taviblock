#!/bin/bash

# Universal setup script for Taviblock
# Handles both fresh installs and migrations

set -e

echo "=== Taviblock Setup ==="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run this script with sudo"
    exit 1
fi

# Get the directory where this script is located
REPO_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run uninstall first to clean up any existing installation
echo "1. Running uninstall to clean up any existing installation..."
if [ -f "$REPO_DIR/uninstall.sh" ]; then
    bash "$REPO_DIR/uninstall.sh"
    echo ""
fi

echo "2. Creating directories..."
mkdir -p /var/lib/taviblock
mkdir -p /var/log/taviblock
mkdir -p /etc/taviblock
chmod 755 /var/lib/taviblock
chmod 755 /var/log/taviblock
chmod 755 /etc/taviblock

echo "3. Copying configuration file..."
if [ -f "$REPO_DIR/config.yaml" ]; then
    cp "$REPO_DIR/config.yaml" /etc/taviblock/config.yaml
    chmod 644 /etc/taviblock/config.yaml
    echo "✓ Config file copied to /etc/taviblock/config.yaml"
else
    echo "Warning: config.yaml not found in $REPO_DIR"
fi

echo "4. Installing taviblock Python package..."
cd "$REPO_DIR"
/usr/bin/python3 setup.py install

echo "5. Making scripts executable..."
chmod +x "$REPO_DIR/cli/taviblock.py"
chmod +x "$REPO_DIR/cli/daemon.py"
chmod +x "$REPO_DIR/cli/db.py"
chmod +x "$REPO_DIR/cli/watchdog.py"
chmod +x "$REPO_DIR/cli/process_monitor.py"

echo "6. Initializing database..."
/usr/bin/python3 "$REPO_DIR/cli/db.py"

echo "7. Installing daemons with enhanced protection..."
# Use enhanced daemon configuration if available, otherwise use standard
if [ -f "$REPO_DIR/enhanced-daemon.plist" ]; then
    cp "$REPO_DIR/enhanced-daemon.plist" /Library/LaunchDaemons/com.taviblock.daemon.plist
else
    cp "$REPO_DIR/com.taviblock.daemon.plist" /Library/LaunchDaemons/
fi
chown root:wheel /Library/LaunchDaemons/com.taviblock.daemon.plist
chmod 644 /Library/LaunchDaemons/com.taviblock.daemon.plist

# Install watchdog service
if [ -f "$REPO_DIR/com.taviblock.watchdog.plist" ]; then
    cp "$REPO_DIR/com.taviblock.watchdog.plist" /Library/LaunchDaemons/
    chown root:wheel /Library/LaunchDaemons/com.taviblock.watchdog.plist
    chmod 644 /Library/LaunchDaemons/com.taviblock.watchdog.plist
fi

echo "8. Starting services..."
launchctl load -w /Library/LaunchDaemons/com.taviblock.daemon.plist
if [ -f "/Library/LaunchDaemons/com.taviblock.watchdog.plist" ]; then
    launchctl load -w /Library/LaunchDaemons/com.taviblock.watchdog.plist
fi

# Optional: Set up cron monitoring for extra protection
if [ -f "$REPO_DIR/cli/process_monitor.py" ]; then
    echo "7a. Setting up additional cron monitoring (optional)..."
    CRON_CMD="*/5 * * * * /usr/bin/python3 $REPO_DIR/cli/process_monitor.py >> /var/log/taviblock/cron_monitor.log 2>&1"
    (crontab -l 2>/dev/null | grep -v "process_monitor.py"; echo "$CRON_CMD") | crontab - 2>/dev/null || true
fi

echo "8. Setting up passwordless sudo for taviblock..."
# Get the actual user who ran sudo (not root)
ACTUAL_USER="${SUDO_USER:-$USER}"
echo "Configuring passwordless sudo for user: $ACTUAL_USER"

# Create sudoers.d directory if it doesn't exist
mkdir -p /etc/sudoers.d

# Find where taviblock was installed
TAVIBLOCK_PATH=$(which taviblock)

# Create the sudoers file for taviblock
echo "$ACTUAL_USER ALL=(ALL) NOPASSWD: $TAVIBLOCK_PATH" > /etc/sudoers.d/taviblock
chmod 440 /etc/sudoers.d/taviblock

# Verify the file is valid
if visudo -c -f /etc/sudoers.d/taviblock >/dev/null 2>&1; then
    echo "✓ Passwordless sudo configured successfully"
else
    echo "✗ Error configuring sudoers - removing invalid file"
    rm -f /etc/sudoers.d/taviblock
fi

echo ""
echo "=== Setup Complete! ==="
echo ""

# Check if protection features are installed
if [ -f "/Library/LaunchDaemons/com.taviblock.watchdog.plist" ]; then
    echo "✓ Enhanced protection enabled:"
    echo "  - Daemon auto-restarts if killed"
    echo "  - Watchdog process monitors daemon"
    echo "  - Common kill signals are ignored"
    echo ""
fi

echo "You can now use taviblock:"
echo ""
echo "  taviblock status          # Show status"
echo "  taviblock unblock gmail   # Unblock gmail"
echo "  taviblock bypass          # Emergency unblock"
echo "  taviblock peek            # Quick peek"
echo ""
echo "For passwordless sudo (optional), add this alias to your ~/.zshrc:"
echo "  alias taviblock='sudo taviblock'"
echo ""

if [ -f "$REPO_DIR/cli/watchdog.py" ]; then
    echo "=== Additional Security Notes ==="
    echo ""
    echo "For maximum protection against bypass:"
    echo "1. Remove sudo access from your regular user account"
    echo "2. Enable System Integrity Protection (SIP)"
    echo "3. Consider using Parental Controls"
    echo ""
    echo "To properly stop the blocking system:"
    echo "  sudo launchctl unload /Library/LaunchDaemons/com.taviblock.daemon.plist"
    echo "  sudo launchctl unload /Library/LaunchDaemons/com.taviblock.watchdog.plist"
    echo ""
fi