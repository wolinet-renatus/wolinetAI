#!/usr/bin/env python3
"""
Wolinex Brand Asset Generator
Generates high-resolution SVGs, PNGs, ICO, and ICNS icons matching
the Mitambo color theme (Electric Azure #30a2ff & Warm Amber Gold #fdb515)
with rich textures, subtle cyber glow, and sharp geometric typography.
"""

import os
import subprocess
import sys
from pathlib import Path
from PIL import Image

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = WORKSPACE_DIR / "assets" / "branding"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Mitambo Color Palette
AZURE_LIGHT = "#5ec2ff"
AZURE_MAIN = "#30a2ff"
AZURE_DEEP = "#0284c7"
AZURE_DARK = "#0369a1"

GOLD_LIGHT = "#fde047"
GOLD_MAIN = "#fdb515"
GOLD_DEEP = "#f59e0b"
GOLD_DARK = "#d97706"

BG_OBSIDIAN = "#070a13"
BG_CARD = "#0d1322"
BG_BORDER = "#1e293b"

# --- 1. Master Icon Emblem SVG (Pure Symbol) ---
def get_icon_svg(size=1024, with_bg=True, bg_color=BG_OBSIDIAN):
    bg_element = f'''<rect width="{size}" height="{size}" rx="{size * 0.22}" fill="url(#bgGrad)" stroke="url(#borderGrad)" stroke-width="{size * 0.015}"/>
    <circle cx="{size * 0.5}" cy="{size * 0.48}" r="{size * 0.38}" fill="url(#coreGlow)" opacity="0.65"/>
    ''' if with_bg else ''

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">
  <defs>
    <!-- Background Gradients -->
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0f172a"/>
      <stop offset="50%" stop-color="#090d16"/>
      <stop offset="100%" stop-color="#020408"/>
    </linearGradient>
    
    <linearGradient id="borderGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.4"/>
      <stop offset="50%" stop-color="#1e293b" stop-opacity="0.2"/>
      <stop offset="100%" stop-color="#f59e0b" stop-opacity="0.3"/>
    </linearGradient>

    <radialGradient id="coreGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#30a2ff" stop-opacity="0.25"/>
      <stop offset="60%" stop-color="#fdb515" stop-opacity="0.08"/>
      <stop offset="100%" stop-color="#000000" stop-opacity="0"/>
    </radialGradient>

    <!-- Mitambo Gold Slant Gradient -->
    <linearGradient id="goldGrad" x1="20%" y1="0%" x2="80%" y2="100%">
      <stop offset="0%" stop-color="{GOLD_LIGHT}"/>
      <stop offset="45%" stop-color="{GOLD_MAIN}"/>
      <stop offset="100%" stop-color="{GOLD_DEEP}"/>
    </linearGradient>

    <!-- Mitambo Azure Blue Slant Gradient -->
    <linearGradient id="blueGrad" x1="20%" y1="0%" x2="80%" y2="100%">
      <stop offset="0%" stop-color="{AZURE_LIGHT}"/>
      <stop offset="45%" stop-color="{AZURE_MAIN}"/>
      <stop offset="100%" stop-color="{AZURE_DEEP}"/>
    </linearGradient>

    <linearGradient id="cyanGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#67e8f9"/>
      <stop offset="100%" stop-color="#0284c7"/>
    </linearGradient>

    <!-- Bevel Highlights -->
    <linearGradient id="specularGold" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.6"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>

    <linearGradient id="specularBlue" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.7"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>

    <!-- Soft Drop Shadows -->
    <filter id="shadowFilter" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="{size * 0.016}" stdDeviation="{size * 0.024}" flood-color="#000000" flood-opacity="0.75"/>
    </filter>

    <filter id="neonGlow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="{size * 0.02}" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  {bg_element}

  <!-- Emblem Group: Dynamic W Architecture -->
  <g transform="translate({size * 0.5}, {size * (0.49 if with_bg else 0.5)}) scale({size / 1024})" filter="url(#shadowFilter)">
    
    <!-- Outer Cyan/Blue Wing (Right Facet) -->
    <path d="M 120 -280 
             L 290 -280 
             C 320 -280 345 -260 335 -225 
             L 140 270 
             C 125 310 85 325 50 310 
             L -20 280 
             L 75 40 
             Z" 
          fill="url(#blueGrad)" />

    <!-- Specular Highlight for Blue Wing -->
    <path d="M 120 -280 L 150 -280 L 100 290 L 70 290 Z" 
          fill="url(#specularBlue)" opacity="0.45" />

    <!-- Left Amber/Gold Wing (Left Facet) -->
    <path d="M -290 -100 
             L -130 -100 
             C -100 -100 -80 -80 -90 -50 
             L -210 270 
             C -225 310 -265 325 -300 310 
             L -340 285 
             C -365 260 -360 220 -345 180 
             Z" 
          fill="url(#goldGrad)" />

    <!-- Center Intermeshing Neural Apex / Chevron (Cyan-to-Gold Fusion) -->
    <path d="M -110 -280 
             L 50 -280 
             C 75 -280 90 -260 80 -235 
             L -60 130 
             C -75 165 -110 180 -140 165 
             L -190 140 
             L -75 -160 
             Z" 
          fill="url(#cyanGrad)" opacity="0.95" />

    <!-- High-tech Accent Dot / Sovereign Core Gem -->
    <circle cx="160" cy="-210" r="22" fill="#ffffff" filter="url(#neonGlow)"/>
    <circle cx="-160" cy="-30" r="16" fill="{GOLD_LIGHT}" filter="url(#neonGlow)"/>
    <circle cx="0" cy="220" r="14" fill="{AZURE_LIGHT}" filter="url(#neonGlow)"/>
  </g>
</svg>'''


# --- 2. Master Horizontal Logo SVG (Icon + "WOLINEX" Typography) ---
def get_horizontal_logo_svg(width=1600, height=450, dark_mode=True):
    bg_rect = f'<rect width="{width}" height="{height}" fill="{BG_OBSIDIAN if dark_mode else "#ffffff"}"/>'
    text_color_main = "#ffffff" if dark_mode else "#0f172a"
    text_color_sub = "#94a3b8" if dark_mode else "#64748b"
    tagline_color = AZURE_LIGHT if dark_mode else AZURE_DARK

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <defs>
    <!-- Gradients -->
    <linearGradient id="goldGradHoriz" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{GOLD_LIGHT}"/>
      <stop offset="50%" stop-color="{GOLD_MAIN}"/>
      <stop offset="100%" stop-color="{GOLD_DEEP}"/>
    </linearGradient>

    <linearGradient id="blueGradHoriz" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{AZURE_LIGHT}"/>
      <stop offset="50%" stop-color="{AZURE_MAIN}"/>
      <stop offset="100%" stop-color="{AZURE_DEEP}"/>
    </linearGradient>

    <linearGradient id="cyanGradHoriz" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#67e8f9"/>
      <stop offset="100%" stop-color="#0284c7"/>
    </linearGradient>

    <linearGradient id="textGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{text_color_main}"/>
      <stop offset="70%" stop-color="{text_color_main}"/>
      <stop offset="100%" stop-color="{AZURE_LIGHT}"/>
    </linearGradient>

    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="8" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>

    <filter id="logoShadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="6" stdDeviation="12" flood-color="#000000" flood-opacity="0.45"/>
    </filter>
  </defs>

  {bg_rect}

  <!-- Emblem on Left -->
  <g transform="translate(220, 225) scale(0.32)" filter="url(#logoShadow)">
    <!-- Right Blue Wing -->
    <path d="M 120 -280 L 290 -280 C 320 -280 345 -260 335 -225 L 140 270 C 125 310 85 325 50 310 L -20 280 L 75 40 Z" 
          fill="url(#blueGradHoriz)" />

    <!-- Left Gold Wing -->
    <path d="M -290 -100 L -130 -100 C -100 -100 -80 -80 -90 -50 L -210 270 C -225 310 -265 325 -300 310 L -340 285 C -365 260 -360 220 -345 180 Z" 
          fill="url(#goldGradHoriz)" />

    <!-- Center Cyan Apex -->
    <path d="M -110 -280 L 50 -280 C 75 -280 90 -260 80 -235 L -60 130 C -75 165 -110 180 -140 165 L -190 140 L -75 -160 Z" 
          fill="url(#cyanGradHoriz)" opacity="0.95" />

    <!-- Accents -->
    <circle cx="160" cy="-210" r="22" fill="#ffffff" filter="url(#glow)"/>
    <circle cx="-160" cy="-30" r="16" fill="{GOLD_LIGHT}" filter="url(#glow)"/>
    <circle cx="0" cy="220" r="14" fill="{AZURE_LIGHT}" filter="url(#glow)"/>
  </g>

  <!-- Typography "WOLINEX" -->
  <g transform="translate(420, 255)">
    <text font-family="-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif" 
          font-size="142" 
          font-weight="900" 
          letter-spacing="14" 
          fill="url(#textGrad)">WOLIN<tspan fill="url(#goldGradHoriz)">EX</tspan></text>
          
    <text x="8" y="65" 
          font-family="-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', Roboto, sans-serif" 
          font-size="28" 
          font-weight="700" 
          letter-spacing="10" 
          fill="{tagline_color}" 
          opacity="0.92">SOVEREIGN AI WORKSTATION</text>
  </g>
</svg>'''


# --- 3. Square Badge Logo SVG (Icon + "WOLINEX" below) ---
def get_square_logo_svg(size=1024, dark_mode=True):
    bg_rect = f'''<rect width="{size}" height="{size}" rx="{size * 0.22}" fill="{BG_OBSIDIAN if dark_mode else "#ffffff"}" stroke="{AZURE_MAIN if dark_mode else "#cbd5e1"}" stroke-opacity="0.3" stroke-width="12"/>
    <circle cx="{size * 0.5}" cy="{size * 0.42}" r="{size * 0.35}" fill="url(#coreGlowSquare)" opacity="0.7"/>
    '''

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">
  <defs>
    <radialGradient id="coreGlowSquare" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#30a2ff" stop-opacity="0.25"/>
      <stop offset="60%" stop-color="#fdb515" stop-opacity="0.1"/>
      <stop offset="100%" stop-color="#000000" stop-opacity="0"/>
    </radialGradient>

    <linearGradient id="goldGradSq" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{GOLD_LIGHT}"/>
      <stop offset="50%" stop-color="{GOLD_MAIN}"/>
      <stop offset="100%" stop-color="{GOLD_DEEP}"/>
    </linearGradient>

    <linearGradient id="blueGradSq" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{AZURE_LIGHT}"/>
      <stop offset="50%" stop-color="{AZURE_MAIN}"/>
      <stop offset="100%" stop-color="{AZURE_DEEP}"/>
    </linearGradient>

    <linearGradient id="cyanGradSq" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#67e8f9"/>
      <stop offset="100%" stop-color="#0284c7"/>
    </linearGradient>

    <filter id="shadowSq" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="16" stdDeviation="24" flood-color="#000000" flood-opacity="0.75"/>
    </filter>
  </defs>

  {bg_rect}

  <!-- Emblem Centered Upper -->
  <g transform="translate({size * 0.5}, {size * 0.42}) scale({size / 1380})" filter="url(#shadowSq)">
    <path d="M 120 -280 L 290 -280 C 320 -280 345 -260 335 -225 L 140 270 C 125 310 85 325 50 310 L -20 280 L 75 40 Z" fill="url(#blueGradSq)" />
    <path d="M -290 -100 L -130 -100 C -100 -100 -80 -80 -90 -50 L -210 270 C -225 310 -265 325 -300 310 L -340 285 C -365 260 -360 220 -345 180 Z" fill="url(#goldGradSq)" />
    <path d="M -110 -280 L 50 -280 C 75 -280 90 -260 80 -235 L -60 130 C -75 165 -110 180 -140 165 L -190 140 L -75 -160 Z" fill="url(#cyanGradSq)" opacity="0.95" />
    <circle cx="160" cy="-210" r="22" fill="#ffffff"/>
    <circle cx="-160" cy="-30" r="16" fill="{GOLD_LIGHT}"/>
  </g>

  <!-- Typography "WOLINEX" Below -->
  <g transform="translate({size * 0.5}, {size * 0.84})" text-anchor="middle">
    <text font-family="-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif" 
          font-size="{size * 0.11}" 
          font-weight="900" 
          letter-spacing="{size * 0.012}" 
          fill="#ffffff">WOLIN<tspan fill="url(#goldGradSq)">EX</tspan></text>
  </g>
</svg>'''


# --- 4. Menu Bar Template Glyph SVG ---
def get_glyph_svg(size=22):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 22 22" width="{size}" height="{size}">
  <path d="M 13.5 3 L 18 3 C 18.8 3 19.3 3.5 19 4.2 L 14.5 16 C 14.2 17 13.2 17.5 12.2 17 L 10.5 16.2 L 12.5 10 Z" fill="#ffffff"/>
  <path d="M 4 8 L 8 8 C 8.8 8 9.3 8.5 9 9.2 L 6 16.5 C 5.6 17.5 4.5 18 3.5 17.5 L 2.5 16.8 C 1.8 16.2 1.8 15.2 2.2 14.2 Z" fill="#ffffff" opacity="0.75"/>
  <path d="M 8 3 L 12 3 C 12.6 3 13 3.5 12.8 4.1 L 9 13 C 8.6 14 7.5 14.5 6.7 14 L 5.5 13.5 L 8.5 6 Z" fill="#ffffff" opacity="0.9"/>
</svg>'''


# --- Helper: Render SVG to PNG via Headless Chrome ---
def render_svg_to_png(svg_content, out_png_path, width, height, transparent=False):
    tmp_html = Path(f"/tmp/wolinex_render_{os.getpid()}_{Path(out_png_path).stem}.html")
    bg_style = "background:transparent;" if transparent else "background:#070a13;"
    
    html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{ width:{width}px; height:{height}px; {bg_style} overflow:hidden; }}
</style>
</head>
<body>
{svg_content}
</body>
</html>'''
    tmp_html.write_text(html, encoding="utf-8")

    bg_color_arg = "--default-background-color=00000000" if transparent else "--default-background-color=ff070a13"
    cmd = [
        CHROME_BIN,
        "--headless",
        "--disable-gpu",
        bg_color_arg,
        f"--window-size={width},{height}",
        f"--screenshot={out_png_path}",
        f"file://{tmp_html.absolute()}"
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    if tmp_html.exists():
        tmp_html.unlink()


def main():
    print("Generating Wolinex vector SVGs and assets...")

    # 1. Generate SVGs
    icon_svg_str = get_icon_svg(1024, with_bg=True)
    icon_transparent_svg = get_icon_svg(1024, with_bg=False)
    horiz_logo_dark_svg = get_horizontal_logo_svg(1600, 450, dark_mode=True)
    horiz_logo_light_svg = get_horizontal_logo_svg(1600, 450, dark_mode=False)
    square_logo_svg = get_square_logo_svg(1024, dark_mode=True)
    glyph_svg_str = get_glyph_svg(22)
    favicon_svg_str = get_icon_svg(64, with_bg=True)

    # Save SVGs
    (OUTPUT_DIR / "icon.svg").write_text(icon_svg_str, encoding="utf-8")
    (OUTPUT_DIR / "icon-transparent.svg").write_text(icon_transparent_svg, encoding="utf-8")
    (OUTPUT_DIR / "wolinex-logo.svg").write_text(horiz_logo_dark_svg, encoding="utf-8")
    (OUTPUT_DIR / "wolinex-logo-dark.svg").write_text(horiz_logo_dark_svg, encoding="utf-8")
    (OUTPUT_DIR / "wolinex-logo-light.svg").write_text(horiz_logo_light_svg, encoding="utf-8")
    (OUTPUT_DIR / "wolinex-logo-square.svg").write_text(square_logo_svg, encoding="utf-8")
    (OUTPUT_DIR / "glyph.svg").write_text(glyph_svg_str, encoding="utf-8")
    (OUTPUT_DIR / "favicon.svg").write_text(favicon_svg_str, encoding="utf-8")

    print("Rendering high-res master PNGs...")
    master_icon_png = OUTPUT_DIR / "icon.png"
    render_svg_to_png(icon_svg_str, master_icon_png, 1024, 1024, transparent=False)

    master_icon_2x_png = OUTPUT_DIR / "icon@2x.png"
    render_svg_to_png(icon_svg_str, master_icon_2x_png, 2048, 2048, transparent=False)

    logo_dark_png = OUTPUT_DIR / "wolinex-logo-dark.png"
    render_svg_to_png(horiz_logo_dark_svg, logo_dark_png, 1600, 450, transparent=False)
    
    logo_main_png = OUTPUT_DIR / "wolinex-logo.png"
    render_svg_to_png(horiz_logo_dark_svg, logo_main_png, 1600, 450, transparent=False)

    logo_light_png = OUTPUT_DIR / "wolinex-logo-light.png"
    render_svg_to_png(horiz_logo_light_svg, logo_light_png, 1600, 450, transparent=False)

    logo_square_png = OUTPUT_DIR / "wolinex-logo-square.png"
    render_svg_to_png(square_logo_svg, logo_square_png, 1024, 1024, transparent=False)

    # Template glyphs for macOS menu bar
    render_svg_to_png(glyph_svg_str, OUTPUT_DIR / "iconTemplate.png", 22, 22, transparent=True)
    render_svg_to_png(glyph_svg_str, OUTPUT_DIR / "iconTemplate@2x.png", 44, 44, transparent=True)
    render_svg_to_png(glyph_svg_str, OUTPUT_DIR / "iconTemplateUpdate.png", 22, 22, transparent=True)
    render_svg_to_png(glyph_svg_str, OUTPUT_DIR / "iconTemplateUpdate@2x.png", 44, 44, transparent=True)

    print("Generating resolution scaling variants...")
    master_img = Image.open(master_icon_png)
    
    sizes = [512, 256, 128, 64, 48, 32, 16]
    for s in sizes:
        resized = master_img.resize((s, s), Image.Resampling.LANCZOS)
        resized.save(OUTPUT_DIR / f"icon-{s}.png", format="PNG", optimize=True)

    # Favicons
    master_img.resize((256, 256), Image.Resampling.LANCZOS).save(OUTPUT_DIR / "wolinex-favicon.png", format="PNG")
    master_img.resize((32, 32), Image.Resampling.LANCZOS).save(OUTPUT_DIR / "favicon-32x32.png", format="PNG")
    master_img.resize((16, 16), Image.Resampling.LANCZOS).save(OUTPUT_DIR / "favicon-16x16.png", format="PNG")
    master_img.resize((48, 48), Image.Resampling.LANCZOS).save(OUTPUT_DIR / "favicon.png", format="PNG")

    # Windows ICO (multi-resolution 256, 128, 64, 48, 32, 16)
    ico_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    master_img.save(OUTPUT_DIR / "icon.ico", format="ICO", sizes=ico_sizes)
    master_img.save(OUTPUT_DIR / "favicon.ico", format="ICO", sizes=[(48, 48), (32, 32), (16, 16)])

    # macOS ICNS generation using iconutil
    print("Compiling macOS icon.icns via iconutil...")
    iconset_dir = OUTPUT_DIR / "icon.iconset"
    iconset_dir.mkdir(exist_ok=True)
    
    iconset_mappings = [
        (16, "icon_16x16.png"),
        (32, "icon_16x16@2x.png"),
        (32, "icon_32x32.png"),
        (64, "icon_32x32@2x.png"),
        (128, "icon_128x128.png"),
        (256, "icon_128x128@2x.png"),
        (256, "icon_256x256.png"),
        (512, "icon_256x256@2x.png"),
        (512, "icon_512x512.png"),
        (1024, "icon_512x512@2x.png"),
    ]

    for dim, name in iconset_mappings:
        im = master_img.resize((dim, dim), Image.Resampling.LANCZOS)
        im.save(iconset_dir / name, format="PNG")

    subprocess.run(["iconutil", "-c", "icns", str(iconset_dir), "-o", str(OUTPUT_DIR / "icon.icns")], check=True)
    subprocess.run(["rm", "-rf", str(iconset_dir)], check=True)

    print(f"All brand assets generated successfully into: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

