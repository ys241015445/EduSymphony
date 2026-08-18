"""Offline Seedream sprite generator for ExpertPetArena (character bible + 8 poses).

Usage (from backend/ with .env loaded):
  python scripts/gen_pet_sprites.py
  python scripts/gen_pet_sprites.py --only lesson_optimizer   # one role
  python scripts/gen_pet_sprites.py --skip-existing

Writes image files to frontend/public/pets/{spriteKey}/{pose}.png (auto-matted RGBA)
Requires DOUBAO_API_KEY + DOUBAO_IMAGE_MODEL.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
OUT = REPO / "frontend" / "public" / "pets"
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

from app.core.config import settings  # noqa: E402
from app.services.ai_service import AIService  # noqa: E402
from matte_pet_sprites import matte_file  # noqa: E402

STYLE_LOCK = (
    "Style lock (MUST match every frame of this character): chibi desktop-pet mascot, "
    "cute three-head-tall proportions, soft cel-shaded illustration, rounded shapes, "
    "clean single character centered, soft studio lighting, pure transparent background, "
    "NO text, NO watermark, NO logo, NO UI chrome, NO extra animals, square 1:1 composition, "
    "high clarity game-sprite look, consistent face and outfit across poses."
)

# bible: shared identity prefix per role
CHARACTERS: list[dict] = [
    {
        "key": "lesson_optimizer",
        "bible": (
            "Wise owl teacher mascot named 'Owl Optimizer'. Round big eyes with gold spectacles, "
            "soft blue academic scarf, tiny chalk in wing, warm brown-cream feathers, calm smile."
        ),
    },
    {
        "key": "student_engagement",
        "bible": (
            "Playful fox teacher mascot named 'Fox Engage'. Orange-purple fur accents, purple hoodie, "
            "star sticker on cheek, energetic grin, fluffy tail curled."
        ),
    },
    {
        "key": "innovative_teaching",
        "bible": (
            "Energetic rabbit teacher mascot named 'Bunny Innovate'. Cream fur, amber sweater, "
            "lightbulb pin on chest, long ears up, curious sparkle eyes."
        ),
    },
    {
        "key": "deep_learning",
        "bible": (
            "Thoughtful dolphin teacher mascot named 'Dolphin Deep'. Smooth teal-green body, "
            "small backpack with books, gentle eyes, friendly smile, standing upright chibi pose."
        ),
    },
    {
        "key": "cognitive_development",
        "bible": (
            "Curious cat teacher mascot named 'Kitty Cogni'. Soft rose-pink accents, tiny headset, "
            "question-mark yarn ball prop, big sparkling eyes, cream fur."
        ),
    },
    {
        "key": "moderator",
        "bible": (
            "Calm bear moderator mascot named 'Bear Host'. Indigo necktie, round glasses, "
            "clipboard under arm, warm brown fur, reassuring smile."
        ),
    },
    {
        "key": "writer",
        "bible": (
            "Gentle deer writer mascot named 'Deer Scribe'. Teal scarf, fountain pen in hoof, "
            "soft tan fur, antlers with tiny leaf, serene expression."
        ),
    },
]

POSES: dict[str, str] = {
    "idle": "standing idle, soft smile, looking forward, relaxed arms at sides",
    "listen": "listening attentively, head tilted slightly, eyes focused toward the side",
    "think": "thinking pose, one paw on chin, small thought dots above head (no readable text)",
    "speak": "speaking enthusiastically, mouth open, one paw raised explaining",
    "walk": "mid-step walking toward viewer-left, lively motion, same outfit",
    "vote_yes": "raising a small green check placard, approving gesture, happy",
    "vote_no": "raising a small red cross placard, polite disagreeing gesture",
    "cheer": "cheering happily, both paws up, celebratory bounce, sparkles (no text)",
}


def _prompt(bible: str, pose_desc: str) -> str:
    return f"{STYLE_LOCK} Character bible: {bible} Pose for this frame: {pose_desc}."


def _save_data_url(data_url: str, path: Path) -> bool:
    m = re.match(r"^data:image/(\w+);base64,(.+)$", data_url, re.S)
    if not m:
        return False
    ext = m.group(1).lower()
    if ext == "jpeg":
        ext = "jpg"
    raw = base64.b64decode(m.group(2))
    path.parent.mkdir(parents=True, exist_ok=True)
    out = path.with_suffix(f".{ext}")
    # Remove stale sibling extensions so probes stay unambiguous
    for stale in (".png", ".jpg", ".jpeg", ".webp"):
        sibling = path.with_suffix(stale)
        if sibling != out and sibling.exists():
            sibling.unlink()
    out.write_bytes(raw)
    print(f"  wrote {out} ({len(raw)} bytes)", flush=True)
    try:
        matted = matte_file(out, delete_source=True)
        if matted:
            print(f"  matted {matted.name}", flush=True)
    except Exception as e:
        print(f"  matte skipped: {e}", flush=True)
    return True


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="Only generate one spriteKey")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--poses", help="Comma-separated pose subset")
    args = ap.parse_args()

    if not settings.DOUBAO_IMAGE_MODEL:
        print("DOUBAO_IMAGE_MODEL empty — abort")
        return 1

    pose_keys = list(POSES.keys())
    if args.poses:
        pose_keys = [p.strip() for p in args.poses.split(",") if p.strip() in POSES]

    chars = CHARACTERS
    if args.only:
        chars = [c for c in CHARACTERS if c["key"] == args.only]
        if not chars:
            print(f"unknown key {args.only}")
            return 1

    ai = AIService()
    print(f"OUT={OUT} model={settings.DOUBAO_IMAGE_MODEL} roles={len(chars)} poses={pose_keys}", flush=True)

    def _exists(key: str, pose: str) -> Path | None:
        base = OUT / key / pose
        for ext in (".png", ".jpg", ".webp", ".jpeg"):
            p = base.with_suffix(ext)
            if p.exists() and p.stat().st_size > 1000:
                return p
        return None

    ok = 0
    fail = 0
    for ch in chars:
        key = ch["key"]
        for pose in pose_keys:
            existing = _exists(key, pose)
            if args.skip_existing and existing is not None:
                print(f"[{key}/{pose}] skip existing", flush=True)
                ok += 1
                continue
            print(f"[{key}/{pose}] generating…", flush=True)
            url = await ai.generate_image(
                _prompt(ch["bible"], POSES[pose]),
                size="1024x1024",
            )
            if not url:
                print("  SKIP (empty)", flush=True)
                fail += 1
                continue
            if _save_data_url(url, OUT / key / pose):
                ok += 1
            else:
                print("  SKIP (bad data url)", flush=True)
                fail += 1
            await asyncio.sleep(0.4)

    print(f"done ok={ok} fail={fail}", flush=True)
    return 0 if ok > 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
