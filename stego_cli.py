"""
Spread Spectrum Steganography
Hides data by spreading it across the entire image using pseudo-random patterns.
More robust against compression, virtually invisible.
"""

import numpy as np
from PIL import Image
import hashlib
import sys

def text_to_bits(text):
    """Convert text to bit array."""
    bits = []
    for char in text.encode('utf-8'):
        for i in range(7, -1, -1):
            bits.append((char >> i) & 1)
    return bits

def bits_to_text(bits):
    """Convert bit array back to text."""
    chars = []
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            if i + j < len(bits):
                byte = (byte << 1) | bits[i + j]
        if byte == 0:  # Null terminator
            break
        chars.append(chr(byte))
    return ''.join(chars)

def generate_spread_pattern(key, size, num_chips):
    """Generate pseudo-random spread pattern from key."""
    np.random.seed(int(hashlib.sha256(key.encode()).hexdigest()[:8], 16))
    
    # Generate chip positions (where to embed each bit redundantly)
    positions = []
    total_pixels = size[0] * size[1]
    
    for _ in range(num_chips):
        pos = np.random.permutation(total_pixels)
        positions.append(pos)
    
    return positions

def embed_spread(image_path, message, output_path, key="secret_key", strength=3, redundancy=50):
    """
    Embed message using spread spectrum.
    
    key: Password for encoding/decoding
    strength: Pixel modification amount (1-10, higher = more robust but more visible)
    redundancy: How many pixels per bit (higher = more robust, lower capacity)
    """
    # Load image
    img = Image.open(image_path).convert('RGB')
    pixels = np.array(img, dtype=np.int16)  # int16 to avoid overflow
    height, width = pixels.shape[:2]
    
    # Prepare message with length header and null terminator
    msg_bits = text_to_bits(message + '\x00')
    
    # Add 16-bit length header
    msg_len = len(message)
    length_bits = [(msg_len >> (15-i)) & 1 for i in range(16)]
    all_bits = length_bits + msg_bits
    
    # Check capacity
    total_pixels = width * height
    pixels_needed = len(all_bits) * redundancy
    
    if pixels_needed > total_pixels:
        max_chars = (total_pixels // redundancy - 16) // 8
        raise ValueError(f"Message too long. Max ~{max_chars} characters with current settings.")
    
    print(f"Embedding {len(message)} chars ({len(all_bits)} bits) into {width}x{height} image")
    print(f"Using {pixels_needed:,} of {total_pixels:,} pixels ({100*pixels_needed/total_pixels:.1f}%)")
    
    # Generate spread pattern
    np.random.seed(int(hashlib.sha256(key.encode()).hexdigest()[:8], 16))
    
    # Embed each bit across multiple pixels
    flat_pixels = pixels.reshape(-1, 3)
    
    for bit_idx, bit in enumerate(all_bits):
        # Get random pixel indices for this bit
        chip_indices = np.random.choice(total_pixels, redundancy, replace=False)
        
        # Modify pixels: +strength for 1, -strength for 0
        modifier = strength if bit == 1 else -strength
        
        for idx in chip_indices:
            # Modify blue channel (least perceptible to human eye)
            flat_pixels[idx, 2] = np.clip(flat_pixels[idx, 2] + modifier, 0, 255)
    
    # Reshape and save
    result = flat_pixels.reshape(height, width, 3).astype(np.uint8)
    result_img = Image.fromarray(result)
    result_img.save(output_path, quality=95)
    
    print(f"✓ Saved to: {output_path}")
    print(f"✓ Key: '{key}' (needed for decoding)")
    print(f"✓ Strength: {strength}, Redundancy: {redundancy}")
    
    return result_img


def decode_spread(image_path, key="secret_key", strength=3, redundancy=50):
    """
    Decode message using spread spectrum.
    Must use same key, strength, and redundancy as encoding.
    """
    # Load image
    img = Image.open(image_path).convert('RGB')
    pixels = np.array(img, dtype=np.int16)
    height, width = pixels.shape[:2]
    total_pixels = width * height
    
    flat_pixels = pixels.reshape(-1, 3)
    
    # Reset random seed to same state
    np.random.seed(int(hashlib.sha256(key.encode()).hexdigest()[:8], 16))
    
    # First decode length (16 bits)
    length_bits = []
    for bit_idx in range(16):
        chip_indices = np.random.choice(total_pixels, redundancy, replace=False)
        
        # Sum the blue channel modifications
        total = sum(flat_pixels[idx, 2] for idx in chip_indices)
        avg = total / redundancy
        
        # Compare to what we'd expect
        # This is a simplified correlation - actual spread spectrum uses more sophisticated detection
        length_bits.append(1 if avg > 127 else 0)
    
    # Hmm, this simple approach won't work well. Let me use a better correlation method.
    # Reset and try correlation-based detection
    
    np.random.seed(int(hashlib.sha256(key.encode()).hexdigest()[:8], 16))
    
    # We need a reference to correlate against
    # For now, decode by looking at relative modifications
    
    # Read all potential bits (up to reasonable limit)
    max_bits = min(16 + 8 * 1000, total_pixels // redundancy)  # Max ~1000 chars
    
    decoded_bits = []
    
    for bit_idx in range(max_bits):
        chip_indices = np.random.choice(total_pixels, redundancy, replace=False)
        
        # Use correlation: check if pixels are consistently above or below neighbors
        votes = 0
        for idx in chip_indices:
            # Simple: check if blue channel is odd (1) or even (0) after our modification
            # This works because we add/subtract consistently
            pixel_val = flat_pixels[idx, 2]
            # Vote based on whether modification seems positive or negative
            # Compare to local average (rough estimate)
            neighbors = []
            row, col = idx // width, idx % width
            for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                nr, nc = row + dr, col + dc
                if 0 <= nr < height and 0 <= nc < width:
                    neighbors.append(flat_pixels[nr * width + nc, 2])
            if neighbors:
                local_avg = sum(neighbors) / len(neighbors)
                if pixel_val > local_avg:
                    votes += 1
                else:
                    votes -= 1
        
        decoded_bits.append(1 if votes > 0 else 0)
    
    # Extract length
    msg_len = 0
    for i in range(16):
        msg_len = (msg_len << 1) | decoded_bits[i]
    
    # Sanity check
    if msg_len > 1000 or msg_len < 0:
        print(f"Warning: Decoded length {msg_len} seems wrong. Trying to decode anyway...")
        msg_len = min(100, (len(decoded_bits) - 16) // 8)
    
    # Extract message bits
    msg_bits = decoded_bits[16:16 + msg_len * 8 + 8]  # +8 for null terminator
    
    # Convert to text
    message = bits_to_text(msg_bits)
    
    return message


def embed_dct_robust(image_path, message, output_path, key="secret_key"):
    """
    Alternative: Embed in DCT coefficients (more robust to JPEG).
    Uses a simpler approach - modifies pixel blocks.
    """
    from PIL import ImageFilter
    
    img = Image.open(image_path).convert('RGB')
    pixels = np.array(img, dtype=np.float32)
    height, width = pixels.shape[:2]
    
    # Convert message to bits
    msg_bits = text_to_bits(message + '\x00')
    
    # Use 8x8 blocks like JPEG
    block_size = 8
    blocks_h = height // block_size
    blocks_w = width // block_size
    
    # Seed RNG with key
    np.random.seed(int(hashlib.sha256(key.encode()).hexdigest()[:8], 16))
    
    # Select random blocks
    total_blocks = blocks_h * blocks_w
    if len(msg_bits) > total_blocks:
        raise ValueError(f"Message too long. Max {total_blocks // 8} characters.")
    
    block_order = np.random.permutation(total_blocks)
    
    # Embed one bit per block by modifying block variance
    for bit_idx, bit in enumerate(msg_bits):
        block_idx = block_order[bit_idx]
        by = (block_idx // blocks_w) * block_size
        bx = (block_idx % blocks_w) * block_size
        
        block = pixels[by:by+block_size, bx:bx+block_size, 2]  # Blue channel
        mean_val = np.mean(block)
        
        # Modify block to encode bit
        # 1 = increase variance slightly, 0 = decrease
        if bit == 1:
            # Push values away from mean
            block = np.where(block > mean_val, block + 2, block - 2)
        else:
            # Push values toward mean  
            block = mean_val + (block - mean_val) * 0.95
        
        pixels[by:by+block_size, bx:bx+block_size, 2] = np.clip(block, 0, 255)
    
    result = Image.fromarray(pixels.astype(np.uint8))
    result.save(output_path, quality=95)
    
    print(f"✓ DCT-style embedding complete: {output_path}")
    print(f"✓ Embedded {len(message)} characters in {len(msg_bits)} blocks")
    print(f"✓ Key: '{key}'")
    
    return result


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Spread Spectrum Steganography")
        print("=" * 40)
        print("\nEncode:")
        print("  python stego_spread.py encode <image> <message> [output] [key]")
        print("\nDecode:")
        print("  python stego_spread.py decode <image> [key]")
        print("\nExample:")
        print("  python stego_spread.py encode photo.png 'Secret!' hidden.png mypassword")
        print("  python stego_spread.py decode hidden.png mypassword")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    if mode == 'encode':
        image = sys.argv[2]
        message = sys.argv[3]
        output = sys.argv[4] if len(sys.argv) > 4 else 'spread_output.png'
        key = sys.argv[5] if len(sys.argv) > 5 else 'secret_key'
        
        embed_spread(image, message, output, key, strength=4, redundancy=100)
        
    elif mode == 'decode':
        image = sys.argv[2]
        key = sys.argv[3] if len(sys.argv) > 3 else 'secret_key'
        
        result = decode_spread(image, key, strength=4, redundancy=100)
        print(f"\nDecoded: {result}")
    
    else:
        print(f"Unknown mode: {mode}")
