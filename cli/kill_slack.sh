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

    # Check if the blocking entry for gmail.com is present in /etc/hosts
    if grep -q "127\.0\.0\.1[[:space:]]*gmail\.com" /etc/hosts; then
        echo "$(date): gmail.com block is active; closing any Gmail tabs in Google Chrome."
        osascript <<'EOF'
if application "Google Chrome" is running then
    tell application "Google Chrome"
        repeat with w in windows
            set gmailTabs to {}
            repeat with t in tabs of w
                if (URL of t contains "gmail.com") or (URL of t contains "mail.google.com") then
                    copy t to end of gmailTabs
                end if
            end repeat
            repeat with t in gmailTabs
                close t
            end repeat
        end repeat
    end tell
end if
EOF
    fi

    sleep 10
done
