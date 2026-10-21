import numpy as np
import pytest

from spritekiln.expr import ExprError, compile_expr, evaluate


def test_plain_values_pass_through():
    assert evaluate(3, {}) == 3
    assert evaluate(0.5, {}) == 0.5


def test_arithmetic_with_channels():
    assert evaluate('0.78 + bob', {'bob': 0.02}) == pytest.approx(0.80)
    assert evaluate('2 ** 3 // 3 % 2', {}) == 0
    assert evaluate('-a', {'a': 1.5}) == -1.5


def test_lists_are_vectors_not_concatenation():
    out = evaluate('[1, 0, 0] + [0, 1, 0]', {})
    assert isinstance(out, np.ndarray)
    np.testing.assert_allclose(out, [1, 1, 0])
    np.testing.assert_allclose(evaluate('2 * [1, 2, 3]', {}), [2, 4, 6])


def test_yaml_list_with_expressions():
    out = evaluate(['a', 2, '3 * a'], {'a': 1.0})
    np.testing.assert_allclose(out, [1, 2, 3])


def test_yaml_list_with_vector_items_stays_a_list():
    out = evaluate(['[0, 1, 0]', 2], {})
    assert isinstance(out, list) and len(out) == 2


def test_phase_variables_come_from_env():
    env = dict(p=np.pi / 2, t=0.25, f=2, n=8)
    assert evaluate('sin(p)', env) == pytest.approx(1.0)
    assert evaluate('t * n + f', env) == pytest.approx(4.0)


@pytest.mark.parametrize('src, expected', [
    ('pulse(0, 0, 70)', 1.0),
    ('pulse(70, 0, 70)', 0.0),
    ('pulse(35, 0, 70)', 0.5),
    ('clamp(5, 0, 1)', 1.0),
    ('pos(-2)', 0.0),
    ('neg(-2)', -2.0),
    ('smoothstep(0, 1, 0.5)', 0.5),
    ('lerp(2, 4, 0.25)', 2.5),
    ('mix(2, 4, 0.5)', 3.0),
    ('min(3, 1) + max(3, 1)', 4.0),
    ('abs(-2) + sqrt(4)', 4.0),
    ('floor(1.7) + sign(-3)', 0.0),
    ('radians(180)', np.pi),
    ('tau / pi', 2.0),
    ('exp(0)', 1.0),
])
def test_functions(src, expected):
    assert float(evaluate(src, {})) == pytest.approx(expected)


def test_vector_functions():
    np.testing.assert_allclose(evaluate('unit([3, 0, 4])', {}), [0.6, 0, 0.8])
    np.testing.assert_allclose(evaluate('v(1, 2, 3)', {}), [1, 2, 3])
    np.testing.assert_allclose(evaluate('roty(pi / 2) @ [0, 0, 1]', {}), [1, 0, 0], atol=1e-12)
    np.testing.assert_allclose(evaluate('rotx(pi / 2) @ [0, 1, 0]', {}), [0, 0, 1], atol=1e-12)
    np.testing.assert_allclose(evaluate('rotz(pi / 2) @ [1, 0, 0]', {}), [0, 1, 0], atol=1e-12)


def test_noise_is_deterministic_and_in_unit_range():
    vals = [evaluate(f'noise({i}, 3)', {}) for i in range(20)]
    assert vals == [evaluate(f'noise({i}, 3)', {}) for i in range(20)]
    assert all(0 <= v < 1 for v in vals)
    assert evaluate('noise(1, 0)', {}) != evaluate('noise(1, 1)', {})


def test_conditionals_comparisons_and_subscripts():
    assert evaluate('1 if a > 0 else 2', {'a': 1}) == 1
    assert evaluate('a > 0 and b < 0', {'a': 1, 'b': -1})
    assert evaluate('not a', {'a': 0})
    assert evaluate('[4, 5, 6][1]', {}) == 5
    np.testing.assert_allclose(evaluate('[4, 5, 6][1:]', {}), [5, 6])


@pytest.mark.parametrize('src', [
    'a.__class__',
    '(lambda: 1)()',
    '[x for x in [1, 2]]',
    'f(1)(2)',
    '{1: 2}',
])
def test_disallowed_syntax(src):
    with pytest.raises(ExprError):
        compile_expr(src)


def test_no_builtins():
    with pytest.raises(ExprError, match='unknown channel or function'):
        evaluate('__import__("os")', {})
    with pytest.raises(ExprError):
        evaluate('open("x")', {})


def test_unknown_name_and_syntax_error_messages():
    with pytest.raises(ExprError, match='unknown channel or function'):
        evaluate('bob + 1', {})
    with pytest.raises(ExprError, match='syntax error'):
        evaluate('1 +', {})


def test_compiled_expressions_are_cached():
    assert compile_expr('1 + 2') is compile_expr('1 + 2')
