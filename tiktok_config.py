#!/usr/bin/env python3
"""
TikTok Mobile API Configuration
Centralized configuration for mobile API emulation
"""

# TikTok App Constants (reverse engineered from official app)
TIKTOK_CONFIG = {
    # App identification
    "APP_VERSION": "34.1.2",
    "VERSION_CODE": "2023401020", 
    "BUILD_NUMBER": "34.1.2",
    "MANIFEST_VERSION_CODE": "2023401020",
    "APP_NAME": "musical_ly",
    "APP_ID": "1233",
    "AID": "1233",
    "CHANNEL": "googleplay",
    
    # API endpoints (multiple regions for fallback)
    "BASE_URLS": [
        "https://api16-normal-c-useast1a.tiktokv.com",
        "https://api16-core-c-useast1a.tiktokv.com",
        "https://api19-normal-c-useast1a.tiktokv.com", 
        "https://api22-normal-c-useast1a.tiktokv.com",
        "https://api16-normal-c-useast2a.tiktokv.com",
        "https://api16-normal-c-alisg.tiktokv.com",  # Singapore
        "https://api16-normal-c-maliva16.tiktokv.com"  # Alternative
    ],
    
    # Rate limiting
    "MIN_REQUEST_INTERVAL": 1.0,  # Minimum seconds between requests
    "MAX_RETRIES": 3,
    "REQUEST_TIMEOUT": 30,
    
    # Device fingerprinting
    "DEVICE_MODELS": [
        {
            "model": "SM-G998B",
            "brand": "samsung",
            "manufacturer": "samsung", 
            "device": "o1s",
            "product": "o1sxxx",
            "board": "universal2100",
            "hardware": "exynos2100",
            "android_version": "13",
            "sdk_version": "33",
            "resolution": "1440*3200",
            "dpi": 515
        },
        {
            "model": "Pixel 7 Pro", 
            "brand": "google",
            "manufacturer": "Google",
            "device": "cheetah", 
            "product": "cheetah",
            "board": "cheetah",
            "hardware": "cheetah",
            "android_version": "14",
            "sdk_version": "34",
            "resolution": "1440*3120", 
            "dpi": 512
        },
        {
            "model": "OnePlus 11",
            "brand": "OnePlus",
            "manufacturer": "OnePlus",
            "device": "PJD110",
            "product": "OnePlus11", 
            "board": "taro",
            "hardware": "qcom",
            "android_version": "13",
            "sdk_version": "33",
            "resolution": "1440*3216",
            "dpi": 525
        },
        {
            "model": "iPhone 15 Pro",
            "brand": "Apple", 
            "manufacturer": "Apple",
            "device": "iPhone16,1",
            "product": "iPhone16,1",
            "board": "iPhone16,1", 
            "hardware": "iPhone16,1",
            "android_version": "17.0",
            "sdk_version": "34",
            "resolution": "1179*2556",
            "dpi": 460
        }
    ],
    
    # Network carriers (for realistic fingerprinting)
    "CARRIERS": [
        {"mcc_mnc": "310260", "carrier": "T-Mobile", "region": "US"},
        {"mcc_mnc": "311480", "carrier": "Verizon", "region": "US"},
        {"mcc_mnc": "310410", "carrier": "AT&T", "region": "US"},
        {"mcc_mnc": "302720", "carrier": "Rogers", "region": "CA"},
        {"mcc_mnc": "234015", "carrier": "Vodafone", "region": "GB"}
    ],
    
    # Regions for geo-consistency
    "REGIONS": [
        {"code": "US", "timezone": "America/New_York", "offset": "-18000"},
        {"code": "CA", "timezone": "America/Toronto", "offset": "-18000"}, 
        {"code": "GB", "timezone": "Europe/London", "offset": "0"},
        {"code": "AU", "timezone": "Australia/Sydney", "offset": "+39600"}
    ]
}

# Signature generation keys (simplified - real keys are more complex)
SIGNATURE_KEYS = {
    "X_SS_STUB_KEY": "tiktok_stub_key_2024",
    "X_GORGON_KEY": "tiktok_gorgon_key_2024", 
    "X_KHRONOS_KEY": "tiktok_khronos_key_2024"
}

# Success rate optimization
FALLBACK_CONFIG = {
    # Try mobile API first (highest success rate)
    "PRIMARY_EXTRACTOR": "mobile_api",
    
    # Fallback chain in order of preference
    "FALLBACK_EXTRACTORS": [
        "mobile_api",
        "web_api", 
        "oembed",
        "ytdlp"
    ],
    
    # Video URL priority (no watermark > watermark)
    "URL_PRIORITY": [
        "play_addr",        # Highest quality, no watermark
        "download_addr",    # May have watermark
        "play_addr_h264",   # H264 encoded
        "play_addr_bytevc1" # ByteVC1 encoded
    ],
    
    # CDN fallback (try different CDNs if one fails)
    "CDN_FALLBACK": True,
    "MAX_CDN_RETRIES": 3
}

# Logging configuration
LOGGING_CONFIG = {
    "LOG_LEVEL": "INFO",
    "LOG_API_REQUESTS": True,
    "LOG_DEVICE_FINGERPRINTS": False,  # Set to True for debugging
    "LOG_SIGNATURES": False  # Set to True for debugging (security risk)
}