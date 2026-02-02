# StegoTool - Book Cipher Steganography

A steganography tool that hides secret messages in images using a **book cipher**. Messages survive JPEG compression down to quality 60.

## ⚠️ IMPORTANT: Shared Source Text Required

**Both sender and receiver must have the SAME source text (book) file to communicate!**

The source text acts as a shared secret key. Without it, the message cannot be decoded.

## Quick Start

```bash
# Install dependencies
pip install pillow numpy scipy reedsolo

# Run GUI
python stego_gui.py

# Or use CLI
python book_cipher.py encode image.png "secret message" output.png --source mybook.txt
python book_cipher.py decode output.png --source mybook.txt
```

## How the Book Cipher Works

Each character in your message is found in the source text, and its **relative position** is recorded.

### Example

Message: `"The"`  
Source text: `"...at The old house where They lived..."`

1. Find `'T'` at position 325 → record: **325** (absolute, first char)
2. Find `'h'` at position 225 → record: **-100** (100 chars backwards)
3. Find `'e'` at position 228 → record: **+3** (3 chars forwards)

Result: `[325, -100, +3]`

The cipher always finds the **nearest occurrence** of each character, whether forwards or backwards in the text. This minimizes the numbers stored.

These positions are then:
1. Compressed with zlib
2. Protected with Reed-Solomon error correction
3. Embedded in the image using DCT watermarking

## Encoding Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    ENCODING PIPELINE                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  "Meet at noon"                                             │
│        ↓                                                    │
│  ┌─────────────┐                                            │
│  │ BOOK CIPHER │  Find each character in source text       │
│  └─────────────┘  Record relative positions [+325,-50,+3]  │
│        ↓                                                    │
│  ┌─────────────┐                                            │
│  │ COMPRESSION │  zlib compress the position data          │
│  └─────────────┘  Typically 40-60% reduction               │
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

## Security

### Why a Book Cipher?

1. **Shared Secret**: Without the source text, decoding is impossible
2. **Plausible Deniability**: The source text can be any innocent file
3. **Variable Key**: Different books = different encodings
4. **Large Key Space**: A novel has millions of character positions

### Choosing a Source Text

- **Any text file works** - novels, articles, random text
- **Larger is better** - more positions = harder to crack
- **Keep it secret** - share it securely with your recipient
- **Must contain all characters** - ensure your book has every character you need

### What's NOT Encrypted

- The image itself is not encrypted
- Anyone with this tool AND your source text can decode
- For additional security, encrypt your message before encoding

## Usage

### GUI Application

```bash
python stego_gui.py
```

1. **Encode Tab**:
   - Select your source text (book) file
   - Select an image to hide the message in
   - Type your secret message
   - Click "Encode Message"
   - Save the output image

2. **Decode Tab**:
   - Select the SAME source text file
   - Select the encoded image
   - Click "Decode Message"

### Command Line

```bash
# Encode
python book_cipher.py encode photo.jpg "Secret message" output.png --source mybook.txt

# Decode
python book_cipher.py decode output.png --source mybook.txt

# Test JPEG survival
python test_compression.py
```

## Capacity Limits

Capacity depends on image size:

| Image Size | Resolution | ~Max Characters |
|------------|------------|-----------------|
| VGA | 640×480 | ~75 |
| HD | 1280×720 | ~250 |
| Full HD | 1920×1080 | ~500 |
| 4K | 3840×2160 | ~2000 |

## JPEG Survival

Tested with 176-character message:

| Format | Quality | Result |
|--------|---------|--------|
| PNG | lossless | ✓ PASS |
| JPEG | 90 | ✓ PASS |
| JPEG | 80 | ✓ PASS |
| JPEG | 70 | ✓ PASS |
| JPEG | 60 | ✓ PASS |
| JPEG | 55 | ✗ FAIL |
| WebP | lossless | ✓ PASS |
| WebP | 80 | ✓ PASS |

## File Structure

```
StegoTool/
├── stego_gui.py          # Tkinter GUI application
├── book_cipher.py        # Core encoding/decoding logic
├── test_compression.py   # JPEG survival test script
├── docs/index.html       # Web application
└── README.md             # This documentation
```

## Dependencies

```
pillow      # Image handling
numpy       # Array operations  
scipy       # DCT functions
reedsolo    # Reed-Solomon error correction
```

Install: `pip install pillow numpy scipy reedsolo`

## Technical Details

### Settings (tuned for JPEG Q60 survival)

```python
strength = 150      # DCT modification strength
rs_symbols = 64     # Reed-Solomon parity symbols  
repetition = 7      # Bit repetition count
```

### Position Encoding

- **Zigzag encoding**: Converts signed integers to unsigned for efficient storage
- **Varint encoding**: Variable-length encoding (small numbers = fewer bytes)
- **zlib compression**: Further reduces data size

### DCT Watermarking

- Embeds one bit per 8×8 pixel block
- Uses coefficient at position (4,3) - mid-frequency
- Quantization Index Modulation (QIM) for robust embedding

## Limitations

1. **Shared secret required**: Both parties need the same source text
2. **Character availability**: Source text must contain all message characters
3. **Image modification**: Cropping/resizing breaks the watermark
4. **Compression floor**: JPEG quality below 60 corrupts the data

## License

MIT License - Use freely, modify freely, share freely.
