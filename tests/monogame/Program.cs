// Prints PXRESULT <json> with what KilnAnimator did on a render JSON (args[0]: a spec with `mirror: true`).
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Microsoft.Xna.Framework;
using SpriteKiln;

var sheet = KilnSheet.Parse(File.ReadAllText(args[0]), _ => null);
var r = new Dictionary<string, object>();
var a = new KilnAnimator(sheet);
var log = new List<string>();
a.OnEvent += (anim, ev) => log.Add($"{anim}:{ev}");
a.OnFinished += anim => { log.Add("finished:" + anim); a.Play("idle"); };
a.Play("attack");
log.Add("after-play");
int total = sheet.Animations["attack"].ByDirection["s"].TotalMs;
for (int i = 0; i < 100; i++) a.Update(total / 100.0);
a.Update(50);
r["events"] = log.ToList();   // a copy: the checks below play more clips
r["after"] = new[] { a.Animation, a.Finished.ToString() };
r["directions"] = sheet.Directions.Select(d => d.Name + (sheet.Mirrors.TryGetValue(d.Name, out var t) ? ">" + t : "")).ToList();

a.Play("idle", true);
a.SetDirection("e");
var srcE = a.Source;
bool hasE = a.TryGetSocket("staff_tip", out var east, out var depthE);
a.SetDirection("w");
bool hasW = a.TryGetSocket("staff_tip", out var west, out var depthW);
r["mirror"] = new object[] { a.Flipped, a.Source == srcE, hasE && hasW, west.X, -east.X, west.Y - east.Y, depthW - depthE };
var faces = new List<string>();
foreach (var v in new[] { new Vector2(-1, 0), new Vector2(0, -1), new Vector2(0, 1), new Vector2(1, 0) })
{
    a.FaceTowards(v);
    faces.Add(a.Direction);
}
r["face"] = faces;
System.Console.WriteLine("PXRESULT " + JsonSerializer.Serialize(r));
