"""Build the showcase images from a render and its splash art.

    python tools/make_showcase.py specs/characters/huntress/huntress.yaml showcase/huntress [--anim idle]

Writes into the target folder:
  from_this_to_this.png  the splash art next to the sprite in 8 directions
  turnaround.gif         the animation playing once in each direction, turning around the character (4x)
Reads <spec dir>/out/<name>/ (run `spritekiln render` first) and <spec dir>/splash.png.
"""

import argparse
import json
import os
import sys

from PIL import Image

BG = (24, 22, 30, 255)
ORDER = ['s', 'se', 'e', 'ne', 'n', 'nw', 'w', 'sw']


def load(spec_path):
    folder = os.path.dirname(os.path.abspath(spec_path))
    name = os.path.splitext(os.path.basename(spec_path))[0]
    render = os.path.join(folder, 'out', name)
    with open(os.path.join(render, f'{name}.json'), encoding='utf-8') as fh:
        data = json.load(fh)
    block = data.get('spritekiln') or data['pxforge']
    atlas = Image.open(os.path.join(render, data['meta']['image'])).convert('RGBA')
    return folder, data, block, atlas


def frames(data, block, atlas, anim, direction):
    """[(image, ms)] of one clip (a mirrored direction is its twin flipped)."""
    twin = (block.get('mirrors') or {}).get(direction)
    clip = block['animations'][anim]['directions'][twin or direction]
    out = []
    for key, ms in zip(clip['frames'], clip['durations']):
        f = data['frames'][key]['frame']
        img = atlas.crop((f['x'], f['y'], f['x'] + f['w'], f['y'] + f['h']))
        out.append((img.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if twin else img, ms))
    return out


def on_bg(img, scale):
    big = img.resize((img.width * scale, img.height * scale), Image.Resampling.NEAREST)
    bg = Image.new('RGBA', big.size, BG)
    bg.alpha_composite(big)
    return bg


def bbox(images, pad=2):
    """The box around the opaque pixels of all images (same size), with a margin."""
    boxes = [img.getchannel('A').getbbox() for img in images]
    boxes = [b for b in boxes if b]
    w, h = images[0].size
    x0, y0 = max(0, min(b[0] for b in boxes) - pad), max(0, min(b[1] for b in boxes) - pad)
    x1, y1 = min(w, max(b[2] for b in boxes) + pad), min(h, max(b[3] for b in boxes) + pad)
    return x0, y0, x1, y1


def from_this_to_this(folder, data, block, atlas, anim, out, height=768):
    dirs = [d for d in ORDER if d in block['direction_yaw']]
    first = [frames(data, block, atlas, anim, d)[0][0] for d in dirs]
    box = bbox(first)
    crops = [img.crop(box) for img in first]
    cols = 4 if len(crops) > 4 else len(crops)
    rows = (len(crops) + cols - 1) // cols
    scale = max(1, height // rows // crops[0].height)
    cells = [on_bg(c, scale) for c in crops]
    cw, ch = cells[0].size
    sprites = Image.new('RGBA', (cols * cw, rows * ch), BG)
    for i, c in enumerate(cells):
        sprites.paste(c, ((i % cols) * cw, (i // cols) * ch))
    name = 'splash_alpha.png' if os.path.exists(os.path.join(folder, 'splash_alpha.png')) else 'splash.png'
    splash = Image.open(os.path.join(folder, name)).convert('RGBA')
    box = splash.getchannel('A').getbbox() or (0, 0, splash.width, splash.height)
    splash = splash.crop(box)
    splash = splash.resize(
        (round(splash.width * sprites.height * 0.94 / splash.height), round(sprites.height * 0.94)),
        Image.Resampling.LANCZOS,
    )
    gap = 64
    sheet = Image.new('RGBA', (gap + splash.width + gap + sprites.width, sprites.height), BG)
    sheet.alpha_composite(splash, (gap, (sprites.height - splash.height) // 2))
    mid, cy = gap + splash.width + gap // 2, sprites.height // 2  # an arrow between the two
    for i in range(16):
        for y in range(cy - 16 + i, cy + 16 - i):
            sheet.putpixel((mid - 8 + i, y), (200, 190, 220, 255))
    sheet.paste(sprites, (gap + splash.width + gap, 0))
    sheet.convert('RGB').save(os.path.join(out, 'from_this_to_this.png'), optimize=True)


def turnaround(data, block, atlas, anim, out, scale=4):
    clips = [frames(data, block, atlas, anim, d) for d in ORDER if d in block['direction_yaw']]
    box = bbox([img for clip in clips for img, _ in clip])
    imgs = [on_bg(img.crop(box), scale).convert('RGB') for clip in clips for img, _ in clip]
    durs = [ms for clip in clips for _, ms in clip]
    imgs[0].save(
        os.path.join(out, 'turnaround.gif'), save_all=True, append_images=imgs[1:], duration=durs, loop=0, optimize=True
    )


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('spec')
    p.add_argument('out')
    p.add_argument('--anim', default='idle')
    a = p.parse_args(argv)
    folder, data, block, atlas = load(a.spec)
    os.makedirs(a.out, exist_ok=True)
    from_this_to_this(folder, data, block, atlas, a.anim, a.out)
    turnaround(data, block, atlas, a.anim, a.out)
    print('wrote', os.path.join(a.out, 'from_this_to_this.png'), 'and turnaround.gif')


if __name__ == '__main__':
    sys.exit(main())
