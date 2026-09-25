"""The social preview image: site/og.png, 1280x640 (8.7).

    python plan/findability-research/social_preview.py

GitHub's repository settings take it as the social preview (uploaded by
hand: Settings > General > Social preview), and build_docs.py copies it to
assets/og.png for the OpenGraph cards. It needs Pillow and the Windows fonts
it names, so it is run by a person, not by CI; the PNG it writes is what is
committed. The words are build_docs.HEADLINE, and one refusal the guides
show on every push.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import build_docs  # noqa: E402

W, H = 1280, 640
GREEN = (11, 107, 78)          # the favicon's green
INK = (255, 255, 255)
SOFT = (200, 230, 218)
PANEL = (7, 60, 45)
RED = (255, 160, 150)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(name, size)


def wrap(draw: ImageDraw.ImageDraw, text: str, face: ImageFont.FreeTypeFont,
         width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=face) <= width:
            line = trial
        else:
            lines.append(line)
            line = word
    lines.append(line)
    return lines


def main() -> int:
    img = Image.new("RGB", (W, H), GREEN)
    d = ImageDraw.Draw(img)
    d.text((80, 64), "Sabline", font=font("arialbd.ttf", 64), fill=INK)
    d.text((80, 140), "formerly Velaris  ·  sabline.dev",
           font=font("arial.ttf", 26), fill=SOFT)
    head = font("arialbd.ttf", 50)
    y = 210
    for line in wrap(d, build_docs.HEADLINE, head, W - 160):
        d.text((80, y), line, font=head, fill=INK)
        y += 64
    d.rounded_rectangle((80, 420, W - 80, 560), radius=14, fill=PANEL)
    mono = font("consola.ttf", 22)
    d.text((108, 442), "$ sabline changed_files.vel --allow io,net:api.github.com:443",
           font=mono, fill=SOFT)
    d.text((108, 480), "error[E314] 'post' reaches host 'collector.example.net',",
           font=mono, fill=RED)
    d.text((108, 512), "which this run does not allow", font=mono, fill=RED)
    out = ROOT / "site" / "og.png"
    img.save(out, optimize=True)
    print(f"wrote {out.relative_to(ROOT).as_posix()}: {W}x{H}, "
          f"{out.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
