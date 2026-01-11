#!/usr/bin/env python3
"""
Integration script to set up Chrome profile approach for YouTube session extension
"""

import os
import shutil
import json
from datetime import datetime

def setup_chrome_profile_integration():
    """Set up the Chrome profile integration"""
    print("🔧 Setting up Chrome Profile Integration for YouTube")
    print("=" * 50)
    
    # Check if tldv_profile exists
    if not os.path.exists("tldv_profile"):
        print("❌ tldv_profile folder not found!")
        print("Please ensure the tldv_profile folder is in the current directory")
        return False
    
    print("✅ Found tldv_profile folder")
    
    # Check if chrome_profile_manager.py exists
    if not os.path.exists("chrome_profile_manager.py"):
        print("❌ chrome_profile_manager.py not found!")
        print("Please ensure the chrome_profile_manager.py file is in the current directory")
        return False
    
    print("✅ Found chrome_profile_manager.py")
    
    # Test the Chrome profile approach
    try:
        from chrome_profile_manager import ChromeProfileManager
        
        manager = ChromeProfileManager()
        
        # Get session info
        info = manager.get_session_info()
        if info:
            print(f"📊 Profile contains {info['total_cookies']} cookies")
            print(f"🔑 Found {len(info['session_cookies'])} session cookies")
            
            # Show session cookies
            for cookie in info['session_cookies']:
                print(f"  - {cookie['name']} @ {cookie['domain']} (expires: {cookie['expires']})")
        
        # Test cookie extraction
        cookies = manager.extract_cookies_from_profile()
        if cookies:
            print(f"✅ Successfully extracted {len(cookies)} cookies from profile")
            
            # Save test cookies
            if manager.save_cookies_netscape_format(cookies):
                print(f"✅ Test cookies saved to {manager.google_cookies_output}")
                
                # Show file size
                file_size = os.path.getsize(manager.google_cookies_output)
                print(f"📁 Cookie file size: {file_size} bytes")
                
                return True
            else:
                print("❌ Failed to save test cookies")
                return False
        else:
            print("❌ No cookies extracted from profile")
            return False
            
    except Exception as e:
        print(f"❌ Error testing Chrome profile: {str(e)}")
        return False

def create_backup_profile():
    """Create a backup of the tldv_profile for YouTube use"""
    print("\n🔄 Creating backup profile for YouTube...")
    
    backup_path = "youtube_profile"
    
    try:
        # Remove existing backup if it exists
        if os.path.exists(backup_path):
            shutil.rmtree(backup_path)
            print(f"🗑️ Removed existing backup at {backup_path}")
        
        # Create new backup
        shutil.copytree("tldv_profile", backup_path)
        print(f"✅ Created backup profile at {backup_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to create backup profile: {str(e)}")
        return False

def update_server_integration():
    """Show how to integrate with the existing server"""
    print("\n📝 Server Integration Instructions:")
    print("=" * 30)
    
    print("1. Your cookie_manager.py has been updated to use Chrome profile approach first")
    print("2. If Chrome profile fails, it falls back to the original cookie-based method")
    print("3. The server.py will automatically use the new approach when you call /extend_youtube_session")
    
    print("\n🔧 To test the integration:")
    print("  1. Run: python test_chrome_profile.py")
    print("  2. Start your server: python server.py")
    print("  3. Call the endpoint: curl -X POST http://localhost:5000/extend_youtube_session")
    
    print("\n📊 Benefits of Chrome Profile Approach:")
    print("  ✅ Uses existing authenticated session from tldv")
    print("  ✅ No need to manually upload cookies")
    print("  ✅ More reliable session refresh")
    print("  ✅ Automatic fallback to cookie method")
    print("  ✅ Better compatibility with yt-dlp")

def main():
    """Main integration setup"""
    print("🚀 Chrome Profile Integration Setup")
    print("=" * 40)
    
    # Step 1: Setup Chrome profile integration
    if not setup_chrome_profile_integration():
        print("\n❌ Chrome profile integration setup failed")
        return False
    
    # Step 2: Create backup profile
    if not create_backup_profile():
        print("\n❌ Backup profile creation failed")
        return False
    
    # Step 3: Show integration instructions
    update_server_integration()
    
    print("\n🎉 Chrome Profile Integration Setup Complete!")
    print("\n🧪 Next Steps:")
    print("  1. Run 'python test_chrome_profile.py' to test the setup")
    print("  2. Start your server with 'python server.py'")
    print("  3. Test the endpoint with your client or curl")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        print("\n❌ Setup failed. Please check the errors above.")
        exit(1)
    else:
        print("\n✅ Setup completed successfully!")