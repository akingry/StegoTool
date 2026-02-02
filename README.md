# StegoTool - JPEG-Resistant Steganography

A robust steganography tool that hides secret messages in images using a multi-layer approach: **Compression → Error Correction → DCT Watermarking**. Messages survive JPEG compression down to quality 60.

## Quick Start

```bash
# Install dependencies
pip install pillow numpy scipy reedsolo

# Run GUI
python stego_gui.py

# Or use CLI
python book_cipher.py encode image.png "secret message" output.png
python book_cipher.py decode output.png
```

## How It Works

### The Problem
Traditional steganography (LSB embedding) is destroyed by JPEG compression. Social media, messaging apps, and image sharing sites all re-compress images, wiping out hidden data.

### The Solution
This tool uses three layers to achieve JPEG-resistant message hiding:

```
┌─────────────────────────────────────────────────────────────┐
│                    ENCODING PIPELINE                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  "Meet at noon tomorrow"                                    │
│        ↓                                                    │
│  ┌─────────────┐                                            │
│  │ COMPRESSION │  UTF-8 encoding + zlib compression        │
│  └─────────────┘  Typically 40-60% size reduction          │
│        ↓                                                    │
│  ┌─────────────┐                                            │
│  │ REED-SOLOMON│  Add 64 parity symbols for error recovery │
│  └─────────────┘  Can fix corrupted bytes                  │
│        ↓                                                    │
│  ┌─────────────┐                                            │
│  │ REPETITION  │  Repeat each bit 7 times                  │
│  └─────────────┘  Majority vote recovers from noise        │
│        ↓                                                    │
│  ┌─────────────┐                                            │
│  │ DCT WATERMARK│ Embed in frequency domain coefficients   │
│  └─────────────┘  Same domain JPEG uses = survives it      │
│        ↓                                                    │
│  encoded_image.png                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Message Compression (`MessageEncoder` class)

### How It Works
1. Encode message as UTF-8 bytes
2. Compress with zlib (level 9, maximum compression)
3. Any characters supported - letters, numbers, symbols, Unicode

### Example
```
"Meet at noon" (12 chars)
  → UTF-8: 12 bytes
  → Compressed: ~10 bytes (compression helps more with longer text)
```

### Advantages Over Book Cipher
- **Any text supported** - no vocabulary restrictions
- **Predictable capacity** - easier to estimate limits
- **Unicode support** - emojis, special characters, non-English text

---

## Layer 2: Error Correction (`ErrorCorrection` class)

### Reed-Solomon Coding
Adds **64 parity symbols** to the data. This allows recovery even if some bytes are corrupted during JPEG compression.

```python
# 20 bytes of data → 84 bytes after RS encoding
rs = RSCodec(64)  # 64 parity symbols
encoded = rs.encode(data)  # Can fix up to 32 byte errors
```

### Repetition Coding
Each bit is repeated **7 times**. During decoding, majority vote determines the original bit.

```
Original:  1 0 1 1
Repeated:  1111111 0000000 1111111 1111111

After noise (some bits flipped):
           1101111 0010000 1111101 1110111
           
Majority:  1 0 1 1  ✓ (recovered correctly)
```

### Why Both?
- Reed-Solomon fixes **byte-level** corruption
- Repetition fixes **bit-level** noise
- Together they provide extreme robustness

---

## Layer 3: DCT Watermarking (`RobustWatermark` class)

### Why DCT?
JPEG compression works by:
1. Converting image to frequency domain (DCT)
2. Quantizing (rounding) the coefficients
3. The low frequencies survive, high frequencies are discarded

By embedding data in **mid-frequency DCT coefficients**, we put it where JPEG preserves information.

### Embedding Process
1. Divide image into 8×8 pixel blocks
2. Apply 2D DCT to each block
3. Modify coefficient at position (4,3) based on the bit to embed
4. Apply inverse DCT
5. One bit per block

### Quantization Index Modulation (QIM)
```python
# To embed bit in coefficient:
q = strength  # quantization step (150)
quantized = round(coef / q) * q

if bit == 1:
    dct_block[4, 3] = quantized + q * 0.3
else:
    dct_block[4, 3] = quantized - q * 0.3
```

### Extraction
```python
# To extract bit:
quantized = round(coef / q) * q
bit = 1 if coef >= quantized else 0
```

---

## Capacity Limits

Capacity depends on image size (number of 8×8 blocks) and error correction overhead.

### Formula
```
total_blocks = (width // 8) * (height // 8)
available_bits = total_blocks - 24  # 24-bit length header
available_bytes = available_bits // (8 * repetition)  # repetition = 7
usable_bytes = available_bytes - rs_symbols  # rs_symbols = 64
max_chars ≈ usable_bytes * 1.5  # compression ratio ~0.6-0.7
```

### Reference Table

| Image Size | Resolution | Blocks | ~Max Chars |
|------------|------------|--------|------------|
| VGA | 640×480 | 4,800 | ~50 |
| HD | 1280×720 | 14,400 | ~200 |
| Full HD | 1920×1080 | 32,400 | ~500 |
| 4K | 3840×2160 | 129,600 | ~2000 |

The GUI calculates and displays the exact limit for any selected image.

---

## JPEG Survival Test Results

Tested with 176-character message on 1280×720 image:

| Format | Quality | Result |
|--------|---------|--------|
| PNG | lossless | ✓ PASS |
| JPEG | 95 | ✓ PASS |
| JPEG | 90 | ✓ PASS |
| JPEG | 85 | ✓ PASS |
| JPEG | 80 | ✓ PASS |
| JPEG | 75 | ✓ PASS |
| JPEG | 70 | ✓ PASS |
| JPEG | 65 | ✓ PASS |
| JPEG | 60 | ✓ PASS |
| JPEG | 55 | ✗ FAIL |
| WebP | lossless | ✓ PASS |
| WebP | 90 | ✓ PASS |
| WebP | 80 | ✓ PASS |
| WebP | 70 | ✗ FAIL |

---

## File Structure

```
StegoTool/
├── stego_gui.py          # Tkinter GUI application
├── book_cipher.py        # Core encoding/decoding logic
├── test_compression.py   # JPEG survival test script
└── README.md             # This documentation
```

### stego_gui.py
- `StegoApp` - Main application class
- `setup_encode_tab()` - Encode UI with image selection, message input, capacity display
- `setup_decode_tab()` - Decode UI with image selection and output display
- `update_capacity()` - Calculates and displays character limits
- `encode_message()` / `decode_message()` - Threading wrappers

### book_cipher.py
- `MessageEncoder` - UTF-8 encoding + zlib compression
- `ErrorCorrection` - Reed-Solomon + repetition coding
- `RobustWatermark` - DCT-domain bit embedding/extraction
- `encode_image()` / `decode_image()` - High-level API

---

## Settings (Tuned for JPEG Q60 Survival)

```python
strength = 150      # DCT modification strength
rs_symbols = 64     # Reed-Solomon parity symbols  
repetition = 7      # Bit repetition count
```

These settings survive JPEG quality 60+. For higher capacity with less robustness, reduce these values.

---

## Usage Examples

### GUI
1. Run `python stego_gui.py`
2. **Encode tab**: Select image → Type message → See capacity → Encode
3. **Decode tab**: Select encoded image → Decode → Read message

### CLI
```bash
# Encode a message
python book_cipher.py encode photo.jpg "Meet me at the old bridge tomorrow" secret.png

# Decode a message
python book_cipher.py decode secret.png

# Test JPEG survival at various quality levels
python test_compression.py
```

### Sharing
1. Encode message into PNG or WebP (lossless)
2. Share as PNG/WebP (lossless) OR JPEG/WebP quality 60+ (lossy but survives)
3. Recipient decodes with same tool

### Supported Formats
- **Input**: PNG, JPEG, WebP, BMP
- **Output**: PNG (lossless), WebP (lossless)
- **Survives**: JPEG q60+, WebP q80+

---

## Dependencies

```
pillow      # Image handling
numpy       # Array operations  
scipy       # DCT functions
reedsolo    # Reed-Solomon error correction
```

Install: `pip install pillow numpy scipy reedsolo`

---

## Limitations

1. **Capacity**: Heavy error correction limits message size (~500 chars for 1080p)
2. **Image modification**: Cropping, resizing, or heavy editing breaks the watermark
3. **Not encryption**: This is steganography (hiding), not cryptography (securing)
4. **Compression floor**: JPEG quality below 60 will corrupt the data

---

## Security Notes

- Messages are **hidden**, not **encrypted**
- Anyone with this tool can decode your message
- For secure communication, encrypt your message first, then encode the ciphertext
- The compression adds obscurity but is not cryptographically secure

---

## Technical References

- DCT Watermarking: Cox et al., "Secure Spread Spectrum Watermarking for Multimedia"
- Reed-Solomon: Standard error correction used in CDs, QR codes, satellite comms
- Quantization Index Modulation: Chen & Wornell, "Quantization Index Modulation"
