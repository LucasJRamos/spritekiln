"""Safe expression evaluator for spec values.

Any numeric field in a spec may be a string expression. Lists inside expressions
are numpy vectors (so [1,0,0] + [0,1,0] adds, it does not concatenate).
Available: channel names, p (phase 0..2pi), t (0..1), f (frame index), n (frame count),
sx (+1 on _L side, -1 on _R side), and the functions below.
"""

import ast

import numpy as np

from .errors import SpriteKilnError
from .sdf import rot_x, rot_y, rot_z


def _arr(x):
    return np.asarray(x, float)


def _unit(v):
    v = _arr(v)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def _lerp(a, b, t):
    return _arr(a) * (1 - t) + _arr(b) * t


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def _pulse(x, center, width):
    """1 at center, falls to 0 at +-width (cosine)."""
    d = np.clip(abs(x - center) / width, 0, 1)
    return 0.5 + 0.5 * np.cos(np.pi * d)


FUNCS = dict(
    sin=np.sin,
    cos=np.cos,
    tan=np.tan,
    abs=abs,
    min=min,
    max=max,
    sqrt=np.sqrt,
    clamp=lambda x, a, b: float(np.clip(x, a, b)),
    lerp=_lerp,
    mix=_lerp,
    unit=_unit,
    smoothstep=_smoothstep,
    pulse=_pulse,
    pos=lambda x: max(0.0, x),
    neg=lambda x: min(0.0, x),
    roty=rot_y,
    rotx=rot_x,
    rotz=rot_z,
    v=lambda *a: _arr(a),
    radians=np.radians,
    pi=np.pi,
    tau=2 * np.pi,
    floor=np.floor,
    sign=np.sign,
    exp=np.exp,
    noise=lambda x, seed=0: float(np.sin(x * 12.9898 + seed * 78.233) * 43758.5453 % 1.0),
)

_ALLOWED = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.Call,
    ast.List,
    ast.Tuple,
    ast.Compare,
    ast.IfExp,
    ast.BoolOp,
    ast.Subscript,
    ast.Index if hasattr(ast, 'Index') else ast.Constant,
    ast.Slice,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.USub,
    ast.UAdd,
    ast.MatMult,
    ast.Lt,
    ast.Gt,
    ast.LtE,
    ast.GtE,
    ast.Eq,
    ast.NotEq,
    ast.And,
    ast.Or,
    ast.Not,
    ast.FloorDiv,
)


class ExprError(SpriteKilnError, ValueError):
    pass


class _ListToArray(ast.NodeTransformer):
    def visit_List(self, node):
        self.generic_visit(node)
        return ast.copy_location(ast.Call(func=ast.Name('_arr', ast.Load()), args=[node], keywords=[]), node)


_cache = {}


def compile_expr(src):
    if src in _cache:
        return _cache[src]
    try:
        tree = ast.parse(src.strip(), mode='eval')
    except SyntaxError as e:
        raise ExprError(f'syntax error in expression {src!r}: {e.msg}') from None
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ExprError(f'not allowed in expression {src!r}: {type(node).__name__}')
        if isinstance(node, ast.Call) and not isinstance(node.func, ast.Name):
            raise ExprError(f'only plain function calls allowed in {src!r}')
    tree = ast.fix_missing_locations(_ListToArray().visit(tree))
    code = compile(tree, '<expr>', 'eval')
    _cache[src] = code
    return code


def evaluate(value, env):
    """Evaluate a spec value: number, list (possibly containing expressions) or expression string."""
    if isinstance(value, str):
        code = compile_expr(value)
        scope = dict(FUNCS)
        scope['_arr'] = _arr
        scope.update(env)
        try:
            out = eval(code, {'__builtins__': {}}, scope)
        except NameError as e:
            raise ExprError(f'{e} in expression {value!r} (unknown channel or function)') from None
        return out
    if isinstance(value, (list, tuple)):
        vals = [evaluate(v, env) for v in value]
        if all(np.ndim(v) == 0 for v in vals):
            return np.asarray(vals, float)
        return vals
    return value
