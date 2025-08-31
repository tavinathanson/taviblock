Block
========================

A streamlined self-control tool for blocking distracting websites on macOS.

## Features

- **Clock-based timing**: All timers use real time and persist through sleep/restarts
- **SQLite state management**: All state stored in a single database - no temporary files
- **Background daemon**: Automatically updates `/etc/hosts` and closes blocked tabs/apps
- **Chrome tab closing**: Automatically closes tabs for blocked domains within 1 second
- **Optimized performance**: Single batched check for all blocked domains (not per-domain)
- **App termination**: Kills apps like Slack when their domains are blocked
- **Session protection**: Prevents duplicate sessions for domains already unblocked
- **Session limits**: Maximum 4 concurrent sessions to prevent abuse
- **Smart time display**: Shows seconds for short durations (≤5 minutes)
- **Overlapping unblocks**: Multiple independent sessions can run simultaneously
- **Simple command**: Just `block` for everything
- **Interactive notifications**: Terminal popup 1 minute before active tabs/apps close

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
6. **Active enforcement** - Chrome tabs are closed within 1 second when domains are blocked
7. **Smart session detection** - Only prevents identical duplicate sessions (bypass doesn't block specific unblocks)

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

# Find the daemon process
ps aux | grep daemon.py
# Or look for 'python3' in Activity Monitor
```

## Advanced Usage

### Overlapping Sessions
You can have multiple unblock sessions running simultaneously:

```bash
block bypass              # Unblocks everything for 5 minutes
block youtube -w 0 -d 60  # Also unblock YouTube for 60 minutes starting now
# YouTube stays unblocked for the full 60 minutes, even after bypass ends
```

The system only prevents creating identical duplicate sessions. Different sessions can overlap freely.

### Interactive Notifications
When you're actively using a blocked domain/app that's about to be closed:

1. **1 minute before closing**: If a Chrome tab or Slack is active, a terminal window pops up
2. **Interactive prompt**: Choose to extend by 5 minutes, 30 minutes, or let it close
3. **Works with your terminal**: Automatically uses iTerm2 if installed, otherwise Terminal.app
4. **30-second timeout**: If you don't respond, the session ends as scheduled

This prevents losing work when you're in the middle of something important.

**Important Notes**: 
- Bypass sessions (emergency 5-minute unblocks) cannot be extended and don't show notifications
- The `block extend` command only works if you're actively using the domain/app
- This prevents arbitrary session extensions and ensures extensions are only granted when truly needed