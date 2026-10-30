"""`spritekiln mcp`: SpriteKiln as Model Context Protocol tools (stdio), for any MCP client.

Tools return JSON and, where it helps, images (pose strips, contact sheets, review and comparison sheets),
so an AI that can see images judges the art directly and one that cannot still gets the numbers. Paths are
relative to the folder the client starts the server in (the project root). Needs the `mcp` extra.
"""

import functools
import io
from typing import Any

from PIL import Image as PILImage

from . import __version__, api
from .errors import SpriteKilnError

INSTRUCTIONS = """SpriteKiln makes animated 8-direction pixel-art sprites from YAML specs.
First call style(): if no art style is recorded for the project, interview the user with the questions of
guide('style') and record the answers with style(answers=...) before generating anything; every asset
follows the recorded style. Then guide('workflow') and guide('spec'). To read a spec, spec_outline() it and
spec_show() the blocks you edit. Loop: edit the spec file -> validate -> pose (look at the image) -> repeat;
render only at the end, then export. If you cannot see images, use review numbers."""


def _pngs(path_or_img):
    """An image as MCP images. Previews are already sized to an AI's image budget (preview.MAX_SIDE); a larger
    one is cut into pieces rather than shrunk, because shrinking by a fraction distorts pixel art."""
    from mcp.server.mcpserver import Image

    from . import preview

    im = PILImage.open(path_or_img) if isinstance(path_or_img, str) else path_or_img
    out = []
    for piece in preview.tiles(im.convert('RGBA')):
        buf = io.BytesIO()
        piece.save(buf, 'PNG')
        out.append(Image(data=buf.getvalue(), format='png'))
    return out


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
            except (OSError, KeyError, ValueError) as e:  # anything else still says what went wrong
                raise ToolError(f'{type(e).__name__}: {e}') from None

        return run

    def tool(fn):
        return server.tool(description=fn.__doc__)(guarded(fn))

    @tool
    def guide(topic: str = 'workflow') -> str:
        """Read SpriteKiln's instructions. Topics: workflow (commands and loop), style (the art-style interview),
        spec (the YAML format), modeling, splash-to-model, animation, art-direction, recipe (modeler -> director
        -> animator)."""
        from .agents import DOCS, source

        name = topic if topic.endswith('.md') else f'{topic}.md'
        if name not in DOCS:
            raise SpriteKilnError(f'unknown topic {topic!r} (use {", ".join(d[:-3] for d in DOCS)})')
        return source(name)

    @tool
    def style(answers: dict[str, Any] | None = None) -> dict:
        """The project's art style (the [style] table of spritekiln.toml). Call it before the first asset of a
        session. Without `answers`: the recorded style (follow it), or `recorded: false` with suggested answers;
        then interview the user with the questions of guide('style') before generating anything, confirm a
        summary, and call style(answers={...}) with view (topdown|side), height (px of a human-sized character
        on screen), directions (8|4|2), mirror (yes|no), palette, colors, outline (selective|dark|colored|none),
        outline_color, shading (soft|flat|toon), lines (depth|depth+normal|none), highlights (yes|no), dither
        (none|bayer2|bayer4), light (classic|top|dramatic|soft|flat), proportions (stylized|chibi|realistic), face
        (minimal|simple|detailed), animation (fluid|snappy), snap (yes|no), references (list), notes. The renderer
        applies the look fields to every asset (style_preview shows them). A recorded style changes only when the
        user explicitly asks: then pass only the changed answers."""
        from . import style as S
        from .update import stale_note

        res = S.record(answers) if answers else S.status()
        note = stale_note()
        if note:
            res['note'] = note
        return res

    @tool
    def style_preview(
        spec: str | None = None,
        fields: str | None = None,
        direction: str = 'se',
        anim: str | None = None,
        frame: int = 0,
        scale: int = 4,
    ) -> list:
        """The same pose under every choice of the style's look fields (outline, shading, lines, highlights,
        dither, light; comma-separated `fields` for some), one row per field, the project's style for the rest
        (* marks it). Without `spec`, the humanoid template: show it to the user during the style interview so
        they choose by looking."""
        out, rows = api.style_preview(spec, _split(fields), direction, anim, frame, scale)
        return [{'image': out, 'rows': rows}, *_pngs(out)]

    @tool
    def new(
        name: str,
        template: str | None = None,
        folder: str | None = None,
        ref: str | None = None,
        view: str | None = None,
        extends: bool = False,
    ) -> dict:
        """Create a spec from a template (default folder: the project's specs folder + /characters). `ref`: a
        splash art copied next to the spec. `view`: topdown (3/4, 8 directions) or side (side-scroller profile,
        directions e and w); default from the project. `template`: humanoid or side_humanoid (the default for a
        side view). `extends`: a short spec that extends the template (states only what differs) instead of a
        copy. Returns the spec path."""
        from .style import missing_note

        path = api.new(name, template, folder, ref, view=view, extends=extends)
        note = missing_note(path)
        return {'spec': path, **({'note': note} if note else {})}

    @tool
    def kits(name: str | None = None) -> dict | list:
        """The kits a spec can add with `use: [{kit, as, at, with}]` (weapons, shields, headwear, capes, belts,
        heads and hair): name, attachment frame, summary and params. With `name`: that kit, its params block with
        comments and its channels block (what an animator drives, named `<as>_<channel>` in a spec)."""
        return api.kits(name)

    @tool
    def validate(spec: str) -> dict:
        """Check a spec: errors and warnings with file:line:column, and a summary (parts, animations, sockets)."""
        return api.validate(spec)

    @tool
    def spec_outline(spec: str) -> str:
        """A map of a spec file: each part, animation, IK chain and socket on a line with its line range and a
        summary (material, space, primitives; frames, duration, loop), the other sections as one line of names.
        Read it instead of the whole file, then spec_show the blocks you will edit."""
        from . import outline

        return outline.outline_text(spec)

    @tool
    def spec_show(spec: str, paths: str, resolved: bool = False) -> str:
        """The numbered source lines of some blocks of a spec, comments kept: comma-separated paths such as
        parts.helm, animations.walk, animations.walk.keys[2] (a mirrored _R item shows its _L source). Edit
        those lines in place. `resolved`: the blocks as the renderer sees them (mirrored, defaults filled in)."""
        from . import outline

        return outline.show(spec, _split(paths), resolved)

    @tool
    def pose(
        spec: str,
        anim: str | None = None,
        frame: int = 0,
        dirs: str = 'all',
        scale: int | None = None,
        bg: str | None = None,
        tint: str | None = None,
        draft: bool = False,
        focus: str | None = None,
    ) -> list:
        """Render one pose (rest, or `anim` at `frame`) in several directions side by side and return the image.
        Cheap (about 1 s per direction): use it after every edit. `draft`: one sample per pixel, about 6x
        faster, for silhouettes and poses (rougher edges); look at a full pose before `render`. `bg`/`tint`:
        preview over the game's floor under the scene light. `focus`: a close-up of a bone and what hangs below
        it (`head`: the head, hair, eyes and headwear) or of parts by name; judge every face with it. The image is
        cropped around the sprite (or the focus) and zoomed by a whole factor up to `scale` (3; 12 with `focus`)
        that fits an image budget: `zoom` and `crop` ([x0, y0, x1, y1] in frame pixels) map its pixels back to the
        frame."""
        if scale is None:
            scale = 12 if focus else 3
        out, dl, view = api.pose(spec, anim, frame, dirs, scale, bg, tint, draft=draft, focus=focus)
        return [
            {'image': out, 'directions': dl, 'draft': draft, 'zoom': view['scale'], 'crop': view['crop']},
            *_pngs(out),
        ]

    @tool
    def render(
        spec: str,
        anims: str | None = None,
        dirs: str | None = None,
        jobs: int | None = None,
        force: bool = False,
        sheets: bool = True,
        draft: bool = False,
    ) -> list:
        """Render animations (comma-separated; default all) and write atlas, JSON, GIFs and qa.json. Slow (about
        190 frames for 3 animations x 8 directions). Returns QA and paths, plus up to 3 contact sheets.
        `draft`: one sample per pixel and previews only (GIFs and contact sheets, no atlas, JSON or QA), to check
        motion quickly."""
        res = api.render(spec, _split(anims), _split(dirs), jobs, force, draft=draft)
        summary = {k: v for k, v in res.items() if k != 'spec'}
        out = [summary]
        if sheets:
            out += [im for p in list(res['contact_sheets'].values())[:3] for im in _pngs(p)]
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
        return [slim, *_pngs(rep['files']['sheet'])]

    @tool
    def ref_compare(spec: str, image: str, dir: str = 's', anim: str | None = None, frame: int = 0) -> list:
        """Compare the model with a splash art seen from `dir`: silhouette IoU (corrected for the camera pitch,
        plus the raw value), hints on which height is too wide or narrow, and the comparison sheet."""
        res = api.ref_compare(spec, image, dir, anim, frame)
        return [{k: v for k, v in res.items() if k not in ('ref', 'render')}, *_pngs(res['sheet'])]

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
