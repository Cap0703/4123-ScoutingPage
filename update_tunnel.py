# update_tunnel.py
import requests
import subprocess
import json
import os
from datetime import datetime
import sys

def get_tunnel_url():
    """Get the current tunnel URL from Cloudflare"""
    try:
        result = subprocess.run(['cloudflared', 'tunnel', 'list'], 
                              capture_output=True, text=True, timeout=30)
        lines = result.stdout.split('\n')
        for line in lines:
            if 'scouting-tunnel' in line:
                parts = line.split()
                if len(parts) >= 3:
                    return parts[2]  # This is the tunnel URL
    except Exception as e:
        print(f"Error getting tunnel URL: {e}")
    return None

def update_github_tunnel_url(url):
    """Update the GitHub repository with the current tunnel URL"""
    # Create a simple HTML file that redirects to your tunnel
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="0; url=https://{url}" />
    <title>Redirecting to Scouting App</title>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            text-align: center; 
            padding: 50px; 
            background-color: #0b233f;
            color: white;
        }}
        a {{ color: #d4af37; }}
    </style>
</head>
<body>
    <h1>FRC Scouting App</h1>
    <p>Redirecting to <a href="https://{url}">Scouting App</a></p>
    <p>If you are not redirected automatically, click the link above.</p>
</body>
</html>"""
    
    # Write to a file
    with open('tunnel_redirect.html', 'w') as f:
        f.write(html_content)
    
    # Also create a simple JSON file with the URL for API access
    with open('tunnel_url.json', 'w') as f:
        json.dump({'tunnel_url': f'https://{url}'}, f)
    
    print("Tunnel URL files updated.")
    
    # Try to push to GitHub if git is configured
    try:
        subprocess.run(['git', 'add', 'tunnel_redirect.html', 'tunnel_url.json'], check=True)
        subprocess.run(['git', 'commit', '-m', f'Update tunnel URL: {url}'], check=True)
        subprocess.run(['git', 'push'], check=True)
        print("Changes pushed to GitHub successfully.")
    except subprocess.CalledProcessError:
        print("Git operations failed. Please manually commit and push the changes.")
    except FileNotFoundError:
        print("Git not found. Please manually commit and push the changes.")

if __name__ == "__main__":
    tunnel_url = get_tunnel_url()
    if tunnel_url:
        print(f"Current tunnel URL: {tunnel_url}")
        update_github_tunnel_url(tunnel_url)
    else:
        print("Could not retrieve tunnel URL. Is the Cloudflare tunnel running?")
        sys.exit(1)