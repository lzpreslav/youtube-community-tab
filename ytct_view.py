#!/usr/bin/env python3
"""Build browsable index.html pages for ytct.py downloads.

    ytct_view.py DIR

If DIR holds post .json files, writes DIR/index.html. Otherwise treats DIR as an
archive root: builds a page for every subdirectory with posts, plus DIR/index.html
listing the channels.
"""
import html
import json
import os
import re
import sys
from urllib.parse import quote

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ytct_view.html")
MEDIA_RE = re.compile(r"^(?P<id>.+?)(?:_(?P<n>\d+|thumb))?\.(?:jpe?g|png|webp|gif)$", re.I)


def load_posts(directory):
    names = os.listdir(directory)
    media = {}
    for name in names:
        m = MEDIA_RE.match(name)
        if m:
            entry = media.setdefault(m["id"], {"images": [], "thumb": None})
            if m["n"] == "thumb":
                entry["thumb"] = name
            else:
                entry["images"].append((int(m["n"] or -1), name))
    posts = []
    for name in names:
        if not name.endswith(".json"):
            continue
        path = os.path.join(directory, name)
        try:
            with open(path, encoding="utf8") as f:
                post = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(post, dict) or "post_id" not in post:
            continue
        m = media.get(post["post_id"], {"images": [], "thumb": None})
        post["_files"] = {"images": [n for _, n in sorted(m["images"])], "thumb": m["thumb"]}
        post["_mtime"] = int(os.path.getmtime(path))
        posts.append(post)
    return posts


def channel_name(posts):
    shared = {p["original_post"]["post_id"] for p in posts if p.get("original_post")}
    for p in posts:
        if p["post_id"] not in shared:
            return "".join(r.get("text", "") for r in (p.get("author") or {}).get("authorText", {}).get("runs", []))
    return ""


def write_channel(directory, posts=None):
    posts = posts if posts is not None else load_posts(directory)
    with open(TEMPLATE, encoding="utf8") as f:
        page = f.read()
    data = json.dumps(posts, ensure_ascii=False).replace("<", "\\u003c")
    with open(os.path.join(directory, "index.html"), "w", encoding="utf8") as f:
        f.write(page.replace("/*__POSTS__*/[]", data))
    return posts


def write_root(root):
    rows = []
    for name in sorted(os.listdir(root), key=str.lower):
        sub = os.path.join(root, name)
        if os.path.isdir(sub):
            posts = load_posts(sub)
            if posts:
                write_channel(sub, posts)
                rows.append((name, channel_name(posts) or name, len(posts)))
    items = "\n".join(
        f'<li><a href="{html.escape(quote(d))}/index.html">{html.escape(n)}</a> <span>{c} posts</span></li>'
        for d, n, c in rows
    )
    with open(os.path.join(root, "index.html"), "w", encoding="utf8") as f:
        f.write(
            '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            "<title>Community post archive</title><style>body{margin:0 auto;max-width:640px;padding:16px;background:#111;"
            "color:#e6e6e6;font:15px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;color-scheme:dark}a{color:#7ab7ff}"
            f"span{{color:#999;font-size:13px}}</style><h1>Channels</h1><ul>\n{items}\n</ul>\n"
        )
    return len(rows)


if __name__ == "__main__":
    if len(sys.argv) != 2 or not os.path.isdir(sys.argv[1]):
        sys.exit(__doc__)
    target = sys.argv[1]
    posts = load_posts(target)
    if posts:
        write_channel(target, posts)
        print(f"wrote {os.path.join(target, 'index.html')} ({len(posts)} posts)")
    else:
        print(f"wrote {os.path.join(target, 'index.html')} ({write_root(target)} channels)")
