"""
Steganography Tool - GUI Application
Hide and extract secret messages in images using robust DCT watermarking.
Survives JPEG compression down to quality 60.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from PIL import Image, ImageTk
import threading
import os

# Import the robust encoding from book_cipher
from book_cipher import encode_image, decode_image, BookCipher, RobustWatermark

class StegoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Steganography Tool")
        self.root.geometry("800x750")
        self.root.configure(bg='#1e1e1e')
        
        # Robust encoding settings (survives JPEG q60)
        self.strength = 150  # DCT modification strength
        self.rs_symbols = 64
        self.repetition = 7
        
        # Variables
        self.image_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.source_text_path = tk.StringVar()  # Path to shared book/source text
        self.current_image = None
        self.preview_photo = None
        
        # Capacity limits (calculated from image)
        self.max_chars = None
        self.max_words = None
        
        self.setup_ui()
    
    def setup_ui(self):
        # Style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background='#1e1e1e')
        style.configure('TLabel', background='#1e1e1e', foreground='#ffffff', font=('Segoe UI', 10))
        style.configure('TButton', font=('Segoe UI', 10))
        style.configure('Header.TLabel', font=('Segoe UI', 14, 'bold'), foreground='#58a6ff')
        
        # Main container
        main = ttk.Frame(self.root, padding=20)
        main.pack(fill=tk.BOTH, expand=True)
        
        # Header
        ttk.Label(main, text="🔐 Steganography Tool", style='Header.TLabel').pack(pady=(0, 5))
        ttk.Label(main, text="JPEG-resistant encoding (survives quality 60+)", 
                  foreground='#3fb950').pack(pady=(0, 15))
        
        # Notebook for tabs
        notebook = ttk.Notebook(main)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Encode tab
        encode_frame = ttk.Frame(notebook, padding=15)
        notebook.add(encode_frame, text="  Encode  ")
        self.setup_encode_tab(encode_frame)
        
        # Decode tab
        decode_frame = ttk.Frame(notebook, padding=15)
        notebook.add(decode_frame, text="  Decode  ")
        self.setup_decode_tab(decode_frame)
        
        # Info tab
        info_frame = ttk.Frame(notebook, padding=15)
        notebook.add(info_frame, text="  Info  ")
        self.setup_info_tab(info_frame)
    
    def setup_encode_tab(self, parent):
        # Source text selection (REQUIRED - the shared book)
        source_frame = ttk.Frame(parent)
        source_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(source_frame, text="Source Text (Book):").pack(side=tk.LEFT)
        ttk.Entry(source_frame, textvariable=self.source_text_path, width=45).pack(side=tk.LEFT, padx=5)
        ttk.Button(source_frame, text="Browse...", command=self.browse_source_text).pack(side=tk.LEFT)
        
        # Source text note
        source_note = ttk.Label(parent, text="⚠️ IMPORTANT: Sender and receiver must share the SAME source text file!", 
                                foreground='#f0883e', font=('Segoe UI', 9, 'bold'))
        source_note.pack(anchor=tk.W, pady=(0, 10))
        
        # Image selection
        img_frame = ttk.Frame(parent)
        img_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(img_frame, text="Source Image:").pack(side=tk.LEFT)
        ttk.Entry(img_frame, textvariable=self.image_path, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(img_frame, text="Browse...", command=self.browse_image).pack(side=tk.LEFT)
        
        # Preview (fixed height)
        self.encode_preview_frame = ttk.Frame(parent, height=180)
        self.encode_preview_frame.pack(fill=tk.X, pady=10)
        self.encode_preview_frame.pack_propagate(False)
        
        self.encode_preview_label = ttk.Label(self.encode_preview_frame, text="No image loaded")
        self.encode_preview_label.pack(expand=True)
        
        # Message input with character counter
        msg_header = ttk.Frame(parent)
        msg_header.pack(fill=tk.X, pady=(10, 5))
        ttk.Label(msg_header, text="Secret Message:").pack(side=tk.LEFT)
        self.char_count_label = ttk.Label(msg_header, text="0 / ? chars", foreground='#8b949e')
        self.char_count_label.pack(side=tk.RIGHT)
        
        self.message_text = scrolledtext.ScrolledText(parent, height=4, font=('Consolas', 10),
                                                       bg='#2d2d2d', fg='#ffffff', insertbackground='white')
        self.message_text.pack(fill=tk.X)
        
        # Bind events for character limiting
        self.message_text.bind('<KeyRelease>', self.on_message_change)
        self.message_text.bind('<<Paste>>', self.on_paste)
        self.message_text.bind('<Control-v>', self.on_paste)
        self.message_text.bind('<Control-V>', self.on_paste)
        
        # Capacity info
        self.capacity_label = ttk.Label(parent, text="Capacity: Select an image to see capacity")
        self.capacity_label.pack(anchor=tk.W, pady=5)
        
        # Encoding note
        self.word_note = ttk.Label(parent, text="Note: Characters are encoded as positions in the source text (book cipher)", 
                                   foreground='#58a6ff', font=('Segoe UI', 9))
        self.word_note.pack(anchor=tk.W)
        
        # Encode button
        self.encode_btn = ttk.Button(parent, text="🔒 Encode Message", command=self.encode_message)
        self.encode_btn.pack(pady=15)
        
        # Status
        self.encode_status = ttk.Label(parent, text="", foreground='#3fb950')
        self.encode_status.pack()
    
    def setup_decode_tab(self, parent):
        # Source text selection (REQUIRED - must match sender's book)
        source_frame = ttk.Frame(parent)
        source_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(source_frame, text="Source Text (Book):").pack(side=tk.LEFT)
        self.decode_source_path = tk.StringVar()
        ttk.Entry(source_frame, textvariable=self.decode_source_path, width=45).pack(side=tk.LEFT, padx=5)
        ttk.Button(source_frame, text="Browse...", command=self.browse_decode_source_text).pack(side=tk.LEFT)
        
        # Source text note
        source_note = ttk.Label(parent, text="⚠️ Must be the SAME source text the sender used!", 
                                foreground='#f0883e', font=('Segoe UI', 9, 'bold'))
        source_note.pack(anchor=tk.W, pady=(0, 10))
        
        # Image selection
        img_frame = ttk.Frame(parent)
        img_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(img_frame, text="Encoded Image:").pack(side=tk.LEFT)
        self.decode_path = tk.StringVar()
        ttk.Entry(img_frame, textvariable=self.decode_path, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(img_frame, text="Browse...", command=self.browse_decode_image).pack(side=tk.LEFT)
        
        # Preview (fixed height)
        self.decode_preview_frame = ttk.Frame(parent, height=180)
        self.decode_preview_frame.pack(fill=tk.X, pady=10)
        self.decode_preview_frame.pack_propagate(False)
        
        self.decode_preview_label = ttk.Label(self.decode_preview_frame, text="No image loaded")
        self.decode_preview_label.pack(expand=True)
        
        # Format selection
        format_frame = ttk.Frame(parent)
        format_frame.pack(fill=tk.X, pady=10)
        ttk.Label(format_frame, text="Supports: PNG, WebP (lossless), or JPEG/WebP (quality 60+)", 
                  foreground='#8b949e').pack(side=tk.LEFT)
        
        # Decode button
        self.decode_btn = ttk.Button(parent, text="🔓 Decode Message", command=self.decode_message)
        self.decode_btn.pack(pady=15)
        
        # Decoded message output
        ttk.Label(parent, text="Decoded Message:").pack(anchor=tk.W, pady=(10, 5))
        self.decoded_text = scrolledtext.ScrolledText(parent, height=6, font=('Consolas', 10),
                                                       bg='#2d2d2d', fg='#ffffff')
        self.decoded_text.pack(fill=tk.X)
        
        # Status
        self.decode_status = ttk.Label(parent, text="", foreground='#3fb950')
        self.decode_status.pack(pady=5)
    
    def setup_info_tab(self, parent):
        ttk.Label(parent, text="How It Works", style='Header.TLabel').pack(anchor=tk.W, pady=(0, 15))
        
        info = """
Book Cipher Steganography with JPEG Survival
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ IMPORTANT: Sender and receiver must share the SAME 
   source text (book) file to communicate!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HOW THE BOOK CIPHER WORKS:

Each character in your message is found in the source 
text, and its RELATIVE position is recorded.

Example: Message "The" with source text positions:
   • 'T' found at position 325 → record: 325
   • 'h' found at position 225 → record: -100 (backwards)
   • 'e' found at position 228 → record: +3 (forwards)
   
Result: [325, -100, +3] (compressed and embedded)

The cipher always finds the NEAREST occurrence of each
character, whether forwards or backwards in the text.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LAYERS OF PROTECTION:

1. BOOK CIPHER
   • Characters encoded as relative positions
   • Requires shared source text (the "book")
   • Positions compressed with zlib

2. ERROR CORRECTION  
   • Reed-Solomon coding (64 parity symbols)
   • Repetition coding (7x bit repetition)
   • Recovers from JPEG compression artifacts

3. DCT WATERMARKING
   • Embeds in frequency domain coefficients
   • Survives JPEG/WebP quality down to 60

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SECURITY:

• Without the source text, the message cannot be decoded
• Choose a book/text that only you and recipient have
• Larger texts = more security (more positions to search)
• The source text is your shared secret key

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tips:
   • Share the source text file securely beforehand
   • Use any .txt file as your "book"
   • Larger images = more message capacity
   • Save as PNG/WebP lossless for best quality
        """
        
        info_text = scrolledtext.ScrolledText(parent, height=22, font=('Consolas', 9),
                                              bg='#2d2d2d', fg='#a0a0a0')
        info_text.pack(fill=tk.BOTH, expand=True, pady=10)
        info_text.insert(tk.END, info)
        info_text.configure(state='disabled')
    
    def browse_source_text(self):
        path = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Select Source Text (Book) - Must be shared with receiver"
        )
        if path:
            self.source_text_path.set(path)
    
    def browse_decode_source_text(self):
        path = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Select Source Text (Book) - Must match sender's book"
        )
        if path:
            self.decode_source_path.set(path)
    
    def browse_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All files", "*.*")]
        )
        if path:
            self.image_path.set(path)
            self.load_preview(path, self.encode_preview_label)
            self.update_capacity()
    
    def browse_decode_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All files", "*.*")]
        )
        if path:
            self.decode_path.set(path)
            self.load_preview(path, self.decode_preview_label)
    
    def load_preview(self, path, label):
        try:
            img = Image.open(path)
            img.thumbnail((250, 250))
            photo = ImageTk.PhotoImage(img)
            label.configure(image=photo, text="")
            label.image = photo
        except Exception as e:
            label.configure(text=f"Error loading image: {e}", image="")
    
    def update_capacity(self):
        """Calculate and display capacity for the selected image."""
        try:
            img = Image.open(self.image_path.get())
            width, height = img.size
            
            # Calculate available 8x8 blocks
            blocks_h = height // 8
            blocks_w = width // 8
            total_blocks = blocks_h * blocks_w
            
            # Calculate exact capacity with current error correction settings
            # Flow: message → compress → RS encode → repetition → embed
            # 
            # Available bits for data = total_blocks - 24 (header)
            # After repetition: available_bytes = available_bits / (8 * repetition)
            # After RS: usable_bytes = available_bytes - rs_symbols
            # With zlib compression: ~1.5-2x expansion for usable chars
            
            available_bits = total_blocks - 24
            available_bytes_after_rep = available_bits // (8 * self.repetition)
            usable_bytes = max(0, available_bytes_after_rep - self.rs_symbols)
            
            # Conservative estimate: short text compresses poorly
            # Use 1:1 ratio for safety (compression helps more with longer text)
            self.max_chars = usable_bytes
            self.max_words = self.max_chars // 6  # Average ~6 chars per word including space
            
            # Color code based on capacity
            if self.max_chars < 100:
                cap_color = '#f0883e'  # Orange - limited
            elif self.max_chars < 300:
                cap_color = '#58a6ff'  # Blue - moderate
            else:
                cap_color = '#3fb950'  # Green - good
            
            self.capacity_label.configure(
                text=f"📊 Capacity: ~{self.max_chars} chars (~{self.max_words} words) • {width}×{height} image • {total_blocks:,} blocks",
                foreground=cap_color
            )
            self.update_char_count()
            
        except Exception as e:
            self.max_words = None
            self.max_chars = None
            self.capacity_label.configure(
                text="📊 Capacity: Select an image to see limit",
                foreground='#8b949e'
            )
            self.char_count_label.configure(text="0 / ? chars", foreground='#8b949e')
    
    def update_char_count(self):
        """Update the character count display with limit enforcement."""
        current_text = self.message_text.get("1.0", "end-1c")
        char_count = len(current_text)
        word_count = len(current_text.split()) if current_text.strip() else 0
        
        if self.max_chars is not None:
            # Show both character and word counts
            self.char_count_label.configure(
                text=f"{char_count} / {self.max_chars} chars • {word_count} words"
            )
            
            # Color code based on character usage
            if char_count > self.max_chars:
                self.char_count_label.configure(foreground='#f85149')  # Red - over limit
                self.encode_btn.configure(state='disabled')
            elif char_count > self.max_chars * 0.8:
                self.char_count_label.configure(foreground='#f0883e')  # Orange - warning
                self.encode_btn.configure(state='normal')
            else:
                self.char_count_label.configure(foreground='#3fb950')  # Green - good
                self.encode_btn.configure(state='normal')
        else:
            self.char_count_label.configure(text=f"{char_count} chars • {word_count} words", foreground='#8b949e')
    
    def on_message_change(self, event=None):
        """Called when message text changes."""
        self.update_char_count()
    
    def on_paste(self, event=None):
        """Handle paste events - limit to max character capacity."""
        try:
            clipboard_text = self.root.clipboard_get()
        except tk.TclError:
            return
        
        if self.max_chars is None:
            return
        
        current_text = self.message_text.get("1.0", "end-1c")
        current_len = len(current_text)
        
        try:
            sel_start = self.message_text.index(tk.SEL_FIRST)
            sel_end = self.message_text.index(tk.SEL_LAST)
            selected_text = self.message_text.get(sel_start, sel_end)
            current_len -= len(selected_text)
        except tk.TclError:
            pass
        
        available = self.max_chars - current_len
        
        if available <= 0:
            return "break"
        
        if len(clipboard_text) > available:
            truncated = clipboard_text[:available]
            
            try:
                self.message_text.delete(tk.SEL_FIRST, tk.SEL_LAST)
            except tk.TclError:
                pass
            
            self.message_text.insert(tk.INSERT, truncated)
            self.update_char_count()
            
            messagebox.showinfo("Paste Truncated", 
                f"Text was truncated to fit capacity.\n"
                f"Pasted {len(truncated)} of {len(clipboard_text)} characters.")
            
            return "break"
        
        self.root.after(10, self.update_char_count)
    
    def encode_message(self):
        if not self.source_text_path.get():
            messagebox.showerror("Error", "Please select a source text (book) file.\n\nThis file must be shared with the receiver!")
            return
        
        if not self.image_path.get():
            messagebox.showerror("Error", "Please select a source image")
            return
        
        message = self.message_text.get("1.0", tk.END).strip()
        if not message:
            messagebox.showerror("Error", "Please enter a message to hide")
            return
        
        # Check character limit
        char_count = len(message)
        if self.max_chars is not None and char_count > self.max_chars:
            messagebox.showerror(
                "Message Too Long", 
                f"Your message has {char_count} characters but this image can only hold ~{self.max_chars} characters.\n\n"
                f"Options:\n"
                f"• Shorten your message\n"
                f"• Use a larger image\n"
                f"• Use a 4K image for more capacity"
            )
            return
        
        output_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG files (lossless)", "*.png"),
                ("WebP lossless", "*.webp"),
                ("All files", "*.*")
            ],
            initialfile="encoded_image.png"
        )
        if not output_path:
            return
        
        self.encode_btn.configure(state='disabled')
        self.encode_status.configure(text="Encoding (this may take a moment)...", foreground='#f0883e')
        
        thread = threading.Thread(target=self._do_encode, args=(message, output_path))
        thread.start()
    
    def _do_encode(self, message, output_path):
        try:
            encode_image(
                self.image_path.get(),
                message,
                output_path,
                strength=self.strength,
                rs_symbols=self.rs_symbols,
                repetition=self.repetition,
                source_path=self.source_text_path.get()
            )
            self.root.after(0, lambda: self._encode_complete(output_path))
        except Exception as e:
            error_msg = str(e)  # Capture immediately
            self.root.after(0, lambda err=error_msg: self._encode_error(err))
    
    def _encode_complete(self, output_path):
        self.encode_btn.configure(state='normal')
        self.encode_status.configure(text=f"✓ Saved to: {os.path.basename(output_path)}", foreground='#3fb950')
        messagebox.showinfo("Success", 
            f"Message encoded successfully!\n\n"
            f"Saved to:\n{output_path}\n\n"
            f"This image can be shared as JPEG or WebP (quality 60+) and still decode correctly.")
    
    def _encode_error(self, error):
        self.encode_btn.configure(state='normal')
        self.encode_status.configure(text=f"Error: {error[:50]}", foreground='#f85149')
        messagebox.showerror("Encoding Failed", f"{error}\n\nTips:\n• Check that your source text contains all characters in your message\n• Try a shorter message or larger image")
    
    def decode_message(self):
        if not self.decode_source_path.get():
            messagebox.showerror("Error", "Please select a source text (book) file.\n\nThis must be the SAME file the sender used!")
            return
        
        if not self.decode_path.get():
            messagebox.showerror("Error", "Please select an image to decode")
            return
        
        self.decode_btn.configure(state='disabled')
        self.decode_status.configure(text="Decoding...", foreground='#f0883e')
        
        thread = threading.Thread(target=self._do_decode)
        thread.start()
    
    def _do_decode(self):
        try:
            result = decode_image(
                self.decode_path.get(),
                strength=self.strength,
                rs_symbols=self.rs_symbols,
                repetition=self.repetition,
                source_path=self.decode_source_path.get()
            )
            self.root.after(0, lambda: self._decode_complete(result))
        except Exception as e:
            error_msg = str(e)  # Capture immediately
            self.root.after(0, lambda err=error_msg: self._decode_error(err))
    
    def _decode_complete(self, message):
        self.decode_btn.configure(state='normal')
        self.decoded_text.delete("1.0", tk.END)
        self.decoded_text.insert(tk.END, message)
        self.decode_status.configure(text="✓ Message decoded successfully", foreground='#3fb950')
    
    def _decode_error(self, error):
        self.decode_btn.configure(state='normal')
        self.decode_status.configure(text=f"Error: {error[:50]}", foreground='#f85149')
        messagebox.showerror("Decoding Failed", 
            f"{error}\n\n"
            f"Possible causes:\n"
            f"• Image doesn't contain a hidden message\n"
            f"• JPEG quality was too low (<60)\n"
            f"• Image was modified/cropped")


if __name__ == '__main__':
    root = tk.Tk()
    app = StegoApp(root)
    root.mainloop()
