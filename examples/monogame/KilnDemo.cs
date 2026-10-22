using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Microsoft.Xna.Framework.Input;
using SpriteKiln;

/// SpriteKiln example: a gargoyle that walks and attacks in 8 directions, lit by a point light through its
/// normal map, with glowing eyes and a spark at the `strike` socket on the `hit` event.
/// Arrow keys (or WASD) move, Space attacks. The scene is drawn at 320x180 and scaled 4x.
/// `--shot out.png` plays a short scripted run, saves a frame and exits (used by the tests).
public class KilnDemo : Game
{
    const int W = 320, H = 180, Zoom = 4;
    const float Speed = 60f;   // px per second

    sealed class Actor
    {
        public KilnAnimator Anim = null!;
        public Vector2 Pos;
    }

    readonly GraphicsDeviceManager _gfx;
    readonly string? _shot;
    SpriteBatch _sb = null!;
    RenderTarget2D _scene = null!;
    Effect _lit = null!;
    Texture2D _white = null!, _flatNormal = null!;
    KilnSheet _sheet = null!;
    readonly List<Actor> _actors = new();
    readonly List<(Vector2 Pos, float Age)> _sparks = new();
    Actor _player = null!;
    int _tick;
    bool _attackHeld;

    public KilnDemo(string[] args)
    {
        _gfx = new GraphicsDeviceManager(this)
        {
            PreferredBackBufferWidth = W * Zoom,
            PreferredBackBufferHeight = H * Zoom,
            GraphicsProfile = GraphicsProfile.HiDef,
        };
        int i = Array.IndexOf(args, "--shot");
        _shot = i >= 0 && i + 1 < args.Length ? args[i + 1] : null;
        Content.RootDirectory = "Content";
        IsMouseVisible = true;
        Window.Title = "SpriteKiln example";
    }

    protected override void LoadContent()
    {
        _sb = new SpriteBatch(GraphicsDevice);
        _scene = new RenderTarget2D(GraphicsDevice, W, H);
        _lit = Content.Load<Effect>("KilnLit");
        _white = new Texture2D(GraphicsDevice, 1, 1);
        _white.SetData(new[] { Color.White });
        _flatNormal = new Texture2D(GraphicsDevice, 1, 1);
        _flatNormal.SetData(new[] { new Color(128, 128, 255) });   // the floor faces the viewer

        _sheet = KilnSheet.Load(GraphicsDevice, Path.Combine(AppContext.BaseDirectory, "sprites", "gargula", "gargula.json"));
        Spawn(new Vector2(80, 70), "se");
        Spawn(new Vector2(245, 135), "w");
        _player = Spawn(new Vector2(160, 100), "s");
        _player.Anim.OnEvent += (anim, ev) =>
        {
            Console.WriteLine($"event {anim}:{ev}");
            if (ev == "hit" && _player.Anim.TryGetSocket("strike", out var off, out _))
                _sparks.Add((_player.Pos + off, 0f));
        };
        _player.Anim.OnFinished += anim =>
        {
            Console.WriteLine($"finished {anim}");
            _player.Anim.Play("idle");
        };
    }

    Actor Spawn(Vector2 pos, string facing)
    {
        var a = new Actor { Anim = new KilnAnimator(_sheet), Pos = pos };
        a.Anim.SetDirection(facing);
        a.Anim.Play("idle");
        _actors.Add(a);
        return a;
    }

    protected override void Update(GameTime gameTime)
    {
        _tick++;
        var (move, attack, quit) = _shot != null ? Scripted() : ReadInput();
        if (quit)
            Exit();
        float dt = (float)gameTime.ElapsedGameTime.TotalSeconds;

        var p = _player.Anim;
        bool attacking = p.Animation == "attack" && !p.Finished;
        if (!attacking)
        {
            if (attack)
                p.Play("attack", true);
            else if (move != Vector2.Zero)
            {
                move.Normalize();
                _player.Pos = Vector2.Clamp(_player.Pos + move * Speed * dt, new Vector2(16, 40), new Vector2(W - 16, H - 8));
                p.FaceTowards(move);
                p.Play("walk");
            }
            else
                p.Play("idle");
        }
        foreach (var a in _actors)
            a.Anim.Update(gameTime);
        for (int i = _sparks.Count - 1; i >= 0; i--)
        {
            _sparks[i] = (_sparks[i].Pos, _sparks[i].Age + dt);
            if (_sparks[i].Age > 0.2f)
                _sparks.RemoveAt(i);
        }
        base.Update(gameTime);
    }

    (Vector2 Move, bool Attack, bool Quit) ReadInput()
    {
        var k = Keyboard.GetState();
        var move = new Vector2(
            (k.IsKeyDown(Keys.Right) || k.IsKeyDown(Keys.D) ? 1 : 0) - (k.IsKeyDown(Keys.Left) || k.IsKeyDown(Keys.A) ? 1 : 0),
            (k.IsKeyDown(Keys.Down) || k.IsKeyDown(Keys.S) ? 1 : 0) - (k.IsKeyDown(Keys.Up) || k.IsKeyDown(Keys.W) ? 1 : 0));
        bool space = k.IsKeyDown(Keys.Space);
        bool attack = space && !_attackHeld;
        _attackHeld = space;
        return (move, attack, k.IsKeyDown(Keys.Escape));
    }

    // --shot: walk right, then attack; the frame after the hit is saved
    (Vector2 Move, bool Attack, bool Quit) Scripted() =>
        (_tick < 45 ? new Vector2(1, 0) : Vector2.Zero, _tick == 50, false);

    protected override void Draw(GameTime gameTime)
    {
        GraphicsDevice.SetRenderTarget(_scene);
        GraphicsDevice.Clear(new Color(18, 16, 24));
        var light = _player.Pos + new Vector2(-24, -40);
        _lit.Parameters["MatrixTransform"].SetValue(Matrix.CreateOrthographicOffCenter(0, W, H, 0, 0, 1));
        _lit.Parameters["Ambient"].SetValue(new Vector3(0.42f, 0.4f, 0.52f));
        _lit.Parameters["LightPos"].SetValue(new[] { new Vector3(light, 40) });
        _lit.Parameters["LightColor"].SetValue(new[] { new Vector3(1f, 0.86f, 0.68f) });
        _lit.Parameters["LightRadius"].SetValue(new[] { 110f });
        _lit.Parameters["LightCount"].SetValue(1);

        _lit.Parameters["NormalMap"].SetValue(_flatNormal);
        _sb.Begin(samplerState: SamplerState.PointClamp, effect: _lit);
        _sb.Draw(_white, new Rectangle(0, 0, W, H), new Color(82, 77, 92));
        _sb.End();

        foreach (var a in _actors.OrderBy(a => a.Pos.Y))   // y-sort: the pivot is the ground point
        {
            _lit.Parameters["NormalMap"].SetValue(_sheet.NormalMap);
            _sb.Begin(samplerState: SamplerState.PointClamp, effect: _lit);
            a.Anim.Draw(_sb, a.Pos);
            _sb.End();
            _sb.Begin(blendState: BlendState.Additive, samplerState: SamplerState.PointClamp);
            a.Anim.DrawEmissive(_sb, a.Pos);
            _sb.End();
        }

        _sb.Begin(blendState: BlendState.Additive, samplerState: SamplerState.PointClamp);
        foreach (var (pos, age) in _sparks)
        {
            float k = 1 - age / 0.2f;
            int r = 2 + (int)(5 * (1 - k)), x = (int)pos.X, y = (int)pos.Y;
            var c = new Color(1f, 0.8f, 0.4f) * k;
            _sb.Draw(_white, new Rectangle(x - r, y, 2 * r + 1, 1), c);   // a small cross that grows and fades
            _sb.Draw(_white, new Rectangle(x, y - r, 1, 2 * r + 1), c);
        }
        _sb.End();

        GraphicsDevice.SetRenderTarget(null);
        _sb.Begin(samplerState: SamplerState.PointClamp);
        _sb.Draw(_scene, new Rectangle(0, 0, W * Zoom, H * Zoom), Color.White);
        _sb.End();

        if (_shot != null && _tick >= 80)
        {
            using (var fs = File.Create(_shot))
                _scene.SaveAsPng(fs, W, H);
            Exit();
        }
        base.Draw(gameTime);
    }
}
