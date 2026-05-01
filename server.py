#!/usr/bin/env python3
"""
Web server for the Match-3 Tile Solver.

Run:  python3 server.py
Then open http://<your-pc-ip>:5000 on your phone (same WiFi).

Requires: GEMINI_API_KEY env var, or a .env file with it.
Get a free key at aistudio.google.com → Get API key.
"""

import io
import json
import os
import re

from flask import Flask, jsonify, request, send_from_directory

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import google.generativeai as genai
from PIL import Image

app = Flask(__name__)

RECOGNIZE_PROMPT = """\
This is a screenshot of a match-3 tile puzzle game (like "3 Tiles", "Tile Busters", etc.).

The board contains tiles/blocks arranged in a grid. Some tiles are stacked on top of others \
— you can tell because they are visually offset (shifted right/down) and cast a shadow on the \
tiles beneath them.

Identify EVERY visible tile and return a JSON array. For each tile include:
  "color"  : a short, consistent snake_case name for the icon/image on that tile \
(e.g. "cat", "star", "anchor", "crown", "red", "blue"). \
Use the EXACT SAME name for all tiles that look identical.
  "x"      : column index, 0-based, left → right
  "y"      : row index,    0-based, top  → bottom
  "layer"  : stack depth — 0 for the bottommost tiles, 1 for tiles sitting on layer 0, \
2 for tiles sitting on layer 1, etc.

Return ONLY a valid JSON array with no extra text or markdown fences.
Example output:
[{"color":"cat","x":0,"y":0,"layer":0},{"color":"star","x":1,"y":0,"layer":1}]
"""


@app.route("/")
def index():
    return send_from_directory(".", "play.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded — send a multipart field named 'image'."}), 400

    file = request.files["image"]
    raw = file.read()
    if not raw:
        return jsonify({"error": "Uploaded file is empty."}), 400

    try:
        img = Image.open(io.BytesIO(raw))
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(
            [RECOGNIZE_PROMPT, img],
            generation_config={"temperature": 0, "max_output_tokens": 4096},
        )
        raw_text = response.text.strip()
    except Exception as e:
        return jsonify({"error": f"Gemini API error: {e}"}), 502

    raw_text = re.sub(r"^```[a-z]*\n?", "", raw_text)
    raw_text = re.sub(r"\n?```$", "", raw_text)
    raw_text = raw_text.strip()

    try:
        blocks = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return jsonify({"error": f"Could not parse Gemini's response as JSON: {exc}",
                        "raw": raw_text}), 500

    if not isinstance(blocks, list) or not blocks:
        return jsonify({"error": "Gemini returned an empty or non-array response.",
                        "raw": raw_text}), 500

    for i, b in enumerate(blocks):
        b["id"] = i + 1
        b.setdefault("w", 1)
        b.setdefault("h", 1)
        b.setdefault("kind", "normal")
        b.setdefault("threshold", 0)

    return jsonify({"blocks": blocks, "count": len(blocks)})


if __name__ == "__main__":
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print(
            "\nERROR: GEMINI_API_KEY is not set.\n"
            "  Export it before running:  export GEMINI_API_KEY=AIzaSy...\n"
            "  Or create a .env file with GEMINI_API_KEY=AIzaSy...\n"
            "  Get a free key at aistudio.google.com\n"
        )
        raise SystemExit(1)

    genai.configure(api_key=api_key)

    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"\nServer running.")
    print(f"  Local:   http://localhost:5000")
    print(f"  Network: http://{local_ip}:5000  ← open this on your phone\n")

    app.run(host="0.0.0.0", port=5000, debug=False)
