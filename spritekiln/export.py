"""Atlas + JSON (Aseprite-compatible, plus the `spritekiln` block of docs/format.md) + GIFs + contact sheets."""
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import __version__
from .anim import is_loop

FORMAT = 1           # output format version (docs/format.md); bump only on breaking changes

BG = (46, 42, 56, 255)


def upscale(img, k, bg=BG):
    im = Image.fromarray(img).resize((img.shape[1] * k, img.shape[0] * k), Image.NEAREST)
    if bg is None:
        return im
    b = Image.new('RGBA', im.size, bg); b.alpha_composite(im)
    return b


def save_gif(path, frames_rgba, durs, k=5):
    ims = [upscale(f, k).convert('RGB') for f in frames_rgba]
    pal = [im.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for im in ims]
    pal[0].save(path, save_all=True, append_images=pal[1:], duration=[int(d) for d in durs], loop=0,
                disposal=1, optimize=False)


_FONT = None


def font():
    global _FONT
    if _FONT is None:
        try:
            _FONT = ImageFont.load_default(size=12)      # Pillow >= 10.1: TrueType, has accents
        except Exception:  # noqa
            _FONT = ImageFont.load_default()
    return _FONT


def _ascii(t):
    import unicodedata
    return unicodedata.normalize('NFKD', str(t)).encode('ascii', 'ignore').decode()


def label(im, text, xy, fill=(230, 225, 235, 255)):
    d = ImageDraw.Draw(im)
    d.text(xy, _ascii(text), fill=fill, font=font())


def contact_sheet(rows, row_labels, col_count, S, k=3):
    """rows: list of lists of RGBA frames."""
    pad = 18
    W = pad * 3 + col_count * S * k
    H = pad + len(rows) * (S * k + 4)
    im = Image.new('RGBA', (W, H), BG)
    for r, (frames, lab) in enumerate(zip(rows, row_labels)):
        y = pad + r * (S * k + 4)
        label(im, lab, (2, y + 2))
        for c, f in enumerate(frames):
            x = pad * 3 + c * S * k
            im.alpha_composite(upscale(f, k, None), (x, y))
    for c in range(col_count):
        label(im, str(c), (pad * 3 + c * S * k + 2, 3))
    return im


def camera_info(spec, cam):
    """How world units map to pixels (docs/format.md, 'camera')."""
    p = np.radians(spec['camera']['pitch'])
    return {'projection': 'orthographic', 'pitch_deg': float(spec['camera']['pitch']),
            'world_units_per_px': cam.scale, 'px_per_unit': round(1 / cam.scale, 4),
            'ground_k': round(float(np.sin(p)), 4), 'height_k': round(float(np.cos(p)), 4),
            'center': [float(c) for c in cam.center]}


def export(spec, anims, dlist, out, dst, gif_scale=5, block='spritekiln'):
    """Write atlases, JSON and previews. `block`: key of the exporter's JSON block ('pxforge' for projects
    whose runtime predates the rename)."""
    os.makedirs(dst, exist_ok=True)
    pv = os.path.join(dst, 'preview'); os.makedirs(pv, exist_ok=True)
    S = spec['size']; name = spec['name']
    rows = [(a, d) for a in anims for d, _ in dlist]
    cols = max(len([k for k in out if k[0] == a and k[1] == dlist[0][0]]) for a in anims)
    atl = {m: np.zeros((len(rows) * S, cols * S, 4), np.uint8) for m in ('color', 'normal', 'emissive')}
    from .render import Camera
    cam = Camera.from_spec(spec)
    px, py = cam.project([0, 0, 0])
    meta = {'frames': {}, 'meta': {'app': 'spritekiln', 'version': __version__, 'image': f'{name}.png',
                                   'format': 'RGBA8888', 'size': {'w': cols * S, 'h': len(rows) * S},
                                   'scale': '1', 'frameTags': []},
            block: {'format': FORMAT, 'generator': f'spritekiln {__version__}',
                    'name': name, 'frame_size': S, 'pivot': {'x': round(px, 2), 'y': round(py, 2)},
                    'directions': [d for d, _ in dlist], 'direction_yaw': {d: y for d, y in dlist},
                    'camera': camera_info(spec, cam), 'normal_map': f'{name}_normal.png',
                    'emissive_map': f'{name}_emissive.png', 'animations': {}}}
    idx = 0
    for r, (a, d) in enumerate(rows):
        n = len([k for k in out if k[0] == a and k[1] == d])
        loop = is_loop(spec['animations'][a])
        meta['meta']['frameTags'].append({'name': f'{a}_{d}', 'from': idx, 'to': idx + n - 1,
                                          'direction': 'forward'})
        A = meta[block]['animations'].setdefault(a, {'loop': loop, 'directions': {}})
        names, durs, events = [], [], {}
        for i in range(n):
            img, nm, em, ms, ev = out[(a, d, i)]
            ys, xs = r * S, i * S
            atl['color'][ys:ys + S, xs:xs + S] = img
            if nm is not None:
                atl['normal'][ys:ys + S, xs:xs + S] = nm
                atl['emissive'][ys:ys + S, xs:xs + S] = em
            key = f'{a}_{d}_{i}'
            meta['frames'][key] = {'frame': {'x': xs, 'y': ys, 'w': S, 'h': S}, 'rotated': False,
                                   'trimmed': False, 'spriteSourceSize': {'x': 0, 'y': 0, 'w': S, 'h': S},
                                   'sourceSize': {'w': S, 'h': S}, 'duration': int(ms)}
            names.append(key); durs.append(int(ms))
            if ev:
                events[i] = ev
            idx += 1
        A['directions'][d] = {'row': r, 'frames': names, 'durations': durs, 'events': events}
    Image.fromarray(atl['color']).save(os.path.join(dst, f'{name}.png'))
    Image.fromarray(atl['normal']).save(os.path.join(dst, f'{name}_normal.png'))
    Image.fromarray(atl['emissive']).save(os.path.join(dst, f'{name}_emissive.png'))
    with open(os.path.join(dst, f'{name}.json'), 'w', encoding='utf-8') as fh:
        json.dump(meta, fh, indent=1)
    # previews
    for a in anims:
        n = len([k for k in out if k[0] == a and k[1] == dlist[0][0]])
        durs = [out[(a, dlist[0][0], i)][3] for i in range(n)]
        strip = [np.concatenate([out[(a, d, i)][0] for d, _ in dlist], 1) for i in range(n)]
        save_gif(os.path.join(pv, f'{a}_{len(dlist)}dir.gif'), strip, durs, gif_scale if len(dlist) <= 4 else 3)
        sheet = contact_sheet([[out[(a, d, i)][0] for i in range(n)] for d, _ in dlist],
                              [d for d, _ in dlist], n, S, 3)
        sheet.save(os.path.join(pv, f'contact_{a}.png'))
    return meta
