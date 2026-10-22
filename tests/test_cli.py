"""CLI behaviour: user errors are one-line messages with exit code 1, never tracebacks."""

import os
import subprocess
import sys

import pytest

from spritekiln.cli import main

from conftest import REPO

GARGOYLE = os.path.join(REPO, 'specs', 'characters', 'gargula', 'gargula.yaml')


def run(*args):
    return subprocess.run(
        [sys.executable, '-m', 'spritekiln', *args], cwd=REPO, capture_output=True, text=True, encoding='utf-8'
    )


@pytest.mark.parametrize(
    'args, message',
    [
        (['validate', 'nope.yaml'], 'file not found'),
        (['pose', GARGOYLE, '--anim', 'dance'], 'animation "dance" not in spec'),
        (['pose', GARGOYLE, '--anim', 'idle', '--frame', '99'], 'frame 99: animation "idle" has'),
        (['pose', GARGOYLE, '--dirs', 'x'], 'dirs: no direction x here'),
        (['new', 'gargula', '--dir', os.path.join('specs', 'characters')], 'already exists'),
        (['new', 'x', '--template', 'robot'], 'template not found: robot (available: humanoid'),
        (['godot', GARGOYLE, '--project', REPO], 'not a Godot project'),
    ],
)
def test_user_errors_without_traceback(args, message):
    r = run(*args)
    assert r.returncode == 1
    assert r.stderr.startswith('error: ') and message in r.stderr, r.stderr
    assert 'Traceback' not in r.stderr


def test_version():
    r = run('--version')
    assert r.returncode == 0 and r.stdout.startswith('spritekiln 0.')


def test_validate_reports_and_exits_1(tmp_path):
    spec = tmp_path / 'bad.yaml'
    spec.write_text(
        open(GARGOYLE, encoding='utf-8').read().replace('parent: torso_rot', 'parent: nowhere', 1), encoding='utf-8'
    )
    with pytest.raises(SystemExit) as e:
        main(['validate', str(spec)])
    assert e.value.code == 1
