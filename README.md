TaviBlock & PF Blocker
========================

## Overview
TaviBlock & PF Blocker is a self-control solution for blocking distracting websites on macOS. It uses a dual-layer approach:

- **Network-Level Blocking**: Modifies `/etc/hosts` to block specified domains.
- **Firewall-Level Blocking**: Uses PF (Packet Filter) rules to block outgoing connections to IP addresses resolved from those domains.

This approach helps prevent access to distracting websites by interfering with both DNS resolution and direct connections at the firewall level.

## Repository Layout

```
taviblock/
├── cli/
│   ├── taviblock.py     # CLI tool to manage /etc/hosts blocking
│   └── pf_agent.py      # PF Firewall Agent to block resolved IP addresses
├── config.txt           # Configuration file containing list of domains to block
└── README.md            # This file
```

## Prerequisites
- macOS with PF (Packet Filter) enabled
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
[social]
facebook.com
twitter.com

[streaming]
netflix.com
youtube.com
```

### 3. Install the CLI Tool
To easily use the CLI tool from any location, create a symbolic link in your PATH:

```bash
sudo ln -s ~/drive/repos/taviblock_ws/taviblock/cli/taviblock.py /usr/local/bin/taviblock
```

### 4. Set Up the PF Firewall Agent
The PF Firewall Agent (`pf_agent.py`) continuously updates PF rules to block traffic to IP addresses resolved from the domains in your config file.

Run the agent manually with:

```bash
sudo python3 ~/drive/repos/taviblock_ws/taviblock/cli/pf_agent.py
```

#### Optional: Configure a Launch Agent for the PF Agent
To run the PF agent automatically on startup, you can use a Launch Agent (user-level) or a Launch Daemon (system-level). 
If you choose the Launch Agent option, create the plist file at:
  ~/Library/LaunchAgents/com.tavinathanson.taviblock_pf.plist
with the following content:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Inc.//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.tavinathanson.taviblock_pf</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/tavi/drive/repos/taviblock_ws/taviblock/cli/pf_agent.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/taviblock_pf.out</string>
    <key>StandardErrorPath</key>
    <string>/tmp/taviblock_pf.err</string>
</dict>
</plist>
```

2. To load as a Launch Agent:
   launchctl load ~/Library/LaunchAgents/com.tavinathanson.taviblock_pf.plist

Alternatively, to run as a Launch Daemon (recommended for tasks needing elevated privileges):
   a. Copy the plist file to /Library/LaunchDaemons/:
      sudo cp ~/Library/LaunchAgents/com.tavinathanson.taviblock_pf.plist /Library/LaunchDaemons/
   b. Set proper ownership:
      sudo chown root:wheel /Library/LaunchDaemons/com.tavinathanson.taviblock_pf.plist
   c. Load the daemon with:
      sudo launchctl load /Library/LaunchDaemons/com.tavinathanson.taviblock_pf.plist

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

- **disable**: Temporarily disable blocking after a specified delay.

  Example:
  ```bash
  sudo taviblock disable --delay 30 --duration 30
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

- **disable-single**: Temporarily disable blocking for a specific domain or section.

  Example:
  ```bash
  sudo taviblock disable-single --target social --duration 10
  ```

### PF Firewall Agent (`pf_agent.py`)
The PF agent updates firewall rules by performing the following steps:

1. **Reads the Config File**: Retrieves a list of domains from `config.txt` (ignoring comments and section headers).
2. **DNS Resolution**: Resolves each domain to its current IP addresses.
3. **Generate PF Rules**: Creates PF rules for each IP:
   - IPv4: `block drop quick from any to <ip>`
   - IPv6: `block drop quick inet6 from any to <ip>`
4. **Update PF Rules**: Writes the rules to a temporary file and loads them using `pfctl` under the anchor `taviblock_pf`.
5. **Continuous Update**: Repeats this process every 5 minutes.

To run the PF agent manually:

```bash
sudo python3 ~/drive/repos/taviblock_ws/taviblock/cli/pf_agent.py
```

To stop the agent, terminate the process or unload it if it's running as a launch agent:

```bash
launchctl unload ~/Library/LaunchAgents/com.tavinathanson.taviblock_pf.plist
```

## Troubleshooting

- **Check PF Status**: Ensure PF is active with:
  ```bash
  sudo pfctl -s info
  ```

- **Rule Verification**: Inspect the temporary rule file at `/tmp/taviblock_pf.rules` to verify the generated rules.

- **Log Files**: Check `/tmp/taviblock_pf.out` and `/tmp/taviblock_pf.err` for output and error messages if using a launch agent.

- **Permissions**: Both the CLI tool and PF agent require root privileges. Make sure to run them with `

## Slack Blocking using kill_slack.sh

This project now includes a script that automatically terminates the Slack application when a Slack block is active in your /etc/hosts file. The script checks if the following entry (or a similar blocking entry) exists in /etc/hosts:

```
127.0.0.1 slack.com
```

If the block is active and Slack is running, the script will kill the Slack process.

### Kill Slack Script Details

- **Location:** `taviblock/cli/kill_slack.sh`
- **Behavior:** The script continuously checks every 10 seconds if the blocking entry is present and, if so, terminates Slack if it is running.

### Setup Instructions

1. **Add the Blocking Entry:**
   Ensure your `/etc/hosts` file contains the following line when you want to block Slack:

   ```
   127.0.0.1 slack.com
   ```

2. **Make the Script Executable:**

   ```bash
   chmod +x taviblock/cli/kill_slack.sh
   ```

3. **(Optional) Automate with a Launch Agent or Launch Daemon:**
   It is recommended to run the kill_slack.sh script as a Launch Agent (user-level) since it manages a user application (Slack). However, if needed, you can also run it as a Launch Daemon (system-level).

   **Using a Launch Agent (User-level):**
   - Create a plist file at `~/Library/LaunchAgents/com.tavinathanson.killslack.plist` with the following content:
     ```xml
     <?xml version="1.0" encoding="UTF-8"?>
     <!DOCTYPE plist PUBLIC "-//Apple Inc.//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
     <plist version="1.0">
     <dict>
         <key>Label</key>
         <string>com.tavinathanson.killslack</string>
         <key>ProgramArguments</key>
         <array>
             <string>/Users/tavi/repos/taviblock_ws/taviblock/cli/kill_slack.sh</string>
         </array>
         <key>RunAtLoad</key>
         <true/>
         <key>KeepAlive</key>
         <true/>
     </dict>
     </plist>
     ```

   - Load with:
     launchctl load ~/Library/LaunchAgents/com.tavinathanson.killslack.plist

   - Unload with:
     launchctl unload ~/Library/LaunchAgents/com.tavinathanson.killslack.plist

   **Using a Launch Daemon (System-level):**
   - Copy the above plist file to `/Library/LaunchDaemons/` and set proper ownership:
     sudo cp ~/Library/LaunchAgents/com.tavinathanson.killslack.plist /Library/LaunchDaemons/
     sudo chown root:wheel /Library/LaunchDaemons/com.tavinathanson.killslack.plist

   - Load with:
     sudo launchctl load /Library/LaunchDaemons/com.tavinathanson.killslack.plist

   - Unload with:
     sudo launchctl unload /Library/LaunchDaemons/com.tavinathanson.killslack.plist