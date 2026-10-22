// Run by tests/test_unity_runtime.py inside a scratch Unity project (Assets/Editor/KilnChecks.cs).
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using SpriteKiln;
using UnityEditor;
using UnityEngine;

public static class KilnChecks
{
    static readonly Dictionary<string, object> R = new Dictionary<string, object>();

    public static void Run()
    {
        try { Checks(); }
        catch (Exception e) { R["exception"] = e.ToString(); }
        File.WriteAllText("kiln_result.json", ToJson(R));
        EditorApplication.Exit(0);
    }

    static void Checks()
    {
        AssetDatabase.Refresh();
        // 1. import
        var path = "Assets/SpriteKiln/mirrored/mirrored.kiln";
        var sheet = AssetDatabase.LoadAssetAtPath<KilnSheet>(path);
        R["sheet"] = sheet != null;
        var all = AssetDatabase.LoadAllAssetsAtPath(path);
        R["sprites"] = all.OfType<Sprite>().Count();
        R["clips"] = all.OfType<AnimationClip>().Select(c => c.name).OrderBy(n => n).ToArray();
        R["directions"] = sheet.directions.Select(d => d.name + (d.Mirrored ? ">" + d.mirrorOf : "")).ToArray();
        R["anims"] = sheet.animations.Select(a => a.name + (a.loop ? "" : "!")).ToArray();
        R["emissive"] = sheet.HasEmissive;
        var s0 = sheet.FindClip("idle", "s", out _).sprites[0];
        R["pivot"] = new[] { s0.pivot.x, s0.pivot.y, sheet.pivot.x, sheet.frameSize - sheet.pivot.y };
        R["ppu"] = s0.pixelsPerUnit;
        R["secondary"] = s0.GetSecondaryTextureCount();
        R["filter"] = s0.texture.filterMode.ToString();
        var attack = all.OfType<AnimationClip>().First(c => c.name == "attack_s");
        R["clip_events"] = AnimationUtility.GetAnimationEvents(attack).Select(e => $"{e.time:0.000}:{e.stringParameter}").ToArray();
        R["clip_loop"] = new[] { AnimationUtility.GetAnimationClipSettings(attack).loopTime,
            AnimationUtility.GetAnimationClipSettings(all.OfType<AnimationClip>().First(c => c.name == "idle_s")).loopTime };
        var w = all.OfType<AnimationClip>().First(c => c.name == "idle_w");
        var flip = AnimationUtility.GetEditorCurve(w, EditorCurveBinding.FloatCurve("", typeof(SpriteRenderer), "m_FlipX"));
        R["clip_w_flip"] = flip.Evaluate(0);

        // 2. KilnAnimator: frame-0 events inside Play, exact timing, finish
        var go = new GameObject("kiln", typeof(SpriteRenderer));
        var k = go.AddComponent<KilnAnimator>();
        k.sheet = sheet;
        var log = new List<string>();
        k.EventFired += (a, e) => log.Add($"{a}:{e}");
        k.Finished += a => { log.Add("finished:" + a); k.Play("idle"); };
        k.Play("attack");
        log.Add("after-play");
        float total = sheet.FindClip("attack", "s", out _).durations.Sum();
        for (int i = 0; i < 100; i++)
            k.Tick(total / 1000f / 100f);
        k.Tick(0.05f);
        R["events"] = log.ToArray();
        R["after"] = new[] { k.CurrentAnimation, k.IsPlaying.ToString() };

        // 3. directions and mirroring
        k.Play("idle", true);
        k.SetFacing("e");
        bool hasE = k.TryGetSocket("staff_tip", out var east, out var depthE);
        var spriteE = go.GetComponent<SpriteRenderer>().sprite;
        k.SetFacing("w");
        bool hasW = k.TryGetSocket("staff_tip", out var west, out var depthW);
        var sr = go.GetComponent<SpriteRenderer>();
        R["mirror"] = new object[] { k.Flipped, sr.flipX, sr.sprite == spriteE, hasE && hasW, west.x, -east.x, west.y - east.y, depthW - depthE };
        k.Face(new Vector2(-1, 0)); var left = k.Facing;
        k.Face(new Vector2(0, 1)); var up = k.Facing;
        k.Face(new Vector2(0, -1)); var down = k.Facing;
        k.Face(new Vector2(1, 0)); var right = k.Facing;
        R["face"] = new[] { left, up, down, right };
        var em = go.transform.Find("Emissive");
        R["emissive_child"] = em != null && em.GetComponent<SpriteRenderer>().sprite != null && em.GetComponent<SpriteRenderer>().flipX == false;

        // 4. side view
        var side = AssetDatabase.LoadAssetAtPath<KilnSheet>("Assets/SpriteKiln/minimal_side/minimal_side.kiln");
        R["side"] = side.directions.Select(d => d.name).ToArray();
        R["side_view"] = side.view;

        // 5. a picture of idle frame 0 facing s, e, n and w (w is e flipped), one 32 px cell each
        if (SystemInfo.graphicsDeviceType == UnityEngine.Rendering.GraphicsDeviceType.Null)
            return;
        go.SetActive(false);
        string[] dirs = { "s", "e", "n", "w" };
        for (int i = 0; i < dirs.Length; i++)
        {
            var o = new GameObject("shot_" + dirs[i], typeof(SpriteRenderer));
            o.transform.position = new Vector3(i - 1.5f, 0, 0);
            var a = o.AddComponent<KilnAnimator>();
            a.sheet = sheet;
            a.SetFacing(dirs[i]);
            a.Play("idle");
        }
        float top = sheet.pivot.y / sheet.pixelsPerUnit;            // the cells span [-(32 - top), top] around y = 0
        var cam = new GameObject("cam").AddComponent<Camera>();
        cam.orthographic = true;
        cam.orthographicSize = 0.5f;
        cam.transform.position = new Vector3(0, top - 0.5f, -10);
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = new Color(0, 0, 0, 0);
        var rt = new RenderTexture(128, 32, 24, RenderTextureFormat.ARGB32);
        cam.targetTexture = rt;
        cam.aspect = 4;
        cam.Render();
        RenderTexture.active = rt;
        var shot = new Texture2D(128, 32, TextureFormat.RGBA32, false);
        shot.ReadPixels(new Rect(0, 0, 128, 32), 0, 0);
        shot.Apply();
        RenderTexture.active = null;
        File.WriteAllBytes("kiln_shot.png", shot.EncodeToPNG());
    }

    static string ToJson(object o)
    {
        switch (o)
        {
            case null: return "null";
            case string s: return "\"" + s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n").Replace("\r", "") + "\"";
            case bool b: return b ? "true" : "false";
            case float f: return f.ToString("R", System.Globalization.CultureInfo.InvariantCulture);
            case int i: return i.ToString();
            case Dictionary<string, object> d: return "{" + string.Join(",", d.Select(kv => ToJson(kv.Key) + ":" + ToJson(kv.Value))) + "}";
            case System.Collections.IEnumerable e: return "[" + string.Join(",", e.Cast<object>().Select(ToJson)) + "]";
            default: return ToJson(o.ToString());
        }
    }
}
