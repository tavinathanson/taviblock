#!/bin/bash
# This script kills the Slack process if the block for slack.com is active in /etc/hosts.
# It continuously checks every 10 seconds.
while true; do
    # Check if the blocking entry for slack.com is present in /etc/hosts
    if grep -q "127\.0\.0\.1 slack\.com" /etc/hosts; then
        if pgrep -x "Slack" > /dev/null; then
            echo "$(date): Slack is running and slack.com block is active; terminating Slack."
            killall Slack
        fi
    fi
    sleep 10
done 