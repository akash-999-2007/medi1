import os
import zlib
import struct
from pathlib import Path

ICONS_DIR = Path(__file__).resolve().parent / "static" / "icons"
ICONS_DIR.mkdir(parents=True, exist_ok=True)

# 1. Generate clean medical cross + heart SVG
SVG_CONTENT = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <defs>
    <linearGradient id="medGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#2563eb" />
      <stop offset="100%" stop-color="#0284c7" />
    </linearGradient>
    <linearGradient id="crossGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#10b981" />
      <stop offset="100%" stop-color="#059669" />
    </linearGradient>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="8" stdDeviation="12" flood-color="#1e3a8a" flood-opacity="0.3"/>
    </filter>
  </defs>
  
  <!-- Rounded Base Background -->
  <rect width="512" height="512" rx="120" fill="url(#medGrad)" />
  
  <!-- Subtle Inner Glow Ring -->
  <rect x="20" y="20" width="472" height="472" rx="100" fill="none" stroke="#ffffff" stroke-width="4" stroke-opacity="0.2" />

  <!-- White Badge Shield/Circle -->
  <circle cx="256" cy="256" r="170" fill="#ffffff" filter="url(#shadow)" />

  <!-- Medical Pill & Plus Cross -->
  <!-- Vertical Bar -->
  <rect x="220" y="140" width="72" height="232" rx="36" fill="url(#crossGrad)" />
  <!-- Horizontal Bar -->
  <rect x="140" y="220" width="232" height="72" rx="36" fill="url(#crossGrad)" />

  <!-- Center Pulse Dot -->
  <circle cx="256" cy="256" r="24" fill="#ffffff" />
  <circle cx="256" cy="256" r="14" fill="#2563eb" />
</svg>'''

with open(ICONS_DIR / "icon.svg", "w", encoding="utf-8") as f:
    f.write(SVG_CONTENT)

def create_png(width, height, file_path):
    """Generate a clean RGBA PNG with rounded medical blue background and white/green cross."""
    # Standard PNG writer using zlib
    raw_rows = []
    r_base, g_base, b_base = 37, 99, 235       # #2563eb
    r_cross, g_cross, b_cross = 16, 185, 129    # #10b981
    r_white, g_white, b_white = 255, 255, 255

    cx, cy = width / 2.0, height / 2.0
    r_outer = width * 0.46
    r_inner = width * 0.33
    bar_thick = width * 0.14
    bar_len = width * 0.44

    for y in range(height):
        row = bytearray(b'\x00') # Filter type 0 (None)
        for x in range(width):
            dx = x - cx
            dy = y - cy
            dist = (dx*dx + dy*dy) ** 0.5

            if dist > r_outer:
                # Outside circle
                row.extend((0, 0, 0, 0))
            elif dist > r_inner:
                # Blue outer ring
                row.extend((r_base, g_base, b_base, 255))
            else:
                # Inner disc (White circle)
                # Check if in cross
                in_h_bar = (abs(dy) <= bar_thick / 2.0) and (abs(dx) <= bar_len / 2.0)
                in_v_bar = (abs(dx) <= bar_thick / 2.0) and (abs(dy) <= bar_len / 2.0)
                in_center_dot = dist <= (bar_thick * 0.28)

                if in_center_dot:
                    row.extend((r_base, g_base, b_base, 255))
                elif in_h_bar or in_v_bar:
                    row.extend((r_cross, g_cross, b_cross, 255))
                else:
                    row.extend((r_white, g_white, b_white, 255))
        raw_rows.append(bytes(row))

    raw_data = b''.join(raw_rows)
    compressed = zlib.compress(raw_data)

    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)

    png_bytes = (
        b'\x89PNG\r\n\x1a\n' +
        chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)) +
        chunk(b'IDAT', compressed) +
        chunk(b'IEND', b'')
    )

    with open(file_path, 'wb') as f:
        f.write(png_bytes)

create_png(192, 192, ICONS_DIR / "icon-192.png")
create_png(512, 512, ICONS_DIR / "icon-512.png")
# Also save as favicon
create_png(64, 64, ICONS_DIR / "favicon.ico")

print(f"Generated icons in {ICONS_DIR}")
