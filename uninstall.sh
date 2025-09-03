#!/bin/bash
# Uninstaller for taviblock

echo "Uninstalling taviblock..."

# Stop and remove daemons
echo "Stopping daemons..."
sudo launchctl unload /Library/LaunchDaemons/com.taviblock.daemon.plist 2>/dev/null
sudo launchctl unload /Library/LaunchDaemons/com.taviblock.watchdog.plist 2>/dev/null

echo "Removing daemon files..."
sudo rm -f /Library/LaunchDaemons/com.taviblock.daemon.plist
sudo rm -f /Library/LaunchDaemons/com.taviblock.watchdog.plist

# Uninstall Python package
echo "Uninstalling Python package..."
sudo /usr/bin/python3 -m pip uninstall taviblock -y 2>/dev/null

# Remove data directories
echo "Removing data directories..."
sudo rm -rf /var/lib/taviblock
sudo rm -rf /var/log/taviblock

# Ask about config removal
echo ""
read -p "Remove config file from /etc/taviblock? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    sudo rm -rf /etc/taviblock
    echo "Config directory removed."
else
    echo "Config preserved at /etc/taviblock/config.yaml"
fi

# Clean up hosts file
echo "Cleaning up /etc/hosts..."
sudo sed -i '' '/# BLOCKER START/,/# BLOCKER END/d' /etc/hosts

# Remove command symlinks
sudo rm -f /usr/local/bin/taviblock 2>/dev/null
sudo rm -f /usr/local/bin/block 2>/dev/null

# Remove old sudoers entries
sudo rm -f /etc/sudoers.d/block 2>/dev/null
sudo rm -f /etc/sudoers.d/taviblock 2>/dev/null

echo "Taviblock has been uninstalled."
echo ""
echo "Note: Your config.yaml file has been preserved in this directory."