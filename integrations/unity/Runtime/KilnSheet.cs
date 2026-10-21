using System;
using System.Collections.Generic;
using UnityEngine;

namespace SpriteKiln
{
    /// <summary>
    /// A SpriteKiln render imported from a <c>.kiln</c> file: sprites, frame durations, events and sockets
    /// per animation and direction. <see cref="KilnAnimator"/> plays it.
    /// </summary>
    public class KilnSheet : ScriptableObject
    {
        [Serializable]
        public class Direction
        {
            public string name;
            /// <summary>Model rotation in degrees: s 0, se 45, e 90, ne 135, n 180, nw -135, w -90, sw -45.</summary>
            public float yaw;
            /// <summary>The rendered direction this one plays flipped horizontally (specs with
            /// <c>mirror: true</c>), or empty.</summary>
            public string mirrorOf;

            public bool Mirrored => !string.IsNullOrEmpty(mirrorOf);
        }

        [Serializable]
        public class FrameEvent
        {
            public int frame;
            public string name;
        }

        [Serializable]
        public class SocketTrack
        {
            public string name;
            /// <summary>Per frame: x, y in px from the pivot (y down) and depth in px (&gt; 0 in front).</summary>
            public Vector3[] points;
            /// <summary>Per frame: false while the socket is hidden.</summary>
            public bool[] visible;
        }

        [Serializable]
        public class Clip
        {
            public string direction;
            public Sprite[] sprites;
            /// <summary>Same layout as <see cref="sprites"/>; empty when the asset has no emissive material.</summary>
            public Sprite[] emissive;
            /// <summary>Milliseconds per frame.</summary>
            public float[] durations;
            public List<FrameEvent> events = new List<FrameEvent>();
            public List<SocketTrack> sockets = new List<SocketTrack>();

            public float Length => Sum(durations) / 1000f;

            static float Sum(float[] values)
            {
                float s = 0;
                foreach (var v in values)
                    s += v;
                return s;
            }
        }

        [Serializable]
        public class Anim
        {
            public string name;
            public bool loop;
            /// <summary>One clip per rendered direction (mirrored directions reuse their twin's).</summary>
            public List<Clip> clips = new List<Clip>();
        }

        /// <summary>Cell size in px.</summary>
        public int frameSize;
        /// <summary>Ground point under the model, in px from the cell's top-left. It is the sprites' pivot.</summary>
        public Vector2 pivot;
        public float pixelsPerUnit = 32;
        /// <summary>"topdown" or "side".</summary>
        public string view = "topdown";
        /// <summary>Every direction the asset can face, rendered and mirrored.</summary>
        public List<Direction> directions = new List<Direction>();
        public List<Anim> animations = new List<Anim>();
        public List<string> socketNames = new List<string>();
        public Texture2D atlas;
        public Texture2D normalMap;
        public Texture2D emissiveMap;

        public bool HasEmissive => emissiveMap != null;

        public Anim FindAnimation(string name) => animations.Find(a => a.name == name);

        public Direction FindDirection(string name) => directions.Find(d => d.name == name);

        /// <summary>The clip that shows <paramref name="anim"/> facing <paramref name="direction"/>, and whether it
        /// must be drawn flipped.</summary>
        public Clip FindClip(string anim, string direction, out bool flipped)
        {
            var a = FindAnimation(anim);
            var d = FindDirection(direction);
            flipped = d != null && d.Mirrored;
            if (a == null || a.clips.Count == 0)
                return null;
            var rendered = d == null ? null : (flipped ? d.mirrorOf : d.name);
            return a.clips.Find(c => c.direction == rendered) ?? a.clips[0];
        }
    }
}
