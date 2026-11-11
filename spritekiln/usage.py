"""What SpriteKiln handed to an AI in a session, to measure a workflow before and after changing it.

Off unless the environment variable SPRITEKILN_USAGE names a file: then every CLI command and MCP tool call
appends one JSON line to it (the command, the bytes of text it printed or returned, the images it wrote or
returned with their sizes). `spritekiln usage` sums the file. The token figures are estimates (about 4 bytes of
text per token; an image costs about width x height / 750 tokens in Claude) for comparing two runs of the same
task, not a bill: the log cannot see what the AI read on its own (the docs, the spec, an image it did not open).
"""

import json
import os
import re
import time

ENV = 'SPRITEKILN_USAGE'
BYTES_PER_TOKEN = 4
PIXELS_PER_TOKEN = 750
_IMAGE = re.compile(r'[^\s,()]+\.(?:png|gif)\b', re.I)


def path():
    """The log file, or None when measuring is off."""
    return os.environ.get(ENV) or None


def image_size(p):
    from PIL import Image

    try:
        with Image.open(p) as im:
            return list(im.size)
    except (OSError, ValueError):
        return None


def images_in(text):
    """[[path, width, height]] of the image files a command's output names (previews it wrote)."""
    found = []
    for p in dict.fromkeys(_IMAGE.findall(text)):
        size = image_size(p) if os.path.isfile(p) else None
        if size:
            found.append([p, *size])
    return found


def log(kind, name, text_bytes=0, images=(), seconds=None):
    """Append one call to the log (a no-op when measuring is off). `images`: [[label, width, height]]."""
    dst = path()
    if not dst:
        return
    entry = dict(
        at=time.strftime('%Y-%m-%dT%H:%M:%S'),
        kind=kind,
        name=name,
        text_bytes=int(text_bytes),
        images=[list(i) for i in images],
    )
    if seconds is not None:
        entry['seconds'] = round(seconds, 2)
    try:
        os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
        with open(dst, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except OSError:
        pass  # measuring never breaks the work it measures


def tokens(text_bytes, images):
    return round(text_bytes / BYTES_PER_TOKEN) + sum(round(w * h / PIXELS_PER_TOKEN) for _, w, h in images)


def summary(dst):
    """{calls, text_bytes, images, tokens, seconds, by_name: {name: {...}}} of a log file."""
    total = dict(calls=0, text_bytes=0, images=0, tokens=0, seconds=0.0, by_name={})
    with open(dst, encoding='utf-8') as fh:
        for line in fh:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            t = tokens(e.get('text_bytes', 0), e.get('images') or [])
            row = total['by_name'].setdefault(
                f'{e.get("kind")} {e.get("name")}', dict(calls=0, text_bytes=0, images=0, tokens=0, seconds=0.0)
            )
            for r in (total, row):
                r['calls'] += 1
                r['text_bytes'] += e.get('text_bytes', 0)
                r['images'] += len(e.get('images') or [])
                r['tokens'] += t
                r['seconds'] = round(r['seconds'] + (e.get('seconds') or 0), 2)
    return total


class Tee:
    """A text stream that passes everything through and keeps a copy (what a CLI command printed)."""

    def __init__(self, stream):
        self.stream, self.parts = stream, []

    def write(self, text):
        self.parts.append(text)
        return self.stream.write(text)

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def text(self):
        return ''.join(self.parts)
