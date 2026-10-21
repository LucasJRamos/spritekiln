using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace SpriteKiln.Editor
{
    /// <summary>Minimal JSON reader (JsonUtility cannot read dictionaries): objects become
    /// Dictionary&lt;string, object&gt;, arrays List&lt;object&gt;, numbers double.</summary>
    static class Json
    {
        public static object Parse(string text)
        {
            int i = 0;
            var value = Value(text, ref i);
            Skip(text, ref i);
            if (i != text.Length)
                throw new FormatException($"JSON: unexpected text at {i}");
            return value;
        }

        static void Skip(string s, ref int i)
        {
            while (i < s.Length && char.IsWhiteSpace(s[i]))
                i++;
        }

        static object Value(string s, ref int i)
        {
            Skip(s, ref i);
            if (i >= s.Length)
                throw new FormatException("JSON: unexpected end");
            char c = s[i];
            if (c == '{')
                return Obj(s, ref i);
            if (c == '[')
                return Arr(s, ref i);
            if (c == '"')
                return Str(s, ref i);
            if (Word(s, ref i, "true"))
                return true;
            if (Word(s, ref i, "false"))
                return false;
            if (Word(s, ref i, "null"))
                return null;
            int start = i;
            while (i < s.Length && "+-0123456789.eE".IndexOf(s[i]) >= 0)
                i++;
            if (start == i)
                throw new FormatException($"JSON: unexpected '{c}' at {i}");
            return double.Parse(s.Substring(start, i - start), CultureInfo.InvariantCulture);
        }

        static bool Word(string s, ref int i, string w)
        {
            if (string.CompareOrdinal(s, i, w, 0, w.Length) != 0)
                return false;
            i += w.Length;
            return true;
        }

        static Dictionary<string, object> Obj(string s, ref int i)
        {
            var d = new Dictionary<string, object>();
            i++;
            Skip(s, ref i);
            if (s[i] == '}')
            {
                i++;
                return d;
            }
            while (true)
            {
                Skip(s, ref i);
                string key = Str(s, ref i);
                Skip(s, ref i);
                if (s[i++] != ':')
                    throw new FormatException($"JSON: ':' expected at {i - 1}");
                d[key] = Value(s, ref i);
                Skip(s, ref i);
                char c = s[i++];
                if (c == '}')
                    return d;
                if (c != ',')
                    throw new FormatException($"JSON: ',' or '}}' expected at {i - 1}");
            }
        }

        static List<object> Arr(string s, ref int i)
        {
            var list = new List<object>();
            i++;
            Skip(s, ref i);
            if (s[i] == ']')
            {
                i++;
                return list;
            }
            while (true)
            {
                list.Add(Value(s, ref i));
                Skip(s, ref i);
                char c = s[i++];
                if (c == ']')
                    return list;
                if (c != ',')
                    throw new FormatException($"JSON: ',' or ']' expected at {i - 1}");
            }
        }

        static string Str(string s, ref int i)
        {
            if (s[i] != '"')
                throw new FormatException($"JSON: string expected at {i}");
            i++;
            var sb = new StringBuilder();
            while (s[i] != '"')
            {
                char c = s[i++];
                if (c != '\\')
                {
                    sb.Append(c);
                    continue;
                }
                char e = s[i++];
                switch (e)
                {
                    case 'n': sb.Append('\n'); break;
                    case 't': sb.Append('\t'); break;
                    case 'r': sb.Append('\r'); break;
                    case 'b': sb.Append('\b'); break;
                    case 'f': sb.Append('\f'); break;
                    case 'u':
                        sb.Append((char)Convert.ToInt32(s.Substring(i, 4), 16));
                        i += 4;
                        break;
                    default: sb.Append(e); break;
                }
            }
            i++;
            return sb.ToString();
        }
    }
}
