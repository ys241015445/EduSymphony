"""Matte Seedream pet sprites: opaque JPG/PNG → transparent RGBA PNG.

Usage (from backend/):
  python scripts/matte_pet_sprites.py --delete-source
  python scripts/matte_pet_sprites.py --only lesson_optimizer

Also importable: matte_file(src) -> Path | None
"""
from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
OUT = REPO / "frontend" / "public" / "pets"

DEFAULT_TOLERANCE = 48
FEATHER_SPAN = 16
ERODE_BG = 2


def _dilate(mask: np.ndarray, iterations: int) -> np.ndarray:
    out = mask.copy()
    for _ in range(max(0, iterations)):
        padded = np.pad(out, 1, mode="constant", constant_values=False)
        out = (
            padded[:-2, 1:-1]
            | padded[2:, 1:-1]
            | padded[1:-1, :-2]
            | padded[1:-1, 2:]
            | padded[:-2, :-2]
            | padded[:-2, 2:]
            | padded[2:, :-2]
            | padded[2:, 2:]
            | out
        )
    return out


def matte_rgba(
    im: Image.Image,
    tolerance: int = DEFAULT_TOLERANCE,
    feather_span: int = FEATHER_SPAN,
    erode: int = ERODE_BG,
) -> Image.Image:
    """Edge flood-fill of studio background; light dilate removes JPEG white halo."""
    base = im.convert("RGBA")
    arr = np.asarray(base).astype(np.float32)
    a = arr[:, :, 3:4] / 255.0
    # Flatten onto sampled-ish white only for distance; keep original RGB for output
    rgb = (arr[:, :, :3] * a + 250.0 * (1.0 - a)).astype(np.int16)
    h, w, _ = rgb.shape

    corners = np.array(
        [
            rgb[2, 2],
            rgb[2, w - 3],
            rgb[h - 3, 2],
            rgb[h - 3, w - 3],
            rgb[2, w // 8],
            rgb[2, w - w // 8],
        ],
        dtype=np.int16,
    )
    bg = corners.mean(axis=0)

    dist = np.abs(rgb - bg).sum(axis=2)
    lum = rgb.mean(axis=2)
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    near = (dist <= tolerance) | ((lum >= 225) & (chroma <= 24) & (dist <= tolerance + 20))

    mask = np.zeros((h, w), dtype=bool)
    q: deque[tuple[int, int]] = deque()

    def seed(y: int, x: int) -> None:
        if not mask[y, x] and near[y, x]:
            mask[y, x] = True
            q.append((y, x))

    for x in range(w):
        seed(0, x)
        seed(h - 1, x)
    for y in range(h):
        seed(y, 0)
        seed(y, w - 1)

    while q:
        y, x = q.popleft()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w and not mask[ny, nx] and near[ny, nx]:
                mask[ny, nx] = True
                q.append((ny, nx))

    mask = _dilate(mask, erode)

    # Soft floor plate under feet only (very light, low chroma, lower band)
    lower = np.zeros((h, w), dtype=bool)
    lower[int(h * 0.72) :, :] = True
    soft_floor = lower & (lum >= 205) & (chroma <= 30)
    for _ in range(48):
        grow = _dilate(mask, 1) & soft_floor & (~mask)
        if not grow.any():
            break
        mask |= grow

    alpha = np.full((h, w), 255, dtype=np.uint8)
    alpha[mask] = 0
    fringe = (~mask) & (dist <= tolerance + feather_span)
    if fringe.any():
        t = (dist[fringe].astype(np.float32) - tolerance) / max(1.0, float(feather_span))
        alpha[fringe] = np.clip(t * 255.0, 0, 255).astype(np.uint8)

    src_rgb = np.asarray(base.convert("RGB"), dtype=np.uint8)
    return Image.fromarray(np.dstack([src_rgb, alpha]), "RGBA")


def matte_file(
    src: Path,
    *,
    tolerance: int = DEFAULT_TOLERANCE,
    delete_source: bool = False,
) -> Path | None:
    if not src.exists() or src.stat().st_size < 500:
        return None
    try:
        with Image.open(src) as im:
            matted = matte_rgba(im, tolerance=tolerance)
    except Exception as e:
        print(f"  matte fail {src}: {e}", flush=True)
        return None

    dest = src.with_suffix(".png")
    matted.save(dest, "PNG", optimize=True)
    if delete_source:
        for stale in (".jpg", ".jpeg", ".webp"):
            sib = dest.with_suffix(stale)
            if sib.exists():
                sib.unlink(missing_ok=True)
        if src.suffix.lower() != ".png" and src.exists():
            src.unlink(missing_ok=True)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="Only one spriteKey folder")
    ap.add_argument("--delete-source", action="store_true")
    ap.add_argument("--tolerance", type=int, default=DEFAULT_TOLERANCE)
    args = ap.parse_args()

    if not OUT.exists():
        print(f"missing {OUT}")
        return 1

    roots = [OUT / args.only] if args.only else [d for d in OUT.iterdir() if d.is_dir()]
    ok = 0
    fail = 0
    for folder in roots:
        if not folder.is_dir():
            continue
        stems = sorted(
            {
                p.stem
                for p in folder.glob("*.*")
                if p.suffix.lower() in {".jpg", ".jpeg", ".webp", ".png"}
            }
        )
        for stem in stems:
            # Prefer opaque sources (jpg) over already-matted png
            pick = next(
                (
                    folder / f"{stem}{e}"
                    for e in (".jpg", ".jpeg", ".webp", ".png")
                    if (folder / f"{stem}{e}").exists()
                ),
                None,
            )
            if not pick:
                continue
            print(f"[{folder.name}/{stem}] matting {pick.name}…", flush=True)
            out = matte_file(pick, tolerance=args.tolerance, delete_source=args.delete_source)
            if out:
                if args.delete_source or pick.suffix.lower() in (".jpg", ".jpeg", ".webp"):
                    for stale in (".jpg", ".jpeg", ".webp"):
                        sib = folder / f"{stem}{stale}"
                        if sib.exists():
                            sib.unlink(missing_ok=True)
                print(f"  -> {out.name}", flush=True)
                ok += 1
            else:
                fail += 1

    print(f"done ok={ok} fail={fail}", flush=True)
    return 0 if ok > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
