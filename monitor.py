
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

X_HANDLES = [
    "DeItaone",
    "WatcherGuru",
    "BullTheoryio",
    "KobeissiLetter",
    "PolymarketMoney",
]
WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"]
API_URL = f"https://api.fxtwitter.com/2/profile/{HANDLE}/statuses?count=50"
STATE = Path("state.json")
USER_AGENT = "DiscordX-Monitor/1.0"

def fetch_posts():
    req = urllib.request.Request(
        API_URL,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()
    except urllib.error.HTTPError as e:
        if e.code == 204:
            return []
        raise RuntimeError(f"FxTwitter HTTP {e.code}") from e

    if not data:
        return []

    result = json.loads(data)
    if result.get("code") != 200:
        raise RuntimeError(f"API error: {result}")

    posts = result.get("results")
    if not isinstance(posts, list):
        raise RuntimeError("API results missing or invalid")

    return posts


def is_original(post):
    if post.get("type") == "tombstone":
        return False

    if post.get("replying_to"):
        return False

    if post.get("reposted_by"):
        return False

    author = post.get("author") or {}
    screen_name = (author.get("screen_name") or "").lstrip("@")

    if screen_name and screen_name.lower() != HANDLE.lower():
        return False

    return True


def send_to_discord(post):
    text = post.get("text", "")
    link = post.get("url", "")

    message = (
        f"**@{HANDLE}**\n"
        f"{text[:1600]}\n\n"
        f"{link}"
    )

    payload = json.dumps({
        "content": message,
        "allowed_mentions": {"parse": []}
    }).encode("utf-8")

    req = urllib.request.Request(
        WEBHOOK,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        if response.status not in (200, 204):
            raise RuntimeError("Discord delivery failed")


def main():
    posts = fetch_posts()

    if not posts:
        print("API returned no posts.")
        return

    latest_id = str(posts[0].get("id", ""))

    if not latest_id:
        raise RuntimeError("Latest post has no ID")

    state = (
        json.loads(STATE.read_text())
        if STATE.exists()
        else {}
    )

    last_id = str(state.get("last_id", ""))

    # First run: establish baseline only.
    if not last_id:
        STATE.write_text(json.dumps({"last_id": latest_id}, indent=2))
        print("API baseline initialized. No old posts sent.")
        return

    new_posts = []

    for post in posts:
        post_id = str(post.get("id", ""))

        if post_id == last_id:
            break

        if post_id:
            new_posts.append(post)

    if not new_posts:
        print("No new posts.")
        return

    sent = 0
    skipped = 0

    for post in reversed(new_posts):
        if not is_original(post):
            skipped += 1
            print("Skipped reply or repost:", post.get("id"))
            continue

        send_to_discord(post)
        sent += 1
        print("Delivered:", post.get("url"))

    STATE.write_text(
        json.dumps({"last_id": latest_id}, indent=2)
    )

    print(f"Delivered {sent}; skipped {skipped}.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR:", e, file=sys.stderr)
        raise
