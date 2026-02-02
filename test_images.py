"""Test with actual images at near-max capacity."""

import os
from PIL import Image
from book_cipher import encode_image, decode_image

# Settings
STRENGTH = 150
RS_SYMBOLS = 64
REPETITION = 7

# Test messages sized for each image
# fossil2.png: 7840 blocks → (7840-24)//56 - 64 = 75 bytes max
SMALL_MSG = """The quick brown fox jumps over the lazy dog near the river."""  # 60 chars

LARGE_MSG = """Four score and seven years ago our fathers brought forth on this continent, a new nation, conceived in Liberty, and dedicated to the proposition that all men are created equal.

Now we are engaged in a great civil war, testing whether that nation, or any nation so conceived and so dedicated, can long endure. We are met on a great battle-field of that war. We have come to dedicate a portion of that field, as a final resting place for those who here gave their lives that that nation might live.

It is altogether fitting and proper that we should do this. But, in a larger sense, we can not dedicate, we can not consecrate, we can not hallow this ground. The brave men, living and dead, who struggled here, have consecrated it, far above our poor power to add or detract.

The world will little note, nor long remember what we say here, but it can never forget what they did here."""  # 897 chars

def test_image(image_path, message, name):
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")
    
    # Get image info
    img = Image.open(image_path)
    w, h = img.size
    blocks = (w // 8) * (h // 8)
    
    print(f"Image: {w}x{h} ({blocks:,} blocks)")
    print(f"Message: {len(message)} chars")
    
    # Encode
    encoded_path = f"test_{name}_encoded.png"
    print(f"\nEncoding...")
    
    try:
        encode_image(image_path, message, encoded_path,
                    strength=STRENGTH, rs_symbols=RS_SYMBOLS, repetition=REPETITION)
    except Exception as e:
        print(f"✗ Encoding FAILED: {e}")
        return False
    
    # Test formats
    print(f"\nTesting compression survival:")
    print("-" * 40)
    
    results = []
    
    # PNG (lossless)
    try:
        decoded = decode_image(encoded_path, strength=STRENGTH, rs_symbols=RS_SYMBOLS, repetition=REPETITION)
        match = decoded == message
        results.append(("PNG lossless", match, None))
        print(f"  PNG lossless:  {'✓ PASS' if match else '✗ FAIL'}")
    except Exception as e:
        results.append(("PNG lossless", False, str(e)))
        print(f"  PNG lossless:  ✗ FAIL - {e}")
    
    # JPEG at various qualities
    img_encoded = Image.open(encoded_path)
    
    for quality in [90, 80, 70, 60]:
        jpg_path = f"test_{name}_q{quality}.jpg"
        img_encoded.save(jpg_path, "JPEG", quality=quality)
        
        try:
            decoded = decode_image(jpg_path, strength=STRENGTH, rs_symbols=RS_SYMBOLS, repetition=REPETITION)
            match = decoded == message
            size_kb = os.path.getsize(jpg_path) // 1024
            results.append((f"JPEG q{quality}", match, size_kb))
            print(f"  JPEG q{quality}:      {'✓ PASS' if match else '✗ FAIL'} ({size_kb}KB)")
        except Exception as e:
            results.append((f"JPEG q{quality}", False, str(e)[:30]))
            print(f"  JPEG q{quality}:      ✗ FAIL - {str(e)[:40]}")
        
        os.remove(jpg_path)
    
    # WebP lossless
    webp_path = f"test_{name}.webp"
    img_encoded.save(webp_path, "WEBP", lossless=True)
    try:
        decoded = decode_image(webp_path, strength=STRENGTH, rs_symbols=RS_SYMBOLS, repetition=REPETITION)
        match = decoded == message
        size_kb = os.path.getsize(webp_path) // 1024
        results.append(("WebP lossless", match, size_kb))
        print(f"  WebP lossless: {'✓ PASS' if match else '✗ FAIL'} ({size_kb}KB)")
    except Exception as e:
        results.append(("WebP lossless", False, str(e)))
        print(f"  WebP lossless: ✗ FAIL - {e}")
    os.remove(webp_path)
    
    # Cleanup
    os.remove(encoded_path)
    
    # Summary
    passed = sum(1 for r in results if r[1])
    print(f"\nResult: {passed}/{len(results)} tests passed")
    
    return all(r[1] for r in results[:5])  # PNG + JPEG 60-90


def main():
    print("=" * 60)
    print("STEGANOGRAPHY IMAGE TESTS")
    print("=" * 60)
    
    all_passed = True
    
    # Test fossil2.png (small)
    if os.path.exists("fossil2.png"):
        if not test_image("fossil2.png", SMALL_MSG, "fossil2"):
            all_passed = False
    else:
        print("\n⚠ fossil2.png not found")
    
    # Test forest.webp (large)
    if os.path.exists("forest.webp"):
        if not test_image("forest.webp", LARGE_MSG, "forest"):
            all_passed = False
    else:
        print("\n⚠ forest.webp not found")
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("=" * 60)


if __name__ == "__main__":
    main()
