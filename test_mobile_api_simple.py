#!/usr/bin/env python3
"""
Simple TikTok Mobile API Test
"""

import logging
from tiktok_extractor import TikTokExtractor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_mobile_api():
    """Test mobile API with a known working video ID"""
    
    # Test with the video ID we successfully resolved
    test_url = "https://vt.tiktok.com/ZSa5Uw1Pe/"
    
    print(f"🧪 Testing TikTok Mobile API with: {test_url}")
    
    try:
        extractor = TikTokExtractor("test_user")
        result = extractor.extract_video(test_url)
        
        if result["success"]:
            print("✅ SUCCESS!")
            print(f"📹 Video URL: {result['video_url'][:100]}...")
            print(f"🎬 Title: {result.get('title', 'N/A')}")
            print(f"👤 Author: {result.get('author', 'N/A')}")
            print(f"🔧 Extractor: {result.get('extractor', 'N/A')}")
            print(f"💧 Watermark: {'Yes' if result.get('has_watermark', True) else 'No'}")
            print(f"🎯 Quality: {result.get('quality', 'N/A')}")
            
            # Test if we can access the video URL
            import requests
            try:
                response = requests.head(result['video_url'], timeout=10)
                print(f"🌐 Video URL accessible: {response.status_code == 200}")
                if response.status_code == 200:
                    content_length = response.headers.get('content-length')
                    if content_length:
                        size_mb = int(content_length) / (1024 * 1024)
                        print(f"📦 Video size: {size_mb:.2f} MB")
            except Exception as e:
                print(f"⚠️ Could not test video URL: {e}")
                
        else:
            print(f"❌ FAILED: {result['error']}")
            
    except Exception as e:
        print(f"💥 CRASHED: {e}")

if __name__ == "__main__":
    test_mobile_api()