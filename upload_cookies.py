#!/usr/bin/env python3
"""
Upload social media cookies to Render server
"""

import requests
import sys
import os

def upload_cookies(server_url, cookies_file):
    """Upload cookies file to the server"""
    
    # Ensure URL has proper format
    if not server_url.startswith('http'):
        server_url = f'https://{server_url}'
    
    server_url = server_url.rstrip('/')
    upload_endpoint = f'{server_url}/upload_cookies'
    
    print(f"🚀 Uploading cookies to: {upload_endpoint}")
    
    if not os.path.exists(cookies_file):
        print(f"❌ Error: Cookie file not found: {cookies_file}")
        return False
    
    # Get file size
    file_size = os.path.getsize(cookies_file)
    print(f"📄 Cookie file size: {file_size:,} bytes")
    
    try:
        # Upload the file
        with open(cookies_file, 'rb') as f:
            files = {'file': (os.path.basename(cookies_file), f, 'text/plain')}
            
            print("⬆️ Uploading...")
            response = requests.post(upload_endpoint, files=files, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            print("\n✅ Upload successful!")
            print(f"📊 Statistics:")
            
            if 'statistics' in data:
                stats = data['statistics']
                print(f"   Total cookies: {stats.get('total', 0)}")
                print(f"   TikTok: {stats.get('tiktok', 0)}")
                print(f"   Facebook: {stats.get('facebook', 0)}")
                print(f"   Instagram: {stats.get('instagram', 0)}")
                print(f"   Twitter: {stats.get('twitter', 0)}")
            
            print(f"\n🎉 Your server is now authenticated for all platforms!")
            return True
        else:
            print(f"\n❌ Upload failed!")
            print(f"Status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Connection error: Could not connect to {server_url}")
        print("   Make sure your server is running and the URL is correct")
        return False
    except requests.exceptions.Timeout:
        print(f"\n❌ Timeout: Server took too long to respond")
        return False
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("OneTap Cookie Uploader")
    print("=" * 60)
    print()
    
    # Get server URL
    if len(sys.argv) > 1:
        server_url = sys.argv[1]
    else:
        server_url = input("Enter your Render server URL (e.g., https://your-app.onrender.com): ").strip()
    
    # Get cookies file
    if len(sys.argv) > 2:
        cookies_file = sys.argv[2]
    else:
        cookies_file = "social_cookies.txt"
    
    print()
    success = upload_cookies(server_url, cookies_file)
    
    if success:
        print("\n✅ Done! You can now download private content from all platforms.")
        sys.exit(0)
    else:
        print("\n❌ Upload failed. Please check the error messages above.")
        sys.exit(1)
