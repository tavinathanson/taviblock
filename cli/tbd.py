#!/usr/bin/env python3
import sys
import subprocess
import os

def run_command(command):
    """Run a command and return its output."""
    try:
        # Run command without capturing output so it displays directly
        result = subprocess.run(
            command,
            stdout=None,
            stderr=None
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return False

def main():
    targets = sys.argv[1:]
    if len(targets) == 0:
        # Just 'tbd' - disable all blocking
        return run_command(['taviblock', 'disable'])
    elif len(targets) == 1:
        # 'tbd slack' - disable single domain/section
        return run_command(['taviblock', 'disable-single', '--target', targets[0]])
    elif len(targets) <= 4:
        # 'tbd slack gmail' - disable multiple domains/sections
        return run_command(['taviblock', 'disable-multiple', '--targets'] + targets)
    else:
        print("Usage: sudo tbd [domain1 [domain2 [domain3 [domain4]]]]", file=sys.stderr)
        print("  sudo tbd              - Disable all blocking for 30 minutes", file=sys.stderr)
        print("  sudo tbd domain       - Disable blocking for a single domain/section", file=sys.stderr)
        print("  sudo tbd d1 d2 d3 d4  - Disable blocking for up to 4 domains/sections", file=sys.stderr)
        return False

if __name__ == "__main__":
    sys.exit(0 if main() else 1) 