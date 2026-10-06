import os
import sys
import json
import time
from collections import deque
from pathlib import Path

import requests
from dotenv import load_dotenv

from collectors.chat_logger import connect, parse

load_dotenv()
CLIENT_ID = os.environ["TWITCH_CLIENT_ID"]
USER_TOKEN = os.environ["TWITCH_USER_TOKEN"]
API = "https://api.twitch.tv/helix"
HEADERS = {"Client-Id": CLIENT_ID, "Authorization": f"Bearer {USER_TOKEN}"}

WINDOW = 10        # seconds that count as "right now"
BASELINE = 300     # seconds that count as "normal"
SPIKE_RATIO = 3    # how many times busier than normal = spike
MIN_MSGS = 15      # ignore "spikes" in tiny chats
COOLDOWN = 60      # seconds to wait between clips
WARMUP = 120       # seconds of data before we trust "normal"
STATUS_EVERY = 15  # seconds between heartbeat prints


def check_token():
    r = requests.get("https://id.twitch.tv/oauth2/validate",
                     headers={"Authorization": f"OAuth {USER_TOKEN}"})
    if r.status_code != 200:
        sys.exit("user token is invalid or expired. redo the authorize URL step and update .env")
    info = r.json()
    if "clips:edit" not in info.get("scopes", []):
        sys.exit("token is missing the clips:edit scope. redo the authorize URL step")
    print(f"token ok, expires in ~{info.get('expires_in', 0) // 60} min")


def get_user_id(login):
    r = requests.get(f"{API}/users", headers=HEADERS, params={"login": login})
    r.raise_for_status()
    data = r.json()["data"]
    if not data:
        sys.exit(f"no twitch user named '{login}'. check the name in their URL")
    return data[0]["id"]


def create_clip(broadcaster_id):
    r = requests.post(f"{API}/clips", headers=HEADERS,
                      params={"broadcaster_id": broadcaster_id})
    if r.status_code != 202:
        print(f"clip failed: {r.status_code} {r.text}")
        return None
    return r.json()["data"][0]["id"]


def main(channel):
    check_token()
    broadcaster_id = get_user_id(channel)
    Path("data/raw").mkdir(parents=True, exist_ok=True)
    log_path = f"data/raw/pipeline_clips_{channel}.jsonl"

    sock = connect(channel)
    reader = sock.makefile("r", encoding="utf-8", errors="replace")
    print(f"watching #{channel} for spikes (warming up {WARMUP}s)...")

    times = deque()
    start = time.time()
    last_clip = 0
    last_status = 0

    with open(log_path, "a", encoding="utf-8") as log:
        for line in reader:
            line = line.rstrip("\r\n")
            if line.startswith("PING"):
                sock.sendall(b"PONG :tmi.twitch.tv\r\n")
                continue
            if not parse(line):
                continue

            now = time.time()
            times.append(now)
            while times and times[0] < now - BASELINE:
                times.popleft()

            recent = sum(1 for t in times if t > now - WINDOW)
            elapsed = max(min(now - start, BASELINE), 1)
            normal = len(times) / elapsed * WINDOW

            if now - last_status > STATUS_EVERY:
                print(f"last {WINDOW}s: {recent} msgs | normal: ~{normal:.0f}")
                last_status = now

            if now - start < WARMUP or now - last_clip < COOLDOWN:
                continue
            if recent >= MIN_MSGS and recent > SPIKE_RATIO * normal:
                last_clip = now
                print(f"SPIKE: {recent} msgs in {WINDOW}s (normal ~{normal:.0f})")
                clip_id = create_clip(broadcaster_id)
                url = f"https://clips.twitch.tv/{clip_id}" if clip_id else None
                log.write(json.dumps({
                    "ts": int(now * 1000),
                    "channel": channel,
                    "recent": recent,
                    "normal": round(normal, 1),
                    "clip_id": clip_id,
                    "url": url,
                    "label": None,   # you fill this in later: good / bad
                }) + "\n")
                log.flush()
                if url:
                    print(f"clipped -> {url}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python -m live.spike_clipper <channel>")
    main(sys.argv[1].lower())