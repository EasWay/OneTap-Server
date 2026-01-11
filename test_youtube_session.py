#!/usr/bin/env python3
"""
Test script for YouTube session extension functionality
"""

import requests
import json
import sys
import os

def test_server_endpoints(base_url="https://onetap-225t.onrender.com"):
    """Test all YouTube session related endpoints"""
    
    print(f"🧪 Testing YouTube Session Extension on {base_url}")
    print("=" * 60)
    
    # Test 1: Check server status
    print("1️⃣ Testing server status...")
    try:
        response = requests.get(f"{base_url}/")
        print(f"   ✅ Server Status: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"   ❌ Server unreachable: {e}")
        return
    
    # Test 2: Validate cookies if they exist
    print("\n2️⃣ Validating uploaded cookies...")
    try:
        response = requests.get(f"{base_url}/validate_cookies")
        if response.status_code == 200:
            validation = response.json()
            print(f"   📊 Cookie Count: {validation['cookie_count']}")
            print(f"   🌐 Google Domains: {len(validation['google_domains'])}")
            print(f"   🔐 Auth Cookies Found: {validation['auth_cookies_found']}")
            print(f"   ⚠️ Auth Cookies Missing: {validation['auth_cookies_missing']}")
            print(f"   🔒 __Host- Cookies: {validation['host_cookies_count']}")
            print(f"   🛡️ __Secure- Cookies: {validation['secure_cookies_count']}")
            print(f"   📈 Status: {validation['validation_status']}")
        elif response.status_code == 404:
            print(f"   📝 No Google cookies uploaded yet")
        else:
            print(f"   ⚠️ Validation failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Validation check failed: {e}")
    
    # Test 3: Check YouTube session status
    print("\n3️⃣ Checking YouTube session status...")
    try:
        response = requests.get(f"{base_url}/youtube_session_status")
        if response.status_code == 200:
            status = response.json()
            print(f"   🔄 Scheduler Running: {status.get('scheduler_running', 'Unknown')}")
            print(f"   🍪 Google Cookies: {status['google_cookies_uploaded']} ({status.get('google_cookies_size_bytes', 0)} bytes)")
            print(f"   ⏰ Last Extension: {status['last_extension'] or 'Never'}")
            print(f"   ⏳ Next Extension: {status['next_scheduled_extension'] or 'Not scheduled'}")
            if status.get('minutes_until_next'):
                print(f"   ⏱️ Minutes Until Next: {status['minutes_until_next']}")
        else:
            print(f"   ⚠️ Status check failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Status check failed: {e}")
    
    # Test 4: Try manual extension
    print("\n4️⃣ Testing manual session extension...")
    try:
        response = requests.post(f"{base_url}/extend_youtube_session", timeout=180)  # 3 minute timeout
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Extension successful!")
            print(f"   📅 Timestamp: {result.get('timestamp', 'Not provided')}")
        elif response.status_code == 400:
            result = response.json()
            print(f"   ⚠️ Expected failure (no cookies): {result['error']}")
        else:
            print(f"   ❌ Extension failed: {response.status_code}")
            try:
                error = response.json()
                print(f"   Error details: {error}")
            except:
                print(f"   Raw response: {response.text}")
    except requests.exceptions.Timeout:
        print(f"   ⏰ Request timed out (this may be normal for first run)")
    except Exception as e:
        print(f"   ❌ Extension test failed: {e}")
    
    print("\n" + "=" * 60)
    print("🏁 Test completed!")
    
    # Instructions
    print("\n📋 Next Steps:")
    print("1. If Google cookies show 0 bytes, upload your cookies:")
    print(f"   curl -X POST -F 'file=@your_cookies.txt' {base_url}/update_google_cookies")
    print("2. Validate your cookies:")
    print(f"   curl {base_url}/validate_cookies")
    print("3. Test manual extension (may take 1-2 minutes):")
    print(f"   curl -X POST {base_url}/extend_youtube_session")
    print("4. Monitor status:")
    print(f"   curl {base_url}/youtube_session_status")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
        test_server_endpoints(base_url)
    else:
        test_server_endpoints()