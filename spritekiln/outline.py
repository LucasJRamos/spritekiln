"""A map of a spec file and its blocks by path, so an AI reads what it edits instead of the whole file
(`spritekiln spec outline`, `spritekiln spec show`). Items a spec gets from its base (`extends`) or from a kit
(`use`) are listed with where they come from, and `show` prints their lines from that file."""

import difflib
import json
import os
import re
from collections import Counter

import yaml

from . import schema
from . import spec as specmod
from .errors import SpriteKilnError

ITEMIZED = ('parts', 'animations', 'ik', 'sockets')  # sections listed one item per line; others in one line
NAMES_W = 96  # characters of names listed on one line before "+N more"
SUMMARY_W = 100  # longer summaries are cut
SEP = '; '


def _text(path):
    try:
        with open(path, encoding='utf-8') as fh:
            return fh.read()
    except FileNotFoundError:
        raise SpriteKilnError(f'{path}: file not found') from None


def _blank_or_comment(line):
    s = line.strip()
    return not s or s.startswith('#')


def ranges(path):
    """{path tuple: (first, last)}: 1-based lines of every key and list item of a YAML file, from the key (with
    the comment lines right above it) to the last line of its value that is not blank or a comment."""
    text = _text(path)
    lines = text.split('\n')
    try:
        root = yaml.compose(text, Loader=specmod._Loader)
    except yaml.MarkedYAMLError as e:
        m = e.problem_mark
        raise SpriteKilnError(f'{path}:{m.line + 1}:{m.column + 1}: YAML syntax: {e.problem}') from None
    found = {}

    def last(first, end):
        # a block node ends where the next token starts: at a line's indentation means on an earlier line
        at_start = end.line >= len(lines) or end.column <= _indent(lines[end.line])
        hi = end.line if at_start else end.line + 1
        while hi > first and _blank_or_comment(lines[hi - 1]):
            hi -= 1
        return max(hi, first)

    def walk(node, p):
        if isinstance(node, yaml.MappingNode):
            for k, v in node.value:
                key = p + (str(k.value),)
                lo, col = k.start_mark.line, k.start_mark.column  # 0-based
                while lo > 0 and lines[lo - 1].strip().startswith('#') and _indent(lines[lo - 1]) == col:
                    lo -= 1
                found[key] = (lo + 1, last(k.start_mark.line + 1, v.end_mark))
                walk(v, key)
        elif isinstance(node, yaml.SequenceNode):
            for i, v in enumerate(node.value):
                found[p + (i,)] = (v.start_mark.line + 1, last(v.start_mark.line + 1, v.end_mark))
                walk(v, p + (i,))

    if root is not None:
        walk(root, ())
    return found


def _indent(line):
    return len(line) - len(line.lstrip(' '))


def _span(r):
    a, b = r
    return f'{a}-{b}' if b > a else str(a)


def _names(names):
    out, used = [], 0
    for n in names:
        if used + len(n) + 2 > NAMES_W and out:
            return ', '.join(out) + f' +{len(names) - len(out)} more'
        out.append(n)
        used += len(n) + 2
    return ', '.join(out)


def _part(name, part):
    bits = [f'material {part.get("material") or "/".join(part.get("materials") or [])}']
    if part.get('space'):
        bits.append(f'space {part["space"]}')
    kinds = Counter(next(iter(p)) for p in part.get('prims') or [] if isinstance(p, dict) and p)
    if kinds:
        bits.append(' '.join(f'{k}x{n}' if n > 1 else k for k, n in kinds.items()))
    if part.get('cut'):
        bits.append(f'{len(part["cut"])} cuts')
    paint = [p for p in part.get('paint') or [] if isinstance(p, dict)]
    if paint:
        from .paint import PATTERNS

        kinds = ' '.join(f'{next((k for k in PATTERNS if k in p), "?")} {p.get("material")}' for p in paint)
        bits.append(f'paint: {kinds}')
    if 'when' in part:
        bits.append('conditional')
    if specmod._SIDE.search(name):
        bits.append(f'+ mirror {specmod._SIDE.sub("_R", name)}')
    return SEP.join(bits)


def _animation(sp, name, a):
    from .anim import frames_of, is_loop

    try:
        frames = frames_of(sp, name, 0.0)
        timing = f'{len(frames)} frames, {sum(ms for _, ms, _ in frames):.0f} ms'
    except Exception:  # noqa: BLE001 - an outline still lists an animation that fails to evaluate
        timing = 'does not evaluate (run validate)'
    kind = f'{len(a["keys"])} keys' if isinstance(a, dict) and a.get('keys') else 'cycle'
    return f'{kind}, {timing}, {"loop" if is_loop(a) else "once"}'


def _ik(chain):
    return f'{chain.get("start")} -> {chain.get("end")}, target {chain.get("target")}'


def outline(path):
    """[{path, lines: [first, last], summary}] of a spec, in file order: the header keys in one item, each
    part, animation, IK chain and socket on its own, and the other sections as one line of names."""
    raw = specmod.yload(_text(path)) or {}
    if not isinstance(raw, dict):
        raise SpriteKilnError(f'{path}: spec must be a YAML mapping')
    rng = ranges(path)
    try:
        sp = specmod.load(path)
    except SpriteKilnError:
        sp = None  # still map the file; animation timings need a loadable spec
    items, header = [], []
    for key, value in raw.items():
        r = rng[(key,)]
        if key == 'use' and isinstance(value, list):  # kits: one line each
            kits = [f'{u.get("kit")} as {u.get("as", u.get("kit"))}' for u in value if isinstance(u, dict)]
            items.append(dict(path=key, lines=list(r), summary=f'{len(value)} kits: {", ".join(kits)}'))
            continue
        if not isinstance(value, dict):
            header.append((key, value, r))
            continue
        if key in ITEMIZED:
            items.append(dict(path=key, lines=list(r), summary=f'{len(value)} items'))
            for name, v in value.items():
                if key == 'parts':
                    summary = _part(name, v or {})
                elif key == 'animations':
                    summary = _animation(sp, name, v or {}) if sp else ''
                elif key == 'ik':
                    summary = _ik(v or {})
                else:
                    summary = SEP.join(f'{k} {v[k]}' for k in list(v or {})[:2])
                items.append(dict(path=f'{key}.{name}', lines=list(rng[(key, name)]), summary=summary))
        else:
            items.append(dict(path=key, lines=list(r), summary=f'{len(value)}: {_names(list(value))}'))
    if header:
        first = min(r[0] for _, _, r in header)
        last = max(r[1] for _, _, r in header)
        summary = SEP.join(f'{k} {v if not isinstance(v, list) else ",".join(map(str, v))}' for k, v, _ in header)
        items.insert(0, dict(path='(header)', lines=[first, last], summary=summary))
    if sp and sp.get('_origins') is not None and 'kit' not in raw:
        items = _with_inherited(items, raw, sp)
    return items


def _origin(sp, key):
    """Where an item the spec did not write comes from: 'kit sword (use sword)' or 'humanoid.yaml:120'."""
    for as_, u in (sp.get('_uses') or {}).items():
        if key in [tuple(p) for p in u['paths']]:
            return f'kit {u["kit"]}' + (f' (use {as_})' if as_ != u['kit'] else '')
    src = (sp['_origins'].get(key) or [None])[0]
    return f'{os.path.basename(src[0])}:{src[1]}' if src else 'base'


def _with_inherited(items, raw, sp):
    """The outline of a spec with a base or kits: the sections it inherits, and each inherited item of the itemized
    ones after the spec's own, with where it comes from (`lines` is None for them)."""
    merged = sp['_raw']
    out = list(items)
    for key, value in merged.items():
        if not isinstance(value, dict) or key in ('_mirror',):
            continue
        own = raw.get(key) if isinstance(raw.get(key), dict) else {}
        extra = [n for n in value if n not in own]
        if not extra:
            continue
        listed = f'{len(value)} items' if key in ITEMIZED else f'{len(value)}: {_names(list(value))}'
        if key not in raw:
            out.append(dict(path=key, lines=None, summary=listed, origin='base'))
        else:
            for i in out:
                if i['path'] == key:
                    if key in ITEMIZED:
                        i['summary'] = f'{len(value)} items ({len(own)} here)'
                    else:
                        i['summary'] = f'{len(value)} ({len(own)} here)' + listed[len(str(len(value))) :]
        if key not in ITEMIZED:
            continue
        at = max(
            (j for j, i in enumerate(out) if i['path'] == key or i['path'].startswith(key + '.')), default=len(out) - 1
        )
        added = []
        for name in extra:
            v = value[name]
            if key == 'parts':
                summary = _part(name, v or {})
            elif key == 'animations':
                summary = _animation(sp, name, v or {})
            elif key == 'ik':
                summary = _ik(v or {})
            else:
                summary = SEP.join(f'{k} {v[k]}' for k in list(v or {})[:2])
            origin = _origin(sp, (key, name))
            added.append(dict(path=f'{key}.{name}', lines=None, summary=f'from {origin}{SEP}{summary}', origin=origin))
        out[at + 1 : at + 1] = added
    return out


def outline_text(path):
    """The outline as text: an item of an itemized section is indented under it by its name alone (its path is
    `<section>.<name>`)."""
    items = outline(path)
    names = [('  ' + i['path'].split('.', 1)[1]) if '.' in i['path'] else i['path'] for i in items]
    w = max(map(len, names)) if names else 0
    spans = [
        _span(i['lines']) if i['lines'] else ('kit' if i.get('origin', '').startswith('kit') else 'base') for i in items
    ]
    return '\n'.join(f'{n:<{w}}  {s:>7}  {_cut(i["summary"])}'.rstrip() for n, s, i in zip(names, spans, items))


def _cut(text):
    return text if len(text) <= SUMMARY_W else text[: SUMMARY_W - 3] + '...'


def _plain(obj):
    """Loaded spec values as plain YAML-able data, without the loader's private keys."""
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items() if not str(k).startswith('_')}
    return json.loads(json.dumps(obj, default=lambda o: o.tolist() if hasattr(o, 'tolist') else str(o)))


def _get(tree, path):
    for p in path:
        if isinstance(tree, dict) and p in tree:
            tree = tree[p]
        elif isinstance(tree, list) and isinstance(p, int) and -len(tree) <= p < len(tree):
            tree = tree[p]
        else:
            raise KeyError(p)
    return tree


def _missing(text, known, where):
    near = difflib.get_close_matches(text, known, n=3)
    hint = f' (did you mean {", ".join(near)}?)' if near else ''
    return SpriteKilnError(f'{text}: not in {where}{hint}; `spritekiln spec outline` lists the paths')


def show(path, paths, resolved=False):
    """The source lines of each block (`parts.helm`, `animations.walk.keys[2]`), numbered, comments kept. A
    mirrored `_R` item shows its `_L` source. `resolved`: the block as the renderer sees it instead (defaults,
    mirroring and expressions as written), as YAML."""
    if not paths:
        raise SpriteKilnError('give at least one path, e.g. parts.helm or animations.walk')
    out = []
    if resolved:
        sp = _plain(specmod.load(path))
        for text in paths:
            p = schema.parse_path(text)
            try:
                block = _get(sp, p)
            except KeyError:
                raise _missing(text, [schema.format_path(k) for k in ranges(path)], 'the resolved spec') from None
            dumped = yaml.safe_dump(block, sort_keys=False, allow_unicode=True, width=110, default_flow_style=None)
            out += [f'# {schema.format_path(p)} (resolved)', dumped.rstrip()]
        return '\n'.join(out)
    rng = ranges(path)
    lines = _text(path).split('\n')
    sp = None
    raw = specmod.yload(_text(path)) or {}
    if isinstance(raw, dict) and ('extends' in raw or 'use' in raw) and 'kit' not in raw:
        sp = specmod.load(path)
    for text in paths:
        p = schema.parse_path(text)
        mirror = tuple(re.sub(r'_R$', '_L', x) if isinstance(x, str) else x for x in p)
        source = p if p in rng else mirror
        others = _sources(sp, p, path) or _sources(sp, mirror, path)
        if source not in rng and not others:
            known = set(rng) | set((sp or {}).get('_origins') or {})
            raise _missing(text, [schema.format_path(k) for k in known], path)
        note = f', mirrored from {schema.format_path(source)}' if source != p else ''
        for file, src in others:  # the base's or the kit's lines first
            a, b = ranges(file)[src]
            flines = _text(file).split('\n')
            alias = f' (as {schema.format_path(src)})' if src not in (p, mirror) else ''
            out.append(f'# {schema.format_path(p)}: {_rel(file)} lines {a}-{b}{alias}{note}')
            width = len(str(b))
            out += [f'{i:>{width}}| {flines[i - 1]}'.rstrip() for i in range(a, b + 1)]
        if source in rng:
            a, b = rng[source]
            out.append(f'# {schema.format_path(p)}: lines {a}-{b}{note}')
            width = len(str(b))
            out += [f'{i:>{width}}| {lines[i - 1]}'.rstrip() for i in range(a, b + 1)]
    return '\n'.join(out)


def _sources(sp, p, path):
    """[(file, path in that file)] of the bases and kits that wrote item `p` of a spec, base first."""
    if sp is None or not sp.get('_origins'):
        return []
    path = os.path.abspath(path)
    found = []
    for file, _, _, src in sp['_origins'].get(p, []):
        if os.path.abspath(file) != path and (file, tuple(src)) not in found:
            found.append((file, tuple(src)))
    return found


def _rel(path):
    try:
        rel = os.path.relpath(path)
        return rel if not rel.startswith('..') else path
    except ValueError:  # another drive on Windows
        return path
