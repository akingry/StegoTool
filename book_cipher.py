"""
Book Cipher Steganography with Error Correction

Encodes messages as relative character positions in a shared source text (book).
Both sender and receiver must have the same source text to communicate.

The cipher finds each character's position in the book and records relative
jumps (forward or backward, whichever is shorter). These positions are then
compressed and embedded in the image using DCT watermarking.

Example: "The" with T at position 325, h at 225, e at 228
         Records: [325, -100, +3] (relative positions)
"""

import re
import os
import zlib
import struct
import hashlib
import numpy as np
from PIL import Image
from pathlib import Path
from reedsolo import RSCodec, ReedSolomonError

# Default source text location
DEFAULT_SOURCE_FILE = Path(__file__).parent / "source_text.txt"
GUTENBERG_URL = "https://www.gutenberg.org/cache/epub/766/pg766.txt"  # David Copperfield


class BookCipher:
    """
    Book cipher using character positions in a shared source text.
    
    Both sender and receiver must have the same source text (book) to
    encode and decode messages. Characters are found by their position
    in the text, using relative jumps (forward or backward) for efficiency.
    """
    
    def __init__(self, source_path=None):
        """
        Initialize with a source text file.
        
        Args:
            source_path: Path to the source text file. If None, uses default
                        (downloads David Copperfield from Gutenberg if needed).
        """
        self.source_path = Path(source_path) if source_path else DEFAULT_SOURCE_FILE
        self.text = ""
        self.char_positions = {}  # char -> list of positions
        self._load_source()
    
    def _load_source(self):
        """Load and index the source text."""
        if not self.source_path.exists():
            if self.source_path == DEFAULT_SOURCE_FILE:
                print("Downloading default source text (David Copperfield)...")
                import urllib.request
                data = urllib.request.urlopen(GUTENBERG_URL).read().decode('utf-8')
                self.source_path.write_text(data, encoding='utf-8')
            else:
                raise FileNotFoundError(f"Source text not found: {self.source_path}")
        
        self.text = self.source_path.read_text(encoding='utf-8')
        
        # Build character index: char -> list of positions
        self.char_positions = {}
        for i, char in enumerate(self.text):
            if char not in self.char_positions:
                self.char_positions[char] = []
            self.char_positions[char].append(i)
        
        unique_chars = len(self.char_positions)
        print(f"Loaded source text: {len(self.text):,} characters, {unique_chars} unique chars")
    
    def encode_message(self, message):
        """
        Encode message as sequence of relative character positions.
        
        For each character in the message, finds the nearest occurrence
        in the source text (forward or backward) and records the relative
        jump distance.
        
        Args:
            message: The secret message to encode
            
        Returns:
            Compressed bytes containing the position data
        """
        if not message:
            raise ValueError("Empty message")
        
        positions = []
        current_pos = 0
        
        for i, char in enumerate(message):
            if char not in self.char_positions:
                raise ValueError(
                    f"Character '{char}' (position {i}) not found in source text. "
                    f"The source text may not contain this character."
                )
            
            # Find nearest occurrence (forward or backward)
            occurrences = self.char_positions[char]
            
            # Find the occurrence with shortest distance from current position
            best_pos = min(occurrences, key=lambda p: abs(p - current_pos))
            
            # Calculate relative jump (can be negative)
            jump = best_pos - current_pos
            positions.append(jump)
            current_pos = best_pos
        
        # Encode positions as variable-length signed integers
        encoded = self._encode_positions(positions)
        
        # Compress
        compressed = zlib.compress(encoded, level=9)
        
        print(f"Encoded {len(message)} chars: {len(encoded)} bytes -> {len(compressed)} bytes compressed")
        return compressed
    
    def decode_message(self, compressed_data):
        """
        Decode message from compressed position data.
        
        Args:
            compressed_data: Compressed bytes from encode_message
            
        Returns:
            The decoded message string
        """
        try:
            encoded = zlib.decompress(compressed_data)
        except zlib.error as e:
            raise ValueError(f"Decompression failed: {e}")
        
        positions = self._decode_positions(encoded)
        
        # Reconstruct message by following positions
        chars = []
        current_pos = 0
        
        for jump in positions:
            current_pos += jump
            if 0 <= current_pos < len(self.text):
                chars.append(self.text[current_pos])
            else:
                chars.append(f"[?{current_pos}]")
        
        return ''.join(chars)
    
    def _encode_positions(self, positions):
        """
        Encode positions as variable-length signed integers.
        
        Uses zigzag encoding for efficient storage of signed integers,
        then varint encoding for variable-length output.
        """
        result = bytearray()
        
        # Store count as 2-byte big-endian
        result.extend(struct.pack('>H', len(positions)))
        
        for pos in positions:
            # Zigzag encoding: map signed to unsigned
            # 0 -> 0, -1 -> 1, 1 -> 2, -2 -> 3, 2 -> 4, ...
            if pos >= 0:
                zigzag = pos * 2
            else:
                zigzag = (-pos) * 2 - 1
            
            # Varint encoding
            while zigzag >= 0x80:
                result.append((zigzag & 0x7F) | 0x80)
                zigzag >>= 7
            result.append(zigzag)
        
        return bytes(result)
    
    def _decode_positions(self, data):
        """Decode variable-length signed integers."""
        positions = []
        idx = 0
        
        # Read count
        count = struct.unpack('>H', data[idx:idx+2])[0]
        idx += 2
        
        for _ in range(count):
            # Varint decoding
            zigzag = 0
            shift = 0
            
            while True:
                if idx >= len(data):
                    raise ValueError("Unexpected end of data")
                byte = data[idx]
                idx += 1
                zigzag |= (byte & 0x7F) << shift
                if byte < 0x80:
                    break
                shift += 7
            
            # Zigzag decoding: unsigned to signed
            if zigzag & 1:
                pos = -((zigzag + 1) >> 1)
            else:
                pos = zigzag >> 1
            
            positions.append(pos)
        
        return positions


# Alias for backward compatibility
MessageEncoder = BookCipher


class ErrorCorrection:
    """
    Reed-Solomon error correction + repetition coding for robustness.
    """
    
    def __init__(self, rs_symbols=32, repetition=3):
        """
        rs_symbols: Number of Reed-Solomon parity symbols (more = more robust)
        repetition: How many times to repeat each bit (odd number for majority vote)
        """
        self.rs = RSCodec(rs_symbols)
        self.rs_symbols = rs_symbols
        self.repetition = repetition
    
    def encode(self, data):
        """
        Apply Reed-Solomon encoding, then repetition coding.
        """
        # 1. Reed-Solomon encoding (adds parity bytes)
        rs_encoded = bytes(self.rs.encode(data))
        print(f"  RS encoded: {len(data)} -> {len(rs_encoded)} bytes (+{self.rs_symbols} parity)")
        
        # 2. Repetition coding (repeat each bit)
        bits = self._bytes_to_bits(rs_encoded)
        repeated_bits = []
        for bit in bits:
            repeated_bits.extend([bit] * self.repetition)
        
        print(f"  Repetition: {len(bits)} -> {len(repeated_bits)} bits (x{self.repetition})")
        
        return repeated_bits
    
    def decode(self, repeated_bits):
        """
        Majority vote on repetition coding, then Reed-Solomon decoding.
        """
        # 1. Majority vote to recover original bits
        bits = []
        for i in range(0, len(repeated_bits), self.repetition):
            chunk = repeated_bits[i:i + self.repetition]
            ones = sum(chunk)
            zeros = len(chunk) - ones
            bits.append(1 if ones > zeros else 0)
        
        # 2. Convert bits to bytes
        rs_encoded = self._bits_to_bytes(bits)
        
        # 3. Reed-Solomon decoding (corrects errors)
        try:
            decoded = bytes(self.rs.decode(rs_encoded)[0])
            return decoded
        except ReedSolomonError as e:
            raise ValueError(f"Reed-Solomon decoding failed: {e}")
    
    def _bytes_to_bits(self, data):
        """Convert bytes to bit list."""
        bits = []
        for byte in data:
            for i in range(7, -1, -1):
                bits.append((byte >> i) & 1)
        return bits
    
    def _bits_to_bytes(self, bits):
        """Convert bit list to bytes."""
        # Pad to multiple of 8
        while len(bits) % 8 != 0:
            bits.append(0)
        
        result = bytearray()
        for i in range(0, len(bits), 8):
            byte = 0
            for j in range(8):
                byte = (byte << 1) | bits[i + j]
            result.append(byte)
        return bytes(result)


class RobustWatermark:
    """
    DCT-domain watermarking that survives JPEG compression.
    Embeds data in mid-frequency DCT coefficients.
    """
    
    def __init__(self, strength=50):
        self.strength = strength
        self.block_size = 8
    
    def embed(self, image_path, bits, output_path):
        """Embed bits in image using DCT watermarking."""
        img = Image.open(image_path).convert('RGB')
        pixels = np.array(img, dtype=np.float64)
        
        # Work with luminance (Y channel)
        y_channel = 0.299 * pixels[:,:,0] + 0.587 * pixels[:,:,1] + 0.114 * pixels[:,:,2]
        
        height, width = y_channel.shape
        
        # Add 24-bit length header (supports up to 16M bits)
        total_bits = len(bits)
        length_bits = [(total_bits >> (23 - i)) & 1 for i in range(24)]
        all_bits = length_bits + bits
        
        # Calculate blocks
        blocks_h = height // self.block_size
        blocks_w = width // self.block_size
        total_blocks = blocks_h * blocks_w
        
        if len(all_bits) > total_blocks:
            raise ValueError(f"Data too large: {len(all_bits)} bits, only {total_blocks} blocks available")
        
        print(f"  Embedding {len(all_bits)} bits in {total_blocks} available blocks")
        
        # Embed one bit per block
        bit_idx = 0
        for by in range(blocks_h):
            for bx in range(blocks_w):
                if bit_idx >= len(all_bits):
                    break
                
                y1 = by * self.block_size
                x1 = bx * self.block_size
                block = y_channel[y1:y1+self.block_size, x1:x1+self.block_size].copy()
                
                # Apply DCT
                dct_block = self._dct2(block)
                
                # Embed bit using quantization index modulation
                bit = all_bits[bit_idx]
                coef = dct_block[4, 3]
                
                q = self.strength
                quantized = round(coef / q) * q
                
                if bit == 1:
                    dct_block[4, 3] = quantized + q * 0.3
                else:
                    dct_block[4, 3] = quantized - q * 0.3
                
                # Apply inverse DCT
                block_new = self._idct2(dct_block)
                adjustment = block_new - block
                
                for c in range(3):
                    pixels[y1:y1+self.block_size, x1:x1+self.block_size, c] += adjustment
                
                bit_idx += 1
        
        # Clip and save
        pixels = np.clip(pixels, 0, 255).astype(np.uint8)
        result = Image.fromarray(pixels)
        
        # Determine format from extension
        ext = output_path.lower().split('.')[-1]
        if ext == 'webp':
            result.save(output_path, 'WEBP', lossless=True)
        elif ext in ('jpg', 'jpeg'):
            result.save(output_path, 'JPEG', quality=95)
        else:
            result.save(output_path, 'PNG')
        
        return result
    
    def extract(self, image_path):
        """Extract bits from watermarked image."""
        img = Image.open(image_path).convert('RGB')
        pixels = np.array(img, dtype=np.float64)
        
        y_channel = 0.299 * pixels[:,:,0] + 0.587 * pixels[:,:,1] + 0.114 * pixels[:,:,2]
        
        height, width = y_channel.shape
        blocks_h = height // self.block_size
        blocks_w = width // self.block_size
        
        # Extract all bits we might need
        bits = []
        for by in range(blocks_h):
            for bx in range(blocks_w):
                y1 = by * self.block_size
                x1 = bx * self.block_size
                block = y_channel[y1:y1+self.block_size, x1:x1+self.block_size]
                
                dct_block = self._dct2(block)
                coef = dct_block[4, 3]
                q = self.strength
                
                quantized = round(coef / q) * q
                bit = 1 if coef >= quantized else 0
                bits.append(bit)
        
        # Extract length (24-bit header)
        length = 0
        for i in range(24):
            length = (length << 1) | bits[i]
        
        if length <= 0 or length > len(bits) - 24:
            raise ValueError(f"Invalid length header: {length}")
        
        # Return data bits
        return bits[24:24 + length]
    
    def _dct2(self, block):
        """2D DCT."""
        from scipy.fftpack import dct
        return dct(dct(block.T, norm='ortho').T, norm='ortho')
    
    def _idct2(self, block):
        """2D inverse DCT."""
        from scipy.fftpack import idct
        return idct(idct(block.T, norm='ortho').T, norm='ortho')


def encode_image(image_path, message, output_path, strength=50, rs_symbols=32, repetition=3, source_path=None):
    """
    Encode a message into an image using book cipher + error correction + DCT watermarking.
    
    Args:
        image_path: Path to source image
        message: Secret message to hide
        output_path: Path for output image
        strength: DCT embedding strength (default 50, use 150 for JPEG q60 survival)
        rs_symbols: Reed-Solomon parity symbols (default 32, use 64 for max robustness)
        repetition: Bit repetition count (default 3, use 7 for max robustness)
        source_path: Path to source text file (book). If None, uses default.
    """
    print(f"Encoding: '{message[:50]}{'...' if len(message) > 50 else ''}'")
    
    # 1. Book cipher: encode as relative character positions
    cipher = BookCipher(source_path)
    compressed = cipher.encode_message(message)
    
    # 2. Error correction: add RS parity + repetition
    print("Adding error correction...")
    ec = ErrorCorrection(rs_symbols=rs_symbols, repetition=repetition)
    protected_bits = ec.encode(compressed)
    
    # 3. Embed in image
    print("Embedding in image...")
    watermark = RobustWatermark(strength=strength)
    watermark.embed(image_path, protected_bits, output_path)
    
    print(f"\n✓ Saved to: {output_path}")
    print(f"  Message: {len(message)} chars")
    print(f"  Compressed: {len(compressed)} bytes")
    print(f"  With EC: {len(protected_bits)} bits")
    
    return True


def decode_image(image_path, strength=50, rs_symbols=32, repetition=3, source_path=None):
    """
    Decode a message from a watermarked image.
    
    Args:
        image_path: Path to encoded image
        strength: DCT embedding strength (must match encoding)
        rs_symbols: Reed-Solomon parity symbols (must match encoding)
        repetition: Bit repetition count (must match encoding)
        source_path: Path to source text file (book). Must be same as encoding.
    """
    print(f"Decoding: {image_path}")
    
    # 1. Extract watermark bits
    watermark = RobustWatermark(strength=strength)
    protected_bits = watermark.extract(image_path)
    print(f"  Extracted {len(protected_bits)} bits")
    
    # 2. Remove error correction
    ec = ErrorCorrection(rs_symbols=rs_symbols, repetition=repetition)
    compressed = ec.decode(protected_bits)
    print(f"  After EC: {len(compressed)} bytes")
    
    # 3. Book cipher: decode relative positions to message
    cipher = BookCipher(source_path)
    message = cipher.decode_message(compressed)
    
    return message


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Book Cipher Steganography with Error Correction")
        print("=" * 50)
        print()
        print("Usage:")
        print("  Encode: python book_cipher.py encode <image> <message> [output]")
        print("  Decode: python book_cipher.py decode <image>")
        print("  Test:   python book_cipher.py test <image> <message>")
        print()
        print("Example:")
        print("  python book_cipher.py encode photo.png 'Meet me at noon' secret.png")
        print("  python book_cipher.py decode secret.png")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    if mode == 'encode':
        if len(sys.argv) < 4:
            print("Usage: python book_cipher.py encode <image> <message> [output]")
            sys.exit(1)
        
        image = sys.argv[2]
        message = sys.argv[3]
        output = sys.argv[4] if len(sys.argv) > 4 else 'encoded.png'
        
        encode_image(image, message, output)
        
    elif mode == 'decode':
        if len(sys.argv) < 3:
            print("Usage: python book_cipher.py decode <image>")
            sys.exit(1)
        
        image = sys.argv[2]
        message = decode_image(image)
        print(f"\n✓ Decoded message: {message}")
    
    elif mode == 'test':
        if len(sys.argv) < 4:
            print("Usage: python book_cipher.py test <image> <message>")
            sys.exit(1)
        
        image = sys.argv[2]
        message = sys.argv[3]
        
        print("=" * 50)
        print("JPEG SURVIVAL TEST")
        print("=" * 50)
        
        # Encode
        encode_image(image, message, 'test_encoded.png')
        
        # Test various JPEG quality levels
        img = Image.open('test_encoded.png')
        
        for quality in [90, 85, 80, 75, 70, 65, 60]:
            jpg_path = f'test_q{quality}.jpg'
            img.save(jpg_path, 'JPEG', quality=quality)
            
            try:
                decoded = decode_image(jpg_path)
                status = "✓" if decoded.lower() == message.lower() else f"≈ ({decoded})"
            except Exception as e:
                status = f"✗ {str(e)[:30]}"
            
            print(f"  Quality {quality}: {status}")
    
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
