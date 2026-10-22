"""Check an installed `spritekiln` command the way a new user and an AI client would use it.

    python tools/install_smoke.py

Runs the `spritekiln` found on the PATH (not this checkout) in an empty temporary folder: --version, new,
validate, pose, init with an AI adapter (which writes .mcp.json only when the [mcp] extra is installed), then
starts `spritekiln mcp` and lists its tools over stdio with plain JSON-RPC. Needs only the standard library.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

TOOLS = {'guide', 'new', 'validate', 'pose', 'render', 'review', 'ref_compare', 'export', 'schema'}


def run(exe, *args, cwd):
    print('$ spritekiln', *args, flush=True)
    out = subprocess.run([exe, *args], cwd=cwd, capture_output=True, text=True, timeout=600)
    print(out.stdout + out.stderr, flush=True)
    if out.returncode:
        sys.exit(f'spritekiln {" ".join(args)} failed with exit code {out.returncode}')
    return out.stdout


def mcp_tools(exe, cwd):
    """Initialize an MCP session over stdio and return the tool names."""
    proc = subprocess.Popen(
        [exe, 'mcp'], cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding='utf-8'
    )

    def send(msg):
        proc.stdin.write(json.dumps({'jsonrpc': '2.0', **msg}) + '\n')
        proc.stdin.flush()

    def reply(msg_id):
        for line in proc.stdout:
            msg = json.loads(line)
            if msg.get('id') == msg_id:
                if 'error' in msg:
                    sys.exit(f'MCP error: {msg["error"]}')
                return msg['result']
        sys.exit('the MCP server closed its output')

    try:
        client = {'name': 'install-smoke', 'version': '1'}
        hello = {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': client}
        send({'id': 1, 'method': 'initialize', 'params': hello})
        server = reply(1)['serverInfo']
        send({'method': 'notifications/initialized'})
        send({'id': 2, 'method': 'tools/list'})
        names = {t['name'] for t in reply(2)['tools']}
        print(f'MCP server {server["name"]} {server.get("version", "")}: {sorted(names)}', flush=True)
        return names
    finally:
        proc.kill()
        proc.wait()


def main():
    exe = shutil.which('spritekiln')
    if not exe:
        sys.exit('spritekiln is not on the PATH')
    print('spritekiln:', exe, flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        run(exe, '--version', cwd=tmp)
        run(exe, 'new', 'knight', cwd=tmp)
        spec = os.path.join('specs', 'characters', 'knight', 'knight.yaml')
        run(exe, 'validate', spec, cwd=tmp)
        run(exe, 'pose', spec, '--dirs', 's', cwd=tmp)
        if not os.path.exists(os.path.join(tmp, 'specs', 'characters', 'knight', 'out', 'pose_rest_0.png')):
            sys.exit('pose wrote no image')
        game = os.path.join(tmp, 'game')
        os.makedirs(game)
        run(exe, 'init', '--engine', 'generic', '--ai', 'claude', cwd=game)
        if not os.path.exists(os.path.join(game, '.mcp.json')):
            sys.exit('init wrote no .mcp.json: the [mcp] extra is missing')
        missing = TOOLS - mcp_tools(exe, game)
        if missing:
            sys.exit(f'MCP tools missing: {sorted(missing)}')
    print('install OK', flush=True)


if __name__ == '__main__':
    main()
