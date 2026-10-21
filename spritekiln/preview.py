"""How a sprite reads in the game: over a background image, under the scene's light.

Only previews use this (pose, GIFs, contact sheets, review); atlases are never tinted.
"""

import numpy as np
from PIL import Image

from .errors import SpriteKilnError


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
