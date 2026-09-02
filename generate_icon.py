"""Generate multi-resolution "All" logo icon for Markdown Viewer (.ico file)
   Creates 256×256, 48×48, and 32×32 resolutions for sharp taskbar/title-bar display."""

import struct, zlib, os, math

def create_png(w, h, pixels):
    raw = b''.join(b'\x00' + pixels[y*w*4:(y+1)*w*4] for y in range(h))
    comp = zlib.compress(raw)
    def chunk(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', comp) + chunk(b'IEND', b''))

def render_pixels(S):
    """Render the 'All' logo at size S×S. Returns RGBA bytes."""
    C = S // 2
    R = S // 2 - max(2, S // 32)
    R2 = R * R
    THICK = max(3, S // 16)

    DARK  = (30, 30, 46)
    ACCENT = (137, 180, 250)
    WHITE = (205, 214, 244)
    TRANS = bytes((0, 0, 0, 0))
    T = THICK / S  # normalized thick

    def rgba(r, g, b, a=255): return bytes((r, g, b, a))

    pixels = b''
    for y in range(S):
        for x in range(S):
            dx, dy = x - C, y - C
            inside = dx*dx + dy*dy <= R2
            nx, ny = x / S, y / S

            color = None

            if inside:
                # --- Letter "A" ---
                progress = (ny - 0.30) / (0.72 - 0.30) if 0.30 < ny < 0.72 else -1
                if 0 <= progress <= 1:
                    left_edge  = 0.20 + progress * 0.04
                    right_edge = 0.70 - progress * 0.18
                    # Flat top
                    if progress < 0.08:
                        if left_edge < nx < 0.70:
                            color = WHITE
                    # Crossbar
                    elif 0.38 < ny < 0.50:
                        if left_edge < nx < right_edge:
                            color = WHITE
                    # Left stem
                    elif abs(nx - left_edge) < T or abs(nx - right_edge) < T:
                        color = WHITE
                    # Thick left/right
                    elif left_edge + T < nx < left_edge + 3*T:
                        color = WHITE
                    elif right_edge - 3*T < nx < right_edge - T:
                        color = WHITE

                # --- Letter "l" (first) ---
                if color is None and ny >= 0.30 and ny < 0.72 and 0.74 < nx < 0.81:
                    if abs(nx - 0.775) < T:
                        color = WHITE

                # --- Letter "l" (second) ---
                if color is None and ny >= 0.30 and ny < 0.72 and 0.85 < nx < 0.92:
                    if abs(nx - 0.885) < T:
                        color = WHITE

                # Ring border
                if color is None:
                    dist = math.sqrt(dx*dx + dy*dy)
                    if R - T < dist < R:
                        angle = math.atan2(dy, dx)
                        r = int(40 + 10 * math.sin(angle * 3))
                        g = int(45 + 8 * math.cos(angle * 2))
                        b = int(60 + 12 * math.sin(angle * 4))
                        color = (r, g, b)

                # Background gradient
                if color is None:
                    dist_ratio = dist / R
                    r = int(DARK[0] + (ACCENT[0] - DARK[0]) * (1 - dist_ratio) * 0.2)
                    g = int(DARK[1] + (ACCENT[1] - DARK[1]) * (1 - dist_ratio) * 0.2)
                    b = int(DARK[2] + (ACCENT[2] - DARK[2]) * (1 - dist_ratio) * 0.2)
                    color = (r, g, b)

                pixels += rgba(*color)
            else:
                pixels += TRANS

    return pixels

def create_ico(png_sizes):
    """Create ICO from multiple PNGs. png_sizes = [(w, h, png_bytes), ...]"""
    num = len(png_sizes)
    header = struct.pack('<HHH', 0, 1, num)
    dir_entries = b''
    data_offset = 6 + 16 * num
    for w, h, png in png_sizes:
        ico_w = 0 if w >= 256 else w
        ico_h = 0 if h >= 256 else h
        dir_entries += struct.pack('<BBBBHHII', ico_w, ico_h, 0, 0, 1, 32, len(png), data_offset)
        data_offset += len(png)
    return header + dir_entries + b''.join(p for _, _, p in png_sizes)

def make_icon():
    sizes = [256, 48, 32]
    pngs = []
    for s in sizes:
        pixels = render_pixels(s)
        png = create_png(s, s, pixels)
        pngs.append((s, s, png))
        print(f"  Rendered {s}×{s} PNG ({len(png)} bytes)")

    ico = create_ico(pngs)
    out = os.path.join(os.path.dirname(__file__), 'build_assets', 'app.ico')
    with open(out, 'wb') as f:
        f.write(ico)
    print(f"Logo created: {out} ({len(ico)} bytes, {len(pngs)} resolutions)")

if __name__ == '__main__':
    make_icon()
