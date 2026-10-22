using System;
using System.Linq;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.Rendering;

namespace SpriteKiln
{
    /// <summary>
    /// Plays a <see cref="KilnSheet"/> on this GameObject's SpriteRenderer: animations in up to 8 directions
    /// with exact per-frame durations, gameplay events (hit, windup, step_l...), sockets and an emissive layer.
    /// </summary>
    /// <example>
    /// <code>
    /// kiln.Play("walk");
    /// kiln.Face(rigidbody.linearVelocity);     // nearest exported (or mirrored) direction
    /// kiln.EventFired += (anim, ev) => { if (ev == "hit") DealDamage(); };
    /// kiln.Finished += anim => kiln.Play("idle");
    /// if (kiln.TryGetSocket("muzzle_R", out var local, out _)) SpawnFlash(transform.TransformPoint(local));
    /// </code>
    /// </example>
    [RequireComponent(typeof(SpriteRenderer))]
    [DisallowMultipleComponent]
    public class KilnAnimator : MonoBehaviour
    {
        [Serializable]
        public class EventFiredUnityEvent : UnityEvent<string, string> { }

        [Serializable]
        public class FinishedUnityEvent : UnityEvent<string> { }

        public KilnSheet sheet;
        [SerializeField] string startAnimation = "idle";
        [SerializeField] string startFacing = "s";
        public bool playOnEnable = true;
        [Min(0)] public float speed = 1f;
        /// <summary>Material of the emissive layer. Empty: an unlit sprite material, so it glows in the dark.</summary>
        public Material emissiveMaterial;
        /// <summary>(animation, event) when a frame that carries an event becomes visible.</summary>
        public EventFiredUnityEvent onEvent = new EventFiredUnityEvent();
        /// <summary>(animation) when an animation that does not loop reaches its end.</summary>
        public FinishedUnityEvent onFinished = new FinishedUnityEvent();

        /// <summary>(animation, event) when a frame that carries an event becomes visible.</summary>
        public event Action<string, string> EventFired;
        /// <summary>(animation) when an animation that does not loop reaches its end.</summary>
        public event Action<string> Finished;

        SpriteRenderer _renderer;
        SpriteRenderer _emissive;
        KilnSheet.Anim _anim;
        KilnSheet.Clip _clip;
        string _animName;
        string _facing;
        bool _flipped;
        int _frame;
        float _ms;
        bool _playing;
        int _serial;
        static Material s_unlit;
        const float TieDegrees = 0.5f; // directions this close to the nearest one count as a tie

        public string CurrentAnimation => _animName ?? startAnimation;
        public string Facing => _facing ?? startFacing;
        public int Frame => _frame;
        public bool IsPlaying => _playing;
        /// <summary>True while the current direction is drawn as a flipped copy of its twin.</summary>
        public bool Flipped => _flipped;

        void Awake()
        {
            _renderer = GetComponent<SpriteRenderer>();
            _renderer.spriteSortPoint = SpriteSortPoint.Pivot; // sort by the ground point under the character
        }

        void OnEnable()
        {
            if (playOnEnable && _animName == null && sheet != null)
                Play(startAnimation, true);
        }

        void Update()
        {
            Tick(Time.deltaTime);
        }

        /// <summary>Plays an animation (no direction suffix) in the current direction. Restarts only when
        /// <paramref name="restart"/> is set, the animation changed or it had stopped. Events of frame 0 fire
        /// inside this call.</summary>
        public void Play(string animation, bool restart = false)
        {
            if (sheet == null)
                return;
            var anim = sheet.FindAnimation(animation);
            if (anim == null)
            {
                Debug.LogWarning($"KilnAnimator: no animation '{animation}' in {sheet.name}", this);
                return;
            }
            bool changed = animation != _animName || !_playing;
            _animName = animation;
            _anim = anim;
            _facing ??= sheet.FindDirection(startFacing) != null || sheet.directions.Count == 0
                ? startFacing
                : sheet.directions[0].name; // e.g. a side view, which has no "s"
            if (!changed && !restart)
                return;
            _serial++;
            _frame = 0;
            _ms = 0;
            _playing = true;
            Resolve();
            Show();
            Fire(0);
        }

        /// <summary>Advances the animation by <paramref name="seconds"/> (Update calls it with
        /// Time.deltaTime). Call it yourself after disabling the component for a fixed-step game.</summary>
        public void Tick(float seconds)
        {
            if (!_playing || _clip == null)
                return;
            _ms += seconds * 1000f * speed;
            int serial = _serial;
            while (_playing && serial == _serial)
            {
                float d = Mathf.Max(1f, _clip.durations[_frame]);
                if (_ms < d)
                    break;
                _ms -= d;
                if (_frame + 1 < _clip.sprites.Length)
                    _frame++;
                else if (_anim.loop)
                    _frame = 0;
                else
                {
                    _playing = false;
                    _ms = 0;
                    string done = _animName; // a listener may start another clip
                    Finished?.Invoke(done);
                    onFinished.Invoke(done);
                    break;
                }
                Show();
                Fire(_frame);
            }
        }

        /// <summary>Faces the exported direction nearest to a world vector (x right, y up), e.g. a velocity.</summary>
        public void Face(Vector2 direction)
        {
            if (sheet == null || direction.sqrMagnitude < 1e-12f)
                return;
            float yaw = Mathf.Atan2(direction.x, -direction.y) * Mathf.Rad2Deg;
            float bestDiff = float.MaxValue;
            foreach (var d in sheet.directions)
                bestDiff = Mathf.Min(bestDiff, Mathf.Abs(Mathf.DeltaAngle(yaw, d.yaw)));
            string best = null;
            foreach (var d in sheet.directions)
            {
                if (Mathf.Abs(Mathf.DeltaAngle(yaw, d.yaw)) > bestDiff + TieDegrees)
                    continue;
                if (d.name == Facing)
                    return; // a tie (straight up in a side view) keeps the current direction
                best ??= d.name;
            }
            if (best != null)
                SetFacing(best);
        }

        /// <summary>Sets the direction by name (s, se, e...), keeping the current frame and time.</summary>
        public void SetFacing(string direction)
        {
            if (sheet == null || sheet.FindDirection(direction) == null || direction == _facing)
                return;
            _facing = direction;
            if (_anim == null)
                return;
            Resolve();
            Show();
        }

        /// <summary>World-space unit vector (x right, y up) of the current direction.</summary>
        public Vector2 FacingVector
        {
            get
            {
                var d = sheet == null ? null : sheet.FindDirection(Facing);
                float yaw = (d == null ? 0 : d.yaw) * Mathf.Deg2Rad;
                return new Vector2(Mathf.Sin(yaw), -Mathf.Cos(yaw));
            }
        }

        /// <summary>A socket's position in this transform's local space for the current frame, and its depth
        /// (&gt; 0 in front of the body) in the same units. False while the socket is hidden.</summary>
        public bool TryGetSocket(string socket, out Vector2 local, out float depth)
        {
            local = default;
            depth = 0;
            var track = _clip?.sockets.Find(s => s.name == socket);
            if (track == null || _frame >= track.points.Length || !track.visible[_frame])
                return false;
            var p = track.points[_frame];
            float ppu = sheet.pixelsPerUnit;
            local = new Vector2(_flipped ? -p.x : p.x, -p.y) / ppu;
            depth = p.z / ppu;
            return true;
        }

        /// <summary>True when the socket exists and is visible in the current frame.</summary>
        public bool HasSocket(string socket) => TryGetSocket(socket, out _, out _);

        void Resolve()
        {
            _clip = sheet.FindClip(_animName, Facing, out _flipped);
            if (_clip != null)
                _frame = Mathf.Min(_frame, _clip.sprites.Length - 1);
        }

        void Show()
        {
            if (_clip == null)
                return;
            if (_renderer == null)
                _renderer = GetComponent<SpriteRenderer>();
            _renderer.sprite = _clip.sprites[_frame];
            _renderer.flipX = _flipped;
            if (_clip.emissive != null && _clip.emissive.Length > _frame)
            {
                var em = Emissive();
                em.sprite = _clip.emissive[_frame];
                em.flipX = _flipped;
            }
        }

        void Fire(int frame)
        {
            string anim = _animName; // a listener may start another clip
            foreach (var e in _clip.events.ToArray())
            {
                if (e.frame != frame)
                    continue;
                EventFired?.Invoke(anim, e.name);
                onEvent.Invoke(anim, e.name);
            }
        }

        SpriteRenderer Emissive()
        {
            if (_emissive != null)
                return _emissive;
            // a sorting group keeps the glow with its sprite: it sorts against other objects as one, by the pivot
            if (!TryGetComponent<SortingGroup>(out var group))
            {
                group = gameObject.AddComponent<SortingGroup>();
                group.sortingLayerID = _renderer.sortingLayerID;
                group.sortingOrder = _renderer.sortingOrder;
            }
            var go = new GameObject("Emissive");
            go.transform.SetParent(transform, false);
            _emissive = go.AddComponent<SpriteRenderer>();
            _emissive.sharedMaterial = emissiveMaterial != null ? emissiveMaterial : UnlitMaterial();
            _emissive.sortingLayerID = _renderer.sortingLayerID;
            _emissive.sortingOrder = _renderer.sortingOrder + 1;
            return _emissive;
        }

        static Material UnlitMaterial()
        {
            if (s_unlit == null)
            {
                var shader = Shader.Find("Universal Render Pipeline/2D/Sprite-Unlit-Default") ?? Shader.Find("Sprites/Default");
                s_unlit = new Material(shader) { name = "SpriteKiln Emissive (unlit)" };
            }
            return s_unlit;
        }
    }
}
