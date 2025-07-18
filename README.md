TaviBlock
========================

## Overview
TaviBlock is a self-control solution for blocking distracting websites on macOS. It uses a hosts-based approach:

- **Network-Level Blocking**: Modifies `/etc/hosts` to block specified domains.
- **Application Control**: Automatically closes applications or browser tabs when their corresponding domains are blocked.

This approach helps prevent access to distracting websites and applications, making it harder to procrastinate.

## Repository Layout

```
taviblock/
├── cli/
│   ├── taviblock.py         # CLI tool to manage /etc/hosts blocking
│   └── kill_applications.sh # Script to kill applications or close browser tabs
├── config.txt               # Configuration file containing list of domains to block
└── README.md                # This file
```

## Prerequisites
- macOS
- Python 3
- Root (administrator) privileges

## Installation

### 1. Clone the Repository
Clone the repository into your desired directory:

```bash
git clone https://github.com/tavinathanson/taviblock.git ~/drive/repos/taviblock_ws/taviblock
```

### 2. Configure Domains to Block
Edit the `config.txt` file to list the domains you want to block. Lines starting with `#` are ignored. You may also use section headers (e.g., `[social]`) to group related domains.

Example:

```ini
[ultra_distracting]
netflix.com

[default]
facebook.com
twitter.com
```

The `[ultra_distracting]` section is special - any domains listed here will have longer wait times when using the disable commands:
- For `disable-single`: 30 minutes wait instead of 5 minutes
- For `disable-multiple`: 30 minutes wait instead of 10 minutes

This helps provide extra time to reconsider accessing highly distracting sites.

### 3. Install the CLI Tool
To easily use the CLI tool from any location, create a symbolic link in your PATH:

```bash
sudo ln -s ~/drive/repos/taviblock_ws/taviblock/cli/taviblock.py /usr/local/bin/taviblock
```

## Usage

### CLI Tool (`taviblock.py`)
The CLI tool manages domain blocking via modifications to `/etc/hosts`. Run the following command to see available options:

```bash
sudo taviblock --help
```

Available commands:

- **block**: Enable blocking by updating `/etc/hosts`.

  Example:
  ```bash
  sudo taviblock block --config ~/drive/repos/taviblock_ws/taviblock/config.txt
  ```

- **disable**: Temporarily disable blocking for a fixed period of 30 minutes.

  Example:
  ```bash
  sudo taviblock disable --config ~/drive/repos/taviblock_ws/taviblock/config.txt
  ```

- **update**: Refresh the blocking rules from the current `config.txt` without removing persistent entries.

  Example:
  ```bash
  sudo taviblock update --config ~/drive/repos/taviblock_ws/taviblock/config.txt
  ```

- **status**: Check whether blocking is currently active.

  Example:
  ```bash
  sudo taviblock status
  ```

- **disable-single**: Temporarily disable blocking for a specific domain or section for a fixed period of 30 minutes. The command will wait 5 minutes before disabling and then keep it disabled for 30 minutes.

  Example:
  ```bash
  sudo taviblock disable-single --target social --config ~/drive/repos/taviblock_ws/taviblock/config.txt
  ```

- **disable-multiple**: Temporarily disable blocking for up to 4 domains or sections. The command will wait 10 minutes before disabling and then keep them disabled for 30 minutes.

  Example:
  ```bash
  sudo taviblock disable-multiple --targets social gmail --config ~/drive/repos/taviblock_ws/taviblock/config.txt
  ```

- **bypass**: Immediately disable all blocking for 5 minutes. Can only be used once per hour (enforced by cooldown). No wait time - blocking is removed instantly.

  Example:
  ```bash
  sudo taviblock bypass --config ~/drive/repos/taviblock_ws/taviblock/config.txt
  ```

### Quick Disable Shortcut (`tbd`)
For convenience, a shortcut command `tbd` is provided to quickly disable blocking. This command supports four modes:

1. **Disable All Blocking**:
   ```bash
   sudo tbd
   ```
   This is equivalent to `sudo taviblock disable`

2. **Bypass (Emergency Disable)**:
   ```bash
   sudo tbd bypass
   ```
   This is equivalent to `sudo taviblock bypass` - immediately disables all blocking for 5 minutes (once per hour)

3. **Disable Single Domain/Section**:
   ```bash
   sudo tbd slack
   ```
   This is equivalent to `sudo taviblock disable-single --target slack`

4. **Disable Multiple Domains/Sections** (up to 4):
   ```bash
   sudo tbd slack gmail
   ```
   This is equivalent to `sudo taviblock disable-multiple --targets slack gmail`

To install the shortcut, create a symbolic link in your PATH:
```bash
sudo ln -s ~/drive/repos/taviblock_ws/taviblock/cli/tbd.py /usr/local/bin/tbd
```

Note: The shortcut command must be run with `sudo` as it needs root privileges to modify the hosts file.

### Disable Options Summary

TaviBlock provides several disable options designed with different levels of friction to help you make deliberate choices about when to access blocked content:

| Command | Wait Time | Duration | Frequency | Best For |
|---------|-----------|----------|-----------|----------|
| `bypass` | None (immediate) | 5 minutes | Once per hour | Emergency access, urgent tasks |
| `disable-single` | 5 min (30 min for ultra-distracting) | 30 minutes | Unlimited | Accessing one specific site |
| `disable-multiple` | 10 min (30 min for ultra-distracting) | 30 minutes | Unlimited | Accessing multiple related sites |
| `disable` | 30 minutes | 30 minutes | Unlimited | Complete break from all blocking |

The bypass command is designed for situations where you need immediate access but don't want to completely circumvent the friction-based system. Use it sparingly for genuine emergencies or urgent work needs.

## Application and Tab Management

This project includes a script that automatically manages browser tabs and applications based on the blocked domains:

1. **Chrome Tabs**: The script will close any Chrome tab containing a blocked domain from your config file.

2. **Specific Applications**: The script can also terminate specific applications associated with blocked domains:
   - Slack: When slack.com is blocked, the Slack desktop application is terminated.
   - More applications can be added to the script as needed.

The script automatically reads from your config.txt file, so any domain you add there will be automatically handled for Chrome tabs.

### Setup Instructions

1. **Make the Script Executable:**

   ```bash
   chmod +x taviblock/cli/kill_applications.sh
   ```

2. **Automate with a Launch Daemon:**
   Run the kill_applications.sh script as a Launch Daemon.

   Directly create a plist file at `/Library/LaunchDaemons/com.tavinathanson.killapps.plist` with the following content:

   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple Inc.//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>com.tavinathanson.killapps</string>
       <key>ProgramArguments</key>
       <array>
           <string>/Users/tavi/drive/repos/taviblock_ws/taviblock/cli/kill_applications.sh</string>
       </array>
       <key>RunAtLoad</key>
       <true/>
       <key>KeepAlive</key>
       <true/>
   </dict>
   </plist>
   ```

3. Set proper ownership:
   ```bash
   sudo chown root:wheel /Library/LaunchDaemons/com.tavinathanson.killapps.plist
   ```

4. Load the daemon with:
   ```bash
   sudo launchctl load /Library/LaunchDaemons/com.tavinathanson.killapps.plist
   ```

## Using Chrome with No Cache

To ensure that changes to blocking rules are immediately effective, we recommend using a version of Google Chrome that runs with caching disabled. This approach helps avoid issues where cached data might bypass new blocking rules, ensuring that all requests are subject to the latest rules. This is particularly useful when toggling blocking on and off, as it prevents stale data from being used.

### Why Disable Cache?

When blocking rules are updated, cached data in the browser can sometimes allow access to previously blocked content. By disabling the cache, you ensure that all requests are fresh and subject to the current blocking rules. This is particularly useful when toggling blocking on and off, as it prevents stale data from being used.

### Setting Up a No-Cache Chrome Launcher

1. **Create a Custom Launcher:**
   - Use Automator to create an application that launches Chrome with caching disabled.
   - Add a "Run Shell Script" action with the following command:
     ```bash
     open -a "Google Chrome" --args --disable-application-cache --disk-cache-size=0
     ```
   - Save the application as "Google Chrome No Cache" in your Applications folder.

2. **Add to Dock:**
   - Drag the new application to your Dock for easy access.
   - Optionally, change its icon to match the original Chrome icon for consistency.

By using this custom launcher, you can ensure that Chrome operates without caching, providing a more reliable experience when using TaviBlock.