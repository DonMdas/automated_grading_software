#!/usr/bin/env python3
"""
Simple HTTP server for testing analytics dashboard
"""
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler

class AnalyticsHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.path = '/analytics.html'
        elif self.path == '/analytics':
            self.path = '/analytics.html'
        
        # Change to templates directory
        os.chdir('/home/don/Documents/Internship/aistudioversion/templates')
        return SimpleHTTPRequestHandler.do_GET(self)

def run_server(port=8080):
    server_address = ('', port)
    httpd = HTTPServer(server_address, AnalyticsHandler)
    print(f"Starting server at http://localhost:{port}")
    print("Navigate to http://localhost:8080 to view the analytics dashboard")
    httpd.serve_forever()

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)
