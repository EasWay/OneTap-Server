"""Self-hosted media extraction with a stable OneTap response contract."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
import signal
import sys
import time
import uuid
from urllib.parse import urlparse

import httpx
from source_domains import SUPPORTED_DOMAINS

log = logging.getLogger(__name__)


def safe_diagnostic(value: str) -> str:
    """Keep failure reasons in server logs without copying URLs or credentials."""
    value = re.sub(r"https?://\S+", "[URL]", value)
    value = re.sub(r"(?i)(cookie|authorization|token|signature)\s*[:=]\s*\S+", r"\1=[REDACTED]", value)
    if len(value) <= 4000:
        return value
    return value[:2000] + " …[truncated]… " + value[-2000:]
_slots = asyncio.Semaphore(2)


class ExtractionUnavailable(Exception):
    pass


def media_type(ext: str) -> str:
    if ext.lower() in {"jpg", "jpeg", "png", "webp", "gif"}:
        return "image"
    if ext.lower() in {"mp3", "m4a", "opus", "ogg", "wav", "flac", "aac"}:
        return "audio"
    return "video"


def normalize_cobalt(data: dict) -> list[dict]:
    status = data.get("status")
    if status in {"tunnel", "redirect"}:
        name = Path(data.get("filename") or "media.mp4").name
        ext = Path(name).suffix.lstrip(".") or "mp4"
        items = [{"url": data.get("url"), "filename": name, "ext": ext,
                  "title": Path(name).stem, "type": media_type(ext)}]
    elif status == "picker":
        items = []
        for i, item in enumerate(data.get("picker", []), 1):
            kind = item.get("type")
            ext = {"photo": "jpg", "gif": "gif", "video": "mp4"}.get(kind)
            if not ext:
                raise ExtractionUnavailable("Unsupported Cobalt picker type")
            items.append({"url": item.get("url"), "filename": f"media_{i}.{ext}",
                          "ext": ext, "title": f"media_{i}", "type": media_type(ext)})
        if data.get("audio"):
            name = Path(data.get("audioFilename") or "slideshow_audio.mp3").name
            items.append({"url": data["audio"], "filename": name,
                          "ext": Path(name).suffix.lstrip(".") or "mp3",
                          "title": Path(name).stem, "type": "audio"})
    else:
        # Never treat local-processing components as an already merged video.
        code = data.get("error", {}).get("code", status or "invalid_response")
        raise ExtractionUnavailable(f"Cobalt: {str(code)[:120]}")
    if not items or len(items) > 30:
        raise ExtractionUnavailable("Invalid Cobalt collection size")
    for item in items:
        parsed = urlparse(item.get("url") or "")
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ExtractionUnavailable("Invalid Cobalt media URL")
    return items


async def verify_media(path: Path, expected: str) -> None:
    process = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name",
        "-of", "json", str(path), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=10)
        streams = json.loads(stdout).get("streams", [])
        wanted = "video" if expected == "image" else expected
        if process.returncode or not any(row.get("codec_type") == wanted and row.get("codec_name") for row in streams):
            raise ExtractionUnavailable("Downloaded file has no usable media stream")
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


async def cache_cobalt(items: list[dict], directory: Path) -> list[dict]:
    """Consume tunnels before reporting success, so transfer failures can fall back."""
    directory.mkdir(parents=True, exist_ok=True)
    job = uuid.uuid4().hex
    complete = False
    mime_ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp",
                "image/gif": "gif", "audio/mpeg": "mp3", "audio/mp4": "m4a",
                "audio/ogg": "ogg", "audio/wav": "wav", "audio/flac": "flac",
                "video/mp4": "mp4", "video/webm": "webm"}
    try:
        async with asyncio.timeout(65), httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            for index, item in enumerate(items, 1):
                async with client.stream("GET", item["url"]) as response:
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").split(";")[0]
                    if content_type.startswith("text/") or content_type == "application/json":
                        raise ExtractionUnavailable("Cobalt returned a non-media response")
                    ext = mime_ext.get(content_type, item["ext"])
                    # Some CDNs label MP3 soundtrack bytes as video/mp4. Preserve
                    # the extractor's media kind and let ffprobe validate it.
                    expected = item.get("type", media_type(item["ext"]))
                    if media_type(ext) != expected:
                        ext = item["ext"]
                    path = directory / f"{job}_{index:05d}.{ext}"
                    size = 0
                    with path.open("wb") as output:
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            if size > 250 * 1024 * 1024:
                                raise ExtractionUnavailable("Media exceeds download size limit")
                            output.write(chunk)
                    if not size:
                        raise ExtractionUnavailable("Cobalt returned empty media")
                    await verify_media(path, expected)
                    item.update(local=path.name, filename=path.name, ext=ext,
                                type=media_type(ext), size=size)
                    item.pop("url", None)
        complete = True
        return items
    finally:
        if not complete:
            for path in directory.glob(job + "_*"):
                path.unlink(missing_ok=True)


async def cobalt(url: str, directory: Path) -> list[dict]:
    base = os.environ.get("COBALT_API_URL", "http://127.0.0.1:9000/")
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if os.environ.get("COBALT_API_KEY"):
        headers["Authorization"] = "Api-Key " + os.environ["COBALT_API_KEY"]
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(base, headers=headers, json={
            "url": url, "videoQuality": "1080", "localProcessing": "disabled",
            "filenameStyle": "pretty", "alwaysProxy": True,
        })
        if response.status_code != 200:
            try:
                code = response.json().get("error", {}).get("code", "unknown")
            except (ValueError, AttributeError):
                code = "invalid_response"
            code = re.sub(r"[^a-zA-Z0-9_.-]", "", str(code))[:120]
            raise ExtractionUnavailable(f"Cobalt HTTP {response.status_code}: {code}")
        items = normalize_cobalt(response.json())
        source = urlparse(url)
        if ((source.hostname or "").endswith("instagram.com")
                and source.path.startswith(("/reel/", "/reels/", "/tv/"))
                and not any(item["type"] == "video" for item in items)):
            raise ExtractionUnavailable("Cobalt returned a thumbnail instead of the reel")
        return await cache_cobalt(items, directory)


async def ytdlp(url: str, directory: Path) -> list[dict]:
    directory.mkdir(parents=True, exist_ok=True)
    job = uuid.uuid4().hex
    youtube = is_youtube(url)
    height = os.environ.get("YOUTUBE_MAX_HEIGHT", "720")
    if youtube and height not in {"360", "480", "720", "1080"}:
        raise ExtractionUnavailable("Invalid YouTube maximum height")
    selection = f"bv*[height<={height}]+ba/b[height<={height}]" if youtube else "bv*+ba/b"
    # Separate processes keep the event loop responsive and allow actual cancellation.
    args = [sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-progress",
            "--no-playlist", "--playlist-end", "20", "--socket-timeout", "15",
            "--retries", "1", "--fragment-retries", "1", "--max-filesize", "250M",
            "--js-runtimes", "node", "-f", selection,
            "--merge-output-format", "mp4", "--no-simulate",
            "-o", str(directory / (job + "_%(autonumber)s.%(ext)s")),
            "--print", 'after_move:{"path":%(filepath)j,"title":%(title)j}', "--", url]
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    complete = False
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=90)
        if process.returncode:
            # Do not send extractor stderr (which can contain signed URLs) to clients.
            log.warning("yt-dlp failed with exit code %s: %s", process.returncode, safe_diagnostic(stderr.decode(errors="replace")))
            raise ExtractionUnavailable("yt-dlp could not retrieve this media")
        items = []
        for line in stdout.decode().splitlines():
            record = json.loads(line)
            path = Path(record["path"]).resolve()
            if path.parent != directory.resolve() or not path.name.startswith(job + "_") or not path.is_file():
                raise ExtractionUnavailable("Invalid yt-dlp output path")
            ext = path.suffix.lstrip(".")
            await verify_media(path, media_type(ext))
            items.append({"local": path.name, "filename": path.name, "ext": ext,
                          "title": record.get("title") or "media", "type": media_type(ext),
                          "size": path.stat().st_size})
        if not items or len(items) > 20:
            raise ExtractionUnavailable("No usable media returned by yt-dlp")
        complete = True
        return items
    finally:
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()
        if not complete:
            for path in directory.glob(job + "_*"):
                if path.is_file():
                    path.unlink(missing_ok=True)


async def public_photos(url: str, directory: Path) -> list[dict]:
    """Read public TikTok photo metadata when the two general providers fail."""
    source = urlparse(url)
    if source.hostname not in {"www.tiktok.com", "tiktok.com", "vt.tiktok.com", "vm.tiktok.com"}:
        raise ExtractionUnavailable("No public photo adapter for this source")
    async with httpx.AsyncClient(timeout=15) as client:
        # Resolve only redirects that stay on TikTok, with a finite hop count.
        for _ in range(5):
            response = await client.get(url)
            if not response.is_redirect:
                response.raise_for_status()
                break
            from urllib.parse import urljoin
            url = urljoin(url, response.headers.get("location", ""))
            target = urlparse(url)
            if target.scheme != "https" or target.hostname not in {"www.tiktok.com", "tiktok.com", "vt.tiktok.com", "vm.tiktok.com"} or target.port not in {None, 443}:
                raise ExtractionUnavailable("Unexpected photo redirect")
        source = urlparse(url)
        match = re.fullmatch(r"/@[^/]+/photo/(\d+)/?", source.path)
        if not match:
            raise ExtractionUnavailable("Not a public photo post")
        # TikTok exposes photo itemStruct data through its video-detail page.
        response = await client.get(f"https://www.tiktok.com/@i/video/{match[1]}")
        response.raise_for_status()
        metadata = re.search(r'<script\b[^>]*\bid="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', response.text, re.S)
        if not metadata:
            raise ExtractionUnavailable("Photo metadata unavailable")
        detail = json.loads(metadata[1]).get("__DEFAULT_SCOPE__", {}).get("webapp.video-detail", {})
        item = detail.get("itemInfo", {}).get("itemStruct", {})
        if detail.get("statusCode") != 0 or str(item.get("id")) != match[1] or item.get("privateItem"):
            raise ExtractionUnavailable("Photo metadata does not match a public post")
        rows = []
        for photo in item.get("imagePost", {}).get("images", []):
            urls = photo.get("imageURL", {}).get("urlList", [])
            if not urls:
                raise ExtractionUnavailable("Missing photo asset")
            rows.append({"url": urls[0], "ext": "jpg", "type": "image", "title": item.get("desc") or "Photo"})
        if not rows or len(rows) > 29:
            raise ExtractionUnavailable("Invalid photo collection")
        soundtrack = item.get("music", {}).get("playUrl")
        if soundtrack:
            rows.append({"url": soundtrack, "ext": "mp3", "type": "audio", "title": "Soundtrack"})
        for row in rows:
            asset = urlparse(row["url"])
            if asset.scheme != "https" or not (asset.hostname or "").endswith(".tiktokcdn.com"):
                raise ExtractionUnavailable("Unexpected photo asset host")
        return await cache_cobalt(rows, directory)


async def instagram(url: str, directory: Path) -> list[dict]:
    parsed = urlparse(url)
    match = re.fullmatch(r"/(?:p|reel|reels|tv)/([A-Za-z0-9_-]{5,30})/?", parsed.path)
    if parsed.hostname not in {"instagram.com", "www.instagram.com", "m.instagram.com"} or not match:
        raise ExtractionUnavailable("Not an Instagram post")
    process = await asyncio.create_subprocess_exec(
        sys.executable, str(Path(__file__).with_name("instagram_worker.py")), match[1],
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, start_new_session=True)
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30)
        if process.returncode:
            raise ExtractionUnavailable("Instaloader could not retrieve this public post")
        items = json.loads(stdout)
        if not isinstance(items, list) or not 1 <= len(items) <= 20:
            raise ExtractionUnavailable("Invalid Instagram collection")
        if len(items) == 1 and items[0].get("type") == "video":
            # Instaloader's post.video_url can resolve to a video-only rendition
            # (observed consistently from Render's network, unlike yt-dlp's DASH
            # video+audio selection). Let the provider chain fall through to
            # yt-dlp for single-video posts, which reliably preserves audio.
            raise ExtractionUnavailable("Preferring yt-dlp for single-video audio fidelity")
        for item in items:
            asset = urlparse(item.get("url") or "")
            host = asset.hostname or ""
            if (asset.scheme != "https" or asset.username or asset.password
                    or asset.port not in {None, 443}
                    or not any(host.endswith("." + domain) for domain in {"fbcdn.net", "cdninstagram.com"})
                    or item.get("type") not in {"image", "video"}):
                raise ExtractionUnavailable("Invalid Instagram media asset")
        return await cache_cobalt(items, directory)
    finally:
        if process.returncode is None:
            os.killpg(process.pid, signal.SIGKILL)
            await process.wait()


def is_youtube(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")


async def extract(url: str, directory: Path) -> tuple[str, list[dict]]:
    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError as error:
        raise ExtractionUnavailable("Invalid media URL") from error
    host = (parsed.hostname or "").lower()
    if (parsed.scheme not in {"http", "https"} or parsed.username or parsed.password
            or port not in {None, 80, 443}
            or not any(host == domain or host.endswith("." + domain) for domain in SUPPORTED_DOMAINS)):
        raise ExtractionUnavailable("Unsupported media URL")
    order = os.environ.get("EXTRACTION_PROVIDERS", "cobalt,ytdlp,public_photos").split(",")
    if is_youtube(url):
        order = os.environ.get("YOUTUBE_PROVIDERS", "ytdlp,cobalt").split(",")
    elif host in {"instagram.com", "www.instagram.com", "m.instagram.com"}:
        order = os.environ.get("INSTAGRAM_PROVIDERS", "instagram,ytdlp,cobalt").split(",")
    providers = {"cobalt": cobalt, "ytdlp": ytdlp, "public_photos": public_photos, "instagram": instagram}
    if any(name.strip() not in providers for name in order):
        raise ExtractionUnavailable("Invalid extraction provider configuration")
    async with _slots:
        # Only files from our generated jobs are eligible for cleanup. Retain for one hour.
        directory.mkdir(parents=True, exist_ok=True)
        import re
        for path in directory.iterdir():
            if (re.fullmatch(r"[0-9a-f]{32}_\d+\.[\w.]+", path.name)
                    and path.is_file() and time.time() - path.stat().st_mtime > 3600):
                path.unlink(missing_ok=True)
        for name in map(str.strip, order):
            try:
                items = await providers[name](url, directory)
                return name, items
            except (ExtractionUnavailable, httpx.HTTPError, ValueError, asyncio.TimeoutError) as error:
                log.warning("Extraction provider %s failed (%s): %s", name, type(error).__name__, safe_diagnostic(str(error)))
    raise ExtractionUnavailable("The configured extractors could not retrieve this media. Try again later or use another supported public link.")
