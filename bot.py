"""
MMX Facts — a Bluesky bot that shares facts about JAXA's MMX mission.

    python bot.py post      Post one random fact (run on a schedule)
    python bot.py replies   Reply to "show me the potato!", "feed my Phobos-ia"
                            and @-mentions with a fact (run every so often)
    python bot.py check     Check facts.yaml for problems (too long, missing images)
    python bot.py preview   Print a few example posts without logging in

Set DRY_RUN=1 to log in and look for triggers, but print instead of posting.
Login details come from the BSKY_HANDLE and BSKY_APP_PASSWORD environment variables.
"""

import io
import json
import os
import random
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from atproto import Client, client_utils, models
from PIL import Image

HERE = Path(__file__).parent
FACTS_FILE = HERE / "facts.yaml"
STATE_FILE = HERE / "state.json"

MAX_POST_LENGTH = 300          # Bluesky's limit (characters)
MAX_IMAGE_BYTES = 950_000      # Bluesky's limit is just under 1 MB
MAX_VIDEO_BYTES = 100_000_000  # GitHub won't store files bigger than 100 MB
WEB_UPLOAD_BYTES = 25_000_000  # GitHub's website only accepts uploads up to 25 MB
MAX_REPLIES_PER_RUN = 10       # safety cap so a flood can't make the bot spam
MAX_POST_AGE = timedelta(days=2)  # ignore triggers older than this

# Trigger phrases. Matching ignores capitals, spaces and punctuation, so
# "Show me the POTATO!!" and "feed my phobosia" both count.
TRIGGERS = {
    "potato": "show me the potato",
    "phobosia": "feed my phobos-ia",
}
# What the bot types into Bluesky search to find candidate posts.
SEARCH_QUERIES = ['"show me the potato"', '"feed my phobos"', "phobosia", '"phobos-ia"']

DRY_RUN = os.environ.get("DRY_RUN") == "1"


# ---------------------------------------------------------------- facts ----

def load_facts():
    with open(FACTS_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    facts = [x for x in (data.get("facts") or []) if x and x.get("text")]
    greetings = data.get("greetings") or {}
    return facts, greetings


def squash(text):
    """Lowercase and remove everything that isn't a letter or digit."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def build_text(fact, opener=None):
    """Return (TextBuilder, plain_text) for a fact, adding the opener if it fits."""
    body = str(fact["text"]).strip()
    link = fact.get("link")
    link_part = f"\n\n{link}" if link else ""

    if opener and len(f"{opener}\n\n{body}{link_part}") <= MAX_POST_LENGTH:
        body = f"{opener}\n\n{body}"

    tb = client_utils.TextBuilder()
    tb.text(body)
    if link:
        tb.text("\n\n")
        tb.link(link, link)
    return tb, body + link_part


def load_image(path):
    """Read an image, shrinking it if it's over Bluesky's size limit."""
    img_path = HERE / path
    raw = img_path.read_bytes()
    with Image.open(io.BytesIO(raw)) as img:
        size = img.size
        if len(raw) <= MAX_IMAGE_BYTES:
            return raw, size
        img = img.convert("RGB")
        quality, scale = 90, 1.0
        while True:
            w, h = int(img.width * scale), int(img.height * scale)
            buf = io.BytesIO()
            img.resize((w, h)).save(buf, "JPEG", quality=quality)
            if buf.tell() <= MAX_IMAGE_BYTES or w < 400:
                return buf.getvalue(), (w, h)
            if quality > 70:
                quality -= 10
            else:
                scale *= 0.85


def video_size(path):
    """Return (width, height) of a video so Bluesky shows it the right shape, or None."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0", str(HERE / path)],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        w, h = (int(x) for x in out.split(",")[:2])
        return w, h
    except Exception:
        return None


# ---------------------------------------------------------------- state ----

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"replied": [], "recent_facts": []}


def save_state(state):
    state["replied"] = state["replied"][-1000:]
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


def pick_fact(facts, state):
    """Choose a random fact, avoiding ones used recently."""
    recent = state.get("recent_facts", [])
    avoid = recent[-(len(facts) // 2):] if len(facts) > 1 else []
    choices = [i for i, f in enumerate(facts) if squash(f["text"])[:60] not in avoid]
    i = random.choice(choices or range(len(facts)))
    state.setdefault("recent_facts", []).append(squash(facts[i]["text"])[:60])
    state["recent_facts"] = state["recent_facts"][-50:]
    return facts[i]


# -------------------------------------------------------------- posting ----

def login():
    handle = os.environ["BSKY_HANDLE"]
    client = Client()
    client.login(handle, os.environ["BSKY_APP_PASSWORD"])
    return client


def send(client, fact, opener=None, reply_to=None):
    tb, plain = build_text(fact, opener)
    if DRY_RUN:
        where = f" (reply to {reply_to.parent.uri})" if reply_to else ""
        print(f"--- DRY RUN: would post{where} ---\n{plain}")
        for kind in ("image", "video"):
            if fact.get(kind):
                print(f"[{kind}: {fact[kind]} | alt: {fact.get('alt', '')}]")
        print()
        return

    if fact.get("video"):
        size = video_size(fact["video"])
        client.send_video(
            tb, video=(HERE / fact["video"]).read_bytes(), video_alt=fact.get("alt", ""),
            reply_to=reply_to, langs=["en"],
            video_aspect_ratio=models.AppBskyEmbedDefs.AspectRatio(width=size[0], height=size[1])
            if size else None,
        )
    elif fact.get("image"):
        data, (w, h) = load_image(fact["image"])
        client.send_image(
            tb, image=data, image_alt=fact.get("alt", ""), reply_to=reply_to,
            image_aspect_ratio=models.AppBskyEmbedDefs.AspectRatio(width=w, height=h),
            langs=["en"],
        )
    else:
        client.send_post(tb, reply_to=reply_to, langs=["en"])
    print(f"Posted: {plain[:60]}...")


def reply_ref(uri, cid, record):
    parent = models.ComAtprotoRepoStrongRef.Main(uri=uri, cid=cid)
    root = parent
    if getattr(record, "reply", None):   # replying inside a thread: keep its root
        r = record.reply.root
        root = models.ComAtprotoRepoStrongRef.Main(uri=r.uri, cid=r.cid)
    return models.AppBskyFeedPost.ReplyRef(parent=parent, root=root)


def is_recent(timestamp):
    try:
        when = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return False
    return datetime.now(timezone.utc) - when < MAX_POST_AGE


# ---------------------------------------------------------------- modes ----

def do_post():
    facts, _ = load_facts()
    state = load_state()
    client = login()
    send(client, pick_fact(facts, state))
    save_state(state)


def find_triggers(client, my_did):
    """Return a list of (trigger_name, uri, cid, record, author_did) to answer."""
    found = {}

    # 1. Posts containing a trigger phrase
    for query in SEARCH_QUERIES:
        resp = client.app.bsky.feed.search_posts(
            params={"q": query, "sort": "latest", "limit": 50}
        )
        for post in resp.posts:
            text = squash(getattr(post.record, "text", "") or "")
            for name, phrase in TRIGGERS.items():
                if squash(phrase) in text and is_recent(post.indexed_at):
                    found[post.uri] = (name, post.uri, post.cid, post.record, post.author.did)

    # 2. Posts that @-mention the bot
    resp = client.app.bsky.notification.list_notifications(params={"limit": 50})
    for n in resp.notifications:
        if n.reason == "mention" and n.uri not in found and is_recent(n.indexed_at):
            found[n.uri] = ("mention", n.uri, n.cid, n.record, n.author.did)

    # Never answer the bot's own posts (e.g. its pinned post with the phrases)
    return [t for t in found.values() if t[4] != my_did]


def do_replies():
    facts, greetings = load_facts()
    state = load_state()
    client = login()
    my_did = client.me.did
    already = set(state["replied"])

    todo = [t for t in find_triggers(client, my_did) if t[1] not in already]
    answered_authors = set()
    count = 0
    for name, uri, cid, record, author in todo:
        if count >= MAX_REPLIES_PER_RUN:
            print("Reached the per-run reply limit; the rest will wait for next time.")
            break
        state["replied"].append(uri)       # mark as seen even if we skip it
        if author in answered_authors:     # one reply per person per run
            continue
        opener = random.choice(greetings.get(name) or [None])
        try:
            send(client, pick_fact(facts, state), opener, reply_ref(uri, cid, record))
            answered_authors.add(author)
            count += 1
        except Exception as e:  # one failed reply shouldn't stop the rest
            print(f"Couldn't reply to {uri}: {e}")

    print(f"Replied to {count} post(s).")
    if not DRY_RUN:
        save_state(state)


def do_check():
    facts, greetings = load_facts()
    problems = 0
    longest_opener = max((len(g) for gs in greetings.values() for g in gs or []), default=0)
    for n, fact in enumerate(facts, 1):
        _, plain = build_text(fact)
        label = f"Fact {n} ({str(fact['text'])[:40]}...)"
        if len(plain) > MAX_POST_LENGTH:
            print(f"❌ {label} is {len(plain)} characters; the limit is {MAX_POST_LENGTH}.")
            problems += 1
        elif len(plain) + longest_opener + 2 > MAX_POST_LENGTH:
            print(f"ℹ️  {label} is long enough that some replies will skip the greeting.")
        if fact.get("image"):
            if not (HERE / fact["image"]).exists():
                print(f"❌ {label}: image file '{fact['image']}' not found.")
                problems += 1
            elif not fact.get("alt"):
                print(f"⚠️  {label} has an image but no alt text.")
        if fact.get("video"):
            vid = HERE / str(fact["video"])
            if fact.get("image"):
                print(f"❌ {label} has both an image and a video; Bluesky allows only one.")
                problems += 1
            elif not vid.exists():
                print(f"❌ {label}: video file '{fact['video']}' not found.")
                problems += 1
            elif vid.suffix.lower() != ".mp4":
                print(f"❌ {label}: videos need to be .mp4 files.")
                problems += 1
            elif vid.stat().st_size > MAX_VIDEO_BYTES:
                print(f"❌ {label}: video is over 100 MB, too big to store on GitHub.")
                problems += 1
            elif not fact.get("alt"):
                print(f"⚠️  {label} has a video but no alt text.")
        if fact.get("link") and not str(fact["link"]).startswith(("http://", "https://")):
            print(f"❌ {label}: link should start with https://")
            problems += 1
    print(f"\nChecked {len(facts)} facts: {problems} problem(s).")
    sys.exit(1 if problems else 0)


def do_preview():
    facts, greetings = load_facts()
    for name in ["post", *greetings]:
        fact = random.choice(facts)
        opener = random.choice(greetings[name]) if name in greetings else None
        _, plain = build_text(fact, opener)
        print(f"===== {name} ({len(plain)} chars) =====\n{plain}\n")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    {"post": do_post, "replies": do_replies, "check": do_check,
     "preview": do_preview}[mode]()
