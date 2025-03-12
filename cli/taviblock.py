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
# Use the config.txt file in the repository root by default.
CONFIG_FILE_DEFAULT = str(Path(__file__).resolve().parent.parent / "config.txt")

LOCK_FILE = "/tmp/disable_single.lock"


def require_admin():
    """Ensure the script is run as root."""
    if os.geteuid() != 0:
        print("This script must be run as root. Try running with sudo.")
        sys.exit(1)


def read_config(config_file):
    """
    Read the config file and return a list of domains/subdomains to block.
    This is used for the block/disable/update commands.
    """
    if not os.path.exists(config_file):
        print(f"Config file {config_file} does not exist.")
        sys.exit(1)
    domains = []
    with open(config_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if line.startswith('[') and line.endswith(']'):
                    continue
                domains.append(line)
    return domains


def read_config_sections(config_file):
    """
    Reads the config file and returns a dictionary mapping section names to lists of domains.

    Use section headers in the config file like:
      [gmail]
      gmail.com
      mail.google.com

    Lines not under any header will be added under the "default" section.
    """
    sections = {}
    current_section = "default"
    sections[current_section] = []
    with open(config_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1].strip()
                if current_section not in sections:
                    sections[current_section] = []
            else:
                sections[current_section].append(line)
    return sections


def generate_block_entries(domains):
    """
    Generate hosts file entries for IPv4 and IPv6.

    For a root domain (e.g. facebook.com), block both the bare domain and a list of common subdomains.
    For a specific subdomain (e.g. calendar.google.com), block only that subdomain.
    """
    entries = []
    # List of common subdomain prefixes to block for root domains.
    common_subdomains = ["www", "m", "mobile", "login", "app", "api"]

    for domain in domains:
        domain = domain.strip()
        if not domain:
            continue
        parts = domain.split(".")
        if len(parts) == 2:  # root domain, e.g., facebook.com
            # Add both IPv4 and IPv6 for the root domain
            entries.append(f"127.0.0.1 {domain}")
            entries.append(f"::1 {domain}")
            for prefix in common_subdomains:
                subdomain = f"{prefix}.{domain}"
                entries.append(f"127.0.0.1 {subdomain}")
                entries.append(f"::1 {subdomain}")
        else:
            # For subdomains, block both IPv4 and IPv6 entries.
            entries.append(f"127.0.0.1 {domain}")
            entries.append(f"::1 {domain}")
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


def update_blocking(domains):
    """
    Update the current block with new entries from the latest config,
    including both IPv4 and IPv6 entries, while keeping existing entries.
    """
    new_entries = set(generate_block_entries(domains))
    backup_hosts()

    with open(HOSTS_PATH, "r") as f:
        lines = f.readlines()

    updated_lines = []
    in_block_section = False
    current_block_entries = set()
    block_section_found = False

    for line in lines:
        stripped = line.rstrip("\n")
        if stripped == BLOCKER_START:
            block_section_found = True
            in_block_section = True
            updated_lines.append(stripped)
            continue
        if stripped == BLOCKER_END:
            in_block_section = False
            # Merge existing entries with new IPv4/IPv6 entries.
            union_entries = current_block_entries | new_entries
            for entry in sorted(union_entries):
                updated_lines.append(entry)
            updated_lines.append(stripped)
            continue
        if in_block_section:
            current_block_entries.add(stripped)
        else:
            updated_lines.append(stripped)

    if not block_section_found:
        updated_lines.append(BLOCKER_START)
        for entry in sorted(new_entries):
            updated_lines.append(entry)
        updated_lines.append(BLOCKER_END)

    with open(HOSTS_PATH, "w") as f:
        f.write("\n".join(updated_lines) + "\n")
    print("Blocking updated with IPv4 and IPv6 entries from the latest config.")


def check_single_disable_lock():
    """Return True if no single-domain disable is active; False otherwise."""
    return not os.path.exists(LOCK_FILE)


def create_single_disable_lock(target):
    """Create a lock file to mark a single-domain disable as active."""
    with open(LOCK_FILE, "w") as f:
        f.write(target)


def remove_single_disable_lock():
    """Remove the single-domain disable lock file."""
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)


def remove_entries_for_target(target, entries_to_remove):
    """
    Remove specific block entries (IPv4 and IPv6) from the hosts file block section
    for the given target (either a section or a single domain).
    """
    backup_hosts()
    with open(HOSTS_PATH, "r") as f:
        lines = f.readlines()
    new_lines = []
    in_block_section = False
    for line in lines:
        stripped = line.rstrip("\n")
        if stripped == BLOCKER_START:
            in_block_section = True
            new_lines.append(stripped)
            continue
        if stripped == BLOCKER_END:
            in_block_section = False
            new_lines.append(stripped)
            continue
        if in_block_section:
            if stripped in entries_to_remove:
                continue  # Skip this entry.
        new_lines.append(stripped)
    with open(HOSTS_PATH, "w") as f:
        f.write("\n".join(new_lines) + "\n")
    print(f"Entries for target '{target}' removed from block list.")


def add_entries_for_target(target, entries_to_add):
    """
    Re-add specific block entries (IPv4 and IPv6) into the hosts file block section
    for the given target (either a section or a single domain).
    """
    backup_hosts()
    with open(HOSTS_PATH, "r") as f:
        lines = f.readlines()
    new_lines = []
    in_block_section = False
    block_section_found = False
    existing_entries = set()

    for line in lines:
        stripped = line.rstrip("\n")
        if stripped == BLOCKER_START:
            block_section_found = True
            in_block_section = True
            new_lines.append(stripped)
            continue
        if stripped == BLOCKER_END:
            # Add any missing entries before closing the block section.
            for entry in sorted(entries_to_add):
                if entry not in existing_entries:
                    new_lines.append(entry)
            in_block_section = False
            new_lines.append(stripped)
            continue
        if in_block_section:
            existing_entries.add(stripped)
        new_lines.append(stripped)

    if not block_section_found:
        new_lines.append(BLOCKER_START)
        for entry in sorted(entries_to_add):
            new_lines.append(entry)
        new_lines.append(BLOCKER_END)

    with open(HOSTS_PATH, "w") as f:
        f.write("\n".join(new_lines) + "\n")
    print(f"Entries for target '{target}' re-added to block list.")


def main():
    require_admin()

    parser = argparse.ArgumentParser(description="Domain blocker CLI tool for macOS")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 'block' command: enforce the block based on the config file
    parser_block = subparsers.add_parser(
        "block", help="Enable blocking according to config file"
    )
    parser_block.add_argument(
        "--config", type=str, default=CONFIG_FILE_DEFAULT, help="Path to config file"
    )
    # Extra option for testing: block for one minute then auto-remove
    parser_block.add_argument(
        "--test",
        action="store_true",
        help="Test block for one minute for development purposes",
    )

    # 'disable' command: temporarily disable blocking after a delay
    parser_disable = subparsers.add_parser(
        "disable", help="Temporarily disable blocking after a delay"
    )
    parser_disable.add_argument(
        "--config", type=str, default=CONFIG_FILE_DEFAULT, help="Path to config file"
    )
    parser_disable.add_argument(
        "--delay",
        type=int,
        default=30,
        help="Delay in minutes before unblocking (default: 30)",
    )
    parser_disable.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Duration in minutes for which blocking is disabled (default: 30)",
    )

    # 'update' command: update the current block with new config entries (without removing existing ones)
    parser_update = subparsers.add_parser(
        "update",
        help="Update the current block with latest config, adding new entries only",
    )
    parser_update.add_argument(
        "--config", type=str, default=CONFIG_FILE_DEFAULT, help="Path to config file"
    )

    # 'status' command: check if blocking is currently active
    parser_status = subparsers.add_parser("status", help="Check if blocking is active")

    # 'disable-single' command: temporarily disable a single domain/subdomain or an entire section
    parser_disable_single = subparsers.add_parser(
        "disable-single",
        help="Temporarily disable blocking for a single domain/subdomain or an entire section",
    )
    parser_disable_single.add_argument(
        "--target",
        required=True,
        type=str,
        help="The domain/subdomain or section name to disable",
    )
    parser_disable_single.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Duration in minutes for which blocking is disabled (default: 30)",
    )
    parser_disable_single.add_argument(
        "--config", type=str, default=CONFIG_FILE_DEFAULT, help="Path to config file"
    )

    args = parser.parse_args()

    if args.command == "block":
        domains = read_config(args.config)
        apply_blocking(domains)
        if args.test:
            print("Test mode active: blocking will be removed in 1 minute.")
            time.sleep(60)
            remove_blocking()
            print("Test complete: blocking removed.")
    elif args.command == "disable":
        try:
            print(
                f"Disable command accepted. Blocking will remain active for {args.delay} minutes."
            )
            for minutes_left in range(args.delay, 0, -1):
                print(f"Waiting... {minutes_left} minute(s) remaining until unblock.")
                time.sleep(60)
            remove_blocking()
            print(
                f"Blocking is now disabled for {args.duration} minutes. Enjoy your break!"
            )
            for minutes_left in range(args.duration, 0, -1):
                print(f"Re-enabling block in {minutes_left} minute(s)...")
                time.sleep(60)
        finally:
            domains = read_config(args.config)
            apply_blocking(domains)
            print("Blocking re-enabled automatically on exit.")
    elif args.command == "status":
        if is_blocking_active():
            print("Blocking is active.")
        else:
            print("Blocking is not active.")
    elif args.command == "update":
        domains = read_config(args.config)
        update_blocking(domains)
    elif args.command == "disable-single":
        target = args.target.strip()
        # Read config sections from the config file
        sections = read_config_sections(args.config)
        # Determine if the target is a section name or a single domain/subdomain
        if target in sections:
            domains_to_disable = sections[target]
        else:
            domains_to_disable = [target]
        # Generate the union of block entries (IPv4 & IPv6) for the target domains
        entries_to_disable = set()
        for domain in domains_to_disable:
            entries = generate_block_entries([domain])
            entries_to_disable.update(entries)

        if not check_single_disable_lock():
            print(
                "A single-domain disable is already active. Only one can be active at any given time."
            )
            sys.exit(1)
        create_single_disable_lock(target)
        try:
            print(
                f"Disable-single command accepted for '{target}'. Waiting 5 minutes before disabling..."
            )
            for minutes_left in range(5, 0, -1):
                print(
                    f"Waiting... {minutes_left} minute(s) until '{target}' is disabled."
                )
                time.sleep(60)
            remove_entries_for_target(target, entries_to_disable)
            print(f"'{target}' is now disabled for {args.duration} minute(s).")
            for minutes_left in range(args.duration, 0, -1):
                print(f"Re-enabling '{target}' in {minutes_left} minute(s)...")
                time.sleep(60)
        finally:
            add_entries_for_target(target, entries_to_disable)
            print(f"'{target}' block re-enabled automatically on exit.")
            remove_single_disable_lock()


if __name__ == "__main__":
    main()
