# -*- coding: utf-8 -*-
"""
Brand-New Custom J.A.R.V.I.S. AI Core & Quantum Arc Reactor Icon Generator.
Produces a bespoke, high-definition, multi-layer cyberpunk AI icon using Pillow.
Outputs crisp multi-resolution .ico (256, 128, 64, 48, 32, 16) and 512x512 master .png.
"""
import os
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
ICO_PATH = CONFIG_DIR / "jarvis.ico"
PNG_PATH = CONFIG_DIR / "jarvis.png"

def draw_futuristic_ai_core(size=1024) -> Image.Image:
    """Renders the 1024x1024 master custom J.A.R.V.I.S. AI Core icon."""
    S = size
    cx = cy = S // 2
    R = S // 2 - 20

    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ── 1. Outer Deep Obsidian / Titanium Chassis ─────────────────────────────
    d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(2, 8, 18, 255))
    
    # Outer neon cyan chamfered rim
    rim_w = max(4, S // 50)
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=(0, 220, 255, 240), width=rim_w)
    d.ellipse([cx - R + 6, cy - R + 6, cx + R - 6, cy + R - 6], outline=(0, 110, 160, 180), width=max(1, S // 200))

    # ── 2. Outer Technical Calibration Calipers (36 ticks + 12 chevrons) ───────
    for i in range(36):
        angle = math.radians(i * 10)
        is_major = (i % 3 == 0)
        t_len = S // 28 if is_major else S // 55
        t_w = max(2, S // 180 if is_major else S // 280)
        col = (230, 248, 255, 255) if is_major else (0, 160, 210, 160)
        x1 = cx + int((R - rim_w - 6) * math.cos(angle))
        y1 = cy + int((R - rim_w - 6) * math.sin(angle))
        x2 = cx + int((R - rim_w - 6 - t_len) * math.cos(angle))
        y2 = cy + int((R - rim_w - 6 - t_len) * math.sin(angle))
        d.line([x1, y1, x2, y2], fill=col, width=t_w)

    # ── 3. Electromagnetic Induction Groove ──────────────────────────────────
    R_coil_out = int(R * 0.81)
    R_coil_in  = int(R * 0.58)
    d.ellipse([cx - R_coil_out, cy - R_coil_out, cx + R_coil_out, cy + R_coil_out],
              outline=(0, 70, 100, 200), width=max(2, S // 160))
    d.ellipse([cx - R_coil_in, cy - R_coil_in, cx + R_coil_in, cy + R_coil_in],
              outline=(0, 130, 180, 220), width=max(2, S // 160))

    # ── 4. 12 Radiant Copper-Gold Electromagnetic Coils ──────────────────────
    num_coils = 12
    coil_arc = 20  # degrees
    for i in range(num_coils):
        center_ang = i * (360 / num_coils)
        pts = []
        for step in range(6):
            a = math.radians(center_ang - coil_arc / 2 + step * (coil_arc / 5))
            pts.append((cx + int(R_coil_out * math.cos(a)), cy + int(R_coil_out * math.sin(a))))
        for step in range(6):
            a = math.radians(center_ang + coil_arc / 2 - step * (coil_arc / 5))
            pts.append((cx + int(R_coil_in * math.cos(a)), cy + int(R_coil_in * math.sin(a))))

        # High-gloss copper/gold gradient feel
        d.polygon(pts, fill=(210, 115, 20, 255), outline=(255, 195, 75, 255))

        # Coil winding wire filaments
        for w_offset in (-5, 0, 5):
            wa = math.radians(center_ang + w_offset)
            wx1 = cx + int(R_coil_in * math.cos(wa))
            wy1 = cy + int(R_coil_in * math.sin(wa))
            wx2 = cx + int(R_coil_out * math.cos(wa))
            wy2 = cy + int(R_coil_out * math.sin(wa))
            d.line([wx1, wy1, wx2, wy2], fill=(255, 225, 135, 255), width=max(1, S // 280))

    # ── 5. Multi-Layer Holographic Blue/Cyan Bloom ───────────────────────────
    bloom = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bloom)
    R_b1 = int(R * 0.54)
    bd.ellipse([cx - R_b1, cy - R_b1, cx + R_b1, cy + R_b1], fill=(0, 210, 255, 140))
    R_b2 = int(R * 0.38)
    bd.ellipse([cx - R_b2, cy - R_b2, cx + R_b2, cy + R_b2], fill=(0, 120, 255, 190))
    R_b3 = int(R * 0.22)
    bd.ellipse([cx - R_b3, cy - R_b3, cx + R_b3, cy + R_b3], fill=(180, 245, 255, 240))
    bloom = bloom.filter(ImageFilter.GaussianBlur(S // 26))
    img = Image.alpha_composite(img, bloom)
    d = ImageDraw.Draw(img)

    # ── 6. Tri-Concentric Cyber Energy Rails ──────────────────────────────────
    d.ellipse([cx - R_b1, cy - R_b1, cx + R_b1, cy + R_b1],
              outline=(0, 245, 255, 240), width=max(3, S // 90))
    R_r2 = int(R * 0.44)
    d.ellipse([cx - R_r2, cy - R_r2, cx + R_r2, cy + R_r2],
              outline=(0, 175, 245, 220), width=max(2, S // 140))
    R_r3 = int(R * 0.30)
    d.ellipse([cx - R_r3, cy - R_r3, cx + R_r3, cy + R_r3],
              outline=(140, 235, 255, 250), width=max(2, S // 120))

    # ── 7. 6 Radial Magnetic Focus Vanes ─────────────────────────────────────
    for i in range(6):
        va = math.radians(i * 60)
        x1 = cx + int((R_r3 - 4) * math.cos(va))
        y1 = cy + int((R_r3 - 4) * math.sin(va))
        x2 = cx + int((R_r2 + 6) * math.cos(va))
        y2 = cy + int((R_r2 + 6) * math.sin(va))
        d.line([x1, y1, x2, y2], fill=(255, 255, 255, 240), width=max(2, S // 140))

    # ── 8. Blazing Quantum Fusion Core (White-Hot Laser Singularity) ─────────
    R_core = int(R * 0.17)
    d.ellipse([cx - R_core, cy - R_core, cx + R_core, cy + R_core], fill=(245, 252, 255, 255))
    R_hot = int(R * 0.09)
    d.ellipse([cx - R_hot, cy - R_hot, cx + R_hot, cy + R_hot], fill=(255, 255, 255, 255))

    # ── 9. Four-Point Holographic Cross Flare ────────────────────────────────
    flare_len = int(R * 0.28)
    d.line([cx - flare_len, cy, cx + flare_len, cy], fill=(255, 255, 255, 180), width=max(1, S // 260))
    d.line([cx, cy - flare_len, cx, cy + flare_len], fill=(255, 255, 255, 180), width=max(1, S // 260))

    return img

def build_assets():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Safely remove old icons if present
    for old_file in (ICO_PATH, PNG_PATH):
        if old_file.exists():
            try:
                old_file.unlink()
                print(f"  [-] Deleted old icon: {old_file.name}")
            except Exception as e:
                print(f"  [!] Note removing {old_file.name}: {e}")

    print("[*] Generating Brand-New Custom J.A.R.V.I.S. AI Core master (1024x1024)...")
    master = draw_futuristic_ai_core(1024)

    # 2. Master 512x512 PNG
    png_img = master.resize((512, 512), Image.LANCZOS)
    png_img.save(PNG_PATH, format="PNG")
    print(f"  [OK] Generated high-res PNG: {PNG_PATH}")

    # 3. Multi-resolution Windows .ico (256, 128, 64, 48, 32, 16)
    sizes = [256, 128, 64, 48, 32, 16]
    frames = [master.resize((s, s), Image.LANCZOS) for s in sizes]

    frames[0].save(
        ICO_PATH,
        format="ICO",
        append_images=frames[1:],
        sizes=[(s, s) for s in sizes]
    )
    print(f"  [OK] Generated multi-resolution ICO (256..16px): {ICO_PATH}")

if __name__ == "__main__":
    build_assets()
