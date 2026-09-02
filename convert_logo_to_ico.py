"""Convert the logo PNG into a multi-resolution Windows .ico file.

Reads the design logo (blue gradient rounded square with white "Md"),
resizes it to standard icon resolutions, and writes build_assets/app.ico.
"""

import os
from PIL import Image

LOGO_PATH = os.path.join(os.path.expanduser("~"), "Downloads", "Markdown查看器logo设计.png")
OUT_PATH = os.path.join(os.path.dirname(__file__), "build_assets", "app.ico")

# Standard Windows icon resolutions (largest first)
SIZES = [256, 128, 64, 48, 32, 16]


def make_ico():
    if not os.path.exists(LOGO_PATH):
        raise SystemExit(f"Logo PNG not found: {LOGO_PATH}")

    src = Image.open(LOGO_PATH).convert("RGBA")
    print(f"Source logo: {src.size[0]}x{src.size[1]} {src.mode}")

    # Build each resolution with high-quality LANCZOS resampling.
    frames = []
    for s in SIZES:
        # Image.LANCZOS keeps the "Md" crisp at smaller sizes.
        im = src.resize((s, s), Image.LANCZOS)
        frames.append(im)
        print(f"  Rendered {s}x{s}")

    # Backup the previous icon if present
    if os.path.exists(OUT_PATH):
        bak = OUT_PATH + ".bak"
        if not os.path.exists(bak):
            os.replace(OUT_PATH, bak)
            print(f"  Backed up old icon -> {bak}")

    # Write multi-frame ICO. Pillow picks the PNG format for 256 (to keep
    # quality high) and BMP for the smaller sizes automatically.
    frames[0].save(
        OUT_PATH,
        format="ICO",
        sizes=[(s, s) for s in SIZES],
        append_images=frames[1:],
    )
    print(f"Icon created: {OUT_PATH} ({os.path.getsize(OUT_PATH)} bytes, {len(SIZES)} resolutions)")


if __name__ == "__main__":
    make_ico()
