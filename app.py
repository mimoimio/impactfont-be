import os
import requests
import textwrap
import io
from flask import Flask, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont
from flask_cors import CORS  # <--- Import this

app = Flask(__name__)
CORS(app) # <--- Enable CORS for all routes

# --- CONFIGURATION ---
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf"
FONT_PATH = "Anton-Regular.ttf"

# --- HELPER: Load Font Once on Startup ---
def load_font():
    if not os.path.exists(FONT_PATH):
        print("Downloading font...")
        r = requests.get(FONT_URL, allow_redirects=True)
        with open(FONT_PATH, 'wb') as f:
            f.write(r.content)
    return FONT_PATH

# Ensure font is ready before first request
load_font()

# --- CORE LOGIC (Adapted for Memory Streams) ---
def draw_multiline_text(draw, text, image_size, position):
    W, H = image_size
    
    # 1. Define Constraints
    # We want text to ideally be big (1/8th of height)
    # But we strictly forbid it from exceeding 25% of the total image height
    max_text_height = H * 0.25 
    max_width_px = W * 0.95
    
    # Start with a nice big font
    font_size = int(H / 8) 
    min_font_size = 10 # Don't go smaller than this
    
    # 2. Iterative Shrink Loop
    # We keep shrinking font until the text fits within our max_height
    while font_size > min_font_size:
        font = ImageFont.truetype(FONT_PATH, font_size)
        
        # Calculate how many chars fit on one line at this specific font size
        avg_char_width = font.getlength("A")
        chars_per_line = int(max_width_px / avg_char_width)
        
        # Wrap the text
        lines = textwrap.wrap(text, width=chars_per_line)
        
        # Calculate total height of this specific arrangement
        ascent, descent = font.getmetrics()
        line_height = ascent + descent
        total_text_height = len(lines) * line_height
        
        # CHECK: Does it fit our height limit?
        if total_text_height <= max_text_height:
            # It fits! Break the loop and draw it.
            break 
        else:
            # It's too tall. Shrink font by 2px and try again.
            # This might allow words to jump back to the previous line,
            # reducing the total line count.
            font_size -= 2

    # 3. Draw Logic (Same as before, but using our calculated 'lines' and 'font')
    if position == "top":
        current_y = H * 0.05 
    else: 
        current_y = H - total_text_height - (H * 0.05)

    outline_width = max(2, int(font_size / 15))
    
    for line in lines:
        line_width = font.getlength(line)
        x_pos = (W - line_width) / 2
        
        # Stroke
        draw.text((x_pos, current_y), line, font=font, fill="black", 
                  stroke_width=outline_width, stroke_fill="black")
        # Fill
        draw.text((x_pos, current_y), line, font=font, fill="white")
        
        current_y += line_height

@app.route('/', methods=['GET'])
def index():
    return send_file('index.html')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200
    
@app.route('/meme', methods=['POST'])
def generate_meme():
    # 1. Validation
    if 'image' not in request.files:
        return jsonify({"error": "No image part"}), 400
    
    file = request.files['image']
    top_text = request.form.get('top', '')
    bottom_text = request.form.get('bottom', '')

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    try:
        # 2. Open Image from Memory
        img = Image.open(file.stream).convert("RGB")

        # 3. Force Resize (512x512)
        img = img.resize((512, 512), Image.Resampling.LANCZOS)

        # 4. Draw Text
        draw = ImageDraw.Draw(img)
        if top_text:
            draw_multiline_text(draw, top_text.upper(), img.size, "top")
        if bottom_text:
            draw_multiline_text(draw, bottom_text.upper(), img.size, "bottom")

        # 5. Save to Memory Buffer (BytesIO)
        img_io = io.BytesIO()
        img.save(img_io, 'JPEG', quality=95)
        img_io.seek(0)

        # 6. Return Blob
        return send_file(img_io, mimetype='image/jpeg')

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

