# Design proposals: quality, forms and speed

**Status:** proposed on 2026-10-27. All four stages (01–14) are done on the branch, each proposal with an
"Outcome" section (2026-10-27 and 28); 15 is not scheduled. 16 (heads, faces and hair) was added on 2026-10-30
after the maintainer tested the build. Each proposal is decided on its own;
accepted ones get an ADR in [`../decisions.md`](../decisions.md) and a line in [`../ROADMAP.md`](../ROADMAP.md).

**Where and when:** all of it is developed on the branch `plan/quality-forms-performance`, in four stages
(see "Order"). The stages are milestones on the branch, not releases: `main` gets no release per stage.
Everything ships together as **release 0.3**, when every stage is complete.

The goal of release 0.3: clearly better sprites, above all better **forms** (crisp plates, blades, brims and
cloth instead of "inflated" capsules), while frames render faster, use less memory, and the AI that drives
SpriteKiln spends fewer tokens per asset.

## Where we start (measured on 2026-10-27)
One uncached frame, rest pose, direction `s`. Windows 11, 16 threads, Python 3.12, numpy 2.5. "Traced peak"
is the numpy peak seen by `tracemalloc` for that frame, not the process size.

| spec | frame | groups | total | ray marching | `compose` | traced peak |
|---|---|---|---|---|---|---|
| templar | 96 px | 36 | 6.6 s | 96 % | 0.16 s | 28 MB |
| huntress | 96 px | 46 | 3.0 s | 95 % | 0.06 s | 21 MB |
| gargoyle | 64 px | 23 | 3.5 s | 95 % | 0.07 s | 11 MB |
| gas_lamp | 64 px | 6 | 0.55 s | 92 % | 0.03 s | 14 MB |

What the measurements and the code show:
- **Ray marching is the cost.** The per-pixel Python loops of `compose` are at most 5 % of a frame.
- **numpy is near its ceiling.** Prototypes on this workload: per-ray group culling 0.9–1.3×, adaptive
  supersampling 1.0–2.0×.
- **Group bounds are too loose.** A group with one primitive of radius r gets a bounding radius of r·√3
  (sphere → box → sphere). Fixing it alone gave 1.45–2.7× ([02](02-tight-bounds-and-exact-soft-shading.md)).
- **Shading depends on the bounds.** Soft shadows and AO read the distance to a bounding sphere as if it
  were the surface: tightening the bounds changes 324 colour pixels of the templar, with identical part ids
  ([02](02-tight-bounds-and-exact-soft-shading.md)).
- **One sample per pixel** instead of 3×3 renders the templar 6.7× faster
  ([01](01-draft-preview.md)).
- **Forms are limited to rounded primitives with smooth union.** The templar's cape is a cone with 7 cuts; the
  cross on its back is a cone shell with 11 boxes cut out. About a third of its groups exist only to put a
  colour on a surface ([09](09-surface-paint.md), [13](13-shape-operators.md)).
- **Materials all answer light the same way.** Light is one scalar mapped onto a ramp, with no highlight
  term: metal, cloth and stone read alike ([07](07-material-response.md)).
- **Normals go unused by the pixel stage.** The normal of every pixel is computed but only exported as the
  normal map; inner lines need a depth jump between two different parts ([08](08-lines-from-normals.md)).
- **Tokens:** specs are 8–41 KB (the huntress: 742 lines, about 10k tokens); `docs/agent` is 45 KB (about
  11k tokens); MCP previews are shrunk by non-integer factors, which distorts pixel art
  ([03](03-pixel-exact-previews.md), [04](04-spec-outline-and-show.md), [15](15-agent-context-budget.md)).

## Principles
- The YAML spec stays the single source, written by an AI or by hand. No step needs Blender or a GUI.
- The numpy renderer stays the reference: every faster backend is optional and compared to it.
- Existing specs keep their look unless a proposal says otherwise and explains why
  ([02](02-tight-bounds-and-exact-soft-shading.md) and [06](06-geometry-buffer.md) change pixels on purpose).
- Every visual change goes through the goldens (ADR-007) and a before/after sheet the maintainer approves.
- Measure before and after: each proposal names its numbers.
- Quality first: speed, memory and token savings never come at the cost of the result (see the decisions
  below).

## The proposals
| # | proposal | track | stage | depends on |
|---|---|---|---|---|
| [01](01-draft-preview.md) | Draft preview | speed | 1 | |
| [02](02-tight-bounds-and-exact-soft-shading.md) | Tight bounds and exact soft shading | speed, quality | 1 | |
| [03](03-pixel-exact-previews.md) | Pixel-exact previews for AIs | tokens, quality | 1 | |
| [04](04-spec-outline-and-show.md) | `spec outline` and `spec show` | tokens | 1 | |
| [05](05-compiled-scene-spike.md) | Compiled-scene spike (go / no-go) | speed, memory | 1 | 02 |
| [12](12-compiled-scene-and-fast-backend.md) | Compiled scene and fast backend | speed, memory | 2 | 05 |
| [13](13-shape-operators.md) | Shape operators | forms | 2 | 12 |
| [10](10-thin-parts-and-stability.md) | Thin parts and frame stability | quality | 2 | |
| [06](06-geometry-buffer.md) | Geometry buffer and deferred shading | quality, speed | 3 | 02 |
| [07](07-material-response.md) | Material response: highlights, rim, thresholds | quality | 3 | 06 |
| [08](08-lines-from-normals.md) | Lines from normals, edge highlights | quality | 3 | 06 |
| [09](09-surface-paint.md) | Surface paint | quality, speed, tokens | 3 | 06 |
| [11](11-render-style.md) | Render style presets | quality, tokens | 3 | 06–10 |
| [14](14-kits-and-extends.md) | Kits and `extends` | forms, tokens | 4 | 13 |
| [15](15-agent-context-budget.md) | Agent context budget | tokens | not scheduled yet | 03, 04 |
| [16](16-heads-faces-and-hair.md) | Heads, faces and hair | quality | 4 | 14 |

## Order
Four stages on the branch, in this order, all shipped together as release 0.3:
1. **Quick wins and one measurement:** 01, 02, 03, 04, 05. Draft previews, tight bounds with exact soft
   shading, pixel-exact previews, `spec outline/show`, and the spike that decides the speed track.
2. **Forms and speed:** 12, 13, 10. The compiled scene comes first, so each new primitive is written once in
   the representation both backends read. Then the shape operators. Then thin parts and stability, which the
   new thin plates and shells need.
3. **Surface and style:** 06, 07, 08, 09, 11. A geometry buffer separates ray marching from shading. On top of
   it come material highlights, lines from normals, surface paint, and style presets the renderer applies
   itself. Doing forms first means these are tuned on the final forms.
4. **Reuse:** 14. Kits built with the new shapes, material finishes and paint. Then 16: the head and the
   hair as kits, with the instructions and checks that keep first generations from round heads.

After release 0.3: tiles and environments ([ROADMAP 1](../ROADMAP.md)) and VFX. Tiles inherit the material
and style systems; rendering them earlier would mean redoing them.

## Not planned now
- **GPU rendering (wgpu-py).** It needs Python 3.11 or later (SpriteKiln supports 3.10), its API is still
  0.x, it is float32 only, behaviour varies by driver, and CI machines have no GPU. Revisit it as an opt-in
  preview after 12.
- **Mesh, voxel or image-to-3D import as the main path.** An AI cannot write meshes, the spec would stop
  being self-contained, and third-party models bring licences. Possible later as rigid "imported parts".
- **Noise displacement of surfaces.** It breaks the distance bound (more march steps) and turns into speckle
  at 64 px that the orphan cleanup deletes. Noise is offered as a paint mask instead (09).
- **Content-adaptive downscaling** (Kopf, Shamir and Peers 2013). It is built for photos; SpriteKiln already
  knows the exact part of every sample.

## Decisions
- **2026-10-27, no legacy shading ([02](02-tight-bounds-and-exact-soft-shading.md)).** Exact soft shading
  replaces the old look, with no flag to keep it: the shadows that came from bounding spheres were a bug.
- **2026-10-27, no weaker AI models ([15](15-agent-context-budget.md)).** Every agent and every check keeps
  the model chosen for the session; nothing is routed to a cheaper model to save tokens. Token savings come
  only from reading less (outlines, smaller specs, cropped images), never from a weaker model. ADR-019
  stands.
- **2026-10-27, spike 05: go ([ADR-029](../decisions.md)).** A numba kernel with per-ray group culling renders
  frames 5.7–6.6× faster with identical parts and at most 0.016 % of colour pixels different; design 12 is
  built as the optional `spritekiln[fast]` extra.
- **2026-10-27, order.** Stage 1: 01–05. Stage 2: 12, 13, 10 (forms before surface and style). Stage 3: 06, 07,
  08, 09, 11. Stage 4: 14. Proposal 15 is not scheduled yet.
- **2026-10-27, one release.** Everything is developed on the branch `plan/quality-forms-performance`. The
  stages are milestones, not releases: no release on `main` per stage. Release 0.3 ships everything, complete,
  when the maintainer decides it is ready.
- **2026-10-28, 15 is not in 0.3.** Saving context must not cost visual detail on unique designs: "numbers
  before images", drafts in 4 directions and a standard reference task would let small, expected details be
  lost silently. The proposal's "Review" section says how to rewrite it before it is scheduled.
- **2026-10-30, 16 joins 0.3.** In the maintainer's two test projects the first character came out with a
  ball for a head and a nose nobody asked for, both traced to the templates and the docs; 16 fixes the
  starting point (head and hair kits), the instructions (faces in the style, `brief.head`) and the checks
  (`pose --focus head`, `validate`, the art director) before 0.3 freezes the templates.

## Success, measured at release 0.3
| measure | now | target |
|---|---|---|
| templar, one uncached frame | 6.6 s | ≤ 2.5 s after 02; ≤ 0.8 s with the fast backend (if 05 passes) |
| templar, `pose --dirs all`, uncached | about 45 s | ≤ 5 s with `--draft` |
| full render: peak memory, all processes | measured in 05 (ADR-012: 85 MB per worker) | one process with threads, at most today's peak with all cores busy |
| templar groups / spec lines | 36 / 496 | ≤ 26 / ≤ 350 with paint and operators |
| a new character of the templar's complexity | about 500 lines | ≤ 250 lines with `extends` and kits |
| knowledge loaded on an AI's first turn | about 11k tokens | ≤ 4k tokens |
| look | | before/after sheets of templar, huntress and gargoyle approved; `review` value contrast does not regress |

## Format of each proposal
Status, track, stage and dependencies; **Problem** with evidence; **Goal**; **Proposal**; **Plan**;
**Validation**; **Risks and open questions**.

## Sources
- Dead Cells' 3D-to-2D pipeline: https://www.gamedeveloper.com/production/art-design-deep-dive-using-a-3d-pipeline-for-2d-animation-in-i-dead-cells-i-
- t3ssel8r's technique, recreated: https://www.davidhol.land/articles/3d-pixel-art-rendering/
- ProPixelizer user guide: https://sites.google.com/view/propixelizer/user-guide
- PixelOver shader manual: https://docs.pixelover.io/manual/shader/
- Inigo Quilez, 3D and 2D distance functions, smooth minimum, normals:
  https://iquilezles.org/articles/distfunctions/, https://iquilezles.org/articles/distfunctions2d/,
  https://iquilezles.org/articles/smin/, https://iquilezles.org/articles/normalsSDF/
- hg_sdf (Mercury): https://mercury.sexy/hg_sdf/
- fogleman/sdf: https://github.com/fogleman/sdf
- numba 0.63 release notes (no macOS Intel wheels): https://numba.readthedocs.io/en/stable/release/0.63.0-notes.html
- Keeter, Massively Parallel Rendering of Complex Closed-Form Implicit Surfaces:
  https://www.mattkeeter.com/research/mpr/keeter_mpr20.pdf
