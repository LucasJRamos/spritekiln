"""Animation evaluation: per-direction channels (yaw, dir) and timing targets."""

import textwrap

import pytest

from spritekiln import spec as S
from spritekiln.anim import frames_of, timing_problems, to_frames

SPEC = """\
spritekiln: 1
name: t
directions: 4
ramps:
  body: ["#111111", "#444444", "#888888"]
materials:
  body: {}
channels:
  bob: 0.0
  lean: 0.0
bones:
  hips: {parent: root, pos: "[0, 0.6 + bob, 0]", rot: "[lean, 0, 0]"}
parts:
  torso: {material: body, space: hips, prims: [{sphere: {c: [0, 0, 0], r: 0.2}}]}
animations:
  idle:
    frames: 4
    ms: 100
    channels: {bob: "0.05*(dir == 'e') + 0.01*yaw/90"}
  attack:
    keys:
      - {ms: 50, event: windup, set: {lean: "0.3*pulse(yaw, 180, 60)"}}
      - {ms: 33, event: hit}
      - {ms: 117}
"""


def load(tmp_path, text):
    p = tmp_path / 'spec.yaml'
    p.write_text(textwrap.dedent(text), encoding='utf-8')
    return S.load(str(p))


def test_channels_see_the_direction(tmp_path):
    sp = load(tmp_path, SPEC)
    bob = {d: frames_of(sp, 'idle', yaw)[0][0]['bob'] for d, yaw in sp['directions']}
    assert bob == pytest.approx({'s': 0.0, 'e': 0.06, 'n': 0.02, 'w': -0.01})
    lean = {d: frames_of(sp, 'attack', yaw)[0][0]['lean'] for d, yaw in sp['directions']}
    assert lean == pytest.approx({'s': 0.0, 'e': 0.0, 'n': 0.3, 'w': 0.0})
    assert frames_of(sp, 'attack', 90)[0][0]['dir'] == 'e'


def test_validate_checks_every_direction(tmp_path):
    sp = load(tmp_path, SPEC.replace('"0.3*pulse(yaw, 180, 60)"', '"0.3*pulse(yaw, 180, 60) + bad*(dir == \'w\')"'))
    errors = S.validate(sp)
    assert len(errors) == 1 and 'animations.attack.keys[0].set.lean' in errors[0]


@pytest.mark.parametrize('value, frames', [(2, 2.0), ('2f', 2.0), ('2.5 f', 2.5), ('33ms', 1.98), (' 100 ms ', 6.0)])
def test_to_frames(value, frames):
    assert to_frames(value, 60) == pytest.approx(frames)


def test_bad_duration(tmp_path):
    sp = load(tmp_path, SPEC + 'timing:\n  attack: {hit: soon}\n')
    with pytest.raises(S.SpecError, match="cannot read 'soon'"):
        timing_problems(sp)


def test_timing_targets(tmp_path):
    ok = SPEC + 'timing:\n  attack: {windup: 0f, hit: 50ms, total: 12f}\n'
    assert timing_problems(load(tmp_path, ok)) == []
    late = SPEC + 'timing:\n  attack: {hit: 1f, total: 200ms}\n'
    problems = timing_problems(load(tmp_path, late))
    assert problems == ['timing.attack.hit: at 3.0 f (50 ms) but the target is 1 f (+-1 f at 60 fps)']
    missing = SPEC + 'timing:\n  attack: {release: 2f}\n  dance: {total: 1f}\n'
    problems = timing_problems(load(tmp_path, missing))
    assert 'timing.attack.release: the animation has no "release" event' in problems
    assert 'timing.dance: unknown animation' in problems
    tolerant = SPEC + 'timing:\n  tolerance: 2\n  attack: {hit: 1f}\n'
    assert timing_problems(load(tmp_path, tolerant)) == []


def test_timing_errors_reach_validate_with_a_position(tmp_path):
    sp = load(tmp_path, SPEC + 'timing:\n  attack: {hit: 1f}\n')
    errors = S.validate(sp)
    assert len(errors) == 1 and errors[0].endswith(
        ':26:12: timing.attack.hit: at 3.0 f (50 ms) but the target is 1 f (+-1 f at 60 fps)'
    )


def test_timing_that_depends_on_the_direction(tmp_path):
    text = SPEC.replace('    ms: 100\n', '    ms: "100 + 100*(dir == \'n\')"\n    events: {1: step}\n')
    sp = load(tmp_path, text + 'timing:\n  idle: {step: 100ms}\n')
    assert timing_problems(sp) == ['timing.idle.step: at 12.0 f (200 ms) but the target is 6 f (+-1 f at 60 fps) in n']
