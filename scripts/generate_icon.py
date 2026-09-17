# -*- coding: utf-8 -*-
"""
High-Definition Stark Arc Reactor & J.A.R.V.I.S. Core Icon Generator.
Renders a multi-layer futuristic cyberpunk Arc Reactor icon using Pillow (PIL)
at 1024x1024 master resolution and outputs crisp multi-resolution .ico and .png assets.
"""
import os
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
ICO_PATH = CONFIG_DIR / "jarvis.ico"
PNG_PATH = CONFIG_DIR / "jarvis.png"

def draw_arc_reactor(master_size=1024) -> Image.Image:
    """Draw the master 1024x1024 Arc Reactor image with anti-aliasing and glows."""
    S = master_size
    cx = cy = S // 2
    R = S // 2 - 16

    # Transparent base
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 1. Outer Dark Titanium Housing / Bezel
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(3, 10, 18, 255))
    
    # Outer cyan/steel rim
    bezel_w = max(4, S // 55)
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=(0, 212, 255, 230), width=bezel_w)

    # 2. Outer Technical Calibration Notches (36 tick marks)
    for i in range(36):
        angle = math.radians(i * 10)
        is_major = (i % 3 == 0)
        t_len = S // 30 if is_major else S // 55
        t_w = max(2, S // 250 if not is_major else S // 180)
        t_col = (220, 245, 255, 240) if is_major else (0, 170, 220, 160)
        x1 = cx + int((R - bezel_w - 4) * math.cos(angle))
        y1 = cy + int((R - bezel_w - 4) * math.sin(angle))
        x2 = cx + int((R - bezel_w - 4 - t_len) * math.cos(angle))
        y2 = cy + int((R - bezel_w - 4 - t_len) * math.sin(angle))
        d.line([x1, y1, x2, y2], fill=t_col, width=t_w)

    # 3. Magnetic Coil Channel (Dark Groove)
    R_coil_outer = int(R * 0.82)
    R_coil_inner = int(R * 0.58)
    d.ellipse([cx - R_coil_outer, cy - R_coil_outer, cx + R_coil_outer, cy + R_coil_outer],
              outline=(0, 80, 110, 180), width=max(2, S // 150))
    d.ellipse([cx - R_coil_inner, cy - R_coil_inner, cx + R_coil_inner, cy + R_coil_inner],
              outline=(0, 140, 180, 200), width=max(2, S // 150))

    # 4. 10 Copper Electromagnetic Power Coils
    num_coils = 10
    coil_span = 24  # degrees per coil
    for i in range(num_coils):
        center_ang = i * (360 / num_coils)
        pts = []
        for step in range(7):
            cur_a = math.radians(center_ang - coil_span / 2 + step * (coil_span / 6))
            pts.append((cx + int(R_coil_outer * math.cos(cur_a)),
                        cy + int(R_coil_outer * math.sin(cur_a))))
        for step in range(7):
            cur_a = math.radians(center_ang + coil_span / 2 - step * (coil_span / 6))
            pts.append((cx + int(R_coil_inner * math.cos(cur_a)),
                        cy + int(R_coil_inner * math.sin(cur_a))))
        
        # Copper/Gold coil fill
        d.polygon(pts, fill=(215, 120, 25, 250), outline=(255, 185, 70, 255))

        # Winding wire accents inside the coil
        for w_idx in (-6, 0, 6):
            w_ang = math.radians(center_ang + w_idx)
            wx1 = cx + int(R_coil_inner * math.cos(w_ang))
            wy1 = cy + int(R_coil_inner * math.sin(w_ang))
            wx2 = cx + int(R_coil_outer * math.cos(w_ang))
            wy2 = cy + int(R_coil_outer * math.sin(w_ang))
            d.line([wx1, wy1, wx2, wy2], fill=(255, 215, 120, 255), width=max(1, S // 300))

    # 5. Energy Glow Layer (Cyan / Neon Blue Ambient Bloom)
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    R_glow = int(R * 0.54)
    gd.ellipse([cx - R_glow, cy - R_glow, cx + R_glow, cy + R_glow], fill=(0, 212, 255, 130))
    R_mid = int(R * 0.38)
    gd.ellipse([cx - R_mid, cy - R_mid, cx + R_mid, cy + R_mid], fill=(0, 140, 255, 180))
    R_hot = int(R * 0.22)
    gd.ellipse([cx - R_hot, cy - R_hot, cx + R_hot, cy + R_hot], fill=(160, 240, 255, 240))
    glow = glow.filter(ImageFilter.GaussianBlur(S // 28))
    img = Image.alpha_composite(img, glow)
    d = ImageDraw.Draw(img)

    # 6. High-Tech Concentric Energy Rings
    d.ellipse([cx - R_glow, cy - R_glow, cx + R_glow, cy + R_glow],
              outline=(0, 240, 255, 230), width=max(3, S // 100))
    R_ring2 = int(R * 0.44)
    d.ellipse([cx - R_ring2, cy - R_ring2, cx + R_ring2, cy + R_ring2],
              outline=(0, 180, 240, 210), width=max(2, S // 160))
    R_ring3 = int(R * 0.32)
    d.ellipse([cx - R_ring3, cy - R_ring3, cx + R_ring3, cy + R_ring3],
              outline=(120, 230, 255, 240), width=max(2, S // 130))

    # 7. 6 Radial Tri-vanes / Flux Guides
    for i in range(6):
        ang = math.radians(i * 60 + 30)
        vx1 = cx + int((R_ring3 - 2) * math.cos(ang))
        vy1 = cy + int((R_ring3 - 2) * math.sin(ang))
        vx2 = cx + int((R_ring2 + 4) * math.cos(ang))
        vy2 = cy + int((R_ring2 + 4) * math.sin(ang))
        d.line([vx1, vy1, vx2, vy2], fill=(255, 255, 255, 230), width=max(2, S // 160))

    # 8. Blazing Quantum Fusion Core (White-Hot Center)
    R_core = int(R * 0.18)
    d.ellipse([cx - R_core, cy - R_core, cx + R_core, cy + R_core], fill=(240, 252, 255, 255))
    R_core_inner = int(R * 0.10)
    d.ellipse([cx - R_core_inner, cy - R_core_inner, cx + R_core_inner, cy + R_core_inner], fill=(255, 255, 255, 255))

    return img

def build_assets():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    print("[*] Generating High-Definition Stark Arc Reactor master (1024x1024)...")
    master = draw_arc_reactor(1024)

    # Save 512x512 PNG master
    png_img = master.resize((512, 512), Image.LANCZOS)
    png_img.save(PNG_PATH, format="PNG")
    print(f"  [OK] Saved high-res PNG: {PNG_PATH}")

    # Multi-resolution frames for Windows .ico: 256, 128, 64, 48, 32, 16
    sizes = [256, 128, 64, 48, 32, 16]
    frames = [master.resize((s, s), Image.LANCZOS) for s in sizes]

    frames[0].save(
        ICO_PATH,
        format="ICO",
        append_images=frames[1:],
        sizes=[(s, s) for s in sizes]
    )
    print(f"  [OK] Saved multi-resolution ICO (256..16px): {ICO_PATH}")

if __name__ == "__main__":
    build_assets()
