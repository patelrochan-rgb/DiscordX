import time
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
STATE = Path("state.json")
USER_AGENT = "DiscordX-Monitor/1.0"



def fetch_posts(handle):
    api_url = (
        f"https://api.fxtwitter.com/2/profile/"
        f"{handle}/statuses?count=50"
    )

    delays = [0, 3, 6, 12]
    last_error = None

    for attempt, delay in enumerate(delays, start=1):
        if delay:
            print(
                f"Retrying @{handle} in {delay} seconds "
                f"(attempt {attempt}/4)..."
            )
            time.sleep(delay)

        req = urllib.request.Request(
            api_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = response.read()

            if not data:
                return []

            result = json.loads(data)

            if result.get("code") != 200:
                raise RuntimeError(
                    f"API error for @{handle}: {result}"
                )

            posts = result.get("results")

            if not isinstance(posts, list):
                raise RuntimeError(
                    f"API results missing for @{handle}"
                )

            return posts

        except urllib.error.HTTPError as e:
            if e.code == 204:
                return []

            if e.code not in (404, 429, 500, 502, 503, 504):
                raise RuntimeError(
                    f"FxTwitter HTTP {e.code} for @{handle}"
                ) from e

            last_error = e
            print(
                f"FxTwitter HTTP {e.code} for @{handle} "
                f"(attempt {attempt}/4)"
            )

        except (urllib.error.URLError, TimeoutError) as e:
            last_error = e
            print(
                f"Connection error for @{handle}: {e} "
                f"(attempt {attempt}/4)"
            )

    raise RuntimeError(
        f"FxTwitter failed for @{handle} after 4 attempts: "
        f"{last_error}"
    )



def is_original(post, handle):
    if post.get("type") == "tombstone":
        return False

    if post.get("replying_to"):
        return False

    if post.get("reposted_by"):
        return False

    author = post.get("author") or {}
    screen_name = (author.get("screen_name") or "").lstrip("@")

    if screen_name and screen_name.lower() != handle.lower():
        return False

    return True


def send_to_discord(post, handle):
    text = post.get("text", "")
    link = post.get("url", "")

    message = (
        f"**@{handle}**\n"
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
            raise RuntimeError(
                f"Discord delivery failed for @{handle}"
            )


def load_state():
    if not STATE.exists():
        return {"accounts": {}}

    data = json.loads(STATE.read_text())

    # Migrate the original single-account state automatically.
    if "accounts" not in data:
        old_id = str(data.get("last_id", ""))
        accounts = {}

        if old_id:
            accounts["DeItaone"] = old_id

        return {"accounts": accounts}

    return data


def save_state(state):
    STATE.write_text(json.dumps(state, indent=2))


def monitor_account(handle, state):
    print(f"\nChecking @{handle}...")

    posts = fetch_posts(handle)

    if not posts:
        print(f"No posts returned for @{handle}.")
        return

    latest_id = str(posts[0].get("id", ""))

    if not latest_id:
        raise RuntimeError(f"Latest post has no ID for @{handle}")

    accounts = state["accounts"]
    last_id = str(accounts.get(handle, ""))

    # New account: establish baseline without sending old posts.
    if not last_id:
        accounts[handle] = latest_id
        print(f"Baseline initialized for @{handle}.")
        return

    new_posts = []

    for post in posts:
        post_id = str(post.get("id", ""))

        if post_id == last_id:
            break

        if post_id:
            new_posts.append(post)

    if not new_posts:
        print(f"No new posts from @{handle}.")
        return

    # If the previous cursor is no longer in the fetched timeline,
    # reset the baseline instead of repeatedly sending old posts.
    if not any(str(p.get("id", "")) == last_id for p in posts):
        accounts[handle] = latest_id
        print(f"Previous cursor not found. Baseline reset for @{handle}.")
        return

    sent = 0
    skipped = 0

    for post in reversed(new_posts):
        if not is_original(post, handle):
            skipped += 1
            print(f"Skipped reply/repost from @{handle}: {post.get('id')}")
            continue

        send_to_discord(post, handle)
        sent += 1
        print(f"Delivered @{handle}: {post.get('url')}")

    accounts[handle] = latest_id

    print(
        f"@{handle}: delivered {sent}; skipped {skipped}."
    )


def main():
    state = load_state()

    errors = []

    for handle in X_HANDLES:
        try:
            monitor_account(handle, state)
        except Exception as e:
            errors.append(f"@{handle}: {e}")
            print(f"ERROR monitoring @{handle}: {e}", file=sys.stderr)

    # Save successful account progress and preserve failed cursors.
    save_state(state)

    if errors:
        print("\nSome accounts had errors:")
        for error in errors:
            print(error)
    else:
        print("\nAll accounts checked successfully.")


if __name__ == "__main__":
    main()
