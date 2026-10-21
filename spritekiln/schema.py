"""The spec JSON Schema at runtime: unknown-key warnings and YAML line/column for every problem.

`data/spec.schema.json` is the single source of truth: editors (VS Code + YAML extension) and AIs read it
directly, the tests validate every spec against it with `jsonschema`, and this module walks the subset
needed to spot unknown keys (typos are otherwise silently ignored) without a runtime dependency.
"""

import difflib
import functools
import json
import os
import re

import yaml

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'spec.schema.json')


@functools.lru_cache(maxsize=1)
def schema():
    with open(SCHEMA_PATH, encoding='utf-8') as fh:
        return json.load(fh)


# ---------------------------------------------------------------- unknown keys


def _resolve(sch):
    while isinstance(sch, dict) and '$ref' in sch:
        sch = schema()['$defs'][sch['$ref'].rsplit('/', 1)[1]] | {k: v for k, v in sch.items() if k != '$ref'}
    return sch


def _kind(node):
    if isinstance(node, dict):
        return 'object'
    if isinstance(node, list):
        return 'array'
    if isinstance(node, bool):
        return 'boolean'
    if isinstance(node, (int, float)):
        return 'number'
    if node is None:
        return 'null'
    return 'string'


def _types(sch):
    t = sch.get('type')
    if t is None:
        if 'properties' in sch or 'required' in sch:
            return {'object'}
        return None  # unconstrained
    t = {t} if isinstance(t, str) else set(t)
    return t | ({'number'} if 'integer' in t else set())


def _fits(node, sch):
    sch = _resolve(sch)
    types = _types(sch)
    if types is not None and _kind(node) not in types:
        return False
    if isinstance(node, dict):
        return all(k in node for k in sch.get('required', []))
    return True


def _known(sch):
    """Keys an object schema accepts, or None when it accepts any key."""
    sch = _resolve(sch)
    if sch.get('additionalProperties', True) is not False or sch.get('patternProperties'):
        return None
    return list(sch.get('properties', {}))


def _alternatives(sch):
    for k in ('anyOf', 'oneOf'):
        if k in sch:
            return [_resolve(a) for a in sch[k]]
    return None


def scan(doc):
    """(unknown, missing): [(path, key, allowed keys)] for keys the schema does not know, and
    [(path, key)] for required keys that are absent."""
    unknown, missing = [], []
    _walk(doc, schema(), (), unknown, missing)
    return unknown, missing


def unknown_keys(doc):
    return scan(doc)[0]


def missing_keys(doc):
    return scan(doc)[1]


def _walk(node, sch, path, out, missing):
    sch = _resolve(sch)
    if 'if' in sch and isinstance(node, dict):
        cond = all(k in node for k in _resolve(sch['if']).get('required', []))
        _walk(node, sch['then'] if cond else sch['else'], path, out, missing)
        return
    alts = _alternatives(sch)
    if alts is not None and not ('properties' in sch or 'additionalProperties' in sch):
        fitting = [a for a in alts if _fits(node, a)]
        if not fitting and isinstance(node, dict):
            allowed = sorted({k for a in alts for k in (a.get('properties') or {})})
            if allowed:
                out.extend((path, k, allowed) for k in node if k not in allowed)
            return
        if fitting:
            # the alternative that leaves the fewest unknown keys
            best = min(fitting, key=lambda a: _count_unknown(node, a))
            _walk(node, best, path, out, missing)
        return
    if isinstance(node, dict):
        missing.extend((path, k) for k in sch.get('required', []) if k not in node)
        props = sch.get('properties', {})
        patterns = sch.get('patternProperties', {})
        extra = sch.get('additionalProperties', True)
        for k, v in node.items():
            key = str(k)
            if key in props:
                _walk(v, props[key], path + (key,), out, missing)
            elif any(re.search(p, key) for p in patterns):
                _walk(v, next(s for p, s in patterns.items() if re.search(p, key)), path + (key,), out, missing)
            elif isinstance(extra, dict):
                _walk(v, extra, path + (key,), out, missing)
            elif extra is False:
                out.append((path, key, sorted(props)))
    elif isinstance(node, list) and isinstance(sch.get('items'), dict):
        for i, v in enumerate(node):
            _walk(v, sch['items'], path + (i,), out, missing)


def _count_unknown(node, sch):
    known = _known(sch)
    return 0 if known is None or not isinstance(node, dict) else sum(1 for k in node if str(k) not in known)


def describe_unknown(path, key, allowed):
    where = format_path(path + (key,))
    hint = difflib.get_close_matches(key, allowed, n=1, cutoff=0.6)
    if hint:
        return f'{where}: unknown key "{key}" (did you mean "{hint[0]}"?)'
    shown = ', '.join(allowed[:12]) + (', ...' if len(allowed) > 12 else '')
    return f'{where}: unknown key "{key}" (expected one of: {shown})'


def describe_missing(path, key):
    return f'{format_path(path)}: missing required key "{key}"'


# ---------------------------------------------------------------- positions


def format_path(path):
    out = ''
    for p in path:
        out += f'[{p}]' if isinstance(p, int) else (f'.{p}' if out else str(p))
    return out


_PATH = re.compile(
    r'\b((?:bones|ik|parts|materials|channels|animations|camera|light|shadow|directions|palette)'
    r'(?:\.[A-Za-z0-9_-]+|\[\d+\])*)(?=:| \()'
)  # a path that a message talks about


def parse_path(text):
    path = []
    for name, idx in re.findall(r'([A-Za-z0-9_-]+)|\[(\d+)\]', text):
        path.append(int(idx) if idx else name)
    return tuple(path)


def marks(path, loader):
    """{path tuple: (line, column)} (1-based) for every key and list item of a YAML file."""
    with open(path, encoding='utf-8') as fh:
        root = yaml.compose(fh, Loader=loader)
    found = {}

    def walk(node, p):
        if isinstance(node, yaml.MappingNode):
            for k, v in node.value:
                key = p + (str(k.value),)
                found[key] = (k.start_mark.line + 1, k.start_mark.column + 1)
                walk(v, key)
        elif isinstance(node, yaml.SequenceNode):
            for i, v in enumerate(node.value):
                found[p + (i,)] = (v.start_mark.line + 1, v.start_mark.column + 1)
                walk(v, p + (i,))

    if root is not None:
        walk(root, ())
    return found


def locate(message, spec_marks):
    """(line, column) of the deepest spec path mentioned in a problem message, or None."""
    paths = _PATH.findall(message)
    for text in reversed(paths):  # the last path is the most specific culprit
        path = parse_path(text)
        while path:
            for candidate in (path, tuple(re.sub(r'_R$', '_L', p) if isinstance(p, str) else p for p in path)):
                if candidate in spec_marks:  # an automatic _R twin points at its _L source
                    return spec_marks[candidate]
            path = path[:-1]
    return None
