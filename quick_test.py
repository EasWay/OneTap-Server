#!/usr/bin/env python3
"""
Quick test for Chrome Profile YouTube extension
"""

import os
import json

def quick_test():
    print("🚀 Quick Chrome Profile Test")
    print("=" * 30)
    
    # Check if profile exists
    if not os.path.exists("tldv_profile"):
        print("❌ tldv_profile folder not found!")
        return False
    
    print("✅ tldv_profile found")
    
    # Check cookies file
    cookies_file = "tldv_profile/Default/Network/Cookies"
    if os.path.exists(cookies_file):
        size = os.path.getsize(cookies_file)
        print(f"✅ Cookies database found ({size} bytes)")
    else:
        print("❌ Cookies database not found")
        return False
    
    # Try to extract cookies
    try:
        from chrome_profile_manager import ChromeProfileManager
        manager = ChromeProfileManager()
        
        print("🔄 Extracting cookies...")
        cookies = manager.extract_cookies_from_profile()
        
        if cookies:
            print(f"✅ Extracted {len(cookies)} cookies")
            
            # Count Google/YouTube cookies
            google_cookies = [c for c in cookies if 'google' in c['domain'].lower() or 'youtube' in c['domain'].lower()]
            print(f"📊 {len(google_cookies)} Google/YouTube cookies found")
            
            # Save cookies
            print("💾 Saving cookies...")
            if manager.save_cookies_netscape_format(cookies):
                size = os.path.getsize("google_cookies.txt")
                print(f"✅ Saved to google_cookies.txt ({size} bytes)")
                return True
            else:
                print("❌ Failed to save cookies")
                return False
        else:
            print("❌ No cookies extracted")
            return False
            
    except ImportError:
        print("❌ Missing dependencies. Install with:")
        print("pip install selenium webdriver-manager")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    success = quick_test()
    if success:
        print("\n🎉 Quick test passed! Chrome profile approach is working.")
        print("Run 'python test_chrome_profile.py' for full tests.")
    else:
        print("\n❌ Quick test failed. Check the errors above.")