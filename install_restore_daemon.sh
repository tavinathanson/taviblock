#!/bin/bash

# This script installs the taviblock restore daemon that
# ensures blocks are reapplied on system startup

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo)"
  exit 1
fi

# Path to the plist file in the repo
PLIST_SRC="/Users/tavi/drive/repos/taviblock_ws/taviblock/taviblock_restore.plist"
# Destination path in Launch Daemons
PLIST_DEST="/Library/LaunchDaemons/com.tavinathanson.taviblock_restore.plist"

# Copy the plist file
cp "$PLIST_SRC" "$PLIST_DEST"

# Set proper ownership and permissions
chown root:wheel "$PLIST_DEST"
chmod 644 "$PLIST_DEST"

# Load the daemon
launchctl load "$PLIST_DEST"

echo "Taviblock restore daemon installed and loaded."
echo "Your blocks will now be automatically restored on system startup." 