#!/usr/bin/env python3
"""
Komigrad Full Stack Server
==========================
Frontend: Static Next.js site
Backend:  Real-time Garry's Mod server queries via A2S protocol
"""

import os
import sys
import json
import socket
import struct
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs

# ============================================================
# A2S Protocol - Source Engine Server Query
# ============================================================

A2S_INFO = b'\xff\xff\xff\xffTSource Engine Query\x00'
A2S_PLAYER = b'\xff\xff\xff\xffU\xff\xff\xff\xff'
A2S_RULES = b'\xff\xff\xff\xffV\xff\xff\xff\xff'

def query_server_info(host, port, timeout=3.0):
    """Query server info using A2S_INFO packet."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.sendto(A2S_INFO, (host, port))
        data, addr = sock.recvfrom(4096)
        sock.close()
        
        if len(data) < 5:
            return None
        
        # Parse response
        # Skip header (4 bytes 0xFFFFFFFF + 1 byte type 'I')
        pos = 5
        
        # Protocol version
        protocol = data[pos]; pos += 1
        
        # Server name (null-terminated string)
        name_end = data.index(b'\x00', pos)
        name = data[pos:name_end].decode('utf-8', errors='replace')
        pos = name_end + 1
        
        # Map name
        map_end = data.index(b'\x00', pos)
        map_name = data[pos:map_end].decode('utf-8', errors='replace')
        pos = map_end + 1
        
        # Game directory
        dir_end = data.index(b'\x00', pos)
        game_dir = data[pos:dir_end].decode('utf-8', errors='replace')
        pos = dir_end + 1
        
        # Game description
        desc_end = data.index(b'\x00', pos)
        game_desc = data[pos:desc_end].decode('utf-8', errors='replace')
        pos = desc_end + 1
        
        # App ID
        app_id = struct.unpack_from('<H', data, pos)[0]; pos += 2
        
        # Players count
        players = data[pos]; pos += 1
        
        # Max players
        max_players = data[pos]; pos += 1
        
        # Bots
        bots = data[pos]; pos += 1
        
        # Server type
        server_type = chr(data[pos]); pos += 1
        
        # Environment
        environment = chr(data[pos]); pos += 1
        
        # Visibility (private/public)
        visibility = data[pos]; pos += 1
        
        # VAC
        vac = data[pos]; pos += 1
        
        return {
            'name': name,
            'map': map_name,
            'players': players,
            'max_players': max_players,
            'bots': bots,
            'game': game_desc,
            'online': True
        }
    except Exception as e:
        return {'online': False, 'error': str(e)}

def query_server_players(host, port, timeout=3.0):
    """Query player list using A2S_PLAYER packet with challenge-response."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        
        # Step 1: Send initial request with challenge -1
        sock.sendto(A2S_PLAYER, (host, port))
        data, addr = sock.recvfrom(4096)
        
        if len(data) < 5:
            sock.close()
            return []
        
        # Check if we got a challenge response (type 'A' = 0x41)
        if data[4] == 0x41 and len(data) >= 9:
            # Extract challenge number
            challenge = data[5:9]
            # Step 2: Send request with actual challenge
            player_req = b'\xff\xff\xff\xffU' + challenge
            sock.sendto(player_req, (host, port))
            data, addr = sock.recvfrom(4096)
        
        sock.close()
        
        if len(data) < 6:
            return []
        
        # Parse player list
        pos = 5  # Skip header
        num_players = data[pos]; pos += 1
        
        players = []
        for i in range(num_players):
            if pos >= len(data):
                break
            
            # Index
            pos += 1
            
            # Name (null-terminated)
            name_end = data.index(b'\x00', pos)
            name = data[pos:name_end].decode('utf-8', errors='replace')
            pos = name_end + 1
            
            # Score
            score = struct.unpack_from('<l', data, pos)[0]; pos += 4
            
            # Duration (float)
            duration = struct.unpack_from('<f', data, pos)[0]; pos += 4
            
            if name:  # Skip empty names
                players.append({
                    'name': name,
                    'score': score,
                    'time': max(0, int(duration)) if duration == duration else 0  # NaN check
                })
        
        return players
    except:
        return []

def format_time(seconds):
    """Format seconds to human-readable time."""
    try:
        seconds = float(seconds)
        if seconds < 0 or seconds != seconds:  # NaN check
            return "0:00"
        minutes = int(seconds) // 60
        secs = int(seconds) % 60
        hours = minutes // 60
        minutes = minutes % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"
    except (ValueError, TypeError):
        return "0:00"

# ============================================================
# Server Configuration
# ============================================================

SERVERS = [
    {"id": "1", "name": "KOMIGRAD RU 1", "host": "5.42.211.56", "port": 24215},
    {"id": "2", "name": "KOMIGRAD RU 2", "host": "5.42.211.56", "port": 24216},
]

# Cache for server data
server_cache = {
    'data': None,
    'last_update': 0,
    'lock': threading.Lock()
}

CACHE_TTL = 30  # seconds

def update_server_data():
    """Query all servers and update cache."""
    servers = []
    
    for srv in SERVERS:
        info = query_server_info(srv['host'], srv['port'])
        
        if info and info.get('online'):
            players = query_server_players(srv['host'], srv['port'])
            servers.append({
                'id': srv['id'],
                'name': info.get('name', srv['name']),
                'address': f"{srv['host']}:{srv['port']}",
                'map': info.get('map', '\u2014'),
                'players': info.get('players', 0),
                'maxPlayers': info.get('max_players', 0),
                'online': True,
                'playerList': players
            })
        else:
            servers.append({
                'id': srv['id'],
                'name': srv['name'],
                'address': f"{srv['host']}:{srv['port']}",
                'map': '\u2014',
                'players': 0,
                'maxPlayers': 0,
                'online': False,
                'playerList': []
            })
    
    with server_cache['lock']:
        server_cache['data'] = {'servers': servers}
        server_cache['last_update'] = time.time()
    
    return server_cache['data']

def get_server_data():
    """Get server data from cache or return default."""
    with server_cache['lock']:
        if server_cache['data'] is not None:
            # Check if cache is expired
            if (time.time() - server_cache['last_update']) > CACHE_TTL:
                # Return stale data and update in background
                threading.Thread(target=update_server_data, daemon=True).start()
            return server_cache['data']
        else:
            # No data yet, start update and return default
            threading.Thread(target=update_server_data, daemon=True).start()
            return {
                'servers': [
                    {
                        'id': srv['id'],
                        'name': srv['name'],
                        'address': f"{srv['host']}:{srv['port']}",
                        'map': '\u2014',
                        'players': 0,
                        'maxPlayers': 0,
                        'online': False,
                        'playerList': []
                    }
                    for srv in SERVERS
                ]
            }

# ============================================================
# HTTP Server
# ============================================================

class KomigradHandler(SimpleHTTPRequestHandler):
    """Handler with API support and clean URLs."""
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        if path.endswith('/') and path != '/':
            path = path[:-1]
        
        # API endpoints
        if path == '/api/server':
            return self.handle_api_server()
        
        # Static files
        if os.path.isfile(self.translate_path(path)):
            return super().do_GET()
        
        html_path = path + '.html'
        if os.path.isfile(self.translate_path(html_path)):
            self.path = html_path
            return super().do_GET()
        
        index_path = os.path.join(path, 'index.html')
        if os.path.isfile(self.translate_path(index_path)):
            self.path = index_path
            return super().do_GET()
        
        # Missing JS chunks - return empty JS
        if path.endswith('.js') and '/_next/static/chunks/' in path:
            return self.send_empty_js()
        
        return super().do_GET()
    
    def handle_api_server(self):
        """Handle /api/server - real game server queries."""
        data = get_server_data()
        response = json.dumps(data, ensure_ascii=False).encode('utf-8')
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(response)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(response)
    
    def send_empty_js(self):
        response = b'// empty chunk'
        self.send_response(200)
        self.send_header('Content-Type', 'application/javascript')
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        self.wfile.write(response)
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        super().end_headers()
    
    def log_message(self, format, *args):
        sys.stderr.write("%s - - [%s] %s\n" %
                        (self.address_string(),
                         self.log_date_time_string(),
                         format%args))

# ============================================================
# Main
# ============================================================

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
    daemon_threads = True

def main():
    port = 8080
    directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'komigrad_downloaded')
    os.chdir(directory)
    
    # Initial server query in background
    print("=" * 60)
    print("Komigrad Full Stack Server")
    print("=" * 60)
    print("\nQuerying game servers in background...")
    
    # Start background thread for initial query
    query_thread = threading.Thread(target=update_server_data, daemon=True)
    query_thread.start()
    
    print(f"\nStarting HTTP server on http://127.0.0.1:{port}")
    print(f"Serving from: {directory}")
    print(f"\nAPI Endpoints:")
    print(f"  GET /api/server  - Real-time server data")
    print(f"\nPages:")
    print(f"  http://127.0.0.1:{port}/")
    print(f"  http://127.0.0.1:{port}/docs/rules")
    print(f"  http://127.0.0.1:{port}/docs/administration")
    print(f"  http://127.0.0.1:{port}/docs/donate")
    print(f"\nCache TTL: {CACHE_TTL}s")
    print(f"Press Ctrl+C to stop")
    print("=" * 60)
    
    server = ThreadingHTTPServer(('127.0.0.1', port), KomigradHandler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\nServer stopped.")
        server.server_close()

if __name__ == '__main__':
    main()
