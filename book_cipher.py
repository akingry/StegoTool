"""
Character-Based Steganography with Error Correction

Encodes messages as compressed character data with heavy error correction,
then embeds in image using DCT-domain watermarking that survives JPEG compression.
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


class MessageEncoder:
    """Simple character-based message encoding with compression."""
    
    def __init__(self):
        pass
    
    def encode_message(self, message):
        """
        Encode message as compressed UTF-8 bytes.
        Returns compressed bytes.
        """
        if not message:
            raise ValueError("Empty message")
        
        # Encode as UTF-8
        message_bytes = message.encode('utf-8')
        
        # Compress
        compressed = zlib.compress(message_bytes, level=9)
        
        print(f"Encoded {len(message)} chars: {len(message_bytes)} bytes -> {len(compressed)} bytes compressed")
        return compressed
    
    def decode_message(self, compressed_data):
        """Decode message from compressed data."""
        try:
            decompressed = zlib.decompress(compressed_data)
        except zlib.error as e:
            raise ValueError(f"Decompression failed: {e}")
        
        return decompressed.decode('utf-8')


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


def encode_image(image_path, message, output_path, strength=50, rs_symbols=32, repetition=3):
    """
    Encode a message into an image using compression + error correction + DCT watermarking.
    """
    print(f"Encoding: '{message[:50]}{'...' if len(message) > 50 else ''}'")
    
    # 1. Compress message
    encoder = MessageEncoder()
    compressed = encoder.encode_message(message)
    
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


def decode_image(image_path, strength=50, rs_symbols=32, repetition=3):
    """
    Decode a message from a watermarked image.
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
    
    # 3. Decompress message
    encoder = MessageEncoder()
    message = encoder.decode_message(compressed)
    
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
