import os
import uuid
import logging
import re
import asyncio
import uvloop
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

# Modern Async Stack
from litestar import Litestar, get, post
from litestar.response import File, Stream
from litestar.exceptions import HTTPException
from pydantic import BaseModel, field_validator
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set uvloop as the event loop policy for maximum performance
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# --- CONFIGURATION ---
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Exact UA for consistency
EXACT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"

# --- J2 WRAPPER CONFIG ---
J2_BASE_URL = "https://j2download.com"
J2_API_URL = f"{J2_BASE_URL}/api/autolink"
J2_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"

# --- PYDANTIC MODELS ---
class DownloadRequest(BaseModel):
    url: str
    csrf_token: Optional[str] = None
    cookie_string: Optional[str] = None
    user_agent: Optional[str] = None
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        if not v or not v.strip():
            raise ValueError('URL cannot be empty')
        
        # Clean URL text if needed (extract URL from text)
        url_match = re.search(r'(https?://[^\s]+)', v)
        if url_match:
            extracted_url = url_match.group(1)
            # Don't be too aggressive with cleaning - preserve the full URL
            return extracted_url
        
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        
        return v.strip()

class DownloadResponse(BaseModel):
    status: str
    download_url: Optional[str] = None
    filename: Optional[str] = None
    message: Optional[str] = None
    type: Optional[str] = None
    total_images: Optional[int] = None
    files: Optional[List[Dict[str, Any]]] = None
    title: Optional[str] = None
    platform: Optional[str] = None
    size: Optional[int] = None

def remove_query_params(url: str) -> str:
    """Removes tracking parameters but preserves essential YouTube parameters"""
    try:
        if "youtube.com" in url or "youtu.be" in url:
            # For YouTube, preserve essential parameters like 'v', 'list', 't'
            from urllib.parse import urlparse, parse_qs, urlencode
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            
            # Keep essential YouTube parameters
            essential_params = {}
            for key in ['v', 'list', 't', 'feature']:
                if key in query_params:
                    essential_params[key] = query_params[key]
            
            if essential_params:
                new_query = urlencode(essential_params, doseq=True)
                return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"
            else:
                return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        else:
            # For other platforms, remove query params as before
            if "?" in url: 
                return url.split("?")[0]
            return url
    except: 
        return url

async def expand_short_url(url: str) -> str:
    """Resolves short URLs for all supported platforms - ASYNC VERSION"""
    try:
        short_domains = [
            # TikTok & Related
            'vt.tiktok.com', 'vm.tiktok.com', 'tiktok.com/t/',
            # General Short URLs
            'bit.ly', 't.co', 'tinyurl.com', 'short.link', 'ow.ly',
            # Platform Specific
            'fb.me', 'fb.watch', 'ig.me', 'pin.it', 'lnkd.in', 'youtu.be',
            't.snapchat.com', 'snd.sc', 'spoti.fi', 'redd.it', 'b23.tv',
            # Chinese Platforms
            'xhslink.com', 'douyin.com/share', 'kuaishou.com/s',
            # Other
            'r.mtdv.me', 'x.com', 'bsky.app', 't.me'
        ]
        
        if any(x in url for x in short_domains):
            logger.info(f"🔗 Expanding short URL: {url}")
            headers = {"User-Agent": J2_UA}
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                try:
                    resp = await client.head(url, headers=headers, follow_redirects=True)
                    if resp.status_code >= 400:
                        raise Exception("Head failed")
                except:
                    resp = await client.get(url, headers=headers, follow_redirects=True)
                
                resolved = str(resp.url)
                if "login" not in resolved and "error" not in resolved:
                    clean = remove_query_params(resolved)
                    logger.info(f"✅ Resolved to: {clean}")
                    return clean
        else:
            # For non-short URLs, still apply smart query param removal
            clean = remove_query_params(url)
            if clean != url:
                logger.info(f"🧹 Cleaned URL: {url} -> {clean}")
            return clean
    except Exception as e:
        logger.warning(f"⚠️ URL processing failed: {e}")
    
    # Return original URL if processing fails
    return url

def clean_url_text(text: str) -> str:
    match = re.search(r'(https?://[^\s]+)', text)
    if match: 
        return match.group(1)
    return text

def detect_platform(url: str) -> str:
    """Enhanced platform detection for 50+ supported platforms"""
    domain = urlparse(url).netloc.lower()
    
    # TikTok & Related
    if any(x in domain for x in ["tiktok.com", "vm.tiktok.com", "vt.tiktok.com"]): return "tiktok"
    if "douyin.com" in domain: return "douyin"
    if "capcut.com" in domain: return "capcut"
    
    # Meta Platforms
    if any(x in domain for x in ["facebook.com", "fb.watch", "fb.com", "m.facebook.com"]): return "facebook"
    if any(x in domain for x in ["instagram.com", "instagr.am", "ig.me"]): return "instagram"
    if "threads.net" in domain: return "threads"
    
    # Twitter/X
    if any(x in domain for x in ["twitter.com", "x.com", "t.co", "mobile.twitter.com"]): return "twitter"
    
    # Video Platforms
    if any(x in domain for x in ["youtube.com", "youtu.be", "m.youtube.com", "youtube-nocookie.com"]): return "youtube"
    if "vimeo.com" in domain: return "vimeo"
    if "dailymotion.com" in domain: return "dailymotion"
    if "bilibili.com" in domain or "b23.tv" in domain: return "bilibili"
    if "rumble.com" in domain: return "rumble"
    if "streamable.com" in domain: return "streamable"
    if "ted.com" in domain: return "ted"
    if "sohu.com" in domain or "tv.sohu.com" in domain: return "sohutv"
    if "bitchute.com" in domain: return "bitchute"
    
    # Chinese Platforms
    if "kuaishou.com" in domain or "kwai.com" in domain: return "kuaishou"
    if "xiaohongshu.com" in domain or "xhslink.com" in domain: return "xiaohongshu"
    if "ixigua.com" in domain: return "ixigua"
    if "weibo.com" in domain or "weibo.cn" in domain: return "weibo"
    if "miaopai.com" in domain: return "miaopai"
    if "meipai.com" in domain: return "meipai"
    if "xiaoying.tv" in domain: return "xiaoying"
    if "yingke.com" in domain: return "yingke"
    if "sina.com" in domain: return "sina"
    
    # Social & Communication
    if "reddit.com" in domain or "redd.it" in domain: return "reddit"
    if "snapchat.com" in domain: return "snapchat"
    if "pinterest.com" in domain or "pin.it" in domain: return "pinterest"
    if "tumblr.com" in domain: return "tumblr"
    if "linkedin.com" in domain or "lnkd.in" in domain: return "linkedin"
    if "telegram.org" in domain or "t.me" in domain: return "telegram"
    if "bsky.app" in domain or "bluesky.social" in domain: return "bluesky"
    
    # Indian Platforms
    if "sharechat.com" in domain: return "sharechat"
    if "likee.video" in domain or "like.video" in domain: return "likee"
    if "hipi.co.in" in domain: return "hipi"
    
    # Entertainment & Media
    if "imdb.com" in domain: return "imdb"
    if "imgur.com" in domain: return "imgur"
    if "ifunny.co" in domain: return "ifunny"
    if "izlesene.com" in domain: return "izlesene"
    if "espn.com" in domain: return "espn"
    if "9gag.com" in domain: return "9gag"
    if "ok.ru" in domain or "oke.ru" in domain: return "oke"
    if "febspot.com" in domain: return "febspot"
    if "getstickerpack.com" in domain: return "getstickerpack"
    
    # Audio Platforms
    if "soundcloud.com" in domain or "snd.sc" in domain: return "soundcloud"
    if "mixcloud.com" in domain: return "mixcloud"
    if "spotify.com" in domain or "spoti.fi" in domain: return "spotify"
    if "deezer.com" in domain: return "deezer"
    if "zingmp3.vn" in domain: return "zingmp3"
    if "bandcamp.com" in domain: return "bandcamp"
    if "castbox.fm" in domain: return "castbox"
    
    # File Sharing
    if "mediafire.com" in domain: return "mediafire"
    
    # Adult Content
    if "pornbox.com" in domain: return "pornbox"
    if "xvideos.com" in domain: return "xvideos"
    if "xnxx.com" in domain: return "xnxx"
    
    # QQ Platform
    if "qq.com" in domain: return "qq"
    
    return "generic"

# --- SMART PARSER ---
class J2ResponseParser:
    @staticmethod
    def parse(data, platform):
        """Enhanced parser for 50+ platforms with smart format selection"""
        medias = data.get("medias", [])
        if not medias: return None
        
        logger.info(f"🧠 Parsing {len(medias)} formats for {platform}")
        
        # Platform-specific parsing
        if platform in ["tiktok", "douyin", "capcut"]:
            return J2ResponseParser._parse_tiktok(medias)
        elif platform in ["facebook", "instagram", "threads"]:
            return J2ResponseParser._parse_meta(medias)
        elif platform in ["twitter", "bluesky"]:
            return J2ResponseParser._parse_twitter(medias)
        elif platform in ["youtube", "vimeo", "dailymotion", "bilibili"]:
            return J2ResponseParser._parse_video_platform(medias)
        elif platform in ["soundcloud", "mixcloud", "spotify", "deezer", "zingmp3", "bandcamp", "castbox"]:
            return J2ResponseParser._parse_audio(medias)
        elif platform in ["pinterest", "imgur", "9gag"]:
            return J2ResponseParser._parse_image_platform(medias)
        elif platform in ["kuaishou", "xiaohongshu", "ixigua", "weibo", "miaopai", "meipai", "xiaoying", "yingke", "sina"]:
            return J2ResponseParser._parse_chinese_platform(medias)
        elif platform in ["sharechat", "likee", "hipi"]:
            return J2ResponseParser._parse_indian_platform(medias)
        elif platform in ["reddit", "tumblr", "linkedin"]:
            return J2ResponseParser._parse_social_platform(medias)
        elif platform in ["snapchat", "telegram"]:
            return J2ResponseParser._parse_messaging_platform(medias)
        elif platform in ["pornbox", "xvideos", "xnxx"]:
            return J2ResponseParser._parse_adult_platform(medias)
        
        # Generic fallback - prioritize video with audio
        return J2ResponseParser._parse_generic(medias)
    
    @staticmethod
    def _parse_tiktok(medias):
        """TikTok/Douyin/Capcut - prioritize no watermark HD; prefer tiktokcdn.com over api.tiktokv.com.

        api.tiktokv.com URLs require a session-bound tt_chain_token cookie which is unavailable
        on the proxy server. tiktokcdn.com URLs work without that cookie."""
        video_medias = [m for m in medias if m.get("type") == "video"]
        if not video_medias:
            return medias[0]

        quality_rank = {"hd_no_watermark": 0, "no_watermark": 1}

        def sort_key(m):
            url = m.get("url", "")
            # Prefer CDN URLs that don't require the tt_chain_token cookie
            is_api = 1 if "api.tiktokv.com" in url else 0
            quality = quality_rank.get(m.get("quality", ""), 2)
            return (is_api, quality)

        video_medias.sort(key=sort_key)
        return video_medias[0]

    @staticmethod
    def _parse_meta(medias):
        """Facebook/Instagram/Threads - prioritize HD video"""
        videos = [m for m in medias if m.get("type") == "video"]
        for v in videos:
            q = str(v.get("quality", "")).lower()
            if "hd" in q or "1080" in q or "720" in q:
                return v
        return videos[0] if videos else medias[0]
    
    @staticmethod
    def _parse_twitter(medias):
        """Twitter/X/Bluesky - prefer highest bitrate MP4"""
        videos = [m for m in medias if m.get("type") == "video" and m.get("extension") == "mp4"]
        if not videos: 
            videos = [m for m in medias if m.get("type") == "video"]
        
        if "formats" in medias[0]:
            sub_formats = medias[0].get("formats", [])
            mp4s = [f for f in sub_formats if f.get("container") == "mp4"]
            if mp4s:
                try:
                    mp4s.sort(key=lambda x: int(x.get("bitrate", 0)), reverse=True)
                    return {"url": mp4s[0]["url"], "extension": "mp4"}
                except: pass
        
        try:
            videos.sort(key=lambda x: int(x.get("bitrate", 0)), reverse=True)
        except: pass
        return videos[0] if videos else medias[0]
    
    @staticmethod
    def _parse_video_platform(medias):
        """YouTube/Vimeo/Dailymotion/Bilibili - video with audio"""
        valid_videos = []
        for m in medias:
            if m.get("type") == "video":
                if m.get("is_audio") is True or m.get("audioQuality") or m.get("has_audio"):
                    valid_videos.append(m)
        
        if not valid_videos:
            valid_videos = [m for m in medias if m.get("type") == "video"]
        
        return valid_videos[0] if valid_videos else medias[0]
    
    @staticmethod
    def _parse_audio(medias):
        """Audio platforms - highest quality audio"""
        audio_files = [m for m in medias if m.get("type") == "audio"]
        if audio_files:
            # Sort by bitrate or quality
            try:
                audio_files.sort(key=lambda x: int(x.get("bitrate", 0)), reverse=True)
            except: pass
            return audio_files[0]
        
        # Fallback to any media
        return medias[0]
    
    @staticmethod
    def _parse_image_platform(medias):
        """Pinterest/Imgur/9GAG - prefer images, fallback to video"""
        images = [m for m in medias if m.get("type") == "image"]
        if images: return images[0]
        
        videos = [m for m in medias if m.get("type") == "video"]
        return videos[0] if videos else medias[0]
    
    @staticmethod
    def _parse_chinese_platform(medias):
        """Chinese platforms - similar to TikTok logic"""
        for m in medias:
            if "no_watermark" in str(m.get("quality", "")).lower(): return m
        for m in medias:
            if m.get("type") == "video": return m
        return medias[0]
    
    @staticmethod
    def _parse_indian_platform(medias):
        """Indian platforms - prefer video content"""
        videos = [m for m in medias if m.get("type") == "video"]
        return videos[0] if videos else medias[0]
    
    @staticmethod
    def _parse_social_platform(medias):
        """Reddit/Tumblr/LinkedIn - flexible content"""
        # Prefer video, then image, then any
        videos = [m for m in medias if m.get("type") == "video"]
        if videos: return videos[0]
        
        images = [m for m in medias if m.get("type") == "image"]
        if images: return images[0]
        
        return medias[0]
    
    @staticmethod
    def _parse_messaging_platform(medias):
        """Snapchat/Telegram - any media type"""
        return medias[0]
    
    @staticmethod
    def _parse_adult_platform(medias):
        """Adult platforms - video priority"""
        videos = [m for m in medias if m.get("type") == "video"]
        return videos[0] if videos else medias[0]
    
    @staticmethod
    def _parse_generic(medias):
        """Generic fallback - smart selection"""
        # Priority: video with audio > video > image > audio > any
        videos_with_audio = [m for m in medias if m.get("type") == "video" and (m.get("is_audio") or m.get("has_audio"))]
        if videos_with_audio: return videos_with_audio[0]
        
        videos = [m for m in medias if m.get("type") == "video"]
        if videos: return videos[0]
        
        images = [m for m in medias if m.get("type") == "image"]
        if images: return images[0]
        
        audio = [m for m in medias if m.get("type") == "audio"]
        if audio: return audio[0]
        
        return medias[0]


class AsyncJ2Extractor:
    async def extract_download_url(
        self, 
        video_url: str, 
        provided_token: Optional[str] = None,
        provided_cookies: Optional[str] = None,
        provided_ua: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        try:
            platform = detect_platform(video_url)
            logger.info(f"🎯 J2 Extraction for {platform}: {video_url}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Step 1: Navigation headers (simulate typing URL in browser)
                nav_headers = {
                    "User-Agent": J2_UA,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Sec-Ch-Ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1"
                }
                
                # Handshake logic (only if token not provided)
                csrf_token = provided_token
                cookies_to_use = {}
                
                if provided_cookies:
                    # Parse simplified cookie string: "name1=value1; name2=value2"
                    for cookie in provided_cookies.split(';'):
                        if '=' in cookie:
                            name, value = cookie.strip().split('=', 1)
                            cookies_to_use[name] = value
                    logger.info("✅ Using client-provided session cookies")

                if not csrf_token:
                    logger.info("🤝 Performing J2Download handshake...")
                    home_resp = await client.get(J2_BASE_URL, headers=nav_headers)
                    
                    if home_resp.status_code != 200:
                        logger.warning(f"⚠️ Handshake returned status {home_resp.status_code}")
                        return None
                    
                    cookies_to_use = home_resp.cookies
                    
                    # Deep Token Extraction - Priority 1: Cookies
                    csrf_token = home_resp.cookies.get("csrf_token")
                    if csrf_token:
                        logger.info("✅ Found CSRF token in Cookies")
                else:
                    logger.info("✅ Using client-provided CSRF token")
                
                # Priority 2: HTML Meta Tags (only if handshake was performed)
                if not csrf_token and 'home_resp' in locals():
                    logger.info("🔍 Searching HTML for CSRF token...")
                    meta_match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', home_resp.text)
                    if meta_match:
                        csrf_token = meta_match.group(1)
                        logger.info("✅ Found CSRF token in Meta Tag")
                
                # Priority 3: JavaScript Variables (multiple patterns)
                if not csrf_token:
                    patterns = [
                        r'csrf_token\s*=\s*["\']([^"\']+)["\']',
                        r'csrfToken\s*=\s*["\']([^"\']+)["\']',
                        r'CSRF_TOKEN\s*=\s*["\']([^"\']+)["\']',
                        r'window\.csrf\s*=\s*["\']([^"\']+)["\']',
                        r'window\.csrfToken\s*=\s*["\']([^"\']+)["\']',
                    ]
                    for pattern in patterns:
                        js_match = re.search(pattern, home_resp.text)
                        if js_match:
                            csrf_token = js_match.group(1)
                            logger.info(f"✅ Found CSRF token in JS with pattern: {pattern}")
                            break
                
                # Priority 4: Laravel Token Pattern
                if not csrf_token:
                    laravel_match = re.search(r'_token["\']?\s*:\s*["\']([^"\']+)["\']', home_resp.text)
                    if laravel_match:
                        csrf_token = laravel_match.group(1)
                        logger.info("✅ Found Laravel token")
                
                # Priority 5: XSRF Token (alternative name)
                if not csrf_token:
                    xsrf_match = re.search(r'xsrf[_-]?token["\']?\s*[:=]\s*["\']([^"\']+)["\']', home_resp.text, re.IGNORECASE)
                    if xsrf_match:
                        csrf_token = xsrf_match.group(1)
                        logger.info("✅ Found XSRF token")
                
                # Priority 6: Hidden input fields
                if not csrf_token:
                    input_match = re.search(r'<input[^>]*name=["\'](?:csrf_token|_token|csrfToken)["\'][^>]*value=["\']([^"\']+)["\']', home_resp.text, re.IGNORECASE)
                    if input_match:
                        csrf_token = input_match.group(1)
                        logger.info("✅ Found CSRF token in hidden input")
                
                # Priority 7: Try without CSRF token (some APIs don't require it)
                if not csrf_token:
                    logger.warning("⚠️ No CSRF token found after deep search - attempting without token")
                    csrf_token = ""  # Empty string instead of None to continue
                
                if (csrf_token):
                    logger.info(f"✅ CSRF token acquired: {csrf_token[:10]}...")
                else:
                    logger.info("ℹ️ No CSRF token provided (using session cookies only)")
                
                # Step 2: Switch to XHR headers for API call
                ua_to_use = provided_ua if provided_ua else J2_UA
                xhr_headers = {
                    "User-Agent": ua_to_use,
                    "Referer": f"{J2_BASE_URL}/",
                    "Origin": J2_BASE_URL,
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/plain, */*",
                    "Sec-Fetch-Dest": "empty",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Site": "same-origin",
                    "X-Requested-With": "XMLHttpRequest"
                }
                
                # Handle JWT vs standard CSRF token
                if csrf_token:
                    if csrf_token.startswith("eyJ"):
                        xhr_headers["authorization"] = f"Bearer {csrf_token}"
                        logger.info("🎟️ Using JWT-based Authorization header")
                    else:
                        xhr_headers["x-csrf-token"] = csrf_token
                        logger.info("🎟️ Using standard x-csrf-token header")
                
                payload = {
                    "data": {
                        "url": video_url,
                        "unlock": True
                    }
                }
                
                logger.info(f"🚀 Sending J2Download API request with UA: {ua_to_use[:50]}...")
                logger.info(f"📤 Payload: {payload}")
                
                response = await client.post(J2_API_URL, json=payload, headers=xhr_headers, cookies=cookies_to_use)
                
                logger.info(f"📥 Response status: {response.status_code}")
                
                if response.status_code in [401, 403]:
                    logger.error(f"❌ J2Download API Auth error (Turnstile block?): {response.status_code}")
                    if provided_token:
                        return {"error": "SESSION_EXPIRED", "message": "The captured session is invalid or expired."}
                    return None

                if response.status_code != 200:
                    logger.error(f"❌ J2Download API HTTP error: {response.status_code}")
                    try:
                        error_data = response.json()
                        logger.error(f"❌ Error response: {error_data}")
                    except:
                        logger.error(f"❌ Raw error response: {response.text[:500]}")
                    return None
                
                try:
                    data = response.json()
                    logger.info(f"📥 J2Download response: {data}")
                except Exception as e:
                    logger.error(f"❌ Failed to parse JSON: {e}")
                    logger.error(f"❌ Raw response: {response.text[:1000]}")
                    return None
                
                if "error" in data and data["error"]:
                    j2_status = data.get("status")
                    j2_message = data.get("message", "Unknown error")
                    logger.warning(f"⚠️ J2Download API error: {j2_message}")
                    # J2 status 404 means content genuinely not found (private/deleted/region-locked)
                    if j2_status == 404:
                        return {"error": "CONTENT_NOT_FOUND", "message": j2_message}
                    return None
                
                # Use Smart Parser
                best_media = J2ResponseParser.parse(data, platform)
                if best_media:
                    logger.info(f"✅ J2Download extraction successful!")
                    
                    # Check if it's a multi-media response (like TikTok photo slideshow)
                    medias = data.get("medias", [])
                    images = [m for m in medias if m.get("type") == "image"]
                    
                    if len(images) > 1:
                        # Return full data for multi-image posts
                        return {
                            "url": best_media.get("url"),
                            "ext": best_media.get("extension", "jpg"),
                            "title": data.get("title", "video"),
                            "medias": medias,  # Include all media items
                            "type": "multi_image"
                        }
                    else:
                        # Single media item
                        # Smart extension fallback based on type
                        media_type = best_media.get("type", "video")
                        default_ext = "jpg" if media_type == "image" else "mp4"

                        result = {
                            "url": best_media.get("url"),
                            "ext": best_media.get("extension", best_media.get("ext", default_ext)),
                            "title": data.get("title", "video"),
                            "size": best_media.get("size") or best_media.get("filesize")
                        }

                        # For TikTok, store the next-best video URL as a fallback in case the
                        # primary URL (api.tiktokv.com) is unreachable from the proxy server
                        if platform in ["tiktok", "douyin", "capcut"]:
                            other_videos = [
                                m for m in medias
                                if m.get("type") == "video" and m.get("url") != best_media.get("url")
                            ]
                            if other_videos:
                                result["fallback_url"] = other_videos[0].get("url")

                        return result
                else:
                    logger.warning("⚠️ J2Download: No suitable media found in response")
                    return None
                
        except Exception as e:
            logger.error(f"❌ J2 Failed: {e}")
            return None

@get("/version")
async def get_version() -> Dict[str, Any]:
    """Version endpoint for system updates"""
    return {
        "version": "2.0",
        "latest_version": 10,
        "apk_url": "https://play.google.com/store/apps/details?id=com.tapstream.downloader",
        "play_store_url": "https://play.google.com/store/apps/details?id=com.tapstream.downloader",
        "release_notes": "🚀 OneTap v2.0 - Major Update!\n\n✨ New Features:\n• Enhanced stability and performance\n• Improved download reliability across all platforms\n• Better stream proxy support for social media\n• Enhanced progress tracking\n• General performance optimizations and bug fixes",
        "status": "online",
        "service": "Universal Media Downloader - ASYNC EDITION",
        "framework": "Litestar (ASGI)",
        "performance": "High-Concurrency Async",
        "total_platforms": 50,
        "features": [
            "Lightning-fast async processing with uvloop",
            "Unified J2Download extraction for all platforms",
            "Smart URL processing that preserves essential parameters",
            "Stream proxy for reliable downloads",
            "Handle thousands of concurrent downloads",
            "Download videos without watermarks (TikTok, etc.)",
            "Support for images, videos, and audio",
            "Multiple format support (.mp4, .mp3, .jpg, .png)",
            "Works on all devices (PC, Mac, Android, iOS)",
            "Photo slideshow downloads via stream proxy",
            "Free service with no registration required"
        ],
        "supported_platforms": {
            "video_platforms": [
                "TikTok", "Douyin", "Capcut", "YouTube", "Vimeo", "Dailymotion", 
                "Bilibili", "Rumble", "Streamable", "Ted", "SohuTv", "Bitchute"
            ],
            "social_media": [
                "Instagram", "Facebook", "Threads", "Twitter/X", "Snapchat", 
                "Pinterest", "Reddit", "Tumblr", "LinkedIn", "Bluesky", "Telegram"
            ],
            "chinese_platforms": [
                "Kuaishou", "Xiaohongshu", "Ixigua", "Weibo", "Miaopai", 
                "Meipai", "Xiaoying", "Yingke", "Sina", "QQ"
            ],
            "indian_platforms": [
                "Sharechat", "Likee", "Hipi"
            ],
            "audio_platforms": [
                "Soundcloud", "Mixcloud", "Spotify", "Deezer", "Zingmp3", 
                "Bandcamp", "Castbox"
            ],
            "entertainment": [
                "ESPN", "IMDB", "Imgur", "iFunny", "Izlesene", "9GAG", 
                "oke.ru", "Febspot", "Getstickerpack"
            ],
            "file_sharing": [
                "Mediafire"
            ],
            "adult_content": [
                "Pornbox", "Xvideos", "Xnxx"
            ]
        }
    }

@get("/")
async def index() -> Dict[str, Any]:
    """API information and supported platforms"""
    supported_platforms = {
        "video_platforms": [
            "TikTok", "Douyin", "Capcut", "YouTube", "Vimeo", "Dailymotion", 
            "Bilibili", "Rumble", "Streamable", "Ted", "SohuTv", "Bitchute"
        ],
        "social_media": [
            "Instagram", "Facebook", "Threads", "Twitter/X", "Snapchat", 
            "Pinterest", "Reddit", "Tumblr", "LinkedIn", "Bluesky", "Telegram"
        ],
        "chinese_platforms": [
            "Kuaishou", "Xiaohongshu", "Ixigua", "Weibo", "Miaopai", 
            "Meipai", "Xiaoying", "Yingke", "Sina", "QQ"
        ],
        "indian_platforms": [
            "Sharechat", "Likee", "Hipi"
        ],
        "audio_platforms": [
            "Soundcloud", "Mixcloud", "Spotify", "Deezer", "Zingmp3", 
            "Bandcamp", "Castbox"
        ],
        "entertainment": [
            "ESPN", "IMDB", "Imgur", "iFunny", "Izlesene", "9GAG", 
            "oke.ru", "Febspot", "Getstickerpack"
        ],
        "file_sharing": [
            "Mediafire"
        ],
        "adult_content": [
            "Pornbox", "Xvideos", "Xnxx"
        ]
    }
    
    return {
        "status": "online",
        "service": "Universal Media Downloader - ASYNC EDITION",
        "version": "2.0",
        "latest_version": 10,
        "apk_url": "https://play.google.com/store/apps/details?id=com.tapstream.downloader",
        "release_notes": "🚀 OneTap v2.0 - Major Update!\n\n✨ New Features:\n• Enhanced stability and performance\n• Improved download reliability across all platforms",
        "framework": "Litestar (ASGI)",
        "performance": "High-Concurrency Async",
        "supported_platforms": supported_platforms,
        "total_platforms": sum(len(platforms) for platforms in supported_platforms.values()),
        "features": [
            "Lightning-fast async processing",
            "Handle thousands of concurrent downloads",
            "Download videos without watermarks (TikTok, etc.)",
            "Support for images, videos, and audio",
            "Multiple format support (.mp4, .mp3, .jpg, .png)",
            "Works on all devices (PC, Mac, Android, iOS)",
            "Photo slideshow downloads in MP4 format",
            "Free service with no registration required"
        ],
        "extraction_methods": {
            "youtube": "RapidAPI Direct (Ultra-Fast)",
            "social_media": "J2Download API (50+ sites)",
            "fallback": "Cross-platform compatibility",
            "architecture": "Optimized async stack with uvloop"
        },
        "endpoints": {
            "download": "/download (POST)",
            "files": "/files/<filename> (GET)",
            "version": "/version (GET)"
        }
    }

@post("/download")
async def download_video(data: DownloadRequest) -> DownloadResponse:
    """
    ASYNC High-Performance Download Endpoint with Stream Proxy
    - Uses Pydantic for automatic validation
    - HTTPX for non-blocking HTTP requests
    - Implements stream proxy to avoid 403 errors
    """
    logger.info("🚀 Async download request received")
    
    try:
        uid = str(uuid.uuid4())
        
        # 1. Clean & Expand URL (ASYNC)
        url = await expand_short_url(data.url)
        domain = urlparse(url).netloc.lower()
        platform = detect_platform(url)
        
        logger.info(f"✅ Processing [{platform}]: {url}")
        
        # --- SIMPLIFIED EXTRACTION STRATEGY ---
        # All platforms: J2Download (works for all social media + YouTube)
        
        extraction_result = None
        
        logger.info(f"🎯 {platform} detected - using J2Download")
        j2 = AsyncJ2Extractor()
        extraction_result = await j2.extract_download_url(
            url, 
            provided_token=data.csrf_token,
            provided_cookies=data.cookie_string,
            provided_ua=data.user_agent
        )
        
        # Check for SESSION_EXPIRED special case
        if isinstance(extraction_result, dict) and extraction_result.get("error") == "SESSION_EXPIRED":
             raise HTTPException(status_code=401, detail="SESSION_EXPIRED")

        if isinstance(extraction_result, dict) and extraction_result.get("error") == "CONTENT_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Content not found - the video may be private, deleted, or unavailable")

        if not extraction_result:
            # Return 503 so the client knows this is a transient server-side failure
            raise HTTPException(status_code=503, detail="Media extraction failed - please try again")
        
        logger.info(f"✅ Extraction successful. Platform: {platform}")
        logger.info(f"📦 Extraction result keys: {extraction_result.keys()}")
        logger.info(f"🔗 Direct URL: {extraction_result.get('url', 'N/A')[:100]}...")
        
        # YouTube: Use stream proxy to avoid 403 errors from expired/IP-locked URLs
        if platform == "youtube":
            ext = extraction_result.get("ext", "mp4")
            title = extraction_result.get("title", "video")
            direct_url = extraction_result["url"]
            
            logger.info(f"🎬 YouTube detected - using stream proxy to avoid 403 errors")
            logger.info(f"📱 Direct URL (first 150 chars): {direct_url[:150]}...")
            
            # Store stream data for proxying
            stream_id = uid
            
            # Pre-fetch content length for YouTube as well
            content_length = None
            try:
                async with httpx.AsyncClient(timeout=5.0) as head_client:
                    head_resp = await head_client.head(direct_url, headers={"User-Agent": EXACT_UA}, follow_redirects=True)
                    if head_resp.status_code == 200:
                        content_length = int(head_resp.headers.get("Content-Length", 0))
            except:
                logger.warning(f"⚠️ Failed to pre-fetch Content-Length for YouTube {stream_id}")

            stream_data = {
                "url": direct_url,
                "ext": ext,
                "title": title,
                "platform": platform,
                "size": content_length,
                "source": extraction_result.get("source", "j2")
            }
            
            if not hasattr(app.state, 'streams'):
                app.state.streams = {}
            app.state.streams[stream_id] = stream_data
            
            logger.info(f"✅ YouTube: Stream proxy ready for {stream_id} (Size: {content_length})")
            
            return DownloadResponse(
                status="success",
                download_url=f"/stream/{stream_id}",  # Use stream proxy
                filename=f"{title}.{ext}",
                message="Stream proxy ready",
                title=title,
                platform=platform,
                size=content_length
            )
        
        # Check if it's a multi-image post (like TikTok photo slideshow)
        if isinstance(extraction_result, dict) and "medias" in extraction_result:
            medias = extraction_result["medias"]
            images = [m for m in medias if m.get("type") == "image"]
            
            if len(images) > 1:
                logger.info(f"📸 Multi-image post detected: {len(images)} images")
                
                # For multi-image, create stream URLs for each image
                files = []
                for i, image in enumerate(images):
                    ext = image.get("extension", "jpg")
                    image_stream_id = f"{uid}_image_{i+1}"
                    
                    # Store each image stream
                    if not hasattr(app.state, 'streams'):
                        app.state.streams = {}
                    
                    app.state.streams[image_stream_id] = {
                        "url": image["url"],
                        "ext": ext,
                        "title": f"image_{i+1}",
                        "platform": platform,
                        "source": extraction_result.get("source", "j2")
                    }
                    
                    files.append({
                        "filename": f"image_{i+1}.{ext}",
                        "download_url": f"/stream/{image_stream_id}",
                        "type": "image"
                    })
                
                return DownloadResponse(
                    status="success",
                    message=f"Ready to download {len(files)} images from photo slideshow",
                    type="multi_image",
                    total_images=len(files),
                    files=files,
                    title=extraction_result.get("title", "Photo Post"),
                    platform=platform
                )
        
        # For single video/audio files (non-YouTube, non-multi-image)
        ext = extraction_result.get("ext", "mp4")
        source = extraction_result.get("source", "j2")
        title = extraction_result.get("title", "video")
        direct_url = extraction_result["url"]
        
        # TikTok & Instagram images: Send direct URL (they're more stable than videos)
        if platform in ["tiktok", "instagram"] and ext.lower() in ["jpg", "jpeg", "png", "webp"]:
            logger.info(f"📸 {platform.capitalize()} image detected - sending direct URL")
            logger.info(f"🔗 Direct URL: {direct_url}")
            
            return DownloadResponse(
                status="success",
                download_url=direct_url,  # Direct URL for images
                filename=f"{title}.{ext}",
                message="Direct download ready",
                title=title,
                platform=platform
            )
        
        # All other platforms: Use stream proxy approach
        # Store the direct URL and metadata for streaming
        stream_id = uid
        
        # Pre-fetch content length if possible.
        # TikTok's tt_chain_token is single-use: a HEAD request consumes the token,
        # causing the subsequent GET in /stream to receive 404. Skip HEAD for these URLs.
        content_length = None
        if platform == "tiktok" or "tt_chain_token" in direct_url:
            content_length = extraction_result.get("size")
            logger.info(f"⏭️ Skipping HEAD for TikTok (tt_chain_token) — j2 size: {content_length}")
        else:
            try:
                async with httpx.AsyncClient(timeout=5.0) as head_client:
                    head_resp = await head_client.head(direct_url, headers={"User-Agent": EXACT_UA}, follow_redirects=True)
                    if head_resp.status_code == 200:
                        content_length = int(head_resp.headers.get("Content-Length", 0))
            except:
                logger.warning(f"⚠️ Failed to pre-fetch Content-Length for {stream_id}")

        stream_data = {
            "url": direct_url,
            "ext": ext,
            "title": title,
            "platform": platform,
            "source": source,
            "size": content_length,
            "original_url": url
        }

        # Store fallback URL for TikTok in case the primary CDN URL is unreachable
        if "fallback_url" in extraction_result:
            stream_data["fallback_url"] = extraction_result["fallback_url"]
            logger.info(f"💾 Stored fallback URL for {platform}")
        
        if not hasattr(app.state, 'streams'):
            app.state.streams = {}
        app.state.streams[stream_id] = stream_data
        
        logger.info(f"✅ {platform}: Stream proxy ready for {stream_id} (Size: {content_length})")
        
        return DownloadResponse(
            status="success",
            download_url=f"/stream/{stream_id}",
            filename=f"{title}.{ext}",
            message="Stream proxy ready",
            title=title,
            platform=platform,
            size=content_length
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Final Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@get("/files/{filename:str}")
async def serve_file(filename: str) -> File:
    """Serve downloaded files"""
    file_path = os.path.join(DOWNLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return File(file_path, filename=filename)

@get("/stream/{stream_id:str}")
async def stream_proxy(stream_id: str) -> Stream:
    """
    Stream Proxy Endpoint - Safely streams video with exact Content-Length for progress bars
    """
    from litestar.response import Stream
    import traceback
    import time
    from urllib.parse import parse_qs, urlparse
    
    logger.info(f"🌊 Stream endpoint called for: {stream_id}")
    
    # Initialize client outside the try block so we can ensure it closes on failure
    client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=15.0), follow_redirects=True)
    
    try:
        # Get stream data
        if not hasattr(app.state, 'streams'):
            raise HTTPException(status_code=500, detail="Server state not initialized")
            
        if stream_id not in app.state.streams:
            raise HTTPException(status_code=404, detail="Stream not found")
        
        stream_data = app.state.streams[stream_id]
        video_url = stream_data.get("url")
        ext = stream_data.get("ext")
        title = stream_data.get("title")
        platform = stream_data.get("platform")
        original_url = stream_data.get("original_url")
        
        logger.info(f"🌊 Starting stream proxy for {platform}: {stream_id}")
        
        # Determine content type
        content_type_map = {
            "mp4": "video/mp4",
            "mp3": "audio/mpeg",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webm": "video/webm"
        }
        content_type = content_type_map.get(ext.lower(), "application/octet-stream")
        
        # Create safe filename - remove newlines, emojis, and other illegal characters
        safe_title = title.replace('\n', ' ').replace('\r', ' ')
        # Remove emojis and non-ASCII characters
        safe_title = re.sub(r'[^\x00-\x7F]+', '', safe_title)
        # Remove any remaining special characters except spaces and hyphens
        safe_title = re.sub(r'[^\w\s-]', '', safe_title).strip()[:50]
        filename = f"{safe_title}.{ext}" if safe_title else f"video.{ext}"
        
        current_url = stream_data.get("url", video_url)
        
        # J2Download Platforms (Tiktok, Instagram, Facebook)
        # We now allow the server to proxy these as requested by the user flow.
        
        # Original J2 logic as fallback
        # Check URL expiry for TikTok before streaming
        if platform == "tiktok" and "x-expires=" in current_url:
            try:
                parsed = urlparse(current_url)
                params = parse_qs(parsed.query)
                expires_timestamp = int(params.get('x-expires', [0])[0])
                
                if int(time.time()) >= expires_timestamp:
                    logger.warning(f"⚠️ URL expired, re-extracting...")
                    if original_url:
                        j2 = AsyncJ2Extractor()
                        fresh_result = await j2.extract_download_url(original_url)
                        if fresh_result and fresh_result.get("url"):
                            current_url = fresh_result["url"]
                            stream_data["url"] = current_url
            except Exception as e:
                logger.warning(f"⚠️ Expiry check failed: {e}")
        
        # Build platform-specific request headers.
        # TikTok's CDN (especially api.tiktokv.com) checks the Referer header.
        stream_headers = {"User-Agent": EXACT_UA, "Accept": "*/*"}
        if platform == "tiktok":
            stream_headers["Referer"] = "https://www.tiktok.com/"

        # 1. Start the GET request in streaming mode (DO NOT use a context manager here)
        req = client.build_request("GET", current_url, headers=stream_headers)
        response = await client.send(req, stream=True)
        
        if response.status_code not in [200, 206]:
            await response.aclose()
            # For TikTok 404s, try the stored fallback URL before giving up
            fallback_url = stream_data.get("fallback_url")
            if response.status_code == 404 and fallback_url:
                logger.warning(f"⚠️ Primary URL 404 for {platform}, trying fallback URL...")
                req = client.build_request("GET", fallback_url, headers=stream_headers)
                response = await client.send(req, stream=True)
                if response.status_code not in [200, 206]:
                    await response.aclose()
                    await client.aclose()
                    logger.error(f"❌ HTTP {response.status_code} from media server (fallback also failed)")
                    raise HTTPException(status_code=503, detail="Media temporarily unavailable - please try again")
            else:
                await client.aclose()
                logger.error(f"❌ HTTP {response.status_code} from media server")
                # Return 503 for 404 so the client retries rather than showing a hard error
                raise HTTPException(
                    status_code=503 if response.status_code == 404 else 500,
                    detail="Media temporarily unavailable - please try again" if response.status_code == 404 else f"Failed to fetch: {response.status_code}"
                )
        
        # 2. Extract the exact Content-Length directly from the GET response
        exact_content_length = response.headers.get("Content-Length")
        logger.info(f"📏 Exact Content-Length extracted: {exact_content_length} bytes")
        
        # 3. Create the generator that will yield chunks and handle cleanup
        async def stream_generator():
            try:
                logger.info("✅ Streaming content...")
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    yield chunk
            except Exception as e:
                logger.error(f"❌ Stream interrupted: {e}")
            finally:
                # Crucial: Clean up HTTPX resources when the stream ends or client disconnects
                await response.aclose()
                await client.aclose()
                if hasattr(app.state, 'streams') and stream_id in app.state.streams:
                    del app.state.streams[stream_id]
                logger.info(f"🧹 Cleaned up stream {stream_id}")
        
        # 4. Build headers and pass them to Litestar
        response_headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache"
        }
        
        if exact_content_length:
            response_headers["Content-Length"] = exact_content_length
        
        return Stream(
            stream_generator(),
            media_type=content_type,
            headers=response_headers
        )
        
    except HTTPException:
        await client.aclose()
        raise
    except Exception as e:
        await client.aclose()
        logger.error(f"❌ Stream proxy error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

# Create Litestar app
app = Litestar(
    route_handlers=[index, get_version, download_video, serve_file, stream_proxy]
)

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🚀 Starting ASYNC Universal Media Downloader on port {port}")
    
    uvicorn.run(
        "server:app",
        host="0.0.0.0", 
        port=port,
        loop="uvloop"
    )
