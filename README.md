# TaviBlock & Gmail Blocker Sync

This repository provides a self-control solution for blocking Gmail on macOS by combining a CLI tool (which updates your `/etc/hosts` file) with a Chrome extension that blocks Gmail in the browser. Both components are synchronized via a native messaging host.

## Components

### CLI Tool (`cli/taviblock.py`)
- **Function:**
  Modifies `/etc/hosts` to block specified domains (IPv4/IPv6) based on a config file.
- **Commands:**
  - `block`: Enforce blocking.
  - `disable`: Temporarily disable blocking.
  - `update`: Update the block list.
  - `status`: Check block status.
  - `disable-single`: Temporarily disable blocking for a single domain or section.
- **Status Sync:**
  Writes current status (`blocked` or `unblocked`) to `/tmp/gmailblock_status.txt` for use by the Chrome extension.

### Chrome Extension (`chrome-extension/gmail-blocker-sync/`)
- **Function:**
  Uses Manifest V3 and the declarativeNetRequest API to block requests to `mail.google.com` in Chrome when blocking is active.
- **Key Files:**
  - `manifest.json` (updated to Manifest V3)
  - `background.js` (now uses dynamic rules via declarativeNetRequest)
- **Native Messaging:**
  Periodically queries a native messaging host for block status.

### Native Messaging Host (`native/gmailblock_status_host.py`)
- **Function:**
  Reads `/tmp/gmailblock_status.txt` (updated by the CLI tool) and returns the current status (`blocked` or `unblocked`) to the Chrome extension.
- **Manifest:**
  The file `com.example.gmailblockstatus.json` defines how Chrome can invoke the host.

## Design Considerations & Discussion Summary

- **Network-Level Blocking:**
  The CLI tool updates `/etc/hosts` with entries to redirect target domains to localhost, affecting new DNS lookups for both IPv4 and IPv6. However, persistent connections may still exist.

- **SelfControl-Like Lockout:**
  Commands allow temporary disabling (with timers) so that blocking can be enforced for a set duration without easy circumvention.

- **Browser-Level Blocking:**
  To complement the hosts file method, a Chrome extension intercepts requests to Gmail. With Manifest V3, the extension uses declarativeNetRequest dynamic rules—updated based on the block status provided via native messaging—to block Gmail requests.

- **Synchronization:**
  The CLI tool writes to a status file, which the native messaging host reads and reports to the extension. This keeps network-level and browser-level blocking synchronized.

- **Repository Organization & Persistence:**
  All code lives in this repository. Symlinks and launch agents can be used to integrate the CLI tool into system paths and ensure it runs on startup.

## Installation

### 1. Repository Setup
Clone the repository into your drive:
```bash
git clone <your-repo-url> ~/drive/repos/taviblock
