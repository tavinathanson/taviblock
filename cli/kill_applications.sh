#!/bin/bash
# This script checks for blocked domains in /etc/hosts and kills the corresponding applications
# or closes browser tabs. It continuously checks every 10 seconds.

CONFIG_FILE="$(dirname "$0")/../config.txt"

# Function to extract domains from config file
extract_domains() {
    # Remove comments, section headers, and blank lines
    grep -v "^#" "$CONFIG_FILE" | grep -v "^\[.*\]$" | grep -v "^$"
}

# Function to check if a domain is blocked in hosts file
is_domain_blocked() {
    local domain=$1
    grep -q "127\.0\.0\.1[[:space:]]*$domain" /etc/hosts
}

# Function to close Chrome tabs for a specific domain
close_chrome_tabs() {
    local domain=$1
    echo "$(date): $domain block is active; closing any matching tabs in Google Chrome."
    
    osascript <<EOF
if application "Google Chrome" is running then
    tell application "Google Chrome"
        repeat with w in windows
            set matchingTabs to {}
            repeat with t in tabs of w
                set tabURL to URL of t
                # Exact domain matching - checks if the domain is exactly in the URL
                # This prevents subdomains of different services from matching (e.g., something.sharepoint.com won't match microsoft.com)
                if tabURL contains "://$domain" or tabURL contains "://www.$domain" then
                    copy t to end of matchingTabs
                end if
            end repeat
            repeat with t in matchingTabs
                close t
            end repeat
        end repeat
    end tell
end if
EOF
}

# Function to kill specific applications
kill_application() {
    local app_name=$1
    local domain=$2
    
    if pgrep -x "$app_name" > /dev/null; then
        echo "$(date): $app_name is running and $domain block is active; terminating $app_name."
        killall "$app_name"
    fi
}

while true; do
    # Special case for Slack application
    if is_domain_blocked "slack.com"; then
        kill_application "Slack" "slack.com"
    fi
    
    # Process all domains in config file for Chrome tabs
    all_domains=$(extract_domains)
    
    for domain in $all_domains; do
        if is_domain_blocked "$domain"; then
            # Close Chrome tabs for this domain
            close_chrome_tabs "$domain"
            
            # Add specific application handling based on domain
            case "$domain" in
                "netflix.com")
                    # If Netflix has a desktop app in the future, add logic here
                    ;;
                "youtube.com")
                    # If YouTube has a desktop app in the future, add logic here
                    ;;
                # Add other application-specific cases here as needed
            esac
        fi
    done
    
    sleep 10
done
