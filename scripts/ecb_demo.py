#!/usr/bin/env python3
"""Generate assets/images/security-vocabulary/ecb-demo.png.

Draws a flat-colour padlock, encrypts its raw pixel bytes with AES-128 in ECB mode and in
CTR mode (same key), and shows the three versions side by side. Real AES, no mock-up:
in ECB mode equal plaintext blocks give equal ciphertext blocks, so the outline survives.

    pip install cryptography pillow matplotlib
    python3 scripts/ecb_demo.py
"""
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from PIL import Image, ImageDraw

W = H = 192  # 192 * 192 * 3 bytes is a multiple of the 16-byte AES block size
OUT = Path(__file__).resolve().parent.parent / "assets" / "images" / "security-vocabulary" / "ecb-demo.png"


def draw_padlock() -> Image.Image:
    img = Image.new("RGB", (W, H), (32, 78, 140))
    d = ImageDraw.Draw(img)
    d.arc((48, 16, 144, 112), 180, 360, fill=(200, 200, 205), width=14)  # shackle
    d.rectangle((48, 64, 62, 100), fill=(200, 200, 205))
    d.rectangle((130, 64, 144, 100), fill=(200, 200, 205))
    d.rounded_rectangle((30, 92, 162, 172), radius=10, fill=(240, 180, 30))  # body
    d.ellipse((86, 115, 106, 135), fill=(30, 30, 30))  # keyhole
    d.polygon([(92, 130), (100, 130), (104, 155), (88, 155)], fill=(30, 30, 30))
    return img


def encrypt(raw: bytes, mode) -> bytes:
    enc = Cipher(algorithms.AES(KEY), mode).encryptor()
    return enc.update(raw) + enc.finalize()


raw = draw_padlock().tobytes()
assert len(raw) % 16 == 0
KEY = os.urandom(16)  # a fresh random key each run: the picture looks the same either way
ecb = encrypt(raw, modes.ECB())
ctr = encrypt(raw, modes.CTR(os.urandom(16)))

fig, axes = plt.subplots(1, 3, figsize=(9.6, 3.5), dpi=110)
for ax, (title, data) in zip(axes, [("Original", raw), ("AES-128, ECB mode", ecb), ("AES-128, CTR mode", ctr)]):
    ax.imshow(Image.frombytes("RGB", (W, H), data), interpolation="nearest")
    ax.set_title(title, fontsize=11)
    ax.axis("off")
plt.tight_layout()
OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT, facecolor="white")
print(f"wrote {OUT}")
