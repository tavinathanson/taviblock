#!/usr/bin/env python3
import argparse
import time
import os
import sys
from pathlib import Path

# Path to the system hosts file on macOS
HOSTS_PATH = "/etc/hosts"
# Markers to delimit our managed block section in /etc/hosts
BLOCKER_START = "# BLOCKER START"
BLOCKER_END = "# BLOCKER END"
# Default config file location (one domain per line, ignore lines starting with '#')
current_directory = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE_DEFAULT = os.path.join(current_directory, "config.txt")

def require_admin():
    """Ensure the script is run as root."""
    if os.geteuid() != 0:
        print("This script must be run as root. Try running with sudo.")
        sys.exit(1)

def read_config(config_file):
    """Read the config file and return a list of domains/subdomains to block."""
    if not os.path.exists(config_file):
        print(f"Config file {config_file} does not exist.")
        sys.exit(1)
    domains = []
    with open(config_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                domains.append(line)
    return domains

def generate_block_entries(domains):
    """
    Generate hosts file entries.

    For a root domain (assumed if there are only two parts, e.g. facebook.com),
    block both the bare domain and a list of common subdomains.
    For a specific subdomain (e.g. calendar.google.com), block only that subdomain.
    """
    entries = []
    # List of common subdomain prefixes to block for root domains.
    common_subdomains = ["www", "m", "mobile", "login", "app", "api"]

    for domain in domains:
        domain = domain.strip()
        if not domain:
            continue
        parts = domain.split('.')
        if len(parts) == 2:  # root domain like facebook.com
            entries.append(f"127.0.0.1 {domain}")
            for prefix in common_subdomains:
                entries.append(f"127.0.0.1 {prefix}.{domain}")
        else:
            # For specified subdomains, only block the exact entry.
            entries.append(f"127.0.0.1 {domain}")
    return entries

def backup_hosts():
    """Make a backup copy of /etc/hosts if one doesn't already exist."""
    backup_file = HOSTS_PATH + ".backup"
    if not os.path.exists(backup_file):
        os.system(f"cp {HOSTS_PATH} {backup_file}")

def apply_blocking(domains):
    """Apply the blocking by updating /etc/hosts with our entries."""
    backup_hosts()
    block_entries = generate_block_entries(domains)
    with open(HOSTS_PATH, "r") as f:
        lines = f.readlines()

    # Remove any existing block section from our tool
    new_lines = []
    in_block_section = False
    for line in lines:
        if line.strip() == BLOCKER_START:
            in_block_section = True
            continue
        if line.strip() == BLOCKER_END:
            in_block_section = False
            continue
        if not in_block_section:
            new_lines.append(line.rstrip("\n"))

    # Append our block section
    new_lines.append(BLOCKER_START)
    new_lines.extend(block_entries)
    new_lines.append(BLOCKER_END)

    with open(HOSTS_PATH, "w") as f:
        f.write("\n".join(new_lines) + "\n")
    print("Blocking applied.")

def remove_blocking():
    """Remove the blocking section from /etc/hosts."""
    backup_hosts()
    with open(HOSTS_PATH, "r") as f:
        lines = f.readlines()
    new_lines = []
    in_block_section = False
    for line in lines:
        if line.strip() == BLOCKER_START:
            in_block_section = True
            continue
        if line.strip() == BLOCKER_END:
            in_block_section = False
            continue
        if not in_block_section:
            new_lines.append(line.rstrip("\n"))
    with open(HOSTS_PATH, "w") as f:
        f.write("\n".join(new_lines) + "\n")
    print("Blocking removed.")

def is_blocking_active():
    """Check if our block markers exist in /etc/hosts."""
    with open(HOSTS_PATH, "r") as f:
        for line in f:
            if line.strip() == BLOCKER_START:
                return True
    return False

def main():
    require_admin()

    parser = argparse.ArgumentParser(description="Domain blocker CLI tool for macOS")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 'block' command: enforce the block based on the config file
    parser_block = subparsers.add_parser("block", help="Enable blocking according to config file")
    parser_block.add_argument("--config", type=str, default=CONFIG_FILE_DEFAULT, help="Path to config file")

    # 'disable' command: temporarily disable blocking after a delay
    parser_disable = subparsers.add_parser("disable", help="Temporarily disable blocking after a delay")
    parser_disable.add_argument("--config", type=str, default=CONFIG_FILE_DEFAULT, help="Path to config file")
    parser_disable.add_argument("--delay", type=int, default=30,
                                help="Delay in minutes before unblocking (default: 30)")
    parser_disable.add_argument("--duration", type=int, default=30,
                                help="Duration in minutes for which blocking is disabled (default: 30)")

    # 'status' command: check if blocking is currently active
    parser_status = subparsers.add_parser("status", help="Check if blocking is active")

    args = parser.parse_args()

    if args.command == "block":
        domains = read_config(args.config)
        apply_blocking(domains)
    elif args.command == "disable":
        print(f"Disable command accepted. Blocking will remain active for {args.delay} minutes.")
        time.sleep(args.delay * 60)
        remove_blocking()
        print(f"Blocking is disabled for {args.duration} minutes. Enjoy your break!")
        time.sleep(args.duration * 60)
        domains = read_config(args.config)
        apply_blocking(domains)
        print("Blocking re-enabled.")
    elif args.command == "status":
        if is_blocking_active():
            print("Blocking is active.")
        else:
            print("Blocking is not active.")

if __name__ == "__main__":
    main()
