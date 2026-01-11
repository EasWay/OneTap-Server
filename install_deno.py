#!/usr/bin/env python3
"""
Install Deno JavaScript runtime for Render deployment
"""
import os
import subprocess
import sys
import urllib.request
import zipfile
import stat

def install_deno():
    """Install Deno if not already present"""
    
    # Check if Deno is already available
    try:
        result = subprocess.run(['deno', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Deno already installed: {result.stdout.split()[1]}")
            return True
    except FileNotFoundError:
        pass
    
    print("🦕 Installing Deno JavaScript runtime...")
    
    # Determine installation directory
    if os.path.exists("/opt/render"):
        # Render environment
        install_dir = "/opt/render/.deno"
    else:
        # Local or other environment
        install_dir = os.path.expanduser("~/.deno")
    
    bin_dir = os.path.join(install_dir, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    
    # Download and install Deno
    try:
        # Use the install script method
        install_script_url = "https://deno.land/x/install/install.sh"
        
        # Set environment variables for the install script
        env = os.environ.copy()
        env['DENO_INSTALL'] = install_dir
        
        # Download and run install script
        result = subprocess.run([
            'curl', '-fsSL', install_script_url
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            # Run the install script
            install_result = subprocess.run([
                'sh', '-c', result.stdout
            ], env=env, capture_output=True, text=True)
            
            if install_result.returncode == 0:
                # Add to PATH
                deno_bin = os.path.join(bin_dir, 'deno')
                if os.path.exists(deno_bin):
                    # Make executable
                    os.chmod(deno_bin, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
                    
                    # Update PATH
                    current_path = os.environ.get('PATH', '')
                    if bin_dir not in current_path:
                        os.environ['PATH'] = f"{bin_dir}:{current_path}"
                    
                    print(f"✅ Deno installed successfully at {deno_bin}")
                    return True
        
        print("❌ Failed to install Deno via install script")
        return False
        
    except Exception as e:
        print(f"❌ Error installing Deno: {e}")
        return False

if __name__ == "__main__":
    success = install_deno()
    sys.exit(0 if success else 1)