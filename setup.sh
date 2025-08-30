#!/bin/bash

# Universal setup script for Block
# Handles both fresh installs and migrations

set -e

echo "=== Block Setup ==="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run this script with sudo"
    exit 1
fi

REPO_DIR="/Users/tavi/drive/repos/taviblock_ws/taviblock"

# Migration: Stop and remove old daemons
echo "1. Cleaning up old installations..."
launchctl unload /Library/LaunchDaemons/com.tavinathanson.killapps.plist 2>/dev/null || true
rm -f /Library/LaunchDaemons/com.tavinathanson.killapps.plist
launchctl unload /Library/LaunchDaemons/com.taviblock.daemon.plist 2>/dev/null || true

# Migration: Remove old lock files
rm -f /tmp/disable_single.lock
rm -f /tmp/disable_multiple.lock
rm -f /tmp/bypass.lock

# Migration: Remove old symlinks
rm -f /usr/local/bin/taviblock
rm -f /usr/local/bin/taviblock.old
rm -f /usr/local/bin/tbd
rm -f /usr/local/bin/tbd.old

echo "2. Creating directories..."
mkdir -p /var/lib/taviblock
mkdir -p /var/log/taviblock
chmod 755 /var/lib/taviblock
chmod 755 /var/log/taviblock

echo "3. Making scripts executable..."
chmod +x "$REPO_DIR/cli/block.py"
chmod +x "$REPO_DIR/cli/daemon.py"
chmod +x "$REPO_DIR/cli/db.py"

echo "4. Initializing database..."
python3 "$REPO_DIR/cli/db.py"

echo "5. Creating block command..."
ln -sf "$REPO_DIR/cli/block.py" /usr/local/bin/block

echo "6. Installing daemon..."
cp "$REPO_DIR/com.taviblock.daemon.plist" /Library/LaunchDaemons/
chown root:wheel /Library/LaunchDaemons/com.taviblock.daemon.plist
chmod 644 /Library/LaunchDaemons/com.taviblock.daemon.plist

echo "7. Starting daemon..."
launchctl load -w /Library/LaunchDaemons/com.taviblock.daemon.plist

echo "8. Setting up passwordless sudo..."
# Get the actual user who ran sudo (not root)
ACTUAL_USER="${SUDO_USER:-$USER}"
echo "Configuring passwordless sudo for user: $ACTUAL_USER"

# Create sudoers.d directory if it doesn't exist
mkdir -p /etc/sudoers.d

# Create the sudoers file for block
echo "$ACTUAL_USER ALL=(ALL) NOPASSWD: /usr/local/bin/block" > /etc/sudoers.d/block
chmod 440 /etc/sudoers.d/block

# Verify the file is valid
if visudo -c -f /etc/sudoers.d/block >/dev/null 2>&1; then
    echo "✓ Passwordless sudo configured successfully"
else
    echo "✗ Error configuring sudoers - removing invalid file"
    rm -f /etc/sudoers.d/block
fi

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "To finish setup, add this alias to your shell:"
echo ""
echo "  ./add_alias.sh"
echo "  source ~/.zshrc"
echo ""
echo "Then you can use:"
echo "  block              # Show status"
echo "  block gmail        # Unblock gmail"
echo "  block bypass       # Emergency unblock"
echo ""