using SpriteKiln;
using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

/// <summary>
/// SpriteKiln demo: put this on an empty GameObject in a new scene, drop gargula.kiln on Sheet and press Play.
/// Arrow keys move, Space attacks. Builds a player and two statues with KilnAnimator; the attack's `hit`
/// event spawns a spark at the `strike` socket.
/// </summary>
public class GargoyleDemo : MonoBehaviour
{
    public KilnSheet sheet;
    public float speed = 1.8f;

    KilnAnimator _player;

    void Start()
    {
        if (sheet == null)
        {
            Debug.LogError("GargoyleDemo: drop gargula.kiln on Sheet", this);
            enabled = false;
            return;
        }
        var cam = Camera.main;
        if (cam != null)
        {
            cam.orthographic = true;
            cam.orthographicSize = 3f;
            cam.backgroundColor = new Color(0.13f, 0.12f, 0.17f);
            cam.transparencySortMode = TransparencySortMode.CustomAxis; // sort by the ground point
            cam.transparencySortAxis = Vector3.up;
        }
        Spawn("Statue", new Vector2(-2.5f, 0.6f), "se");
        Spawn("Statue", new Vector2(2.6f, -1.2f), "w");
        _player = Spawn("Player", Vector2.zero, "s");
        _player.EventFired += OnEvent;
        _player.Finished += anim => _player.Play("idle");
    }

    KilnAnimator Spawn(string name, Vector2 at, string facing)
    {
        var go = new GameObject(name, typeof(SpriteRenderer));
        go.transform.position = at;
        var kiln = go.AddComponent<KilnAnimator>();
        kiln.sheet = sheet;
        kiln.SetFacing(facing);
        kiln.Play("idle");
        return kiln;
    }

    void Update()
    {
        if (_player == null)
            return;
        bool attacking = _player.CurrentAnimation == "attack" && _player.IsPlaying;
        var move = ReadMove();
        if (attacking)
            return;
        if (AttackPressed())
            _player.Play("attack", true);
        else if (move != Vector2.zero)
        {
            _player.transform.position += (Vector3)(move.normalized * speed * Time.deltaTime);
            _player.Face(move);
            _player.Play("walk");
        }
        else
            _player.Play("idle");
    }

    void OnEvent(string anim, string ev)
    {
        if (ev != "hit" || !_player.TryGetSocket("strike", out var local, out _))
            return;
        var spark = new GameObject("Spark", typeof(SpriteRenderer)).AddComponent<Spark>();
        spark.transform.position = _player.transform.TransformPoint(local);
    }

    static Vector2 ReadMove()
    {
#if ENABLE_INPUT_SYSTEM
        var k = Keyboard.current;
        if (k == null)
            return Vector2.zero;
        return new Vector2((k.rightArrowKey.isPressed ? 1 : 0) - (k.leftArrowKey.isPressed ? 1 : 0),
            (k.upArrowKey.isPressed ? 1 : 0) - (k.downArrowKey.isPressed ? 1 : 0));
#else
        return new Vector2(Input.GetAxisRaw("Horizontal"), Input.GetAxisRaw("Vertical"));
#endif
    }

    static bool AttackPressed()
    {
#if ENABLE_INPUT_SYSTEM
        return Keyboard.current != null && Keyboard.current.spaceKey.wasPressedThisFrame;
#else
        return Input.GetKeyDown(KeyCode.Space);
#endif
    }

    /// <summary>A short flash: a white square sprite that grows and fades.</summary>
    class Spark : MonoBehaviour
    {
        const float Life = 0.2f;
        float _t;
        SpriteRenderer _r;

        void Start()
        {
            _r = GetComponent<SpriteRenderer>();
            var tex = Texture2D.whiteTexture;
            _r.sprite = Sprite.Create(tex, new Rect(0, 0, tex.width, tex.height), new Vector2(0.5f, 0.5f), 32);
            _r.sortingOrder = 100;
        }

        void Update()
        {
            _t += Time.deltaTime;
            float k = 1f - _t / Life;
            if (k <= 0)
            {
                Destroy(gameObject);
                return;
            }
            transform.localScale = Vector3.one * (1f + 2f * (1f - k));
            _r.color = new Color(1f, 0.8f, 0.4f, k);
        }
    }
}
