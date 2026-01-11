#!/usr/bin/env python3
"""
Test script for Chrome Profile YouTube session extension
"""

import os
import sys
import json
from chrome_profile_manager import ChromeProfileManager

def test_profile_extraction():
    """Test extracting cookies from the Chrome profile"""
    print("=== Testing Chrome Profile Cookie Extraction ===")
    
    manager = ChromeProfileManager()
    
    # Check if profile exists
    if not os.path.exists(manager.profile_path):
        print(f"❌ Profile not found at: {manager.profile_path}")
        return False
    
    print(f"✅ Profile found at: {manager.profile_path}")
    
    # Test cookie extraction
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
    
    # Test saving cookies
    if manager.save_cookies_netscape_format(cookies):
        print(f"✅ Cookies saved to {manager.google_cookies_output}")
        
        # Check file size
        file_size = os.path.getsize(manager.google_cookies_output)
        print(f"📁 Cookie file size: {file_size} bytes")
        
        return True
    else:
        print("❌ Failed to save cookies")
        return False

def test_session_info():
    """Test getting session information"""
    print("\n=== Testing Session Information ===")
    
    manager = ChromeProfileManager()
    info = manager.get_session_info()
    
    if info:
        print("📊 Session Information:")
        print(json.dumps(info, indent=2))
        return True
    else:
        print("❌ Failed to get session information")
        return False

def test_full_extension():
    """Test the full session extension process"""
    print("\n=== Testing Full Session Extension ===")
    
    manager = ChromeProfileManager()
    
    # Run the full extension process
    success = manager.extend_youtube_session()
    
    if success:
        print("✅ Full session extension completed successfully!")
        
        # Verify the output file
        if os.path.exists(manager.google_cookies_output):
            file_size = os.path.getsize(manager.google_cookies_output)
            print(f"📁 Output file: {manager.google_cookies_output} ({file_size} bytes)")
            
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
        print("❌ Full session extension failed")
        return False

def main():
    """Run all tests"""
    print("🧪 Chrome Profile YouTube Session Extension Tests")
    print("=" * 50)
    
    # Check if profile exists
    profile_path = "tldv_profile"
    if not os.path.exists(profile_path):
        print(f"❌ Chrome profile not found at: {profile_path}")
        print("Please ensure the tldv_profile folder is in the current directory")
        return False
    
    tests = [
        ("Cookie Extraction", test_profile_extraction),
        ("Session Information", test_session_info),
        ("Full Extension", test_full_extension)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
            if result:
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {str(e)}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Chrome profile approach is working.")
        return True
    else:
        print("⚠️ Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)