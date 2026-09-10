"""Isolated public-post metadata extraction; never reads browser/account sessions."""
import json
import re
import sys

import instaloader


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


def main():
    shortcode = sys.argv[1]
    if not re.fullmatch(r"[A-Za-z0-9_-]{5,30}", shortcode):
        raise ValueError("Invalid post shortcode")
    with instaloader.Instaloader(quiet=True, max_connection_attempts=1, request_timeout=15) as loader:
        post = instaloader.Post.from_shortcode(loader.context, shortcode)
        if post.shortcode != shortcode:
            raise ValueError("Instagram returned a different post")
        print(json.dumps(post_items(post)))


if __name__ == "__main__":
    main()
