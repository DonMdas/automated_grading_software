#!/usr/bin/env python3
"""
Configuration script to update BASE_URL and related URLs dynamically.
This script helps set up the application for different environments (dev, staging, production).
"""

import os
import re
from pathlib import Path

def update_env_file(env_file_path, base_url):
    """Update the BASE_URL in an environment file."""
    if not os.path.exists(env_file_path):
        print(f"⚠️  {env_file_path} not found, skipping...")
        return
    
    with open(env_file_path, 'r') as f:
        content = f.read()
    
    # Update BASE_URL only - keep Google OAuth redirect URI as is
    content = re.sub(r'BASE_URL=.*', f'BASE_URL={base_url}', content)
    
    with open(env_file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Updated {env_file_path}")

def configure_for_environment(environment):
    """Configure URLs for different environments."""
    base_urls = {
        'development': 'http://localhost:8000',
        'staging': 'https://staging.your-domain.com',
        'production': 'https://your-domain.com'
    }
    
    if environment not in base_urls:
        print(f"❌ Unknown environment: {environment}")
        print(f"Available environments: {', '.join(base_urls.keys())}")
        return
    
    base_url = base_urls[environment]
    
    print(f"🔧 Configuring for {environment} environment...")
    print(f"📍 Base URL: {base_url}")
    
    # Update .env files
    update_env_file('.env', base_url)
    update_env_file('.env.example', '${BASE_URL}')  # Keep template format for example
    update_env_file('backupenv.txt', '${BASE_URL}')  # Keep template format for backup
    
    print(f"\n✅ Configuration complete for {environment}!")
    print(f"🌐 Application will be available at: {base_url}")
    print(f"⚠️  Note: Google OAuth redirect URI remains unchanged")

def configure_custom_url(custom_url):
    """Configure with a custom URL."""
    print(f"🔧 Configuring with custom URL: {custom_url}")
    
    update_env_file('.env', custom_url)
    
    print(f"\n✅ Configuration complete!")
    print(f"🌐 Application will be available at: {custom_url}")
    print(f"⚠️  Note: Google OAuth redirect URI remains unchanged")

def main():
    import sys
    
    if len(sys.argv) < 2:
        print("📖 Usage:")
        print("  python configure_url.py <environment>")
        print("  python configure_url.py custom <url>")
        print("")
        print("🌍 Available environments:")
        print("  development  - http://localhost:8000")
        print("  staging      - https://staging.your-domain.com")
        print("  production   - https://your-domain.com")
        print("")
        print("🔧 Custom URL example:")
        print("  python configure_url.py custom https://myapp.mydomain.com")
        return
    
    if sys.argv[1] == 'custom':
        if len(sys.argv) < 3:
            print("❌ Please provide a custom URL")
            print("Example: python configure_url.py custom https://myapp.mydomain.com")
            return
        configure_custom_url(sys.argv[2])
    else:
        configure_for_environment(sys.argv[1])

if __name__ == "__main__":
    main()
