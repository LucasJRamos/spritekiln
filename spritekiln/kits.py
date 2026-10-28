"""Bases and kits (design 14): a spec `extends` another one and `use`s kits, reusable parts with parameters.

`resolve` turns a spec file into one plain document, as if it had been written in full, and remembers where every
item came from (file, line and its path in that file), so that problems, `spec outline` and `spec show` point at
the base or the kit that wrote it:

- `extends: humanoid`: a built-in template, a template of the project (<specs>/templates/<name>.yaml) or a path
  relative to the spec. The base is merged deeply and the spec's keys win; lists are replaced, never merged.
  `remove: [parts.cape, use.sword]` deletes paths of the base (or everything one of its `use` entries added).
- `use: [{kit: sword, as: sword, at: wrist_R, with: {length: 0.5}, materials: {steel: iron}}]`: the kit's parts,
  bones, IK chains, sockets and channels join the spec, named `<as>_<name>` (an item named like the kit is
  `<as>`), attached to the frame `at` (the kit says `at` for it). Its `params` are replaced by their values in its
  expressions. Its materials and ramps are used only where the spec has none of that name, and so are the
  host channels it reads (`host_channels: {coat: 0}`). A `use` with the `as` of one of the base's replaces it.

A kit file opened as a spec (`spritekiln pose specs/kits/axe.yaml`) is the kit on its `host`, for authoring.
"""

import ast
import copy
import difflib
import os
from typing import NamedTuple

from . import resources, schema
from .errors import SpriteKilnError

KIT_KEYS = (
    'spritekiln',
    'pxforge',
    'kit',
    'license',
    'summary',
    'host',
    'at',
    'host_remove',
    'params',
    'host_channels',
    'materials',
    'ramps',
    'channels',
    'bones',
    'ik',
    'parts',
    'sockets',
)
USE_KEYS = ('kit', 'as', 'at', 'with', 'materials')
PREFIXED = ('parts', 'bones', 'ik', 'sockets', 'channels')  # named <as>_<name> when a kit adds them
NOT_INHERITED = ('spritekiln', 'pxforge', 'name', 'brief', 'extends', 'remove', 'use')
FRAME_FIELDS = {'space', 'parent', 'bone', 'start', 'joint', 'end', 'pole_space', 'at'}  # hold a frame's name
NAME_FIELDS = {'mode', 'axis', 'axes', 'ramp', 'finish', 'kit', 'as'}  # plain words, never expressions
RESERVED = {'p', 't', 'f', 'n', 'yaw', 'dir', 'sx', 'root', 'True', 'False'}


class Resolved(NamedTuple):
    doc: dict  # the spec as if written in full
    origins: dict  # path tuple -> [(file, line, column, path in that file)], base first, the spec's own last
    files: list  # base and kit files read
    uses: dict  # `as` -> {kit, file, paths}: what each `use` entry added
    kit_ramps: dict  # ramps the kits bring, used where the palette has none of that name


def is_kit(raw):
    return isinstance(raw, dict) and 'kit' in raw


def _read(path):
    from .spec import _read_yaml

    raw = _read_yaml(path)
    if not isinstance(raw, dict):
        raise SpriteKilnError(f'{path}: must be a YAML mapping')
    return raw


def _marks(path):
    from .spec import _Loader

    try:
        return schema.marks(path, _Loader)
    except OSError:
        return {}


def _at(path, marks, key):
    """'file:line:column: ' of a path in a file (or of its nearest parent)."""
    key = tuple(key)
    while key and key not in marks:
        key = key[:-1]
    line, col = marks.get(key, (1, 1))
    return f'{_rel(path)}:{line}:{col}: '


def _rel(path):
    try:
        rel = os.path.relpath(path)
        return rel if not rel.startswith('..') else path
    except ValueError:  # another drive on Windows
        return path


def _project_dir(start, sub):
    from . import config

    cfg = config.load(start)
    return os.path.join(cfg['specs'], sub) if cfg else None


def _find(ref, start, kind):
    """A base template or a kit by name or path: a path relative to `start`, the project's
    <specs>/<templates|kits>/<name>.yaml, then the built-in one. Returns (path or None, names available)."""
    ref = str(ref)
    if ref.endswith(('.yaml', '.yml')) or '/' in ref or '\\' in ref:
        p = ref if os.path.isabs(ref) else os.path.join(start, ref)
        return (os.path.abspath(p) if os.path.isfile(p) else None), []
    names = []
    folder = _project_dir(start, kind)
    if folder and os.path.isdir(folder):
        p = os.path.join(folder, f'{ref}.yaml')
        if os.path.isfile(p):
            return os.path.abspath(p), []
        names += [os.path.splitext(f)[0] for f in os.listdir(folder) if f.endswith('.yaml')]
    p = resources.template(ref) if kind == 'templates' else resources.kit(ref)
    if p:
        return os.path.abspath(p), []
    names += resources.templates() if kind == 'templates' else resources.kits()
    return None, sorted(set(names))


def _not_found(what, ref, names, where):
    near = difflib.get_close_matches(str(ref), names, n=1)
    hint = f' (did you mean {near[0]}?)' if near else f' (available: {", ".join(names)})' if names else ''
    return SpriteKilnError(f'{where}{what} "{ref}" not found{hint}')


def deep_merge(base, over):
    """`over` merged into a copy of `base`: mappings merge key by key, anything else (lists too) is replaced."""
    if not isinstance(base, dict) or not isinstance(over, dict):
        return copy.deepcopy(over)
    out = dict(base)
    for k, v in over.items():
        out[k] = deep_merge(base[k], v) if k in base else copy.deepcopy(v)
    return out


def _paths(node, prefix=()):
    yield prefix
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _paths(v, prefix + (str(k),))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _paths(v, prefix + (i,))


def _delete(doc, path):
    node = doc
    for p in path[:-1]:
        try:
            node = node[p]
        except (KeyError, IndexError, TypeError):
            return False
    last = path[-1]
    if isinstance(node, dict) and last in node:
        del node[last]
        return True
    if isinstance(node, list) and isinstance(last, int) and -len(node) <= last < len(node):
        del node[last]
        return True
    return False


def _absolute_palettes(doc, folder):
    """A base's palette files are relative to the base: make them absolute so the spec finds them."""
    pal = doc.get('palette')
    if pal is None:
        return

    def fix(p):
        if isinstance(p, str) and (p.endswith(('.yaml', '.yml')) or '/' in p) and not os.path.isabs(p):
            full = os.path.join(folder, p)
            return os.path.abspath(full) if os.path.exists(full) else p
        return p

    doc['palette'] = [fix(p) for p in pal] if isinstance(pal, list) else fix(pal)


def resolve(path, raw=None, _stack=()):
    """The spec at `path` (or its already read `raw` mapping) with its base and kits resolved."""
    path = os.path.abspath(path)
    raw = _read(path) if raw is None else raw
    folder = os.path.dirname(path)
    marks = {} if is_kit(raw) else _marks(path)
    if is_kit(raw):  # a kit opened as a spec: the kit on its host
        raw = {
            'spritekiln': 1,
            'name': raw['kit'],
            'extends': raw.get('host', 'humanoid'),
            'remove': list(raw.get('host_remove') or []),
            'use': [{'kit': path, 'as': raw['kit'], 'at': raw.get('at', 'root')}],
        }
    own = {p: [(path, line, col, p)] for p, (line, col) in marks.items()}
    if 'extends' not in raw and 'use' not in raw:
        return Resolved(raw, own, [], {}, {})
    doc, origins, files, uses, kit_ramps = {}, {}, [], {}, {}
    if 'extends' in raw:
        base, names = _find(raw['extends'], folder, 'templates')
        where = _at(path, marks, ('extends',))
        if base is None:
            raise _not_found('extends: base', raw['extends'], names, where)
        if base in _stack or base == path:
            raise SpriteKilnError(f'{where}extends: "{raw["extends"]}" extends this spec back (a loop)')
        b = resolve(base, None, _stack + (path,))
        doc = {k: copy.deepcopy(v) for k, v in b.doc.items() if k not in NOT_INHERITED}
        _absolute_palettes(doc, os.path.dirname(base))
        origins = {p: v for p, v in b.origins.items() if p and p[0] not in NOT_INHERITED}
        files, uses, kit_ramps = [base, *b.files], copy.deepcopy(b.uses), dict(b.kit_ramps)
    for i, item in enumerate(raw.get('remove') or []):
        where = _at(path, marks, ('remove', i))
        text = str(item)
        if text.startswith('use.'):
            name = text[4:]
            if name not in uses:
                raise _not_found('remove: use', name, sorted(uses), where)
            for p in uses.pop(name)['paths']:
                _delete(doc, p)
            continue
        p = schema.parse_path(text)
        if not p or not _delete(doc, p):
            known = [schema.format_path(q) for q in _paths(doc) if q and len(q) <= max(len(p), 2)]
            raise _not_found('remove: path', text, known, where)
    for i, entry in enumerate(raw.get('use') or []):
        where = _at(path, marks, ('use', i))
        if not isinstance(entry, dict) or 'kit' not in entry:
            raise SpriteKilnError(f'{where}use[{i}]: give at least `kit: <name>` (and `as`, `at`, `with`)')
        k = load_kit(entry, folder, where, f'use[{i}]')
        if k['as'] in uses:  # the same `as` as one of the base's: this one replaces it
            for p in uses.pop(k['as'])['paths']:
                _delete(doc, p)
        for sec in PREFIXED:
            for item_name, item in k['items'][sec].items():
                if item_name in (doc.get(sec) or {}):
                    raise SpriteKilnError(
                        f'{where}use[{i}]: kit {k["kit"]} adds {sec}.{item_name}, which the spec already has '
                        f'(give this use another `as`, or remove the other one)'
                    )
                doc.setdefault(sec, {})[item_name] = item
        uses[k['as']] = dict(kit=k['kit'], file=k['file'], paths=k['paths'], pending=k['materials'])
        origins.update(k['origins'])
        files.append(k['file'])
        for r, colors in k['ramps'].items():
            kit_ramps.setdefault(r, colors)
        uses[k['as']]['host_channels'] = k['host_channels']
    doc = deep_merge(doc, {k: v for k, v in raw.items() if k not in ('extends', 'remove', 'use')})
    for u in uses.values():  # kit materials and host channels where the spec (or its base) has none of them
        for m, (mat, src) in (u.pop('pending', None) or {}).items():
            mats = doc.setdefault('materials', {})
            if m not in mats:
                mats[m] = copy.deepcopy(mat)
                origins[('materials', m)] = [src]
        for c, (value, src) in (u.pop('host_channels', None) or {}).items():
            chans = doc.setdefault('channels', {})
            if c not in chans:
                chans[c] = copy.deepcopy(value)
                origins[('channels', c)] = [src]
    for k in ('extends', 'remove', 'use'):
        if k in raw:
            doc[k] = copy.deepcopy(raw[k])
    for p, src in own.items():
        origins[p] = [s for s in origins.get(p, []) if s[0] != path] + src
    present = set(_paths(doc))
    origins = {p: v for p, v in origins.items() if p in present}
    return Resolved(doc, origins, files, uses, kit_ramps)


def load_kit(entry, folder, where='', label='use'):
    """One `use` entry: the kit's items renamed and with its params replaced, ready to join a spec."""
    for key in entry:
        if key not in USE_KEYS:
            hint = difflib.get_close_matches(str(key), USE_KEYS, n=1)
            raise SpriteKilnError(
                f'{where}{label}: unknown key "{key}"' + (f' (did you mean "{hint[0]}"?)' if hint else '')
            )
    file, names = _find(entry['kit'], folder, 'kits')
    if file is None:
        raise _not_found(f'{label}.kit: kit', entry['kit'], names, where)
    raw = _read(file)
    kmarks = _marks(file)
    for key in raw:
        if key not in KIT_KEYS:
            allowed = ', '.join(KIT_KEYS)
            raise SpriteKilnError(f'{_at(file, kmarks, (key,))}unknown key "{key}" in a kit (use {allowed})')
    kit = str(raw.get('kit') or os.path.splitext(os.path.basename(file))[0])
    as_ = str(entry.get('as') or kit)
    at = str(entry.get('at') or raw.get('at') or 'root')
    params = dict(raw.get('params') or {})
    given = entry.get('with') or {}
    if not isinstance(given, dict):
        raise SpriteKilnError(f'{where}{label}.with: a mapping of params ({", ".join(params) or "the kit has none"})')
    for key in given:
        if key not in params:
            hint = difflib.get_close_matches(str(key), list(params), n=1)
            raise SpriteKilnError(
                f'{where}{label}.with: kit {kit} has no param "{key}"'
                + (f' (did you mean "{hint[0]}"?)' if hint else f' (params: {", ".join(params) or "none"})')
            )
    params.update(given)
    for key in params:
        from .expr import FUNCS

        if key in FUNCS or key in RESERVED or not str(key).isidentifier():
            raise SpriteKilnError(f'{_at(file, kmarks, ("params", key))}param "{key}": pick another name')
    remap = dict(entry.get('materials') or {})

    def pname(n):
        return as_ if n == kit else f'{as_}_{n}'

    frames = set(raw.get('bones') or {})
    for chain in (raw.get('ik') or {}).values():
        if isinstance(chain, dict):
            frames |= {chain.get('joint'), chain.get('end')} - {None}
    channels = set(raw.get('channels') or {})
    sub = {k: _value_ast(v) for k, v in params.items()}

    def frame(n):
        n = str(n).strip()
        return at if n == 'at' else pname(n) if n in frames else n

    def expr(text):
        try:
            tree = ast.parse(text.strip(), mode='eval')
        except SyntaxError:
            return text
        changed = False

        class T(ast.NodeTransformer):
            def visit_Name(self, node):
                nonlocal changed
                if node.id in sub:
                    changed = True
                    return ast.copy_location(copy.deepcopy(sub[node.id]), node)
                if node.id in channels:
                    changed = True
                    return ast.copy_location(ast.Name(pname(node.id), ast.Load()), node)
                return node

        tree = ast.fix_missing_locations(T().visit(tree))
        if not changed:
            return text
        try:
            return ast.literal_eval(tree.body)  # a param alone: its value (a number, a list, true/false)
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
            return ast.unparse(tree.body)

    def xform(v, key=None):
        if isinstance(v, dict):
            return {k: xform(x, k) for k, x in v.items()}
        if isinstance(v, list):
            return [xform(x, None if key == 'at' else key) for x in v]
        if not isinstance(v, str):
            return v
        if key == 'at' and v.strip() not in frames and v.strip() != 'at':
            return expr(v)  # a host frame (left as it is) or a plane's distance (`at: length`)
        if key in FRAME_FIELDS:
            return frame(v)
        if key in ('material', 'materials'):
            return remap.get(v, v)
        if v.startswith('@'):
            return '@' + frame(v[1:])
        if key in NAME_FIELDS:
            return v
        return expr(v)

    items, origins, paths = {}, {}, []
    for sec in PREFIXED:
        items[sec] = {}
        for n, item in (raw.get(sec) or {}).items():
            new = pname(str(n))
            items[sec][new] = xform(copy.deepcopy(item))
            paths.append((sec, new))
            for p, (line, col) in kmarks.items():
                if p[:2] == (sec, str(n)):
                    origins[(sec, new, *p[2:])] = [(file, line, col, p)]
    materials = {}
    for m, mat in (raw.get('materials') or {}).items():
        if m not in remap:
            line, col = kmarks.get(('materials', str(m)), (1, 1))
            materials[str(m)] = (xform(copy.deepcopy(mat)), (file, line, col, ('materials', str(m))))
    host_channels = {}
    for c, value in (raw.get('host_channels') or {}).items():
        line, col = kmarks.get(('host_channels', str(c)), (1, 1))
        host_channels[str(c)] = (value, (file, line, col, ('host_channels', str(c))))
    return dict(
        kit=kit,
        file=file,
        host_channels=host_channels,
        **{'as': as_},
        items=items,
        origins=origins,
        paths=paths,
        materials=materials,
        ramps=dict(raw.get('ramps') or {}),
    )


def _value_ast(v):
    if isinstance(v, (bool, int, float)) or v is None:
        return ast.Constant(v)
    if isinstance(v, (list, tuple)):
        return ast.List([_value_ast(x) for x in v], ast.Load())
    try:
        return ast.parse(str(v).strip(), mode='eval').body
    except SyntaxError:
        raise SpriteKilnError(f'param value {v!r}: not a number, a list or an expression') from None


def catalogue(start=None):
    """Every kit this project can use: [{name, file, summary, at, host, license, params, materials, origin}]."""
    out, seen = [], set()
    folder = _project_dir(start or os.getcwd(), 'kits')
    sources = []
    if folder and os.path.isdir(folder):
        sources += [(os.path.join(folder, f), 'project') for f in sorted(os.listdir(folder)) if f.endswith('.yaml')]
    sources += [(resources.kit(n), 'built-in') for n in resources.kits()]
    for file, origin in sources:
        name = os.path.splitext(os.path.basename(file))[0]
        if name in seen:
            continue  # a project kit shadows the built-in one
        seen.add(name)
        try:
            raw = _read(file)
        except SpriteKilnError:
            continue
        out.append(
            dict(
                name=name,
                origin=origin,
                file=file,
                summary=raw.get('summary', ''),
                at=raw.get('at', 'root'),
                host=raw.get('host', 'humanoid'),
                license=raw.get('license', ''),
                params=raw.get('params') or {},
                materials=sorted(raw.get('materials') or {}),
            )
        )
    return out
