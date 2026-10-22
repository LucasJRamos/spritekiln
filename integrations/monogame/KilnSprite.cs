// SpriteKiln -> MonoGame runtime (MonoGame 3.8+, .NET 6+). One file: copy it into your project.
// Loads <name>.json + <name>.png (and the _normal/_emissive maps) written by `spritekiln render` and plays
// animations in up to 8 directions with exact per-frame durations, gameplay events (hit, step_l...),
// sockets and mirrored directions (specs with `mirror: true`).
//
// Usage:
//   var sheet = KilnSheet.Load(GraphicsDevice, "sprites/gargula/gargula.json");
//   var anim  = new KilnAnimator(sheet);
//   anim.OnEvent += (name, evt) => { if (evt == "hit") DealDamage(); };
//   anim.Play("walk");                      // frame-0 events fire inside the call
//   anim.FaceTowards(velocity);             // screen vector (x right, y down) -> nearest direction
//   anim.Update(gameTime);
//   anim.Draw(spriteBatch, position);       // position = point on the ground under the character
//   if (anim.TryGetSocket("strike", out var off, out var depth)) SpawnSpark(position + off);
// Emissive layer: anim.DrawEmissive(...) inside a SpriteBatch with BlendState.Additive.
// Normal-mapped light: KilnLit.fx (see its header).

using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;

namespace SpriteKiln
{
    public sealed class KilnClip
    {
        public Rectangle[] Frames = Array.Empty<Rectangle>();
        public int[] DurationsMs = Array.Empty<int>();
        public Dictionary<int, string[]> Events = new();
        public Dictionary<string, Vector3?[]> Sockets = new();   // per frame: (x, y) px from the pivot, z = depth
        public int TotalMs;
    }

    public sealed class KilnAnimation
    {
        public string Name = "";
        public bool Loop;
        public Dictionary<string, KilnClip> ByDirection = new();  // rendered directions only
    }

    public sealed class KilnSheet
    {
        public Texture2D Texture = null!;
        public Texture2D? NormalMap;
        public Texture2D? EmissiveMap;
        public int FrameSize;
        public Vector2 Pivot;                                     // ground point under the model, in cell pixels
        public List<(string Name, float Yaw)> Directions = new(); // rendered and mirrored
        public Dictionary<string, string> Mirrors = new();        // mirrored direction -> rendered twin
        public Dictionary<string, KilnAnimation> Animations = new();

        public static KilnSheet Load(GraphicsDevice gd, string jsonPath)
        {
            string dir = Path.GetDirectoryName(jsonPath) ?? ".";
            return Parse(File.ReadAllText(jsonPath), file =>
            {
                string path = Path.Combine(dir, file);
                if (!File.Exists(path)) return null;
                using var fs = File.OpenRead(path);
                return Texture2D.FromStream(gd, fs);
            });
        }

        /// Reads a render JSON; `loadTexture` turns an atlas file name into a texture (null when missing).
        public static KilnSheet Parse(string json, Func<string, Texture2D?> loadTexture)
        {
            using var doc = JsonDocument.Parse(json);
            var root = doc.RootElement;
            var meta = root.GetProperty("meta");
            // SpriteKiln output format 1; files from pxforge <= 0.1 (or the `pxforge` command) use the old key
            var px = root.TryGetProperty("spritekiln", out var block) ? block : root.GetProperty("pxforge");
            var sheet = new KilnSheet
            {
                Texture = loadTexture(meta.GetProperty("image").GetString()!)!,
                FrameSize = px.GetProperty("frame_size").GetInt32(),
            };
            var pv = px.GetProperty("pivot");
            sheet.Pivot = new Vector2(pv.GetProperty("x").GetSingle(), pv.GetProperty("y").GetSingle());
            if (px.TryGetProperty("normal_map", out var nm))
                sheet.NormalMap = loadTexture(nm.GetString()!);
            if (px.TryGetProperty("emissive_map", out var em))
                sheet.EmissiveMap = loadTexture(em.GetString()!);

            var yaws = px.TryGetProperty("direction_yaw", out var dy) ? dy : default;
            float Yaw(string n) => yaws.ValueKind == JsonValueKind.Object && yaws.TryGetProperty(n, out var y)
                ? y.GetSingle() : DefaultYaw(n);
            foreach (var d in px.GetProperty("directions").EnumerateArray())
                sheet.Directions.Add((d.GetString()!, Yaw(d.GetString()!)));
            if (px.TryGetProperty("mirrors", out var mirrors))
                foreach (var m in mirrors.EnumerateObject())
                {
                    sheet.Mirrors[m.Name] = m.Value.GetString()!;
                    sheet.Directions.Add((m.Name, Yaw(m.Name)));
                }

            var frames = root.GetProperty("frames");
            foreach (var a in px.GetProperty("animations").EnumerateObject())
            {
                var anim = new KilnAnimation { Name = a.Name, Loop = a.Value.GetProperty("loop").GetBoolean() };
                foreach (var d in a.Value.GetProperty("directions").EnumerateObject())
                {
                    var names = d.Value.GetProperty("frames");
                    var durs = d.Value.GetProperty("durations");
                    var clip = new KilnClip
                    {
                        Frames = new Rectangle[names.GetArrayLength()],
                        DurationsMs = new int[names.GetArrayLength()],
                    };
                    int i = 0;
                    foreach (var f in names.EnumerateArray())
                    {
                        var r = frames.GetProperty(f.GetString()!).GetProperty("frame");
                        clip.Frames[i++] = new Rectangle(r.GetProperty("x").GetInt32(), r.GetProperty("y").GetInt32(),
                                                         r.GetProperty("w").GetInt32(), r.GetProperty("h").GetInt32());
                    }
                    i = 0;
                    foreach (var ms in durs.EnumerateArray()) { clip.DurationsMs[i] = ms.GetInt32(); clip.TotalMs += clip.DurationsMs[i]; i++; }
                    if (d.Value.TryGetProperty("events", out var evs))
                        foreach (var e in evs.EnumerateObject())
                        {
                            var list = new List<string>();
                            foreach (var s in e.Value.EnumerateArray()) list.Add(s.GetString()!);
                            clip.Events[int.Parse(e.Name)] = list.ToArray();
                        }
                    if (d.Value.TryGetProperty("sockets", out var sks))
                        foreach (var sk in sks.EnumerateObject())
                        {
                            var pts = new Vector3?[sk.Value.GetArrayLength()];
                            int j = 0;
                            foreach (var p in sk.Value.EnumerateArray())
                                pts[j++] = p.ValueKind == JsonValueKind.Array
                                    ? new Vector3(p[0].GetSingle(), p[1].GetSingle(), p[2].GetSingle())
                                    : null;                                   // hidden in this frame
                            clip.Sockets[sk.Name] = pts;
                        }
                    anim.ByDirection[d.Name] = clip;
                }
                sheet.Animations[a.Name] = anim;
            }
            return sheet;
        }

        static float DefaultYaw(string n) => n switch
        {
            "s" => 0, "se" => 45, "e" => 90, "ne" => 135, "n" => 180, "nw" => -135, "w" => -90, "sw" => -45, _ => 0
        };

        /// Screen-space vector (x right, y down) -> nearest direction (mirrored ones included).
        public string DirectionFor(Vector2 v, string fallback)
        {
            if (v.LengthSquared() < 1e-6f) return fallback;
            float yaw = MathHelper.ToDegrees(MathF.Atan2(v.X, v.Y));   // s = 0, e = 90, n = 180, w = -90
            string best = fallback; float bestD = float.MaxValue;
            foreach (var (name, y) in Directions)
            {
                float d = MathF.Abs(MathHelper.WrapAngle(MathHelper.ToRadians(yaw - y)));
                if (d < bestD) { bestD = d; best = name; }
            }
            return best;
        }
    }

    public sealed class KilnAnimator
    {
        public readonly KilnSheet Sheet;
        public string Animation { get; private set; } = "";
        public string Direction { get; private set; }
        public int Frame { get; private set; }
        public bool Finished { get; private set; }
        /// True while the current direction is drawn as a flipped copy of its twin.
        public bool Flipped => Sheet.Mirrors.ContainsKey(Direction);
        public float Speed = 1f;
        public event Action<string, string>? OnEvent;      // (animation, event)
        public event Action<string>? OnFinished;           // a non-looping animation reached its end

        double _t;
        int _serial;

        public KilnAnimator(KilnSheet sheet)
        {
            Sheet = sheet;
            Direction = sheet.Directions.Count > 0 ? sheet.Directions[0].Name : "s";
        }

        /// Plays an animation (no direction suffix). Restarts only when `restart`, when it changed or when it had
        /// finished. Events of frame 0 fire inside this call.
        public void Play(string name, bool restart = false)
        {
            if (!Sheet.Animations.ContainsKey(name)) throw new ArgumentException($"SpriteKiln: animation '{name}' not found");
            if (name == Animation && !restart && !Finished) return;
            Animation = name; Frame = 0; _t = 0; Finished = false; _serial++;
            Fire(0);
        }

        public void FaceTowards(Vector2 screenDir) => SetDirection(Sheet.DirectionFor(screenDir, Direction));

        /// Sets the direction by name (s, se, e...), keeping the current frame.
        public void SetDirection(string dir)
        {
            foreach (var (name, _) in Sheet.Directions)
                if (name == dir) { Direction = dir; return; }
        }

        KilnClip? Clip()
        {
            if (!Sheet.Animations.TryGetValue(Animation, out var a)) return null;
            string dir = Sheet.Mirrors.TryGetValue(Direction, out var twin) ? twin : Direction;
            return a.ByDirection.TryGetValue(dir, out var c) ? c : null;
        }

        public void Update(GameTime gt) => Update(gt.ElapsedGameTime.TotalMilliseconds);

        /// Advances by `ms` milliseconds (times Speed), firing the events of every frame that becomes visible.
        public void Update(double ms)
        {
            var c = Clip();
            if (c == null || Finished || c.Frames.Length == 0) return;
            _t += ms * Speed;
            int serial = _serial;
            while (serial == _serial && _t >= Math.Max(1, c.DurationsMs[Frame]))
            {
                _t -= Math.Max(1, c.DurationsMs[Frame]);
                if (Frame + 1 >= c.Frames.Length)
                {
                    if (Sheet.Animations[Animation].Loop) Frame = 0;
                    else { Finished = true; _t = 0; OnFinished?.Invoke(Animation); return; }
                }
                else Frame++;
                Fire(Frame);   // a listener may start another animation: the loop then stops
            }
        }

        void Fire(int f)
        {
            var c = Clip();
            string anim = Animation;
            if (c != null && c.Events.TryGetValue(f, out var evs))
                foreach (var e in evs) OnEvent?.Invoke(anim, e);
        }

        /// Socket of the current frame: `offset` in pixels from the ground pivot (x right, y down; multiply by
        /// the draw scale) and `depth` in pixels toward the viewer (> 0 in front of the body, < 0 behind).
        /// False when the clip has no such socket or it is hidden in this frame.
        public bool TryGetSocket(string name, out Vector2 offset, out float depth)
        {
            offset = Vector2.Zero; depth = 0f;
            var c = Clip();
            if (c == null || !c.Sockets.TryGetValue(name, out var pts) || Frame >= pts.Length || pts[Frame] is not Vector3 v)
                return false;
            offset = new Vector2(Flipped ? -v.X : v.X, v.Y); depth = v.Z;
            return true;
        }

        public Rectangle Source
        {
            get
            {
                var c = Clip();
                return c == null || c.Frames.Length == 0 ? Rectangle.Empty : c.Frames[Math.Min(Frame, c.Frames.Length - 1)];
            }
        }

        /// Draws with the sprite's ground pivot at `groundPos` (flipped for mirrored directions). Use integer
        /// scales for crisp pixels and SamplerState.PointClamp in SpriteBatch.Begin.
        public void Draw(SpriteBatch sb, Vector2 groundPos, Color? tint = null, int scale = 1, float layerDepth = 0f)
            => DrawWith(Sheet.Texture, sb, groundPos, tint ?? Color.White, scale, layerDepth);

        /// Draws the emissive layer (eyes, magic, fire) in the same place: call it inside a SpriteBatch with
        /// BlendState.Additive, after the sprites, so it stays bright in dark scenes.
        public void DrawEmissive(SpriteBatch sb, Vector2 groundPos, int scale = 1, float layerDepth = 0f)
        {
            if (Sheet.EmissiveMap != null) DrawWith(Sheet.EmissiveMap, sb, groundPos, Color.White, scale, layerDepth);
        }

        void DrawWith(Texture2D tex, SpriteBatch sb, Vector2 groundPos, Color tint, int scale, float layerDepth)
        {
            var src = Source;
            bool flip = Flipped;
            // SpriteBatch flips the texture inside the quad, not around the origin: mirror the origin too
            var origin = flip ? new Vector2(src.Width - Sheet.Pivot.X, Sheet.Pivot.Y) : Sheet.Pivot;
            sb.Draw(tex, new Vector2(MathF.Round(groundPos.X), MathF.Round(groundPos.Y)), src, tint, 0f, origin, scale,
                    flip ? SpriteEffects.FlipHorizontally : SpriteEffects.None, layerDepth);
        }
    }
}
