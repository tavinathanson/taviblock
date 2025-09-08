# taviblock

A domain blocking tool for macOS where **everything is blocked by default** - sites are only accessible during temporary unblock sessions.

## Core Principle: Block by Default

**All configured domains are permanently blocked.** The only way to access them is through temporary, time-limited unblock sessions. When a session expires, domains are automatically re-blocked immediately.

## Key Features

- **Flexible YAML Configuration**: Define custom profiles, timing rules, and domain groups
- **Independent Parallel Sessions**: Unblock multiple domains with separate timers
- **Smart Timing**: Concurrent penalties prevent gaming the system
- **Background Daemon**: Automatically updates `/etc/hosts` and closes blocked tabs
- **Persistent State**: All sessions survive restarts and crashes
- **Profile System**: Create custom profiles for different scenarios (work, focus, research)
- **Tag-based Control**: Group and unblock domains by purpose
- **Emergency Bypass**: Once-per-hour emergency access with cooldown
- **Active Enforcement**: Automatically closes Chrome tabs and terminates apps (like Slack) for blocked domains
- **Real-time Monitoring**: Checks and enforces blocks every second
- **Default Profile Shortcuts**: Set a default profile to enable shortcut commands
- **Duplicate Prevention**: Automatically skips domains that are already unblocked or pending

## Installation

Taviblock requires system-wide installation since it needs sudo access to modify `/etc/hosts`:

```bash
# Clone the repository
git clone https://github.com/yourusername/taviblock.git
cd taviblock

# Install using macOS system Python (recommended)
sudo /usr/bin/python3 setup.py install
```

This uses the macOS system Python which avoids any Homebrew Python restrictions.

## Configuration

Taviblock uses a YAML configuration file (`config.yaml`) to define domains and blocking profiles. The default location is in the taviblock directory, but you can specify a custom location with `--config`.

### Example Configuration

```yaml
# Optional: Set a default profile for shortcut commands
default_profile: unblock

domains:
  # Individual domains with tags
  netflix.com:
    tags: [ultra_distracting, entertainment]
  
  reddit.com:
    tags: [social, distracting]
  
  # Domain groups
  gmail:
    domains:
      - gmail.com
      - mail.google.com
    tags: [communication, email]
  
  slack:
    domains:
      - slack.com
      - slack-edge.com
    tags: [communication, work]

profiles:
  # Standard unblock with wait times
  unblock:
    description: "Standard unblock with wait time"
    wait:
      base: 5
      concurrent_penalty: 5  # Each additional session adds 5 min
    duration: 30
    tag_rules:
      - tags: [ultra_distracting]
        wait_override: 30
  
  # Quick check
  quick:
    description: "Quick 30-second check"
    wait:
      base: 0.5  # 30 seconds
      concurrent_penalty: 0
    duration: 1
  
  # Emergency bypass
  bypass:
    description: "Emergency 5-minute unblock (once per hour)"
    wait: 0
    duration: 5
    cooldown: 60
    all: true  # Unblocks everything
  
  # Custom work profile
  work:
    description: "Work mode - communication tools only"
    wait: 0
    duration: 120
    tags: [work, communication]
```

## Usage

### Basic Commands

```bash
# Show status
sudo taviblock status

# Unblock specific domains/groups
sudo taviblock unblock gmail              # 5 min wait, 30 min duration
sudo taviblock unblock gmail slack        # Multiple independent sessions
sudo taviblock unblock netflix            # 30 min wait (ultra_distracting)

# Default profile shortcut (when default_profile is set in config)
sudo taviblock gmail                      # Same as: sudo taviblock unblock gmail
sudo taviblock gmail slack                # Same as: sudo taviblock unblock gmail slack

# Use other profiles
sudo taviblock quick gmail                # 30-second quick check
sudo taviblock bypass                     # Emergency 5-min unblock all
sudo taviblock peek                       # 60-second peek at everything
sudo taviblock work                       # 2-hour work session

# Cancel sessions
sudo taviblock cancel                     # Cancel all sessions
sudo taviblock cancel 42                  # Cancel session by ID
sudo taviblock cancel slack               # Cancel session by name

# Replace pending sessions
sudo taviblock replace 42 reddit         # Replace session 42 with reddit
sudo taviblock replace slack gmail       # Replace pending slack with gmail

# Daemon control
sudo taviblock daemon start
sudo taviblock daemon stop
sudo taviblock daemon logs
```

### Key Concepts

1. **Parallel Sessions**: Each domain/group gets its own independent session timer
2. **Concurrent Penalties**: Additional sessions have longer wait times to prevent abuse
3. **Profile-based**: Different profiles for different use cases (quick, work, bypass)
4. **Tag-based Selection**: Profiles can target domains by tags
5. **Cooldowns**: Some profiles (like bypass) have cooldowns between uses

### Default Profile Shortcuts

When you set `default_profile` in your config.yaml, you can omit the profile name for quicker commands:

```yaml
# In config.yaml
default_profile: unblock
```

```bash
# These commands become equivalent:
sudo taviblock gmail              # → sudo taviblock unblock gmail
sudo taviblock gmail slack        # → sudo taviblock unblock gmail slack
sudo taviblock facebook.com       # → sudo taviblock unblock facebook.com
```

This makes the most common operation (unblocking) faster to type while still allowing explicit profile commands like `quick`, `bypass`, etc.

### Duplicate Session Prevention

Taviblock intelligently prevents duplicate sessions:

```bash
# First command creates a session
sudo taviblock unblock slack

# Second command recognizes slack is already active
sudo taviblock unblock slack
# Output: "Already unblocked: slack"

# If a session is waiting to start
sudo taviblock unblock twitter  # (with 5 min wait)
sudo taviblock unblock twitter  # Run immediately after
# Output: "Already pending: twitter"
```

The concurrent penalty only applies to new sessions, not skipped duplicates.

### Flexible Session Management

#### Cancel by Name
You can now cancel sessions by specifying the domain/group name instead of remembering session IDs:

```bash
# Cancel by ID (traditional way)
sudo taviblock cancel 42

# Cancel by name (new way)
sudo taviblock cancel slack
sudo taviblock cancel gmail

# Cancel all sessions
sudo taviblock cancel
```

#### Replace Pending Sessions
Change your mind about what to unblock? You can replace any pending (not yet active) session:

```bash
# Replace by session ID
sudo taviblock replace 42 reddit
# Replaces pending session 42 with a new session for reddit

# Replace by domain name
sudo taviblock replace slack gmail
# Finds the pending slack session and replaces it with gmail

# Replace with multiple targets
sudo taviblock replace twitter gmail slack
# Replaces pending twitter session with both gmail and slack
```

**Important**: You can only replace sessions that are still pending (waiting to start). Once a session becomes active, it cannot be replaced—only cancelled.

## How It Works

1. **Default State**: All domains in config.yaml are blocked via `/etc/hosts`
2. **Temporary Exceptions**: The `unblock` command creates time-limited exceptions
3. **Automatic Re-blocking**: When sessions expire, domains return to blocked state
4. **Persistent Enforcement**: Background daemon continuously enforces the block list
5. **Fail-Safe Design**: On daemon shutdown, full blocking is restored immediately

## Advanced Features

### Progressive Penalty System

Incentivize less frequent unblocking by adding cumulative wait time throughout the day:

```yaml
# In config.yaml
progressive_penalty:
  enabled: true
  per_unblock: 10         # Seconds added per unblock
  exclude_profiles: []    # Profiles that don't count
```

How it works:
- Each unblock adds 10 seconds to all future wait times today
- Example: 5th unblock of the day = +50 seconds (almost a minute) extra wait
- Resets daily at 4 AM
- View current penalty with `sudo taviblock status`
- Exclude emergency profiles: `exclude_profiles: [bypass]`

This gentle friction encourages more intentional unblocking decisions.

### Custom Profiles
Add your own profiles to `config.yaml`:

```yaml
profiles:
  focus:
    description: "Deep focus mode"
    wait: 0
    duration: 90
    only: [gmail]  # Only unblock gmail
  
  research:
    description: "Research session"
    wait: 10
    duration: 45
    tags: [news, educational]
```

### Tag-based Blocking
Group domains by purpose and unblock by tag:

```yaml
domains:
  github.com:
    tags: [development, work]
  stackoverflow.com:
    tags: [development, educational]

profiles:
  dev:
    description: "Development session"
    wait: 0
    duration: 180
    tags: [development]
```

## File Locations

- **Config**: `./config.yaml` (or specify with `--config`)
- **Database**: `/var/lib/taviblock/state.db`
- **Logs**: `/var/log/taviblock/daemon.log`

## Troubleshooting

```bash
# Check current status
sudo taviblock status

# View daemon logs
sudo taviblock daemon logs

# Restart daemon
sudo taviblock daemon restart

# Check if daemon is running
ps aux | grep taviblock
```