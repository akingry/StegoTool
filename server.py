"""
KGBCREST Backend Server
Kingry Graphical Book Cipher Compression Resistant Encrypted Steganography Tool

Handles all encoding/decoding computation in Python.
The HTML frontend just sends requests to this server.
Source text is loaded automatically from source_text.txt on startup.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import base64
import io
import os
import tempfile
from urllib.parse import parse_qs, urlparse
from PIL import Image

from book_cipher import encode_image, decode_image, BookCipher

# Settings
STRENGTH = 150
RS_SYMBOLS = 64
REPETITION = 7

# Source text path (same directory as server)
SOURCE_TEXT_FILE = os.path.join(os.path.dirname(__file__), 'source_text.txt')

# Global cipher instance (loaded on startup)
cipher = None


def load_source_text():
    """Load source text on server startup."""
    global cipher
    
    if not os.path.exists(SOURCE_TEXT_FILE):
        print(f"ERROR: source_text.txt not found at {SOURCE_TEXT_FILE}")
        print("Please create source_text.txt with your shared source text.")
        return False
    
    try:
        cipher = BookCipher(SOURCE_TEXT_FILE)
        print(f"✓ Loaded source text: {len(cipher.text):,} chars, {len(cipher.char_positions)} unique")
        return True
    except Exception as e:
        print(f"ERROR loading source text: {e}")
        return False


class KGBCRESTHandler(BaseHTTPRequestHandler):
    
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def _send_error(self, message, status=400):
        self._send_json({'error': message}, status)
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """Serve static files"""
        path = urlparse(self.path).path
        
        if path == '/' or path == '/index.html':
            self._serve_file('web_client.html', 'text/html')
        elif path.endswith('.js'):
            self._serve_file(path[1:], 'application/javascript')
        elif path.endswith('.css'):
            self._serve_file(path[1:], 'text/css')
        elif path == '/api/status':
            self._send_json({
                'status': 'ok', 
                'version': '1.0',
                'sourceLoaded': cipher is not None,
                'sourceChars': len(cipher.text) if cipher else 0
            })
        else:
            self._send_error('Not found', 404)
    
    def _serve_file(self, filename, content_type):
        try:
            filepath = os.path.join(os.path.dirname(__file__), filename)
            with open(filepath, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self._send_error('File not found', 404)
    
    def do_POST(self):
        """Handle API requests"""
        path = urlparse(self.path).path
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_error('Invalid JSON')
            return
        
        if path == '/api/capacity':
            self._handle_capacity(data)
        elif path == '/api/encode':
            self._handle_encode(data)
        elif path == '/api/decode':
            self._handle_decode(data)
        else:
            self._send_error('Unknown endpoint', 404)
    
    def _handle_capacity(self, data):
        """Calculate capacity for an image"""
        try:
            width = data.get('width', 0)
            height = data.get('height', 0)
            
            if width <= 0 or height <= 0:
                self._send_error('Invalid dimensions')
                return
            
            blocks_w = width // 8
            blocks_h = height // 8
            total_blocks = blocks_w * blocks_h
            
            available_bits = total_blocks - 24
            available_bytes = available_bits // (8 * REPETITION)
            usable_bytes = max(0, available_bytes - RS_SYMBOLS)
            
            self._send_json({
                'ok': True,
                'blocks': total_blocks,
                'maxChars': usable_bytes
            })
        except Exception as e:
            self._send_error(str(e))
    
    def _handle_encode(self, data):
        """Encode a message into an image"""
        try:
            if cipher is None:
                self._send_error('Source text not loaded. Check source_text.txt exists.')
                return
            
            message = data.get('message', '')
            image_data = data.get('image', '')  # Base64 encoded
            password = data.get('password', '') or None  # Optional AES-256 password
            
            if not message:
                self._send_error('No message provided')
                return
            
            if not image_data:
                self._send_error('No image provided')
                return
            
            # Decode base64 image
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            
            image_bytes = base64.b64decode(image_data)
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                f.write(image_bytes)
                input_path = f.name
            
            output_path = input_path.replace('.png', '_encoded.png')
            
            try:
                # Encode using the pre-loaded source text
                encode_image(
                    input_path, message, output_path,
                    strength=STRENGTH, rs_symbols=RS_SYMBOLS, repetition=REPETITION,
                    source_path=SOURCE_TEXT_FILE, password=password
                )
                
                # Read encoded image
                with open(output_path, 'rb') as f:
                    encoded_bytes = f.read()
                
                encoded_base64 = base64.b64encode(encoded_bytes).decode('utf-8')
                
                self._send_json({
                    'ok': True,
                    'image': f'data:image/png;base64,{encoded_base64}',
                    'messageLength': len(message)
                })
                
            finally:
                # Cleanup temp files
                for p in [input_path, output_path]:
                    if os.path.exists(p):
                        os.remove(p)
                        
        except Exception as e:
            self._send_error(str(e))
    
    def _handle_decode(self, data):
        """Decode a message from an image"""
        try:
            if cipher is None:
                self._send_error('Source text not loaded. Check source_text.txt exists.')
                return
            
            image_data = data.get('image', '')  # Base64 encoded
            password = data.get('password', '') or None  # Optional AES-256 password
            
            if not image_data:
                self._send_error('No image provided')
                return
            
            # Decode base64 image
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            
            image_bytes = base64.b64decode(image_data)
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                f.write(image_bytes)
                input_path = f.name
            
            try:
                # Decode using the pre-loaded source text
                message = decode_image(
                    input_path,
                    strength=STRENGTH, rs_symbols=RS_SYMBOLS, repetition=REPETITION,
                    source_path=SOURCE_TEXT_FILE, password=password
                )
                
                self._send_json({
                    'ok': True,
                    'message': message,
                    'length': len(message)
                })
                
            finally:
                # Cleanup temp file
                if os.path.exists(input_path):
                    os.remove(input_path)
                        
        except Exception as e:
            self._send_error(str(e))
    
    def log_message(self, format, *args):
        """Custom log format"""
        print(f"[KGBCREST] {args[0]}")


def run_server(port=8080):
    # Load source text on startup
    if not load_source_text():
        print("\nServer starting anyway, but encode/decode will fail without source_text.txt")
    
    # Use 0.0.0.0 to accept external connections (for cloud hosting)
    host = '0.0.0.0'
    server = HTTPServer((host, port), KGBCRESTHandler)
    print(f"\nKGBCREST server running on port {port}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == '__main__':
    import sys
    # Check for PORT environment variable (Railway, Render, etc.)
    port = int(os.environ.get('PORT', sys.argv[1] if len(sys.argv) > 1 else 8080))
    run_server(port)
