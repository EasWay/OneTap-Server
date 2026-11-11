"""Isolated public-post metadata extraction; never reads browser/account sessions."""
import json
import os
import re
import sys
import urllib.request

import instaloader

# Instagram serves the full media payload (all image sizes, carousel items,
# video URLs, caption) inside the post page to search-engine crawlers, using a
# plain page request instead of the throttled GraphQL API. Disable with
# INSTAGRAM_PAGE_FETCH=0.
PAGE_USER_AGENT = "Googlebot/2.1 (+http://www.google.com/bot.html)"
_SIZE_CAPPED = re.compile(r"[?&]stp=[^&]*_[sp]\d+x\d+")


def post_items(post):
    title = (post.caption or "Instagram post")[:500]
    if post.typename == "GraphSidecar":
        nodes = list(post.get_sidecar_nodes())
        if not 1 <= len(nodes) <= 20:
            raise ValueError("Unsupported collection size")
        return [{"url": node.video_url if node.is_video else node.display_url,
                 "type": "video" if node.is_video else "image",
                 "ext": "mp4" if node.is_video else "jpg", "title": title}
                for node in nodes]
    if post.typename not in {"GraphImage", "GraphVideo"}:
        raise ValueError("Unsupported Instagram post type")
    return [{"url": post.video_url if post.is_video else post.url,
             "type": "video" if post.is_video else "image",
             "ext": "mp4" if post.is_video else "jpg", "title": title}]


def _best_image(media):
    candidates = [c.get("url") for c in (media.get("image_versions2") or {}).get("candidates", []) if c.get("url")]
    if not candidates:
        return None
    # Candidates are ordered original-first; avoid cropped/resized renditions.
    return next((u for u in candidates if not _SIZE_CAPPED.search(u)), candidates[0])


def _find_media(node, shortcode):
    if isinstance(node, dict):
        if node.get("code") == shortcode and any(
                key in node for key in ("image_versions2", "video_versions", "carousel_media")):
            return node
        node = list(node.values())
    if isinstance(node, list):
        for child in node:
            found = _find_media(child, shortcode)
            if found:
                return found
    return None


def items_from_page(html, shortcode):
    """Extract media items from the crawler-visible post page; None if absent."""
    for match in re.finditer(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.S):
        if not any(key in match[1] for key in ("image_versions2", "video_versions", "carousel_media")):
            continue
        try:
            media = _find_media(json.loads(match[1]), shortcode)
        except ValueError:
            continue
        if not media:
            continue
        caption = media.get("caption")
        title = ((caption.get("text") if isinstance(caption, dict) else caption) or "Instagram post")[:500]
        parts = media.get("carousel_media") or [media]
        if not 1 <= len(parts) <= 20:
            raise ValueError("Unsupported collection size")
        items = []
        for part in parts:
            videos = part.get("video_versions") or []
            url = videos[0].get("url") if videos else _best_image(part)
            if not url:
                return None
            items.append({"url": url, "type": "video" if videos else "image",
                          "ext": "mp4" if videos else "jpg", "title": title})
        return items
    return None


def fetch_page_items(shortcode):
    request = urllib.request.Request(f"https://www.instagram.com/p/{shortcode}/",
                                     headers={"User-Agent": PAGE_USER_AGENT})
    with urllib.request.urlopen(request, timeout=15) as response:
        html = response.read(8_000_000).decode("utf-8", errors="replace")
    return items_from_page(html, shortcode)


def main():
    shortcode = sys.argv[1]
    if not re.fullmatch(r"[A-Za-z0-9_-]{5,30}", shortcode):
        raise ValueError("Invalid post shortcode")
    if os.environ.get("INSTAGRAM_PAGE_FETCH", "1") != "0":
        try:
            items = fetch_page_items(shortcode)
            if items:
                print(json.dumps(items))
                return
        except Exception as error:  # fall back to Instaloader's GraphQL path
            print(f"page fetch failed: {type(error).__name__}", file=sys.stderr)
    with instaloader.Instaloader(quiet=True, max_connection_attempts=1, request_timeout=15) as loader:
        post = instaloader.Post.from_shortcode(loader.context, shortcode)
        if post.shortcode != shortcode:
            raise ValueError("Instagram returned a different post")
        print(json.dumps(post_items(post)))


if __name__ == "__main__":
    main()
