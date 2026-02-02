"""
Disguised QR Code Steganography
Embeds a QR code as a subtle texture pattern that survives JPEG compression.
"""

import qrcode
from PIL import Image, ImageEnhance, ImageFilter
import sys
import os

def embed_qr(image_path, message, output_path, strength=0.15, position='auto'):
    """
    Embed a QR code disguised as texture into an image.
    
    strength: 0.05-0.25 (lower = more hidden, higher = more robust)
    position: 'auto', 'center', 'bottom-right', or (x, y) tuple
    """
    # Load the carrier image
    img = Image.open(image_path).convert('RGB')
    img_width, img_height = img.size
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=None,  # Auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # 30% error correction - survives damage
        box_size=10,
        border=2,
    )
    qr.add_data(message)
    qr.make(fit=True)
    
    qr_img = qr.make_image(fill_color='black', back_color='white').convert('RGB')
    qr_width, qr_height = qr_img.size
    
    # Scale QR to fit in image (max 40% of smallest dimension)
    max_qr_size = int(min(img_width, img_height) * 0.4)
    if qr_width > max_qr_size:
        scale = max_qr_size / qr_width
        qr_img = qr_img.resize((int(qr_width * scale), int(qr_height * scale)), Image.NEAREST)
        qr_width, qr_height = qr_img.size
    
    # Determine position
    if position == 'auto' or position == 'center':
        x = (img_width - qr_width) // 2
        y = (img_height - qr_height) // 2
    elif position == 'bottom-right':
        x = img_width - qr_width - 20
        y = img_height - qr_height - 20
    else:
        x, y = position
    
    # Create the blend
    # Convert QR to grayscale pattern (-1 to +1 range)
    qr_gray = qr_img.convert('L')
    
    # Apply slight blur to reduce harsh edges (helps survive compression)
    qr_gray = qr_gray.filter(ImageFilter.GaussianBlur(radius=0.5))
    
    # Blend QR into image
    result = img.copy()
    
    for qy in range(qr_height):
        for qx in range(qr_width):
            px, py = x + qx, y + qy
            if 0 <= px < img_width and 0 <= py < img_height:
                # Get QR pixel (0=black, 255=white)
                qr_val = qr_gray.getpixel((qx, qy))
                # Convert to modifier (-strength to +strength)
                modifier = (qr_val / 255.0 - 0.5) * 2 * strength
                
                # Get original pixel
                r, g, b = img.getpixel((px, py))
                
                # Apply modification (affects luminance)
                # Multiply to create texture-like appearance
                factor = 1.0 + modifier
                new_r = int(max(0, min(255, r * factor)))
                new_g = int(max(0, min(255, g * factor)))
                new_b = int(max(0, min(255, b * factor)))
                
                result.putpixel((px, py), (new_r, new_g, new_b))
    
    # Save result
    result.save(output_path, quality=95)
    
    print(f"✓ QR embedded into: {output_path}")
    print(f"  Message: {message[:50]}{'...' if len(message) > 50 else ''}")
    print(f"  QR size: {qr_width}x{qr_height}")
    print(f"  Position: ({x}, {y})")
    print(f"  Strength: {strength}")
    print(f"\nTo decode: Use any QR scanner app, or run with --decode")
    
    return result


def decode_qr(image_path):
    """
    Attempt to decode QR from image (may need enhancement).
    """
    try:
        from pyzbar.pyzbar import decode
        img = Image.open(image_path)
        
        # Try original
        results = decode(img)
        if results:
            return results[0].data.decode('utf-8')
        
        # Try with contrast enhancement
        enhancer = ImageEnhance.Contrast(img)
        for factor in [1.5, 2.0, 2.5, 3.0]:
            enhanced = enhancer.enhance(factor)
            results = decode(enhanced)
            if results:
                return results[0].data.decode('utf-8')
        
        # Try grayscale with threshold
        gray = img.convert('L')
        for threshold in [100, 120, 140, 160]:
            binary = gray.point(lambda p: 255 if p > threshold else 0)
            results = decode(binary)
            if results:
                return results[0].data.decode('utf-8')
        
        return None
    except ImportError:
        print("Note: Install pyzbar for automatic decoding: pip install pyzbar")
        print("Or use any QR scanner app on your phone")
        return None


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage:")
        print("  Encode: python stego_qr.py <image> <message> [output] [strength]")
        print("  Decode: python stego_qr.py --decode <image>")
        print("\nExample:")
        print("  python stego_qr.py photo.png 'Secret message' hidden.png 0.15")
        sys.exit(1)
    
    if sys.argv[1] == '--decode':
        result = decode_qr(sys.argv[2])
        if result:
            print(f"Decoded message: {result}")
        else:
            print("Could not decode QR. Try a QR scanner app with contrast boost.")
    else:
        image_path = sys.argv[1]
        message = sys.argv[2]
        output_path = sys.argv[3] if len(sys.argv) > 3 else 'stego_output.png'
        strength = float(sys.argv[4]) if len(sys.argv) > 4 else 0.15
        
        embed_qr(image_path, message, output_path, strength)
