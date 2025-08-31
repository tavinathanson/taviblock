Block
========================

A streamlined self-control tool for blocking distracting websites on macOS.

## Features

- **Clock-based timing**: All timers use real time and persist through sleep/restarts
- **SQLite state management**: All state stored in a single database - no temporary files
- **Background daemon**: Automatically updates `/etc/hosts` and closes blocked tabs/apps
- **Chrome tab closing**: Automatically closes tabs for blocked domains every 10 seconds
- **App termination**: Kills apps like Slack when their domains are blocked
- **Session protection**: Prevents duplicate sessions for domains already unblocked
- **Session limits**: Maximum 4 concurrent sessions to prevent abuse
- **Smart time display**: Shows seconds for short durations (≤5 minutes)
- **Overlapping unblocks**: Multiple independent sessions can run simultaneously
- **Simple command**: Just `block` for everything

## Installation

### 1. Clone and Setup
```bash
git clone https://github.com/tavinathanson/taviblock.git ~/drive/repos/taviblock_ws/taviblock
cd ~/drive/repos/taviblock_ws/taviblock
sudo ./setup.sh
```

### 2. Add Alias
```bash
./add_alias.sh
source ~/.zshrc
```

That's it! The setup script automatically configures passwordless sudo for the block command.

### 3. Configure Domains
Edit `config.txt` to list domains to block:

```ini
[ultra_distracting]
netflix.com

[gmail]
gmail.com
mail.google.com

[slack]
slack.com

[default]
reddit.com
twitter.com
facebook.com
```

**Special sections:**
- `[ultra_distracting]`: Domains here have longer wait times (30 min instead of 5-10 min)
- Custom sections like `[gmail]` or `[slack]`: Group related domains for easy unblocking

## Usage

### Basic Commands

```bash
block                    # Show status
block gmail              # Unblock gmail (5 min wait, 30 min duration)
block gmail slack        # Unblock multiple sections
block gmail -r 3         # Replace session 3 with gmail
block bypass             # Emergency 5-min unblock (once per hour)
block peek               # 60-second peek after 60-second wait
block cancel             # Cancel all sessions
block cancel 42          # Cancel specific session
```

**Session Limit**: Maximum 4 concurrent unblock sessions to prevent abuse. When you hit the limit, you'll need to either:
- Cancel existing sessions
- Replace a specific session with `-r <id>`

### Advanced Options

```bash
block unblock gmail -w 0 -d 60    # No wait, 60 min duration
block unblock gmail -w 10         # Custom 10 min wait
block unblock slack -r 3          # Replace session 3 with slack
block daemon logs                 # View daemon logs
block daemon restart              # Restart daemon
```

## How It Works

1. **Everything is blocked by default** - The daemon ensures all configured domains are blocked
2. **Unblock sessions temporarily allow access** - Each session has a wait time and duration
3. **Sessions can overlap** - Unblock gmail, then later unblock slack - both stay unblocked independently
4. **All state in SQLite** - No temporary files, no lock files - everything is in `/var/lib/taviblock/state.db`
5. **State persists** - Survives restarts, sleep, terminal closures, and system crashes
6. **Active enforcement** - Chrome tabs are closed within 10 seconds when domains are blocked

## Resilient Design

Block is designed to fail closed (keep blocking) rather than fail open:

- **Starts on boot**: The daemon automatically starts when your Mac boots up
- **Daemon auto-restarts**: If the daemon crashes, macOS automatically restarts it
- **Blocks restored on shutdown**: When the daemon stops, it restores full blocking first
- **Auto-start on command**: Running any `block` command will start the daemon if it's not running
- **No easy bypass**: You can't just kill the daemon to unblock everything - it blocks on exit

To completely disable blocking, you would need to:
1. Stop the daemon: `sudo launchctl unload /Library/LaunchDaemons/com.taviblock.daemon.plist`
2. Manually edit `/etc/hosts` to remove the block entries
3. Even then, any `block` command will restart everything

## Wait Times

| Command | Regular Domains | Ultra Distracting |
|---------|----------------|-------------------|
| Single target | 5 minutes | 30 minutes |
| Multiple targets | 10 minutes | 30 minutes |
| Bypass | No wait | No wait |
| Peek | 60 seconds | 60 seconds |

## Examples

```bash
# Morning routine - check email quickly
block gmail

# Need to focus but check Slack periodically  
block slack

# Emergency - need everything for 5 minutes
block bypass

# Just want to see what's happening
block peek

# Unblock immediately for a meeting
block unblock slack -w 0 -d 60

# Cancel everything and focus
block cancel
```

## File Locations

- **Config**: `~/drive/repos/taviblock_ws/taviblock/config.txt`
- **Database**: `/var/lib/taviblock/state.db`
- **Logs**: `/var/log/taviblock/daemon.log`
- **Daemon**: `/Library/LaunchDaemons/com.taviblock.daemon.plist`

## Troubleshooting

```bash
# Check what's happening
block
block daemon logs

# Restart everything
block daemon restart

# Reset all state
sudo rm /var/lib/taviblock/state.db
block daemon restart
```