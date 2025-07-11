#!/usr/bin/env python3
"""
Simple callback proxy server for Google OAuth
Runs on port 53981 to match the redirect URI in credentials
Forwards the callback to our main backend server
"""

import http.server
import socketserver
import urllib.parse
import urllib.request
import json
from urllib.parse import urlparse, parse_qs

class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse the URL and query parameters
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)
        
        if 'code' in query_params and 'state' in query_params:
            # This is a Google OAuth callback
            code = query_params['code'][0]
            state = query_params['state'][0] if 'state' in query_params else None
            
            # Forward to our main backend
            backend_url = f"http://localhost:8001/api/auth/google/callback?code={code}"
            if state:
                backend_url += f"&state={state}"
            
            try:
                # Make request to backend
                with urllib.request.urlopen(backend_url) as response:
                    if response.getcode() == 200:
                        # Success - redirect to frontend
                        self.send_response(302)
                        self.send_header('Location', 'http://localhost:3002/auth/google-success.html')
                        self.end_headers()
                    else:
                        # Error
                        self.send_response(302)
                        self.send_header('Location', 'http://localhost:3002/auth/google-error.html')
                        self.end_headers()
            except Exception as e:
                print(f"Error forwarding callback: {e}")
                self.send_response(302)
                self.send_header('Location', 'http://localhost:3002/auth/google-error.html')
                self.end_headers()
        else:
            # Default response
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Google OAuth Callback Proxy - Waiting for callback...")
    
    def log_message(self, format, *args):
        print(f"[OAuth Proxy] {format % args}")

if __name__ == "__main__":
    PORT = 53981
    
    with socketserver.TCPServer(("", PORT), CallbackHandler) as httpd:
        print(f"🔄 OAuth callback proxy running on port {PORT}")
        print(f"📡 Forwarding callbacks to backend at localhost:8001")
        httpd.serve_forever()
