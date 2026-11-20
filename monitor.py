#!/usr/bin/env python3
"""Poll an FxEmbed/FxTwitter RSS feed and forward eligible posts to Discord."""
import json
import os
import re
import sys
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
from html import unescape

HANDLE = os.getenv("X_HANDLE", "DeItaone").lstrip("@")
WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"]
FEED_URL = f"https://fxtwitter.com/{HANDLE}/feed.xml"
STATE_PATH = Path("state.json")
USER_AGENT = "DeItaoneDiscordBridge/1.0 (GitHub Actions; RSS polling)"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read()

def local_name(tag):
    return tag.rsplit("}", 1)[-1].lower()

def clean_html(value):
    value = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.I)
    value = re.sub(r"</p\s*>", "\n\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    return unescape(value).strip()

def parse_feed(xml_bytes):
    root = ET.fromstring(xml_bytes)
    entries = []
    for item in root.iter():
        if local_name(item.tag) not in ("item", "entry"):
            continue
        fields = {}
        for child in item:
            key = local_name(child.tag)
            val = child.attrib.get("href", "") if key == "link" else (child.text or "")
            if key not in fields:
                fields[key] = val.strip()
            elif key == "category":
                fields[key] += " " + val.strip()
        link = fields.get("link", "")
        if not link:
            continue
        # Normalize links to canonical X URLs when the feed provides an FxTwitter URL.
        link = link.replace("https://fxtwitter.com/", "https://x.com/")
        link = link.replace("https://fixupx.com/", "https://x.com/")
        guid = fields.get("guid") or fields.get("id") or link
        title = clean_html(fields.get("title", ""))
        description = clean_html(fields.get("description") or fields.get("summary") or fields.get("content", ""))
        text = description or title
        cats = (fields.get("category", "") + " " + fields.get("type", "")).lower()
        entries.append({
            "id": guid, "link": link, "title": title, "text": text,
            "categories": cats, "published": fields.get("pubdate") or fields.get("published") or fields.get("updated", "")
        })
    # Newest first; preserve feed order if dates are not parseable.
    return entries

def is_reply_or_repost(post):
    # Only exclude these when the feed explicitly exposes a reliable marker.
    marker = post["categories"]
    text = (post["title"] + "\n" + post["text"]).strip()
    if re.search(r"\b(reply|repost|retweet|retweeted)\b", marker, re.I):
        return True
    if re.match(r"^RT\s+@", text, re.I):
        return True
    return False

def send_discord(post):
    content = f"**@{HANDLE}**\n{post['text'][:3500]}\n\n{post['link']}"
    payload = json.dumps({"content": content, "allowed_mentions": {"parse": []}}).encode()
    req = urllib.request.Request(
        WEBHOOK, data=payload,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        if response.status not in (200, 204):
            raise RuntimeError(f"Discord returned HTTP {response.status}")

def main():
    try:
        posts = parse_feed(fetch(FEED_URL))
    except Exception as exc:
        print(f"ERROR: Could not read feed {FEED_URL}: {exc}", file=sys.stderr)
        raise

    if not posts:
        print("Feed contained no entries.")
        return

    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}
    last_id = state.get("last_id")

    # First run establishes a baseline and intentionally sends nothing historic.
    if not last_id:
        STATE_PATH.write_text(json.dumps({"last_id": posts[0]["id"]}, indent=2) + "\n")
        print(f"Initialized baseline at newest feed item; no historical posts sent. Found {len(posts)} entries.")
        return

    new_posts = []
    for post in posts:
        if post["id"] == last_id:
            break
        new_posts.append(post)

    if not new_posts:
        print("No new posts.")
        return

    # Process oldest to newest. Advance the cursor only after successful delivery.
    for post in reversed(new_posts):
        if is_reply_or_repost(post):
            print(f"Skipped marked reply/repost: {post['link']}")
            continue
        send_discord(post)
        print(f"Delivered: {post['link']}")

    # Record the newest item, including filtered items, to avoid rechecking forever.
    STATE_PATH.write_text(json.dumps({"last_id": posts[0]["id"]}, indent=2) + "\n")

if __name__ == "__main__":
    main()
