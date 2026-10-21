using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.AssetImporters;
using UnityEngine;

namespace SpriteKiln.Editor
{
    /// <summary>
    /// Imports a SpriteKiln render: <c>&lt;name&gt;.kiln</c> (the render JSON under another extension, since
    /// Unity owns <c>.json</c>) next to <c>&lt;name&gt;.png</c>, <c>_normal.png</c> and <c>_emissive.png</c>.
    /// Produces a <see cref="KilnSheet"/>, the atlases as point-filtered textures, one sprite per frame (pivot
    /// on the ground point, normal map as the <c>_NormalMap</c> secondary texture for 2D lights) and, when
    /// enabled, an AnimationClip per animation and direction with AnimationEvents.
    /// </summary>
    [ScriptedImporter(1, "kiln")]
    public class KilnImporter : ScriptedImporter
    {
        [Tooltip("Pixels per Unity unit for the sprites, sockets and depth")]
        public float pixelsPerUnit = 32;

        [Tooltip("AnimationClips named <anim>_<dir> for the Animator (KilnAnimator does not need them)")]
        public bool animationClips = true;

        [Tooltip("Method the clips' AnimationEvents call, with the event name as a string")]
        public string eventFunction = "OnKilnEvent";

        public override void OnImportAsset(AssetImportContext ctx)
        {
            var data = Json.Parse(File.ReadAllText(ctx.assetPath)) as Dictionary<string, object>;
            var block = Block(data);
            if (block == null)
            {
                ctx.LogImportError($"{ctx.assetPath} is not a SpriteKiln render (no \"spritekiln\" block)");
                return;
            }
            string dir = Path.GetDirectoryName(ctx.assetPath);
            var meta = (Dictionary<string, object>)data["meta"];
            var frames = (Dictionary<string, object>)data["frames"];
            string name = Get(block, "name", Path.GetFileNameWithoutExtension(ctx.assetPath));

            var sheet = ScriptableObject.CreateInstance<KilnSheet>();
            sheet.name = name;
            sheet.frameSize = (int)Num(block["frame_size"]);
            var pivot = (Dictionary<string, object>)block["pivot"];
            sheet.pivot = new Vector2(Num(pivot["x"]), Num(pivot["y"]));
            sheet.pixelsPerUnit = pixelsPerUnit;
            sheet.view = Get(block, "view", "topdown");

            sheet.atlas = LoadTexture(ctx, dir, (string)meta["image"], false);
            if (sheet.atlas == null)
                return;
            sheet.atlas.name = name;
            ctx.AddObjectToAsset("atlas", sheet.atlas);
            sheet.normalMap = LoadTexture(ctx, dir, Get<string>(block, "normal_map", null), true);
            if (sheet.normalMap != null)
            {
                sheet.normalMap.name = name + "_normal";
                ctx.AddObjectToAsset("normal", sheet.normalMap);
            }
            var emissive = LoadTexture(ctx, dir, Get<string>(block, "emissive_map", null), false);
            if (emissive != null && emissive.GetPixels32().Any(p => p.a > 0))
            {
                emissive.name = name + "_emissive";
                sheet.emissiveMap = emissive;
                ctx.AddObjectToAsset("emissive", emissive);
            }

            var yaws = (Dictionary<string, object>)block["direction_yaw"];
            var mirrors = block.TryGetValue("mirrors", out var m) && m != null
                ? (Dictionary<string, object>)m
                : new Dictionary<string, object>();
            foreach (var d in ((List<object>)block["directions"]).Cast<string>())
                sheet.directions.Add(new KilnSheet.Direction { name = d, yaw = Num(yaws[d]), mirrorOf = "" });
            foreach (var kv in mirrors)
                sheet.directions.Add(new KilnSheet.Direction { name = kv.Key, yaw = Num(yaws[kv.Key]), mirrorOf = (string)kv.Value });
            if (block.TryGetValue("sockets", out var socks) && socks != null)
                sheet.socketNames.AddRange(((List<object>)socks).Cast<string>());

            var secondary = sheet.normalMap == null
                ? Array.Empty<SecondarySpriteTexture>()
                : new[] { new SecondarySpriteTexture { name = "_NormalMap", texture = sheet.normalMap } };
            var sprites = new Dictionary<string, Sprite>();
            var emissiveSprites = new Dictionary<string, Sprite>();
            foreach (var kv in (Dictionary<string, object>)block["animations"])
            {
                var A = (Dictionary<string, object>)kv.Value;
                var anim = new KilnSheet.Anim { name = kv.Key, loop = A.TryGetValue("loop", out var l) && (bool)l };
                foreach (var dv in (Dictionary<string, object>)A["directions"])
                {
                    var D = (Dictionary<string, object>)dv.Value;
                    var keys = ((List<object>)D["frames"]).Cast<string>().ToArray();
                    var clip = new KilnSheet.Clip
                    {
                        direction = dv.Key,
                        sprites = keys.Select(k => MakeSprite(ctx, sheet, sheet.atlas, frames, k, k, secondary, sprites)).ToArray(),
                        emissive = sheet.emissiveMap == null
                            ? Array.Empty<Sprite>()
                            : keys.Select(k => MakeSprite(ctx, sheet, sheet.emissiveMap, frames, k, k + "_emissive", null, emissiveSprites)).ToArray(),
                        durations = ((List<object>)D["durations"]).Select(x => Num(x)).ToArray(),
                    };
                    if (D.TryGetValue("events", out var ev) && ev != null)
                        foreach (var e in (Dictionary<string, object>)ev)
                            foreach (var n in ((List<object>)e.Value).Cast<string>())
                                clip.events.Add(new KilnSheet.FrameEvent { frame = int.Parse(e.Key), name = n });
                    clip.events.Sort((a, b) => a.frame.CompareTo(b.frame));
                    if (D.TryGetValue("sockets", out var sk) && sk != null)
                        foreach (var s in (Dictionary<string, object>)sk)
                        {
                            var pts = (List<object>)s.Value;
                            clip.sockets.Add(new KilnSheet.SocketTrack
                            {
                                name = s.Key,
                                points = pts.Select(p => p is List<object> v ? new Vector3(Num(v[0]), Num(v[1]), Num(v[2])) : Vector3.zero).ToArray(),
                                visible = pts.Select(p => p != null).ToArray(),
                            });
                        }
                    anim.clips.Add(clip);
                }
                sheet.animations.Add(anim);
            }

            if (animationClips)
                foreach (var anim in sheet.animations)
                    foreach (var d in sheet.directions)
                    {
                        var clip = sheet.FindClip(anim.name, d.name, out bool flipped);
                        if (clip != null)
                            ctx.AddObjectToAsset($"clip_{anim.name}_{d.name}", MakeClip($"{anim.name}_{d.name}", anim.loop, clip, flipped));
                    }

            ctx.AddObjectToAsset("sheet", sheet);
            ctx.SetMainObject(sheet);
        }

        Sprite MakeSprite(AssetImportContext ctx, KilnSheet sheet, Texture2D tex, Dictionary<string, object> frames, string key,
            string id, SecondarySpriteTexture[] secondary, Dictionary<string, Sprite> made)
        {
            if (made.TryGetValue(id, out var done))
                return done;
            var f = (Dictionary<string, object>)((Dictionary<string, object>)frames[key])["frame"];
            float x = Num(f["x"]), y = Num(f["y"]), w = Num(f["w"]), h = Num(f["h"]);
            var rect = new Rect(x, tex.height - y - h, w, h); // Unity textures start at the bottom-left
            var pivot = new Vector2(sheet.pivot.x / w, 1f - sheet.pivot.y / h);
            var sprite = secondary == null
                ? Sprite.Create(tex, rect, pivot, pixelsPerUnit, 0, SpriteMeshType.FullRect)
                : Sprite.Create(tex, rect, pivot, pixelsPerUnit, 0, SpriteMeshType.FullRect, Vector4.zero, false, secondary);
            sprite.name = id;
            ctx.AddObjectToAsset(id, sprite);
            made[id] = sprite;
            return sprite;
        }

        AnimationClip MakeClip(string name, bool loop, KilnSheet.Clip clip, bool flipped)
        {
            var ac = new AnimationClip { name = name, frameRate = 1000 };
            int n = clip.sprites.Length;
            var keys = new ObjectReferenceKeyframe[n + 1];
            var emissive = clip.emissive.Length == n ? new ObjectReferenceKeyframe[n + 1] : null;
            var events = new List<AnimationEvent>();
            float t = 0;
            for (int i = 0; i <= n; i++)
            {
                int k = Math.Min(i, n - 1); // the last key holds the last frame until the clip's end
                keys[i] = new ObjectReferenceKeyframe { time = t, value = clip.sprites[k] };
                if (emissive != null)
                    emissive[i] = new ObjectReferenceKeyframe { time = t, value = clip.emissive[k] };
                if (i < n)
                {
                    foreach (var e in clip.events.Where(e => e.frame == i))
                        events.Add(new AnimationEvent { time = t, functionName = eventFunction, stringParameter = e.name });
                    t += clip.durations[i] / 1000f;
                }
            }
            AnimationUtility.SetObjectReferenceCurve(ac, EditorCurveBinding.PPtrCurve("", typeof(SpriteRenderer), "m_Sprite"), keys);
            if (emissive != null)
                AnimationUtility.SetObjectReferenceCurve(ac, EditorCurveBinding.PPtrCurve("Emissive", typeof(SpriteRenderer), "m_Sprite"), emissive);
            AnimationUtility.SetEditorCurve(ac, EditorCurveBinding.FloatCurve("", typeof(SpriteRenderer), "m_FlipX"),
                AnimationCurve.Constant(0, t, flipped ? 1 : 0));
            AnimationUtility.SetAnimationEvents(ac, events.ToArray());
            var settings = AnimationUtility.GetAnimationClipSettings(ac);
            settings.loopTime = loop;
            AnimationUtility.SetAnimationClipSettings(ac, settings);
            return ac;
        }

        static Texture2D LoadTexture(AssetImportContext ctx, string dir, string file, bool linear)
        {
            if (string.IsNullOrEmpty(file))
                return null;
            string path = Path.Combine(dir, file).Replace('\\', '/');
            if (!File.Exists(path))
            {
                if (!linear && !file.EndsWith("_emissive.png"))
                    ctx.LogImportError($"atlas not found: {path} (copy it next to the .kiln file)");
                return null;
            }
            ctx.DependsOnSourceAsset(path);
            var tex = new Texture2D(2, 2, TextureFormat.RGBA32, false, linear);
            if (!tex.LoadImage(File.ReadAllBytes(path)))
            {
                ctx.LogImportError($"cannot read {path}");
                return null;
            }
            tex.filterMode = FilterMode.Point;
            tex.wrapMode = TextureWrapMode.Clamp;
            return tex;
        }

        /// <summary>The exporter's block of a render JSON ("spritekiln", or "pxforge" in older files).</summary>
        static Dictionary<string, object> Block(Dictionary<string, object> data)
        {
            if (data == null)
                return null;
            foreach (var key in new[] { "spritekiln", "pxforge" })
                if (data.TryGetValue(key, out var b) && b is Dictionary<string, object> d)
                    return d;
            return null;
        }

        static float Num(object o) => Convert.ToSingle(o);

        static string Get(Dictionary<string, object> d, string key, string fallback) => Get<string>(d, key, fallback);

        static T Get<T>(Dictionary<string, object> d, string key, T fallback) =>
            d.TryGetValue(key, out var v) && v is T t ? t : fallback;
    }
}
