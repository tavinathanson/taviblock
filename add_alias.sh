#!/bin/bash

# Script to add block alias to shell config

echo "=== Adding block alias ==="

# Detect shell from SHELL environment variable or current shell
if [[ "$SHELL" == *"zsh"* ]] || [[ -n "$ZSH_VERSION" ]]; then
    SHELL_CONFIG="$HOME/.zshrc"
    DETECTED_SHELL="zsh"
elif [[ "$SHELL" == *"bash"* ]] || [[ -n "$BASH_VERSION" ]]; then
    SHELL_CONFIG="$HOME/.bash_profile"
    DETECTED_SHELL="bash"
else
    echo "Unable to detect shell type. Please add this line manually to your shell config:"
    echo "alias block='sudo block'"
    exit 1
fi

echo "Detected shell: $DETECTED_SHELL"
echo "Config file: $SHELL_CONFIG"

# Check if alias already exists
if grep -q "alias block='sudo block'" "$SHELL_CONFIG" 2>/dev/null; then
    echo ""
    echo "✓ Alias already exists in $SHELL_CONFIG"
    echo ""
    echo "You're all set! Just use: block"
else
    echo "" >> "$SHELL_CONFIG"
    echo "# Block - domain blocking tool" >> "$SHELL_CONFIG"
    echo "alias block='sudo block'" >> "$SHELL_CONFIG"
    echo ""
    echo "✓ Added alias to $SHELL_CONFIG"
    echo ""
    echo "Run this command to activate the alias:"
    echo "  source $SHELL_CONFIG"
    echo ""
    echo "Or open a new terminal window."
fi