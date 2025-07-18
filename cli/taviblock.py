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
MULTIPLE_LOCK_FILE = "/tmp/disable_multiple.lock"
BYPASS_LOCK_FILE = "/tmp/bypass.lock"


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


def check_multiple_disable_lock():
    """Return True if no multiple-domain disable is active; False otherwise."""
    return not os.path.exists(MULTIPLE_LOCK_FILE)


def create_multiple_disable_lock(targets):
    """Create a lock file to mark a multiple-domain disable as active."""
    with open(MULTIPLE_LOCK_FILE, "w") as f:
        f.write("\n".join(targets))


def remove_multiple_disable_lock():
    """Remove the multiple-domain disable lock file."""
    if os.path.exists(MULTIPLE_LOCK_FILE):
        os.remove(MULTIPLE_LOCK_FILE)


def check_bypass_lock():
    """Return True if bypass can be used (no active bypass or cooldown expired); False otherwise."""
    if not os.path.exists(BYPASS_LOCK_FILE):
        return True
    
    # Check if cooldown has expired
    try:
        with open(BYPASS_LOCK_FILE, 'r') as f:
            timestamp = float(f.read().strip())
        
        # Check if 1 hour (3600 seconds) has passed since the bypass was used
        current_time = time.time()
        if current_time - timestamp >= 3600:  # 1 hour cooldown
            os.remove(BYPASS_LOCK_FILE)
            return True
        else:
            remaining_minutes = int((3600 - (current_time - timestamp)) / 60) + 1
            print(f"Bypass is on cooldown. {remaining_minutes} minute(s) remaining.")
            return False
    except (ValueError, IOError):
        # If file is corrupted or unreadable, remove it and allow bypass
        os.remove(BYPASS_LOCK_FILE)
        return True


def create_bypass_lock():
    """Create a lock file to mark when bypass was last used."""
    with open(BYPASS_LOCK_FILE, "w") as f:
        f.write(str(time.time()))


def is_ultra_distracting(domain, sections):
    """Check if a domain is in the ultra_distracting section."""
    if 'ultra_distracting' in sections:
        return domain in sections['ultra_distracting']
    return False


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

    # 'disable' command: temporarily disable blocking after a delay
    parser_disable = subparsers.add_parser(
        "disable", help="Temporarily disable blocking after a delay"
    )
    parser_disable.add_argument(
        "--config", type=str, default=CONFIG_FILE_DEFAULT, help="Path to config file"
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
        "--config", type=str, default=CONFIG_FILE_DEFAULT, help="Path to config file"
    )

    # 'disable-multiple' command: temporarily disable multiple domains/sections
    parser_disable_multiple = subparsers.add_parser(
        "disable-multiple",
        help="Temporarily disable blocking for up to 4 domains/sections after a 10-minute wait",
    )
    parser_disable_multiple.add_argument(
        "--targets",
        required=True,
        nargs="+",
        type=str,
        help="Up to 4 domains/subdomains or section names to disable",
    )
    parser_disable_multiple.add_argument(
        "--config", type=str, default=CONFIG_FILE_DEFAULT, help="Path to config file"
    )

    # 'bypass' command: immediately disable all blocking for 5 minutes, once per hour
    parser_bypass = subparsers.add_parser(
        "bypass",
        help="Immediately disable all blocking for 5 minutes (once per hour)",
    )
    parser_bypass.add_argument(
        "--config", type=str, default=CONFIG_FILE_DEFAULT, help="Path to config file"
    )

    args = parser.parse_args()

    if args.command == "block":
        domains = read_config(args.config)
        apply_blocking(domains)
    elif args.command == "disable":
        try:
            print("Disable command accepted. Blocking will remain active for 30 minutes.")
            for minutes_left in range(30, 0, -1):
                print(f"Waiting... {minutes_left} minute(s) remaining until unblock.")
                time.sleep(60)
            remove_blocking()
            print("Blocking is now disabled for 30 minutes. Enjoy your break!")
            for minutes_left in range(30, 0, -1):
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
        # Get a flat list of domains from the config file
        domains_list = read_config(args.config)
        # Determine if the target is a section name or a single domain/subdomain
        if target in sections:
            domains_to_disable = sections[target]
        elif not target.endswith('.com') and (target + '.com') in sections:
            target = target + '.com'
            domains_to_disable = sections[target]
        elif target in domains_list:
            domains_to_disable = [target]
        elif not target.endswith('.com') and (target + '.com') in domains_list:
            target = target + '.com'
            domains_to_disable = [target]
        else:
            print(f"Error: The target '{target}' does not exist in the config file.")
            sys.exit(1)

        # Check if any of the domains are ultra-distracting
        has_ultra_distracting = any(is_ultra_distracting(domain, sections) for domain in domains_to_disable)
        wait_time = 30 if has_ultra_distracting else 5

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
                f"Disable-single command accepted for '{target}'. Waiting {wait_time} minutes before disabling..."
            )
            for minutes_left in range(wait_time, 0, -1):
                print(
                    f"Waiting... {minutes_left} minute(s) until '{target}' is disabled."
                )
                time.sleep(60)
            remove_entries_for_target(target, entries_to_disable)
            print(f"'{target}' is now disabled for 30 minute(s).")
            for minutes_left in range(30, 0, -1):
                print(f"Re-enabling '{target}' in {minutes_left} minute(s)...")
                time.sleep(60)
        finally:
            add_entries_for_target(target, entries_to_disable)
            print(f"'{target}' block re-enabled automatically on exit.")
            remove_single_disable_lock()
    elif args.command == "disable-multiple":
        if len(args.targets) > 4:
            print("Error: You can only specify up to 4 targets.")
            sys.exit(1)

        # Read config sections from the config file
        sections = read_config_sections(args.config)
        # Get a flat list of domains from the config file
        domains_list = read_config(args.config)
        
        # Process each target and collect domains to disable
        all_domains_to_disable = set()
        processed_targets = []
        
        for target in args.targets:
            target = target.strip()
            if target in sections:
                all_domains_to_disable.update(sections[target])
                processed_targets.append(target)
            elif not target.endswith('.com') and (target + '.com') in sections:
                target = target + '.com'
                all_domains_to_disable.update(sections[target])
                processed_targets.append(target)
            elif target in domains_list:
                all_domains_to_disable.add(target)
                processed_targets.append(target)
            elif not target.endswith('.com') and (target + '.com') in domains_list:
                target = target + '.com'
                all_domains_to_disable.add(target)
                processed_targets.append(target)
            else:
                print(f"Error: The target '{target}' does not exist in the config file.")
                sys.exit(1)

        # Check if any of the domains are ultra-distracting
        has_ultra_distracting = any(is_ultra_distracting(domain, sections) for domain in all_domains_to_disable)
        wait_time = 30 if has_ultra_distracting else 10

        # Generate the union of block entries (IPv4 & IPv6) for all target domains
        entries_to_disable = set()
        for domain in all_domains_to_disable:
            entries = generate_block_entries([domain])
            entries_to_disable.update(entries)

        if not check_multiple_disable_lock():
            print("A multiple-domain disable is already active. Only one can be active at any given time.")
            sys.exit(1)
        if not check_single_disable_lock():
            print("A single-domain disable is active. Please wait for it to complete.")
            sys.exit(1)

        create_multiple_disable_lock(processed_targets)
        try:
            print(f"Disable-multiple command accepted for targets: {', '.join(processed_targets)}")
            print(f"Waiting {wait_time} minutes before disabling...")
            for minutes_left in range(wait_time, 0, -1):
                print(f"Waiting... {minutes_left} minute(s) until targets are disabled.")
                time.sleep(60)
            remove_entries_for_target("multiple targets", entries_to_disable)
            print(f"Targets are now disabled for 30 minute(s).")
            for minutes_left in range(30, 0, -1):
                print(f"Re-enabling targets in {minutes_left} minute(s)...")
                time.sleep(60)
        finally:
            add_entries_for_target("multiple targets", entries_to_disable)
            print("Targets block re-enabled automatically on exit.")
            remove_multiple_disable_lock()
    elif args.command == "bypass":
        if not check_bypass_lock():
            sys.exit(1)
        
        # Check if other disable operations are active
        if not check_single_disable_lock():
            print("A single-domain disable is active. Cannot use bypass.")
            sys.exit(1)
        if not check_multiple_disable_lock():
            print("A multiple-domain disable is active. Cannot use bypass.")
            sys.exit(1)
        
        create_bypass_lock()
        try:
            print("Bypass activated! All blocking disabled for 5 minutes.")
            remove_blocking()
            for minutes_left in range(5, 0, -1):
                print(f"Re-enabling all blocking in {minutes_left} minute(s)...")
                time.sleep(60)
        finally:
            domains = read_config(args.config)
            apply_blocking(domains)
            print("All blocking re-enabled automatically. Bypass is now on 1-hour cooldown.")


if __name__ == "__main__":
    main()
