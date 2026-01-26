#!/usr/bin/env python3
"""
Device Fingerprint Manager
Generates realistic Android device fingerprints for TikTok mobile API emulation
"""

import random
import hashlib
import uuid
import time
from tiktok_config import TIKTOK_CONFIG

class DeviceFingerprintManager:
    """
    Manages device fingerprinting for TikTok mobile API emulation
    Generates consistent, realistic device identifiers
    """
    
    def __init__(self, persistent_device_id=None):
        # Use persistent device ID if provided, otherwise generate new one
        if persistent_device_id:
            self.device_id = persistent_device_id
            # Seed random with device ID for consistent fingerprints
            random.seed(int(self.device_id[-10:]))
        else:
            self.device_id = self._generate_device_id()
        
        # Generate consistent device profile
        self.device_profile = self._generate_device_profile()
        self.carrier_info = self._select_carrier()
        self.region_info = self._select_region()
        
        # Generate derived identifiers
        self.install_id = self._generate_install_id()
        self.openudid = self._generate_openudid()
        self.clientudid = self.openudid  # Usually same as openudid
        
        # Reset random seed to avoid affecting other random operations
        random.seed()
    
    def _generate_device_id(self):
        """Generate realistic TikTok device ID (19 digits starting with 7)"""
        return str(random.randint(7000000000000000000, 7999999999999999999))
    
    def _generate_install_id(self):
        """Generate realistic install ID (19 digits starting with 7)"""
        # Base on device ID for consistency
        base = int(self.device_id)
        install_id = base + random.randint(1000000, 9999999)
        return str(install_id)[:19]
    
    def _generate_openudid(self):
        """Generate realistic OpenUDID (32 character hex string)"""
        # Base on device ID for consistency
        seed_data = f"{self.device_id}_{int(time.time() // 86400)}"  # Changes daily
        return hashlib.md5(seed_data.encode()).hexdigest()
    
    def _generate_device_profile(self):
        """Select realistic device profile"""
        return random.choice(TIKTOK_CONFIG["DEVICE_MODELS"])
    
    def _select_carrier(self):
        """Select realistic carrier information"""
        return random.choice(TIKTOK_CONFIG["CARRIERS"])
    
    def _select_region(self):
        """Select realistic region information"""
        return random.choice(TIKTOK_CONFIG["REGIONS"])
    
    def get_user_agent(self):
        """Generate realistic User-Agent string"""
        device = self.device_profile
        
        if "iPhone" in device["model"]:
            # iOS User-Agent
            return (
                f"TikTok/{TIKTOK_CONFIG['APP_VERSION']} "
                f"(iPhone; iOS {device['android_version']}; "
                f"Scale/3.00)"
            )
        else:
            # Android User-Agent
            return (
                f"com.zhiliaoapp.musically/{TIKTOK_CONFIG['APP_VERSION']} "
                f"(Linux; U; Android {device['android_version']}; "
                f"{device['model']} Build/TP1A.220624.014; wv) "
                f"AppleWebKit/537.36 (KHTML, like Gecko) "
                f"Version/4.0 Chrome/119.0.6045.193 Mobile Safari/537.36"
            )
    
    def get_device_params(self):
        """Get device-specific parameters for API requests"""
        device = self.device_profile
        carrier = self.carrier_info
        region = self.region_info
        
        return {
            # Device identification
            "device_id": self.device_id,
            "iid": self.install_id,
            "openudid": self.openudid,
            "uuid": self.openudid,
            "clientudid": self.clientudid,
            
            # Device details
            "device_brand": device["brand"],
            "device_type": device["model"],
            "device_platform": "android" if "iPhone" not in device["model"] else "ios",
            "os": "android" if "iPhone" not in device["model"] else "ios",
            "os_version": device["android_version"],
            "os_api": device["sdk_version"],
            "resolution": device["resolution"],
            "dpi": device["dpi"],
            
            # Network and location
            "carrier_region": region["code"],
            "sys_region": region["code"],
            "region": region["code"],
            "timezone_name": region["timezone"],
            "timezone_offset": region["offset"],
            "mcc_mnc": carrier["mcc_mnc"],
            "ac": "wifi",  # Connection type
            
            # Additional fingerprinting
            "build_number": TIKTOK_CONFIG["BUILD_NUMBER"],
            "channel": TIKTOK_CONFIG["CHANNEL"],
            "is_my_cn": 0,  # Not China region
            "ssmix": "a",
            "as": self._generate_as_param(),
            "cp": self._generate_cp_param()
        }
    
    def _generate_as_param(self):
        """Generate 'as' parameter (anti-spam signature)"""
        # Simplified implementation - real version is more complex
        base_data = f"{self.device_id}{self.install_id}"
        return hashlib.md5(base_data.encode()).hexdigest()[:10]
    
    def _generate_cp_param(self):
        """Generate 'cp' parameter (client proof)"""
        # Simplified implementation - real version is more complex
        base_data = f"{self.openudid}{int(time.time() // 3600)}"  # Changes hourly
        return hashlib.md5(base_data.encode()).hexdigest()[:12]
    
    def get_headers(self, params_string, request_data=None):
        """Generate HTTP headers with device fingerprinting"""
        headers = {
            "User-Agent": self.get_user_agent(),
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            
            # TikTok-specific headers
            "X-SS-Stub": self._generate_x_ss_stub(params_string),
            "X-Gorgon": self._generate_x_gorgon(params_string, request_data),
            "X-Khronos": str(int(time.time())),
            "X-Pods": "",
            
            # Additional fingerprinting headers
            "X-TT-Token": self._generate_tt_token(),
            "X-Ladon": self._generate_ladon_header(),
        }
        
        return headers
    
    def _generate_x_ss_stub(self, params_string):
        """Generate X-SS-Stub header (simplified implementation)"""
        # Real implementation requires reverse engineering TikTok's signature algorithm
        stub_data = f"{params_string}{self.device_id}{int(time.time())}"
        return hashlib.md5(stub_data.encode()).hexdigest()[:32]
    
    def _generate_x_gorgon(self, params_string, request_data=None):
        """Generate X-Gorgon header (simplified implementation)"""
        # Real implementation is much more complex
        gorgon_input = params_string
        if request_data:
            gorgon_input += str(request_data)
        gorgon_input += str(int(time.time()))
        gorgon_input += self.device_id
        
        return hashlib.sha256(gorgon_input.encode()).hexdigest()[:40]
    
    def _generate_tt_token(self):
        """Generate TT-Token header"""
        # Simplified token generation
        token_data = f"{self.device_id}{self.install_id}{int(time.time() // 300)}"  # Changes every 5 minutes
        return hashlib.sha1(token_data.encode()).hexdigest()[:20]
    
    def _generate_ladon_header(self):
        """Generate X-Ladon header (anti-bot protection)"""
        # Simplified implementation
        ladon_data = f"{self.openudid}{int(time.time() // 600)}"  # Changes every 10 minutes
        return hashlib.md5(ladon_data.encode()).hexdigest()[:16]
    
    def get_fingerprint_summary(self):
        """Get summary of device fingerprint for logging"""
        device = self.device_profile
        return {
            "device_id": self.device_id[-8:] + "...",  # Only show last 8 digits
            "model": device["model"],
            "brand": device["brand"],
            "android_version": device["android_version"],
            "region": self.region_info["code"],
            "carrier": self.carrier_info["carrier"]
        }
    
    @classmethod
    def create_persistent_device(cls, user_identifier):
        """Create device fingerprint that's consistent for a specific user"""
        # Generate device ID based on user identifier
        device_seed = hashlib.sha256(user_identifier.encode()).hexdigest()
        device_id = "7" + device_seed[:18]  # 19 digits starting with 7
        
        return cls(persistent_device_id=device_id)