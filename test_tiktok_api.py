#!/usr/bin/env python3
"""
TikTok Mobile API Test Script
Tests the mobile API emulation with various TikTok URL formats
"""

import sys
import logging
import time
from tiktok_extractor import TikTokExtractor
from tiktok_mobile_api import TikTokMobileAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_url_extraction():
    """Test video ID extraction from various URL formats"""
    print("🧪 Testing URL extraction...")
    
    test_urls = [
        "https://www.tiktok.com/@username/video/7298573727421123845",
        "https://vm.tiktok.com/ZMhQKqLDg/",
        "https://vt.tiktok.com/ZSFqKqLDg/",
        "https://www.tiktok.com/t/ZTRQKqLDg/",
        "https://m.tiktok.com/v/7298573727421123845.html"
    ]
    
    api = TikTokMobileAPI("test_user")
    
    for url in test_urls:
        video_id = api.extract_video_id_from_url(url)
        print(f"  URL: {url}")
        print(f"  Video ID: {video_id}")
        print()

def test_device_fingerprinting():
    """Test device fingerprinting consistency"""
    print("🤖 Testing device fingerprinting...")
    
    # Test consistent fingerprinting for same user
    api1 = TikTokMobileAPI("test_user_123")
    api2 = TikTokMobileAPI("test_user_123")
    
    fingerprint1 = api1.device_manager.get_fingerprint_summary()
    fingerprint2 = api2.device_manager.get_fingerprint_summary()
    
    print(f"  User 1 (first instance): {fingerprint1}")
    print(f"  User 1 (second instance): {fingerprint2}")
    print(f"  Consistent: {fingerprint1 == fingerprint2}")
    print()
    
    # Test different fingerprints for different users
    api3 = TikTokMobileAPI("different_user_456")
    fingerprint3 = api3.device_manager.get_fingerprint_summary()
    
    print(f"  User 2: {fingerprint3}")
    print(f"  Different from User 1: {fingerprint1 != fingerprint3}")
    print()

def test_mobile_api_extraction(video_url):
    """Test mobile API extraction for a specific video"""
    print(f"📱 Testing mobile API extraction for: {video_url}")
    
    try:
        extractor = TikTokExtractor("test_user")
        result = extractor.extract_video(video_url)
        
        if result["success"]:
            print("  ✅ Extraction successful!")
            print(f"  📹 Video URL: {result['video_url'][:50]}...")
            print(f"  🎬 Title: {result.get('title', 'N/A')}")
            print(f"  👤 Author: {result.get('author', 'N/A')}")
            print(f"  ⏱️ Duration: {result.get('duration', 0)}s")
            print(f"  👀 Views: {result.get('view_count', 0):,}")
            print(f"  ❤️ Likes: {result.get('like_count', 0):,}")
            print(f"  🔧 Extractor: {result.get('extractor', 'unknown')}")
            print(f"  💧 Watermark: {'Yes' if result.get('has_watermark', True) else 'No'}")
            print(f"  🎯 Quality: {result.get('quality', 'unknown')}")
        else:
            print(f"  ❌ Extraction failed: {result['error']}")
            
    except Exception as e:
        print(f"  💥 Test crashed: {e}")
    
    print()

def test_fallback_chain():
    """Test the fallback chain behavior"""
    print("🔄 Testing fallback chain...")
    
    extractor = TikTokExtractor("test_user")
    
    # Test each extractor individually
    test_video_id = "7298573727421123845"
    test_url = f"https://www.tiktok.com/@test/video/{test_video_id}"
    
    extractors = [
        ("Mobile API", extractor._extract_via_mobile_api),
        ("Web API", extractor._extract_via_web_api),
        ("oEmbed", extractor._extract_via_oembed),
        ("yt-dlp", extractor._extract_via_ytdlp_fallback)
    ]
    
    for name, extractor_func in extractors:
        try:
            print(f"  Testing {name}...")
            result = extractor_func(test_video_id, test_url)
            
            if result["success"]:
                print(f"    ✅ {name} successful")
            else:
                print(f"    ❌ {name} failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"    💥 {name} crashed: {e}")
    
    print()

def test_api_endpoints():
    """Test API endpoint rotation"""
    print("🌐 Testing API endpoint rotation...")
    
    api = TikTokMobileAPI("test_user")
    
    print(f"  Available endpoints: {len(api.base_urls)}")
    for i, endpoint in enumerate(api.base_urls):
        print(f"    {i+1}. {endpoint}")
    
    print(f"  Current endpoint index: {api.current_base_url_index}")
    
    # Test endpoint rotation
    original_index = api.current_base_url_index
    api._rotate_endpoint()
    new_index = api.current_base_url_index
    
    print(f"  After rotation: {new_index}")
    print(f"  Rotation working: {original_index != new_index}")
    print()

def main():
    """Run all tests"""
    print("🚀 TikTok Mobile API Test Suite")
    print("=" * 50)
    
    # Basic tests
    test_url_extraction()
    test_device_fingerprinting()
    test_api_endpoints()
    test_fallback_chain()
    
    # Live extraction test (if URL provided)
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
        test_mobile_api_extraction(test_url)
    else:
        print("💡 Tip: Provide a TikTok URL as argument to test live extraction")
        print("   Example: python test_tiktok_api.py https://vm.tiktok.com/ZMhQKqLDg/")
    
    print("🏁 Test suite completed!")

if __name__ == "__main__":
    main()