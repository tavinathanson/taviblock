TaviBlock & Gmail Blocker Sync

This repository provides a self-control solution for blocking Gmail on macOS by combining a CLI tool with a Chrome extension. The CLI tool modifies your /etc/hosts file to block specified domains (supporting both IPv4 and IPv6) and writes a status flag to /tmp/gmailblock_status.txt. The Chrome extension uses native messaging to query that status and block Gmail in the browser when needed.

Repository Layout

taviblock/
├── cli/
│   └── taviblock.py
├── config.txt
├── chrome-extension/
│   └── gmail-blocker-sync/
│       ├── manifest.json
│       └── background.js
├── native/
│   ├── gmailblock_status_host.py
│   └── com.example.gmailblockstatus.json
└── README.md

Components

CLI Tool (cli/taviblock.py)
------------------------------------------------------------
Function:
  - Modifies /etc/hosts to block domains (e.g., Gmail) based on a configuration file.
Default Config File:
  - The tool uses the config.txt file in the repository root (i.e. ~/drive/repos/taviblock/config.txt) by default.
Commands:
  - block: Enforce blocking.
  - disable: Temporarily disable blocking.
  - update: Update the block list.
  - status: Check block status.
  - disable-single: Temporarily disable blocking for a single domain or section.
Status Synchronization:
  - Writes "blocked" or "unblocked" to /tmp/gmailblock_status.txt, which the native messaging host reads.

Chrome Extension (chrome-extension/gmail-blocker-sync/)
------------------------------------------------------------
Function:
  - Uses Manifest V3 and the declarativeNetRequest API to block requests to mail.google.com when blocking is active.
Key Files:
  - manifest.json (updated to Manifest V3)
  - background.js (queries the native messaging host and updates dynamic rules)
Native Messaging:
  - Communicates with the native messaging host to obtain the current block status.

Native Messaging Host (native/gmailblock_status_host.py)
------------------------------------------------------------
Function:
  - Reads the status file (/tmp/gmailblock_status.txt) and returns the current block status to the Chrome extension.
Manifest:
  - The file com.example.gmailblockstatus.json defines how Chrome can launch the host.

Design Considerations & Discussion Summary

Network-Level Blocking:
  - The CLI tool updates the /etc/hosts file with entries that redirect target domains to localhost.
  - This works for new DNS lookups (for both IPv4 and IPv6) but may not break persistent connections.

SelfControl-Like Lockout:
  - Commands in the CLI tool (e.g., disable and disable-single) allow temporary disabling of the block with timers, making it harder to bypass your self-imposed restrictions.

Browser-Level Blocking:
  - To further enforce self-control, the Chrome extension blocks Gmail in the browser using dynamic rules via the declarativeNetRequest API.
  - It continuously queries a native messaging host to obtain the current block status.

Synchronization:
  - The CLI tool writes a status flag to /tmp/gmailblock_status.txt.
  - The native messaging host reads this file and reports back to the extension, ensuring that both the network-level and browser-level blocks remain synchronized.

Repository Organization & Persistence:
  - All source code lives in this repository.
  - By default, the CLI tool uses the config.txt file located at the repository root.
  - Symlinks and launch agents can be used to integrate the CLI tool into system paths and to run it on startup.

Installation & Setup

1. Repository Setup
   - Clone the repository into your drive:
       git clone <your-repo-url> ~/drive/repos/taviblock

2. CLI Tool
   - Symlink the CLI Tool:
       Create a symlink from your repo to a directory on your PATH (e.g., /usr/local/bin):
           sudo ln -s ~/drive/repos/taviblock/cli/taviblock.py /usr/local/bin/taviblock
   - Usage Examples:
       * Block Domains (applies blocking rules and writes "blocked" to /tmp/gmailblock_status.txt):
           sudo taviblock block --config ~/drive/repos/taviblock/config.txt
       * Temporarily Disable Blocking (waits for a delay, removes blocking, then re-applies after a set duration):
           sudo taviblock disable --config ~/drive/repos/taviblock/config.txt --delay 30 --duration 30
       * Disable a Specific Domain or Section (temporarily disable blocking for a specific target, e.g., [gmail] section):
           sudo taviblock disable-single --target gmail --duration 30
       * Update the Block List (refresh the current block entries without removing existing ones):
           sudo taviblock update --config ~/drive/repos/taviblock/config.txt
       * Check Blocking Status (report whether blocking is active):
           sudo taviblock status
   - Optional – Launch at Boot:
       Create a launch agent (e.g., ~/Library/LaunchAgents/com.yourname.taviblock.plist) with the following contents:

       <?xml version="1.0" encoding="UTF-8"?>
       <!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
       <plist version="1.0">
         <dict>
           <key>Label</key>
           <string>com.yourname.taviblock</string>
           <key>ProgramArguments</key>
           <array>
             <string>/usr/local/bin/taviblock</string>
             <string>block</string>
             <string>--config</string>
             <string>/Users/<YOUR_USERNAME>/drive/repos/taviblock/config.txt</string>
           </array>
           <key>RunAtLoad</key>
           <true/>
           <key>KeepAlive</key>
           <true/>
           <key>StandardOutPath</key>
           <string>/tmp/taviblock.out</string>
           <key>StandardErrorPath</key>
           <string>/tmp/taviblock.err</string>
         </dict>
       </plist>

       Load it with:
           launchctl load ~/Library/LaunchAgents/com.yourname.taviblock.plist

3. Chrome Extension
   - Load Extension:
       1. Open Chrome and navigate to chrome://extensions.
       2. Enable Developer Mode.
       3. Click "Load unpacked" and select the folder:
          ~/drive/repos/taviblock/chrome-extension/gmail-blocker-sync
       4. Note the generated extension ID.
   - Update Native Messaging Manifest:
       - Edit the file native/com.example.gmailblockstatus.json and replace <YOUR_EXTENSION_ID> with your extension’s ID.
   - Install the Manifest:
       mkdir -p ~/Library/Application\ Support/Google/Chrome/NativeMessagingHosts/
       cp ~/drive/repos/taviblock/native/com.example.gmailblockstatus.json ~/Library/Application\ Support/Google/Chrome/NativeMessagingHosts/

4. Native Messaging Host
   - Ensure Executable:
       Make sure the host script is executable:
           chmod +x ~/drive/repos/taviblock/native/gmailblock_status_host.py
   - Manifest Installation:
       Verify that the native messaging host manifest is installed in:
           ~/Library/Application Support/Google/Chrome/NativeMessagingHosts/
