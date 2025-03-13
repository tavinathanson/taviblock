#!/usr/bin/env python3
import time
import socket
import subprocess
from pathlib import Path

# Default location of config file, assumed to be in the repository root
CONFIG_FILE_DEFAULT = Path(__file__).resolve().parent.parent / "config.txt"


def read_domains(config_file):
    """
    Reads the config file and returns a list of domains.
    It ignores comments and section headers.
    """
    domains = set()
    with open(config_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                # Skip section headers
                continue
            domains.add(line)
    return list(domains)


def resolve_domain(domain):
    """
    Resolves a domain name to its IP addresses by querying external DNS using dig.
    Returns a set of IP addresses.
    """
    ip_set = set()
    try:
        # Query A records
        result_a = subprocess.run(["dig", "+short", domain, "A"], capture_output=True, text=True)
        # Query AAAA records
        result_aaaa = subprocess.run(["dig", "+short", domain, "AAAA"], capture_output=True, text=True)
        output = result_a.stdout + "\n" + result_aaaa.stdout
        for line in output.splitlines():
            ip = line.strip()
            if ip:
                ip_set.add(ip)
    except Exception as e:
        print(f"Error resolving {domain}: {e}")
    return ip_set


def generate_pf_rules(ips):
    """
    Generates pf rules to block outgoing connections to each IP.
    For IPv4: 'block drop quick from any to <ip>'
    For IPv6: 'block drop quick inet6 from any to <ip>'
    """
    rules = []
    for ip in sorted(ips):
        if '.' in ip:
            rules.append(f"block drop quick from any to {ip}")
        elif ':' in ip:
            rules.append(f"block drop quick inet6 from any to {ip}")
    return rules


def update_pf_rules(rules):
    """
    Writes the generated rules to a temporary file and loads them into pf using an anchor.
    """
    temp_rule_file = "/tmp/taviblock_pf.rules"
    try:
        with open(temp_rule_file, "w") as f:
            f.write("\n".join(rules) + "\n")
        # Load rules into the pf anchor named 'taviblock_pf'
        subprocess.run(["pfctl", "-a", "taviblock_pf", "-f", temp_rule_file], check=True)
        print("PF rules updated.")
    except Exception as e:
        print(f"Error updating PF rules: {e}")


def main():
    update_interval = 300  # update every 5 minutes (300 seconds)
    config_file = CONFIG_FILE_DEFAULT
    while True:
        print("Updating PF rules...")
        domains = read_domains(config_file)
        all_ips = set()
        for domain in domains:
            ips = resolve_domain(domain)
            all_ips.update(ips)
        rules = generate_pf_rules(all_ips)
        if rules:
            update_pf_rules(rules)
        else:
            print("No PF rules generated.")
        print(f"Sleeping for {update_interval} seconds...")
        time.sleep(update_interval)


if __name__ == '__main__':
    main() 