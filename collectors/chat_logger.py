import socket
import json
import sys
from pathlib import Path
from datetime import datetime

HOST = "irc.chat.twitch.tv"
PORT = 6667
NICK = "justinfan12345"   # anonymous read-only login


def connect(channel):
    sock = socket.socket()
    sock.connect((HOST, PORT))
    sock.sendall(b"CAP REQ :twitch.tv/tags\r\n")
    sock.sendall(f"NICK {NICK}\r\n".encode())
    sock.sendall(f"JOIN #{channel}\r\n".encode())
    return sock


def parse(line):
    if not line.startswith("@") or " PRIVMSG " not in line:
        return None
    tag_str, rest = line[1:].split(" ", 1)
    tags = dict(kv.split("=", 1) for kv in tag_str.split(";"))
    text = rest.split(" :", 1)[1]
    return {
        "ts": int(tags["tmi-sent-ts"]),
        "user": tags.get("display-name"),
        "user_id": tags.get("user-id"),
        "emotes": tags.get("emotes", ""),
        "text": text,
    }


def main(channel):
    Path("data/raw").mkdir(parents=True, exist_ok=True)
    path = f"data/raw/chat_{channel}_{datetime.now():%Y%m%d}.jsonl"
    sock = connect(channel)
    reader = sock.makefile("r", encoding="utf-8", errors="replace")
    print(f"logging #{channel} chat to {path}")

    with open(path, "a", encoding="utf-8") as out:
        for line in reader:
            line = line.rstrip("\r\n")
            if line.startswith("PING"):
                sock.sendall(b"PONG :tmi.twitch.tv\r\n")
                continue
            msg = parse(line)
            if msg:
                out.write(json.dumps(msg) + "\n")
                out.flush()
                print(f"{msg['user']}: {msg['text']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python -m collectors.chat_logger <channel>")
    main(sys.argv[1].lower())