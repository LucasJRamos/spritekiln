"""The MCP server, driven over stdio by a real MCP client, the way any AI client would use it."""

import asyncio
import base64
import json
import sys

import pytest

pytest.importorskip('mcp')

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

EXPECTED_TOOLS = {'guide', 'new', 'validate', 'pose', 'render', 'review', 'ref_compare', 'export', 'schema'}


async def _session(cwd, steps):
    params = StdioServerParameters(command=sys.executable, args=['-m', 'spritekiln', 'mcp'], cwd=str(cwd))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await steps(session)


def run(cwd, steps):
    return asyncio.run(_session(cwd, steps))


def parts(result):
    """(json payloads, png bytes) of a tool result."""
    texts, images = [], []
    for c in result.content:
        if c.type == 'text':
            try:
                texts.append(json.loads(c.text))
            except json.JSONDecodeError:
                texts.append(c.text)
        elif c.type == 'image':
            images.append(base64.b64decode(c.data))
    return texts, images


def test_tools_and_a_character_from_scratch(tmp_path):
    async def steps(s):
        names = {t.name for t in (await s.list_tools()).tools}
        out = {'tools': names}
        out['guide'] = parts(await s.call_tool('guide', {'topic': 'spec'}))[0][0]
        out['new'] = parts(await s.call_tool('new', {'name': 'hero', 'folder': 'specs'}))[0][0]
        spec = out['new']['spec']
        out['validate'] = parts(await s.call_tool('validate', {'spec': spec}))[0][0]
        out['pose'] = parts(await s.call_tool('pose', {'spec': spec, 'dirs': 's,e', 'scale': 2}))
        out['render'] = parts(
            await s.call_tool('render', {'spec': spec, 'anims': 'idle', 'dirs': 's,e', 'jobs': 1, 'sheets': True})
        )
        out['export'] = parts(await s.call_tool('export', {'spec': spec, 'engine': 'generic', 'to': 'game'}))[0][0]
        bad = await s.call_tool('validate', {'spec': 'missing.yaml'})
        out['error'] = (bad.is_error, bad.content[0].text)
        return out

    out = run(tmp_path, steps)
    assert EXPECTED_TOOLS <= out['tools']
    assert out['guide'].startswith('# Spec reference')
    assert out['validate']['ok'] and out['validate']['summary']['name'] == 'hero'
    texts, images = out['pose']
    assert texts[0]['directions'] == ['s', 'e'] and images[0].startswith(b'\x89PNG')
    texts, images = out['render']
    assert texts[0]['frames'] == 12 and texts[0]['qa']['ok'] and len(images) == 1
    assert sorted(p.split('game')[-1].replace('\\', '/') for p in out['export']['files']) == [
        '/hero/hero.json',
        '/hero/hero.png',
        '/hero/hero_emissive.png',
        '/hero/hero_normal.png',
    ]
    assert out['error'][0] and 'file not found' in out['error'][1]
    assert (tmp_path / 'game' / 'hero' / 'hero.json').exists()
