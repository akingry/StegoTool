"""Test JPEG compression survival at various quality levels."""

import os
import sys
from PIL import Image
from book_cipher import encode_image, decode_image

# Test message - Gettysburg Address opening
TEST_MESSAGE = """Four score and seven years ago our fathers brought forth on this continent, a new nation, conceived in Liberty, and dedicated to the proposition that all men are created equal."""

# Settings - increased strength for better JPEG survival
STRENGTH = 150  # Increased from 100
RS_SYMBOLS = 64
REPETITION = 7

def create_test_image(width, height, path):
    """Create a simple test image."""
    import numpy as np
    # Create gradient image with some variation
    img_array = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        for x in range(width):
            img_array[y, x, 0] = (x * 255) // width  # Red gradient
            img_array[y, x, 1] = (y * 255) // height  # Green gradient
            img_array[y, x, 2] = 128  # Blue constant
    img = Image.fromarray(img_array)
    img.save(path)
    return img

def test_jpeg_survival():
    print("=" * 60)
    print("JPEG COMPRESSION SURVIVAL TEST")
    print("=" * 60)
    print(f"\nTest message ({len(TEST_MESSAGE)} chars):")
    print(f"  \"{TEST_MESSAGE[:60]}...\"")
    print()
    
    # Create test image (HD resolution)
    test_img_path = "test_source.png"
    create_test_image(1280, 720, test_img_path)
    print(f"Created test image: 1280x720")
    
    # Encode
    encoded_path = "test_encoded.png"
    print(f"\nEncoding message...")
    try:
        encode_image(
            test_img_path, 
            TEST_MESSAGE, 
            encoded_path,
            strength=STRENGTH,
            rs_symbols=RS_SYMBOLS,
            repetition=REPETITION
        )
    except Exception as e:
        print(f"Encoding failed: {e}")
        return
    
    # Test PNG (lossless) first
    print("\n" + "-" * 60)
    print("Testing formats:")
    print("-" * 60)
    
    try:
        decoded = decode_image(encoded_path, strength=STRENGTH, rs_symbols=RS_SYMBOLS, repetition=REPETITION)
        match = decoded == TEST_MESSAGE
        print(f"  PNG (lossless):  {'✓ PASS' if match else '✗ FAIL'}")
        if not match:
            print(f"    Expected: {TEST_MESSAGE[:50]}...")
            print(f"    Got:      {decoded[:50]}...")
    except Exception as e:
        print(f"  PNG (lossless):  ✗ FAIL - {e}")
    
    # Test JPEG at various quality levels
    img = Image.open(encoded_path)
    
    for quality in [95, 90, 85, 80, 75, 70, 65, 60, 55, 50]:
        jpg_path = f"test_q{quality}.jpg"
        img.save(jpg_path, "JPEG", quality=quality)
        
        try:
            decoded = decode_image(jpg_path, strength=STRENGTH, rs_symbols=RS_SYMBOLS, repetition=REPETITION)
            match = decoded == TEST_MESSAGE
            status = "✓ PASS" if match else f"≈ PARTIAL ({len(decoded)} chars)"
        except Exception as e:
            status = f"✗ FAIL - {str(e)[:30]}"
        
        file_size = os.path.getsize(jpg_path) // 1024
        print(f"  JPEG quality {quality:2d}: {status} ({file_size}KB)")
        
        # Clean up
        os.remove(jpg_path)
    
    # Test WebP
    webp_path = "test_encoded.webp"
    img.save(webp_path, "WEBP", lossless=True)
    try:
        decoded = decode_image(webp_path, strength=STRENGTH, rs_symbols=RS_SYMBOLS, repetition=REPETITION)
        match = decoded == TEST_MESSAGE
        print(f"  WebP (lossless): {'✓ PASS' if match else '✗ FAIL'}")
    except Exception as e:
        print(f"  WebP (lossless): ✗ FAIL - {e}")
    os.remove(webp_path)
    
    # Test WebP lossy
    for quality in [90, 80, 70, 60]:
        webp_path = f"test_webp_q{quality}.webp"
        img.save(webp_path, "WEBP", quality=quality)
        
        try:
            decoded = decode_image(webp_path, strength=STRENGTH, rs_symbols=RS_SYMBOLS, repetition=REPETITION)
            match = decoded == TEST_MESSAGE
            status = "✓ PASS" if match else f"≈ PARTIAL"
        except Exception as e:
            status = f"✗ FAIL - {str(e)[:30]}"
        
        file_size = os.path.getsize(webp_path) // 1024
        print(f"  WebP quality {quality:2d}: {status} ({file_size}KB)")
        
        os.remove(webp_path)
    
    # Cleanup
    os.remove(test_img_path)
    os.remove(encoded_path)
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)

if __name__ == "__main__":
    test_jpeg_survival()
