#!/usr/bin/env python3
import sys, json, struct


def read_message():
    raw_length = sys.stdin.buffer.read(4)
    if len(raw_length) == 0:
        sys.exit(0)
    message_length = struct.unpack("=I", raw_length)[0]
    message = sys.stdin.buffer.read(message_length).decode("utf-8")
    return json.loads(message)


def send_message(message_content):
    message_json = json.dumps(message_content)
    encoded_content = message_json.encode("utf-8")
    sys.stdout.buffer.write(struct.pack("=I", len(encoded_content)))
    sys.stdout.buffer.write(encoded_content)
    sys.stdout.buffer.flush()


def get_status():
    # Read the status from the file updated by the CLI tool
    try:
        with open("/tmp/gmailblock_status.txt", "r") as f:
            status = f.read().strip()
        if status in ["blocked", "unblocked"]:
            return status
    except Exception:
        pass
    return "unblocked"  # Default to unblocked if file doesn't exist


def main():
    while True:
        try:
            message = read_message()
        except Exception:
            break
        if message.get("command") == "getStatus":
            send_message({"status": get_status()})
        else:
            send_message({"error": "unknown command"})


if __name__ == "__main__":
    main()
