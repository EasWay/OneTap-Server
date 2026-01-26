#!/usr/bin/env python3
"""
TikTok Mobile API Emulation
Mimics official TikTok Android app behavior for direct video URL extraction
"""

import hashlib
import hmac
import json
import random
import time
import uuid
import requests
from urllib.parse import urlencode, quote
import logging
from device_fingerprint import DeviceFingerprintManager
from tiktok_config import TIKTOK_CONFIG, FALLBACK_CONFIG

logger = logging.getLogger(__name__)

class TikTokMobileAPI:
    """
    TikTok Mobile API Emulator
    Pretends to be the official TikTok Android app with realistic device fingerprinting
    """
    
    def __init__(self, user_identifier=None):
        # Create persistent device fingerprint for this user/session
        if user_identifier:
            self.device_manager = DeviceFingerprintManager.create_persistent_device(user_identifier)
        else:
            self.device_manager = DeviceFingerprintManager()
        
        # Session management
        self.session = requests.Session()
        self.session_id = None
        self.cookies = {}
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = TIKTOK_CONFIG["MIN_REQUEST_INTERVAL"]
        
        # Fallback endpoints
        self.base_urls = TIKTOK_CONFIG["BASE_URLS"].copy()
        self.current_base_url_index = 0
        
        logger.info(f"🤖 TikTok Mobile API initialized with device: {self.device_manager.get_fingerprint_summary()}")
    
    def _get_current_timestamp(self):
        """Get current timestamp in seconds"""
        return int(time.time())
    
    def _build_common_params(self):
        """Build common parameters for all API requests"""
        timestamp = self._get_current_timestamp()
        device_params = self.device_manager.get_device_params()
        
        params = {
            # App identification
            "aid": TIKTOK_CONFIG["AID"],
            "app_name": TIKTOK_CONFIG["APP_NAME"],
            "version_code": TIKTOK_CONFIG["VERSION_CODE"],
            "version_name": TIKTOK_CONFIG["APP_VERSION"],
            "manifest_version_code": TIKTOK_CONFIG["MANIFEST_VERSION_CODE"],
            "update_version_code": TIKTOK_CONFIG["MANIFEST_VERSION_CODE"],
            
            # Session and timing
            "ts": timestamp,
            "_rticket": timestamp * 1000,
            "cdid": str(uuid.uuid4()),
            
            # Language and locale
            "app_language": "en",
            "language": "en",
        }
        
        # Merge device-specific parameters
        params.update(device_params)
        
        return params
    
    def _rate_limit(self):
        """Implement rate limiting to avoid detection"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            # Add small random jitter to avoid detection
            sleep_time += random.uniform(0.1, 0.5)
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _make_request(self, endpoint, params, data=None, method="GET"):
        """Make authenticated request to TikTok API with fallback"""
        self._rate_limit()
        
        params_str = urlencode(sorted(params.items()))
        
        # Try each base URL until one works
        for attempt in range(len(self.base_urls)):
            base_url = self.base_urls[self.current_base_url_index]
            url = f"{base_url}{endpoint}?{params_str}"
            
            try:
                headers = self.device_manager.get_headers(params_str, data)
                
                logger.info(f"🔄 TikTok API request to {base_url} (attempt {attempt + 1})")
                
                if method == "GET":
                    response = self.session.get(
                        url, 
                        headers=headers, 
                        timeout=TIKTOK_CONFIG["REQUEST_TIMEOUT"],
                        allow_redirects=True
                    )
                else:
                    response = self.session.post(
                        url, 
                        headers=headers, 
                        data=data, 
                        timeout=TIKTOK_CONFIG["REQUEST_TIMEOUT"],
                        allow_redirects=True
                    )
                
                if response.status_code == 200:
                    logger.info(f"✅ TikTok API request successful")
                    try:
                        return response.json()
                    except json.JSONDecodeError:
                        logger.warning("⚠️ Response is not valid JSON")
                        return {"error": "Invalid JSON response"}
                        
                elif response.status_code == 403:
                    logger.warning(f"⚠️ TikTok API blocked request (403) - trying next endpoint")
                    self._rotate_endpoint()
                    continue
                    
                elif response.status_code == 429:
                    logger.warning(f"⚠️ Rate limited (429) - waiting and trying next endpoint")
                    time.sleep(random.uniform(2, 5))  # Wait 2-5 seconds
                    self._rotate_endpoint()
                    continue
                    
                else:
                    logger.warning(f"⚠️ TikTok API returned {response.status_code} - trying next endpoint")
                    self._rotate_endpoint()
                    continue
                    
            except requests.exceptions.Timeout:
                logger.warning(f"⚠️ Request timeout - trying next endpoint")
                self._rotate_endpoint()
                continue
                
            except requests.exceptions.ConnectionError:
                logger.warning(f"⚠️ Connection error - trying next endpoint")
                self._rotate_endpoint()
                continue
                
            except Exception as e:
                logger.warning(f"⚠️ Request failed: {e} - trying next endpoint")
                self._rotate_endpoint()
                continue
        
        raise Exception("All TikTok API endpoints failed")
    
    def _rotate_endpoint(self):
        """Rotate to next API endpoint"""
        self.current_base_url_index = (self.current_base_url_index + 1) % len(self.base_urls)
    
    def get_video_info(self, video_id):
        """
        Get video information using mobile API
        Returns direct video URLs without HTML parsing
        """
        try:
            logger.info(f"🎯 Getting TikTok video info for ID: {video_id}")
            
            # Build API parameters
            params = self._build_common_params()
            params.update({
                "aweme_id": video_id,
                "pull_type": "0"
            })
            
            # Make API request
            response_data = self._make_request("/aweme/v1/feed/", params)
            
            if not response_data or "aweme_list" not in response_data:
                # Try alternative endpoint
                logger.info("🔄 Trying alternative API endpoint")
                response_data = self._make_request("/aweme/v2/feed/", params)
                
                if not response_data or "aweme_list" not in response_data:
                    raise Exception("Invalid API response format from all endpoints")
            
            aweme_list = response_data["aweme_list"]
            if not aweme_list:
                raise Exception("Video not found or may be private/deleted")
            
            video_data = aweme_list[0]
            
            # Extract video URLs with fallback chain
            video_urls = self._extract_video_urls(video_data)
            
            # Extract metadata
            metadata = self._extract_metadata(video_data)
            
            return {
                "video_urls": video_urls,
                "metadata": metadata,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"❌ TikTok mobile API failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _extract_video_urls(self, video_data):
        """Extract video URLs with aggressive fallback chain"""
        urls = {
            "play_addr": [],
            "download_addr": [],
            "play_addr_h264": [],
            "play_addr_bytevc1": []
        }
        
        try:
            video_info = video_data.get("video", {})
            
            # Primary: playAddr (highest quality, no watermark)
            if "play_addr" in video_info:
                play_addr = video_info["play_addr"]
                if "url_list" in play_addr:
                    urls["play_addr"] = play_addr["url_list"]
            
            # Fallback 1: downloadAddr (may have watermark)
            if "download_addr" in video_info:
                download_addr = video_info["download_addr"]
                if "url_list" in download_addr:
                    urls["download_addr"] = download_addr["url_list"]
            
            # Fallback 2: H264 encoded versions
            if "play_addr_h264" in video_info:
                h264_addr = video_info["play_addr_h264"]
                if "url_list" in h264_addr:
                    urls["play_addr_h264"] = h264_addr["url_list"]
            
            # Fallback 3: ByteVC1 encoded versions
            if "play_addr_bytevc1" in video_info:
                bytevc1_addr = video_info["play_addr_bytevc1"]
                if "url_list" in bytevc1_addr:
                    urls["play_addr_bytevc1"] = bytevc1_addr["url_list"]
            
            total_urls = sum(len(v) for v in urls.values())
            logger.info(f"📹 Extracted {total_urls} video URLs")
            
            return urls
            
        except Exception as e:
            logger.error(f"❌ Failed to extract video URLs: {e}")
            return urls
    
    def _extract_metadata(self, video_data):
        """Extract video metadata"""
        try:
            metadata = {
                "title": video_data.get("desc", ""),
                "author": video_data.get("author", {}).get("nickname", ""),
                "author_username": video_data.get("author", {}).get("unique_id", ""),
                "duration": video_data.get("video", {}).get("duration", 0),
                "view_count": video_data.get("statistics", {}).get("play_count", 0),
                "like_count": video_data.get("statistics", {}).get("digg_count", 0),
                "comment_count": video_data.get("statistics", {}).get("comment_count", 0),
                "share_count": video_data.get("statistics", {}).get("share_count", 0),
                "create_time": video_data.get("create_time", 0),
                "video_id": video_data.get("aweme_id", ""),
                "music_title": video_data.get("music", {}).get("title", ""),
                "music_author": video_data.get("music", {}).get("author", "")
            }
            
            return metadata
            
        except Exception as e:
            logger.error(f"❌ Failed to extract metadata: {e}")
            return {}
    
    def extract_video_id_from_url(self, url):
        """Extract video ID from various TikTok URL formats"""
        import re
        
        patterns = [
            r"tiktok\.com/@[^/]+/video/(\d+)",  # @username/video/123456
            r"tiktok\.com/t/([A-Za-z0-9]+)",     # Short URLs
            r"vm\.tiktok\.com/([A-Za-z0-9]+)",  # Mobile URLs
            r"vt\.tiktok\.com/([A-Za-z0-9]+)"   # vt.tiktok.com URLs
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                
                # For short URLs, we need to resolve them first
                if not video_id.isdigit():
                    resolved_id = self._resolve_short_url(url)
                    if resolved_id:
                        return resolved_id
                
                return video_id
        
        return None
    
    def _resolve_short_url(self, short_url):
        """Resolve TikTok short URL to get actual video ID"""
        try:
            logger.info(f"🔗 Resolving TikTok short URL: {short_url}")
            
            # Use mobile User-Agent for consistency
            headers = {
                "User-Agent": self.device_manager.get_user_agent(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
            
            # Follow redirects to get the actual video URL
            response = requests.head(
                short_url, 
                allow_redirects=True, 
                timeout=15,
                headers=headers
            )
            final_url = response.url
            
            # Extract video ID from final URL
            import re
            match = re.search(r"tiktok\.com/@[^/]+/video/(\d+)", final_url)
            if match:
                video_id = match.group(1)
                logger.info(f"✅ Resolved to video ID: {video_id}")
                return video_id
            
            logger.warning(f"⚠️ Could not extract video ID from resolved URL: {final_url}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to resolve short URL: {e}")
            return None