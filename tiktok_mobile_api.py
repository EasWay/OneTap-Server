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
            
            if not response_data:
                raise Exception("Empty response from TikTok API")
            
            logger.info(f"📡 API Response keys: {list(response_data.keys())}")
            
            # Handle different response formats
            aweme_list = None
            if "aweme_list" in response_data:
                aweme_list = response_data["aweme_list"]
            elif "data" in response_data and isinstance(response_data["data"], list):
                aweme_list = response_data["data"]
            elif "aweme_detail" in response_data:
                aweme_list = [response_data["aweme_detail"]]
            
            if not aweme_list:
                # Try alternative endpoint
                logger.info("🔄 Trying alternative API endpoint")
                response_data = self._make_request("/aweme/v2/feed/", params)
                
                if response_data and "aweme_list" in response_data:
                    aweme_list = response_data["aweme_list"]
                
                if not aweme_list:
                    raise Exception("No video data found in API response")
            
            if not aweme_list:
                raise Exception("Video not found or may be private/deleted")
            
            video_data = aweme_list[0]
            logger.info(f"📱 Video data keys: {list(video_data.keys()) if isinstance(video_data, dict) else 'Not a dict'}")
            
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
            logger.info(f"🔍 Extracting video URLs from data with keys: {list(video_data.keys()) if isinstance(video_data, dict) else 'Not a dict'}")
            
            # Try different paths to find video info
            video_info = None
            
            if "video" in video_data:
                video_info = video_data["video"]
            elif "aweme_info" in video_data and "video" in video_data["aweme_info"]:
                video_info = video_data["aweme_info"]["video"]
            elif "item_info" in video_data and "video" in video_data["item_info"]:
                video_info = video_data["item_info"]["video"]
            
            if not video_info:
                logger.warning("⚠️ No video info found in response")
                return urls
            
            logger.info(f"📹 Video info keys: {list(video_info.keys()) if isinstance(video_info, dict) else 'Not a dict'}")
            
            # Extract URLs from different fields
            url_fields = [
                ("play_addr", "play_addr"),
                ("download_addr", "download_addr"), 
                ("play_addr_h264", "play_addr_h264"),
                ("play_addr_bytevc1", "play_addr_bytevc1"),
                ("bit_rate", "play_addr"),  # Sometimes stored under bit_rate
                ("play_url", "play_addr"),  # Alternative field name
                ("download_url", "download_addr")  # Alternative field name
            ]
            
            for field_name, url_type in url_fields:
                if field_name in video_info:
                    field_data = video_info[field_name]
                    
                    # Handle different data structures
                    extracted_urls = []
                    
                    if isinstance(field_data, dict):
                        if "url_list" in field_data:
                            extracted_urls = field_data["url_list"]
                        elif "uri" in field_data:
                            # Sometimes URI needs to be converted to full URL
                            uri = field_data["uri"]
                            if uri:
                                # Try common TikTok CDN patterns
                                cdn_bases = [
                                    "https://v16-webapp-prime.tiktok.com/video/tos/",
                                    "https://v19-webapp-prime.tiktok.com/video/tos/",
                                    "https://v77-webapp-prime.tiktok.com/video/tos/"
                                ]
                                for cdn_base in cdn_bases:
                                    extracted_urls.append(f"{cdn_base}{uri}")
                        elif "url" in field_data:
                            extracted_urls = [field_data["url"]]
                    elif isinstance(field_data, list):
                        # Handle array of URL objects
                        for item in field_data:
                            if isinstance(item, dict):
                                if "url_list" in item:
                                    extracted_urls.extend(item["url_list"])
                                elif "url" in item:
                                    extracted_urls.append(item["url"])
                            elif isinstance(item, str):
                                extracted_urls.append(item)
                    elif isinstance(field_data, str):
                        extracted_urls = [field_data]
                    
                    if extracted_urls:
                        # Clean and validate URLs
                        valid_urls = []
                        for url in extracted_urls:
                            if isinstance(url, str) and url.startswith(('http://', 'https://')):
                                valid_urls.append(url)
                        
                        if valid_urls:
                            urls[url_type].extend(valid_urls)
                            logger.info(f"✅ Found {len(valid_urls)} URLs for {field_name}")
            
            total_urls = sum(len(v) for v in urls.values())
            logger.info(f"📹 Extracted {total_urls} total video URLs")
            
            # Log URL types found
            for url_type, url_list in urls.items():
                if url_list:
                    logger.info(f"  {url_type}: {len(url_list)} URLs")
            
            return urls
            
        except Exception as e:
            logger.error(f"❌ Failed to extract video URLs: {e}")
            return urls
    
    def _extract_metadata(self, video_data):
        """Extract video metadata"""
        try:
            metadata = {}
            
            # Extract title/description
            if "desc" in video_data:
                metadata["title"] = video_data["desc"]
            elif "content" in video_data:
                metadata["title"] = video_data["content"]
            elif "text" in video_data:
                metadata["title"] = video_data["text"]
            else:
                metadata["title"] = ""
            
            # Extract author info
            author_info = video_data.get("author", {})
            if not author_info and "user" in video_data:
                author_info = video_data["user"]
            
            metadata["author"] = author_info.get("nickname", author_info.get("display_name", "Unknown"))
            metadata["author_username"] = author_info.get("unique_id", author_info.get("username", ""))
            
            # Extract video info
            video_info = video_data.get("video", {})
            metadata["duration"] = video_info.get("duration", 0)
            
            # Extract statistics
            stats = video_data.get("statistics", {})
            if not stats and "stats" in video_data:
                stats = video_data["stats"]
            
            metadata["view_count"] = stats.get("play_count", stats.get("view_count", 0))
            metadata["like_count"] = stats.get("digg_count", stats.get("like_count", 0))
            metadata["comment_count"] = stats.get("comment_count", 0)
            metadata["share_count"] = stats.get("share_count", 0)
            
            # Extract other info
            metadata["create_time"] = video_data.get("create_time", 0)
            metadata["video_id"] = video_data.get("aweme_id", video_data.get("item_id", ""))
            
            # Extract music info
            music_info = video_data.get("music", {})
            if not music_info and "audio" in video_data:
                music_info = video_data["audio"]
            
            metadata["music_title"] = music_info.get("title", "")
            metadata["music_author"] = music_info.get("author", music_info.get("artist", ""))
            
            logger.info(f"📊 Extracted metadata: title='{metadata['title'][:50]}...', author='{metadata['author']}'")
            
            return metadata
            
        except Exception as e:
            logger.error(f"❌ Failed to extract metadata: {e}")
            return {
                "title": "",
                "author": "Unknown",
                "author_username": "",
                "duration": 0,
                "view_count": 0,
                "like_count": 0,
                "comment_count": 0,
                "share_count": 0,
                "create_time": 0,
                "video_id": "",
                "music_title": "",
                "music_author": ""
            }
    
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
                
                # For short URLs (non-numeric IDs), we need to resolve them first
                if not video_id.isdigit():
                    logger.info(f"🔗 Short URL detected with ID: {video_id}")
                    resolved_id = self._resolve_short_url(url)
                    if resolved_id and resolved_id.isdigit():
                        logger.info(f"✅ Resolved to numeric video ID: {resolved_id}")
                        return resolved_id
                    else:
                        logger.warning(f"⚠️ Could not resolve short URL to numeric ID: {url}")
                        return None
                
                return video_id
        
        logger.warning(f"⚠️ No matching pattern found for URL: {url}")
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
            
            logger.info(f"🔗 Short URL resolved to: {final_url}")
            
            # Extract video ID from final URL using multiple patterns
            import re
            patterns = [
                r"tiktok\.com/@[^/]+/video/(\d+)",  # Standard format
                r"tiktok\.com/.*?/video/(\d+)",     # Any username format
                r"/video/(\d+)",                    # Just the video ID part
                r"aweme_id=(\d+)",                  # Query parameter
                r"item_id=(\d+)"                    # Alternative parameter
            ]
            
            for pattern in patterns:
                match = re.search(pattern, final_url)
                if match:
                    video_id = match.group(1)
                    if video_id.isdigit():
                        logger.info(f"✅ Resolved to video ID: {video_id}")
                        return video_id
            
            logger.warning(f"⚠️ Could not extract numeric video ID from resolved URL: {final_url}")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Network error resolving short URL: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Failed to resolve short URL: {e}")
            return None