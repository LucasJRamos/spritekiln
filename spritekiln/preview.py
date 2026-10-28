"""How a sprite reads in the game: over a background image, under the scene's light; and how big a preview is.

Only previews use this (pose, GIFs, contact sheets, review); atlases are never tinted or cropped.
"""

import numpy as np
from PIL import Image

from .errors import SpriteKilnError

# AI clients shrink a larger image by a factor that is rarely a whole number (Claude: above about 1568 px on
# the long side or about 1.15 megapixels), which distorts pixel art: uneven pixels, broken outlines. Previews
# are zoomed by whole factors that fit this budget, and cropped to what the sprite shows.
MAX_SIDE = 1536
MAX_AREA = 1_150_000
MARGIN = 2  # px of the frame kept around the sprite when cropping


def content_box(frames, margin=MARGIN):
    """(y0, y1, x0, x1): the union of the non-transparent pixels of same-sized `frames`, grown by `margin` and
    kept inside the frame. The whole frame when they are empty, or opaque everywhere (drawn over a floor)."""
    h, w = frames[0].shape[:2]
    seen = np.zeros((h, w), bool)
    for f in frames:
        seen |= f[..., 3] > 0
    if not seen.any() or seen.all():
        return 0, h, 0, w
    ys, xs = np.nonzero(seen.any(1))[0], np.nonzero(seen.any(0))[0]
    return (
        max(0, int(ys[0]) - margin),
        min(h, int(ys[-1]) + 1 + margin),
        max(0, int(xs[0]) - margin),
        min(w, int(xs[-1]) + 1 + margin),
    )


def crop(frames, box):
    y0, y1, x0, x1 = box
    return [f[y0:y1, x0:x1] for f in frames]


def fit_scale(size_at, want, max_side=MAX_SIDE, max_area=MAX_AREA):
    """The largest whole zoom from `want` down to 1 at which the image fits the budget. `size_at(k)` gives the
    image's (width, height) at zoom k. At zoom 1 it may still be too large: callers then split, never shrink."""
    k = max(1, int(want))
    while k > 1:
        w, h = size_at(k)
        if max(w, h) <= max_side and w * h <= max_area:
            break
        k -= 1
    return k


def tiles(im, max_side=MAX_SIDE, max_area=MAX_AREA):
    """A PIL image cut into pieces within the budget, row by row, without resampling (one piece if it fits)."""
    W, H = im.size
    tw, th = min(W, max_side), min(H, max_side)
    while tw * th > max_area:
        if tw >= th:
            tw = max(1, max_area // th)
        else:
            th = max(1, max_area // tw)
    return [im.crop((x, y, min(x + tw, W), min(y + th, H))) for y in range(0, H, th) for x in range(0, W, tw)]


def parse_tint(text):
    """'0.68,0.71,1.02' (RGB multipliers) or '#aeb5ff' (a light colour, 255 = unchanged) -> (r, g, b)."""
    if text is None:
        return None
    t = str(text).strip()
    try:
        if t.startswith('#') and len(t) == 7:
            return tuple(int(t[i : i + 2], 16) / 255 for i in (1, 3, 5))
        vals = [float(v) for v in t.replace(';', ',').split(',')]
    except ValueError:
        vals = []
    if len(vals) == 1:
        vals *= 3
    if len(vals) != 3 or min(vals) < 0:
        raise SpriteKilnError(f'--tint {text}: use three multipliers like 0.7,0.7,1.0 or a colour like #b3b5ff')
    return tuple(vals)


def load_background(path):
    try:
        return np.asarray(Image.open(path).convert('RGBA'))
    except (OSError, ValueError) as e:
        raise SpriteKilnError(f'--bg {path}: cannot read the image ({e})') from None


def tint(img, k, emissive=None):
    """Multiply the colour of lit pixels by the scene light `k`; emissive pixels keep their colour."""
    if not k:
        return img
    out = img.copy()
    rgb = np.clip(img[..., :3].astype(float) * np.asarray(k, float), 0, 255).astype(np.uint8)
    lit = img[..., 3] > 0
    if emissive is not None:
        lit &= emissive[..., 3] == 0
    out[..., :3] = np.where(lit[..., None], rgb, img[..., :3])
    return out


def backdrop(bg, h, w):
    """`bg` tiled from its top-left corner to h x w (opaque)."""
    reps = (-(-h // bg.shape[0]), -(-w // bg.shape[1]), 1)
    tiled = np.tile(bg, reps)[:h, :w].copy()
    tiled[..., 3] = 255
    return tiled


def over(img, bg):
    """Alpha-composite an RGBA sprite (or strip) over `bg` tiled to its size."""
    base = Image.fromarray(backdrop(bg, *img.shape[:2]))
    base.alpha_composite(Image.fromarray(img))
    return np.asarray(base)


def viewer(bg=None, k=None):
    """Callable(img, emissive=None) -> how the frame looks in the game (None when no option is set)."""
    if bg is None and not k:
        return None

    def look(img, emissive=None):
        lit = tint(img, k, emissive)
        return over(lit, bg) if bg is not None else lit

    return look
