# Expert pet sprites (Seedream offline + matted)

Layout: `{spriteKey}/{pose}.png` (RGBA transparent preferred)

Poses: `idle` · `listen` · `think` · `speak` · `walk` · `vote_yes` · `vote_no` · `cheer`

Generate then matte:

```bash
cd backend
python -u scripts/gen_pet_sprites.py --skip-existing   # auto-mattes after each save
# or rematte existing files:
python -u scripts/matte_pet_sprites.py --delete-source
```

Requires `DOUBAO_API_KEY` + `DOUBAO_IMAGE_MODEL` for generation. Without files, UI falls back to SVG pets.
