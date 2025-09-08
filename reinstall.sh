#!/bin/bash

# Reinstall script that preserves the database
# Simply calls setup.sh with the --preserve-db flag

# Get the directory where this script is located
REPO_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Call setup.sh with the preserve database flag
exec bash "$REPO_DIR/setup.sh" --preserve-db