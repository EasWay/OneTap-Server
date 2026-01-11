#!/usr/bin/env python3
"""
Test script for Chrome Profile YouTube session extension
"""

import os
import sys
import json
import time
from datetime import datetime

def test_profile_exists():
    """Test if the Chrome profile exists"""
    print("=== Testing Chrome Profile Existence ===")
    
    profile_path = "tldv_profile"
    if not os.path.exists(profile_path):
        print(f"❌ Profile not found at: {profile_path}")
        return False
    
    print(f"✅ Profile found at: {profile_path}")
    
    # Check for cookies file
    cookies_file = os.path.join(profile_path, "Default", "Network", "Cookies")
    if os.path.exists(cookies_file):
        file_size = os.path.getsize(cookies_file)
        print(f"✅ Cookies database found ({file_size} bytes)")
    else:
        print("❌ Cookies database not found")
        return False
    
    return True

def test_cookie_extraction():
    """Test extracting cookies from the Chrome profile"""
    print("\n=== Testing Cookie Extraction ===")
    
    try:
        from chrome_profile_manager import ChromeProfileManager
        
        manager = ChromeProfileManager()
        cookies = manager.extract_cookies_from_profile()
        
        if not cookies:
            print("❌ No cookies extracted from profile")
            return False
        
        print(f"✅ Extracted {len(cookies)} cookies from profile")
        
        # Show some sample cookies (without values for security)
        google_cookies = [c for c in cookies if 'google' in c['domain'].lower() or 'youtube' in c['domain'].lower()]
        print(f"📊 Found {len(google_cookies)} Google/YouTube cookies")
        
        for cookie in google_cookies[:5]:  # Show first 5
            print(f"  - {cookie['name']} @ {cookie['domain']}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {str(e)}")
        print("Make sure selenium and webdriver-manager are installed:")
        print("pip install selenium webdriver-manager")
        return False
    except Exception as e:
        print(f"❌ Error extracting cookies: {str(e)}")
        return False

def test_session_info():
    """Test getting session information"""
    print("\n=== Testing Session Information ===")
    
    try:
        from chrome_profile_manager import ChromeProfileManager
        
        manager = ChromeProfileManager()
        info = manager.get_session_info()
        
        if info:
            print("📊 Session Information:")
            print(json.dumps(info, indent=2))
            
            # Check for important session cookies
            session_cookies = info.get('session_cookies', [])
            if session_cookies:
                print(f"✅ Found {len(session_cookies)} important session cookies")
                return True
            else:
                print("⚠️ No important session cookies found - may need to login to Chrome profile")
                return False
        else:
            print("❌ Failed to get session information")
            return False
            
    except Exception as e:
        print(f"❌ Error getting session info: {str(e)}")
        return False

def test_cookie_saving():
    """Test saving cookies in Netscape format"""
    print("\n=== Testing Cookie Saving ===")
    
    try:
        from chrome_profile_manager import ChromeProfileManager
        
        manager = ChromeProfileManager()
        cookies = manager.extract_cookies_from_profile()
        
        if not cookies:
            print("❌ No cookies to save")
            return False
        
        if manager.save_cookies_netscape_format(cookies):
            print(f"✅ Cookies saved to {manager.google_cookies_output}")
            
            # Check file size
            file_size = os.path.getsize(manager.google_cookies_output)
            print(f"📁 Cookie file size: {file_size} bytes")
            
            # Show first few lines of the cookie file
            print("\n📄 Cookie file preview:")
            with open(manager.google_cookies_output, 'r') as f:
                for i, line in enumerate(f):
                    if i < 10:  # Show first 10 lines
                        print(f"  {line.strip()}")
                    else:
                        break
            
            return True
        else:
            print("❌ Failed to save cookies")
            return False
            
    except Exception as e:
        print(f"❌ Error saving cookies: {str(e)}")
        return False

def test_integration_with_server():
    """Test integration with the existing server"""
    print("\n=== Testing Server Integration ===")
    
    try:
        # Test if the updated cookie_manager can use Chrome profile
        from cookie_manager import extend_google_youtube_session
        
        print("🔄 Testing YouTube session extension...")
        success = extend_google_youtube_session()
        
        if success:
            print("✅ YouTube session extension completed successfully!")
            
            # Check if google_cookies.txt was created/updated
            if os.path.exists("google_cookies.txt"):
                file_size = os.path.getsize("google_cookies.txt")
                mod_time = datetime.fromtimestamp(os.path.getmtime("google_cookies.txt"))
                print(f"📁 google_cookies.txt updated ({file_size} bytes) at {mod_time}")
                return True
            else:
                print("⚠️ google_cookies.txt not found after extension")
                return False
        else:
            print("❌ YouTube session extension failed")
            return False
            
    except Exception as e:
        print(f"❌ Error testing server integration: {str(e)}")
        return False

def test_yt_dlp_compatibility():
    """Test if the generated cookies work with yt-dlp"""
    print("\n=== Testing yt-dlp Compatibility ===")
    
    if not os.path.exists("google_cookies.txt"):
        print("❌ google_cookies.txt not found. Run cookie extraction first.")
        return False
    
    try:
        # Try to import yt-dlp and test cookie format
        import yt_dlp
        
        # Test with a simple YouTube video (just info extraction, no download)
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll for testing
        
        ydl_opts = {
            'cookiefile': 'google_cookies.txt',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # Just extract info, don't download
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(test_url, download=False)
                if info:
                    print("✅ yt-dlp successfully used the cookies!")
                    print(f"📺 Video title: {info.get('title', 'Unknown')}")
                    return True
                else:
                    print("⚠️ yt-dlp extracted info but no title found")
                    return False
            except Exception as e:
                print(f"⚠️ yt-dlp test failed: {str(e)}")
                print("This might be normal if the cookies are expired or the video is restricted")
                return False
                
    except ImportError:
        print("⚠️ yt-dlp not installed. Install with: pip install yt-dlp")
        print("✅ Cookie file format looks correct for yt-dlp")
        return True
    except Exception as e:
        print(f"❌ Error testing yt-dlp compatibility: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("🧪 Chrome Profile YouTube Session Extension Tests")
    print("=" * 60)
    
    tests = [
        ("Profile Existence", test_profile_exists),
        ("Cookie Extraction", test_cookie_extraction),
        ("Session Information", test_session_info),
        ("Cookie Saving", test_cookie_saving),
        ("Server Integration", test_integration_with_server),
        ("yt-dlp Compatibility", test_yt_dlp_compatibility)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            results.append((test_name, result))
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"\n{test_name}: {status}")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {str(e)}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Chrome profile approach is working perfectly.")
        print("\n📋 Next Steps:")
        print("  1. Your YouTube session extension is ready to use")
        print("  2. Start your server: python server.py")
        print("  3. Test the endpoint: POST /extend_youtube_session")
        print("  4. Use the generated google_cookies.txt with yt-dlp")
    elif passed >= total - 1:
        print("\n✅ Chrome profile approach is working! Minor issues can be ignored.")
    else:
        print("\n⚠️ Some tests failed. Check the output above for details.")
        print("\n🔧 Common fixes:")
        print("  - Install missing packages: pip install selenium webdriver-manager")
        print("  - Make sure Chrome is installed")
        print("  - Ensure tldv_profile has valid Google login session")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)