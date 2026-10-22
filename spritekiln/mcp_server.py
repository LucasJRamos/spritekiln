"""`spritekiln mcp`: SpriteKiln as Model Context Protocol tools (stdio), for any MCP client.

Tools return JSON and, where it helps, images (pose strips, contact sheets, review and comparison sheets),
so an AI that can see images judges the art directly and one that cannot still gets the numbers. Paths are
relative to the folder the client starts the server in (the project root). Needs the `mcp` extra.
"""

import functools
import io

from PIL import Image as PILImage

from . import __version__, api
from .errors import SpriteKilnError

INSTRUCTIONS = """SpriteKiln makes animated 8-direction pixel-art sprites from YAML specs.
Start with guide('workflow') and guide('spec'). Loop: edit the spec file -> validate -> pose (look at the
image) -> repeat; render only at the end, then export. If you cannot see images, use review numbers."""

MAX_SIDE = 1600  # images larger than this are scaled down before they are sent


def _png(path_or_img, max_side=MAX_SIDE):
    from mcp.server.mcpserver import Image

    im = PILImage.open(path_or_img) if isinstance(path_or_img, str) else path_or_img
    im = im.convert('RGBA')
    k = max(im.size) / max_side
    if k > 1:
        im = im.resize((max(1, round(im.width / k)), max(1, round(im.height / k))), PILImage.NEAREST)
    buf = io.BytesIO()
    im.save(buf, 'PNG')
    return Image(data=buf.getvalue(), format='png')


def _split(value):
    if value is None or isinstance(value, list):
        return value
    return [v.strip() for v in str(value).split(',') if v.strip()] or None


def build():
    """The MCPServer with every SpriteKiln tool registered."""
    from mcp.server.mcpserver import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError

    server = MCPServer('spritekiln', instructions=INSTRUCTIONS, version=__version__)

    def guarded(fn):
        @functools.wraps(fn)
        def run(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except SpriteKilnError as e:  # problems the user (or the AI) can fix -> a tool error, not a crash
                raise ToolError(str(e)) from None

        return run

    def tool(fn):
        return server.tool(description=fn.__doc__)(guarded(fn))

    @tool
    def guide(topic: str = 'workflow') -> str:
        """Read SpriteKiln's instructions. Topics: workflow (commands and loop), spec (the YAML format),
        modeling, splash-to-model, animation, art-direction, recipe (modeler -> director -> animator)."""
        from .agents import DOCS, source

        name = topic if topic.endswith('.md') else f'{topic}.md'
        if name not in DOCS:
            raise SpriteKilnError(f'unknown topic {topic!r} (use {", ".join(d[:-3] for d in DOCS)})')
        return source(name)

    @tool
    def new(
        name: str,
        template: str | None = None,
        folder: str | None = None,
        ref: str | None = None,
        view: str | None = None,
    ) -> dict:
        """Create a spec from a template (default folder: the project's specs folder + /characters). `ref`: a
        splash art copied next to the spec. `view`: topdown (3/4, 8 directions) or side (side-scroller profile,
        directions e and w); default from the project. `template`: humanoid or side_humanoid (the default for a
        side view). Returns the spec path."""
        return {'spec': api.new(name, template, folder, ref, view=view)}

    @tool
    def validate(spec: str) -> dict:
        """Check a spec: errors and warnings with file:line:column, and a summary (parts, animations, sockets)."""
        return api.validate(spec)

    @tool
    def pose(
        spec: str,
        anim: str | None = None,
        frame: int = 0,
        dirs: str = 'all',
        scale: int = 3,
        bg: str | None = None,
        tint: str | None = None,
    ) -> list:
        """Render one pose (rest, or `anim` at `frame`) in several directions side by side and return the image.
        Cheap (about 1 s per direction): use it after every edit. `bg`/`tint`: preview over the game's floor
        under the scene light."""
        out, dl = api.pose(spec, anim, frame, dirs, scale, bg, tint)
        return [{'image': out, 'directions': dl}, _png(out)]

    @tool
    def render(
        spec: str,
        anims: str | None = None,
        dirs: str | None = None,
        jobs: int | None = None,
        force: bool = False,
        sheets: bool = True,
    ) -> list:
        """Render animations (comma-separated; default all) and write atlas, JSON, GIFs and qa.json. Slow (about
        190 frames for 3 animations x 8 directions). Returns QA and paths, plus up to 3 contact sheets."""
        res = api.render(spec, _split(anims), _split(dirs), jobs, force)
        summary = {k: v for k, v in res.items() if k != 'spec'}
        out = [summary]
        if sheets:
            out += [_png(p) for p in list(res['contact_sheets'].values())[:3]]
        return out

    @tool
    def review(
        spec: str,
        anims: str | None = None,
        dirs: str | None = None,
        bg: str | None = None,
        tint: str | None = None,
        against: str | None = None,
        ref: str | None = None,
        ref_dir: str = 's',
    ) -> list:
        """Art-direction numbers and sheet: L* (median/p90) under the scene light, contrast with the floor
        (`bg`), pixels per material and direction, ramp bands, IoU against a splash (`ref`), legibility next to
        another spec (`against`). Returns the report and review.png."""
        from . import preview
        from .review import run

        rep = run(spec, _split(anims), _split(dirs), bg, preview.parse_tint(tint), against, ref, ref_dir)
        slim = {k: v for k, v in rep.items() if k != 'poses'}
        return [slim, _png(rep['files']['sheet'])]

    @tool
    def ref_compare(spec: str, image: str, dir: str = 's', anim: str | None = None, frame: int = 0) -> list:
        """Compare the model with a splash art seen from `dir`: silhouette IoU (corrected for the camera pitch,
        plus the raw value), hints on which height is too wide or narrow, and the comparison sheet."""
        res = api.ref_compare(spec, image, dir, anim, frame)
        return [{k: v for k, v in res.items() if k not in ('ref', 'render')}, _png(res['sheet'])]

    @tool
    def export(
        spec: str, engine: str | None = None, to: str | None = None, project: str | None = None, lit: bool = False
    ) -> dict:
        """Hand a rendered spec to the game engine (spritekiln.toml's, or `engine`: godot, unity, monogame,
        generic). Godot gets SpriteFrames, a CanvasTexture and a ready scene."""
        return api.export(spec, engine, None, to, project, lit)

    @tool
    def schema() -> str:
        """The JSON Schema of the spec format (every key, with descriptions)."""
        from .schema import SCHEMA_PATH

        with open(SCHEMA_PATH, encoding='utf-8') as fh:
            return fh.read()

    return server


def main():
    try:
        server = build()
    except ImportError:
        raise SpriteKilnError('the MCP server needs the mcp extra: pip install "spritekiln[mcp]"') from None
    server.run('stdio')
