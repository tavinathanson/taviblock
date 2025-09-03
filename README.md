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

# Use other profiles
sudo taviblock quick gmail                # 30-second quick check
sudo taviblock bypass                     # Emergency 5-min unblock all
sudo taviblock peek                       # 60-second peek at everything
sudo taviblock work                       # 2-hour work session

# Cancel sessions
sudo taviblock cancel                     # Cancel all sessions
sudo taviblock cancel 42                  # Cancel specific session

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

## How It Works

1. **Default State**: All domains in config.yaml are blocked via `/etc/hosts`
2. **Temporary Exceptions**: The `unblock` command creates time-limited exceptions
3. **Automatic Re-blocking**: When sessions expire, domains return to blocked state
4. **Persistent Enforcement**: Background daemon continuously enforces the block list
5. **Fail-Safe Design**: On daemon shutdown, full blocking is restored immediately

## Advanced Features

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