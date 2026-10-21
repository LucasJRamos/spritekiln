// pxforge -> MonoGame runtime (MonoGame 3.8+, .NET 6+).
// Loads <name>.json + <name>.png (and optional _normal/_emissive maps) exported by `pxforge render`
// and plays 8-direction animations with per-frame durations and gameplay events (hit, step_l, ...).
//
// Usage:
//   var sheet = PxSheet.Load(GraphicsDevice, "Content/sprites/gargula/gargula.json");
//   var anim  = new PxAnimator(sheet);
//   anim.OnEvent += (name, evt) => { if (evt == "hit") DealDamage(); };
//   anim.Play("walk");
//   anim.FaceTowards(velocity);           // picks the nearest of the exported directions
//   anim.Update(gameTime);
//   anim.Draw(spriteBatch, position);     // position = point on the ground under the character

using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;

namespace Pxforge
{
    public sealed class PxClip
    {
        public Rectangle[] Frames = Array.Empty<Rectangle>();
        public int[] DurationsMs = Array.Empty<int>();
        public Dictionary<int, string[]> Events = new();
        public int TotalMs;
    }

    public sealed class PxAnimation
    {
        public string Name = "";
        public bool Loop;
        public Dictionary<string, PxClip> ByDirection = new();
    }

    public sealed class PxSheet
    {
        public Texture2D Texture = null!;
        public Texture2D? NormalMap;
        public Texture2D? EmissiveMap;
        public int FrameSize;
        public Vector2 Pivot;                       // ground point under the character, in frame pixels
        public List<(string Name, float Yaw)> Directions = new();
        public Dictionary<string, PxAnimation> Animations = new();

        public static PxSheet Load(GraphicsDevice gd, string jsonPath)
        {
            string dir = Path.GetDirectoryName(jsonPath) ?? ".";
            using var doc = JsonDocument.Parse(File.ReadAllText(jsonPath));
            var root = doc.RootElement;
            var meta = root.GetProperty("meta");
            var px = root.GetProperty("pxforge");
            var sheet = new PxSheet
            {
                Texture = LoadTex(gd, Path.Combine(dir, meta.GetProperty("image").GetString()!)),
                FrameSize = px.GetProperty("frame_size").GetInt32(),
            };
            var pv = px.GetProperty("pivot");
            sheet.Pivot = new Vector2(pv.GetProperty("x").GetSingle(), pv.GetProperty("y").GetSingle());
            if (px.TryGetProperty("normal_map", out var nm) && File.Exists(Path.Combine(dir, nm.GetString()!)))
                sheet.NormalMap = LoadTex(gd, Path.Combine(dir, nm.GetString()!));
            if (px.TryGetProperty("emissive_map", out var em) && File.Exists(Path.Combine(dir, em.GetString()!)))
                sheet.EmissiveMap = LoadTex(gd, Path.Combine(dir, em.GetString()!));

            var yaws = px.TryGetProperty("direction_yaw", out var dy) ? dy : default;
            foreach (var d in px.GetProperty("directions").EnumerateArray())
            {
                string n = d.GetString()!;
                float yaw = yaws.ValueKind == JsonValueKind.Object && yaws.TryGetProperty(n, out var y)
                    ? y.GetSingle() : DefaultYaw(n);
                sheet.Directions.Add((n, yaw));
            }

            var frames = root.GetProperty("frames");
            foreach (var a in px.GetProperty("animations").EnumerateObject())
            {
                var anim = new PxAnimation { Name = a.Name, Loop = a.Value.GetProperty("loop").GetBoolean() };
                foreach (var d in a.Value.GetProperty("directions").EnumerateObject())
                {
                    var names = d.Value.GetProperty("frames");
                    var durs = d.Value.GetProperty("durations");
                    var clip = new PxClip
                    {
                        Frames = new Rectangle[names.GetArrayLength()],
                        DurationsMs = new int[names.GetArrayLength()],
                    };
                    int i = 0;
                    foreach (var f in names.EnumerateArray())
                    {
                        var r = frames.GetProperty(f.GetString()!).GetProperty("frame");
                        clip.Frames[i] = new Rectangle(r.GetProperty("x").GetInt32(), r.GetProperty("y").GetInt32(),
                                                       r.GetProperty("w").GetInt32(), r.GetProperty("h").GetInt32());
                        i++;
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
                    anim.ByDirection[d.Name] = clip;
                }
                sheet.Animations[a.Name] = anim;
            }
            return sheet;
        }

        static Texture2D LoadTex(GraphicsDevice gd, string path)
        {
            using var fs = File.OpenRead(path);
            return Texture2D.FromStream(gd, fs);
        }

        static float DefaultYaw(string n) => n switch
        {
            "s" => 0, "se" => 45, "e" => 90, "ne" => 135, "n" => 180, "nw" => -135, "w" => -90, "sw" => -45, _ => 0
        };

        /// Screen-space vector (x right, y down) -> nearest exported direction name.
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

    public sealed class PxAnimator
    {
        public readonly PxSheet Sheet;
        public string Animation { get; private set; } = "";
        public string Direction { get; private set; }
        public int Frame { get; private set; }
        public bool Finished { get; private set; }
        public float Speed = 1f;
        public event Action<string, string>? OnEvent;      // (animation, event)
        public event Action<string>? OnFinished;           // non-looping animation reached its end

        double _t;

        public PxAnimator(PxSheet sheet)
        {
            Sheet = sheet;
            Direction = sheet.Directions.Count > 0 ? sheet.Directions[0].Name : "s";
        }

        public void Play(string name, bool restart = false)
        {
            if (!Sheet.Animations.ContainsKey(name)) throw new ArgumentException($"pxforge: animation '{name}' not found");
            if (name == Animation && !restart && !Finished) return;
            Animation = name; Frame = 0; _t = 0; Finished = false;
            Fire(0);
        }

        public void FaceTowards(Vector2 screenDir) => Direction = Sheet.DirectionFor(screenDir, Direction);
        public void SetDirection(string dir) { if (Clip(dir) != null) Direction = dir; }

        PxClip? Clip(string? dir = null)
        {
            if (!Sheet.Animations.TryGetValue(Animation, out var a)) return null;
            return a.ByDirection.TryGetValue(dir ?? Direction, out var c) ? c : null;
        }

        public void Update(GameTime gt)
        {
            var c = Clip();
            if (c == null || Finished || c.Frames.Length == 0) return;
            _t += gt.ElapsedGameTime.TotalMilliseconds * Speed;
            while (_t >= c.DurationsMs[Frame])
            {
                _t -= c.DurationsMs[Frame];
                if (Frame + 1 >= c.Frames.Length)
                {
                    if (Sheet.Animations[Animation].Loop) Frame = 0;
                    else { Finished = true; OnFinished?.Invoke(Animation); return; }
                }
                else Frame++;
                Fire(Frame);
            }
        }

        void Fire(int f)
        {
            var c = Clip();
            if (c != null && c.Events.TryGetValue(f, out var evs))
                foreach (var e in evs) OnEvent?.Invoke(Animation, e);
        }

        public Rectangle Source => Clip()?.Frames[Math.Min(Frame, Clip()!.Frames.Length - 1)] ?? Rectangle.Empty;

        /// Draws with the sprite's ground pivot at `groundPos`. Use integer scales for crisp pixels
        /// and SamplerState.PointClamp in SpriteBatch.Begin.
        public void Draw(SpriteBatch sb, Vector2 groundPos, Color? tint = null, int scale = 1, float layerDepth = 0f)
        {
            sb.Draw(Sheet.Texture, new Vector2(MathF.Round(groundPos.X), MathF.Round(groundPos.Y)), Source,
                    tint ?? Color.White, 0f, Sheet.Pivot, scale, SpriteEffects.None, layerDepth);
        }
    }
}
