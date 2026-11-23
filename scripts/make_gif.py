"""Stitch captured room frames into an animated GIF.

ffmpeg is not required -- Pillow writes the GIF directly.

    python scripts/make_gif.py                      # runs/frames/*.png -> runs/factory.gif
    python scripts/make_gif.py --ms 1400 --width 900

Frames are ordered by filename, so capture them as f00_, f01_, ... The last frame is
held longer, because that is the one a viewer wants to read (the verdict).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRAMES = ROOT / "runs" / "frames"
OUT = ROOT / "runs" / "factory.gif"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=Path, default=FRAMES)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--ms", type=int, default=1200, help="ms per frame")
    ap.add_argument("--hold", type=int, default=4000, help="ms to hold the last frame")
    ap.add_argument("--width", type=int, default=1000, help="scale to this width")
    args = ap.parse_args()

    try:
        from PIL import Image
    except ImportError:
        print("Pillow is required: .venv/bin/pip install pillow", file=sys.stderr)
        return 2

    paths = sorted(p for p in args.frames.glob("*.png"))
    if not paths:
        print(f"no frames in {args.frames}", file=sys.stderr)
        return 2

    images = []
    for p in paths:
        im = Image.open(p).convert("RGB")
        if im.width > args.width:
            h = round(im.height * args.width / im.width)
            im = im.resize((args.width, h), Image.LANCZOS)
        images.append(im)

    # Pad every frame to the tallest, so the GIF does not jitter between sizes.
    w = max(i.width for i in images)
    h = max(i.height for i in images)
    padded = []
    for im in images:
        if im.size != (w, h):
            canvas = Image.new("RGB", (w, h), (255, 255, 255))
            canvas.paste(im, (0, 0))
            im = canvas
        padded.append(im)

    durations = [args.ms] * len(padded)
    durations[-1] = args.hold

    args.out.parent.mkdir(parents=True, exist_ok=True)
    padded[0].save(
        args.out,
        save_all=True,
        append_images=padded[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    size_mb = args.out.stat().st_size / 1_000_000
    print(f"wrote {args.out}  ({len(padded)} frames, {w}x{h}, {size_mb:.1f} MB)")
    if size_mb > 15:
        print("  note: over 15 MB -- consider --width 800 or fewer frames", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
