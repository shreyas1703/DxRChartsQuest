// Functional mini-UnityEngine for running the DxR port headlessly under mono (tests only).
// Implements just enough real behaviour (transform hierarchy, positions/scales, mesh bounds,
// colours, Instantiate) to execute DxR's spec → marks pipeline and dump the resulting geometry.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Reflection;

namespace UnityEngine
{
    public class Object
    {
        public string name = "";
        public bool destroyed;
        public static void Destroy(Object o) { if (o == null) return; o.destroyed = true; var go = o as GameObject; if (go != null && go.transform.parent != null) go.transform.SetParent(null, false); }
        public static void DestroyImmediate(Object o) { Destroy(o); }
        public static void DontDestroyOnLoad(Object o) { }
        public static bool operator ==(Object a, Object b) { bool an = ReferenceEquals(a, null) || a.destroyed, bn = ReferenceEquals(b, null) || b.destroyed; if (an || bn) return an && bn; return ReferenceEquals(a, b); }
        public static bool operator !=(Object a, Object b) { return !(a == b); }
        public static implicit operator bool(Object o) { return o != null; }
        public override bool Equals(object o) { return ReferenceEquals(this, o); }
        public override int GetHashCode() { return base.GetHashCode(); }

        public static T Instantiate<T>(T original, Transform parent) where T : Object { return (T)(Object)GameObject.Clone((GameObject)(Object)original, parent); }
        public static T Instantiate<T>(T original, Vector3 p, Quaternion r, Transform parent) where T : Object { var g = (GameObject)(Object)GameObject.Clone((GameObject)(Object)original, parent); g.transform.localPosition = p; return (T)(Object)g; }
    }

    public class Component : Object
    {
        public GameObject gameObject;
        public Transform transform { get { return gameObject.transform; } }
        public string tag;
        public T GetComponent<T>() { return gameObject.GetComponent<T>(); }
        public T GetComponentInParent<T>() { return gameObject.GetComponent<T>(); }
    }
    public class Behaviour : Component { public bool enabled = true; }
    public class Coroutine { }
    public class MonoBehaviour : Behaviour
    {
        public Coroutine StartCoroutine(IEnumerator e) { return null; }
        public static void print(object o) { Debug.Log(o); }
    }

    public class GameObject : Object
    {
        public Transform transform;
        public List<Component> components = new List<Component>();
        bool _active = true;
        public string tag;
        public GameObject() : this("GameObject") { }
        public GameObject(string n)
        {
            name = n;
            transform = new Transform(); transform.gameObject = this; components.Add(transform);
        }
        public bool activeSelf { get { return _active; } }
        public bool activeInHierarchy { get { return _active && (transform.parent == null || transform.parent.gameObject.activeInHierarchy); } }
        public void SetActive(bool b) { _active = b; }
        public T AddComponent<T>() where T : Component { return (T)AddComponent(typeof(T)); }
        public Component AddComponent(Type t)
        {
            var c = (Component)Activator.CreateInstance(t);
            c.gameObject = this; components.Add(c);
            var awake = t.GetMethod("Awake", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
            if (awake != null && Headless.RunAwake) awake.Invoke(c, null);
            return c;
        }
        public T GetComponent<T>()
        {
            foreach (var c in components) if (c is T) return (T)(object)c;
            return default(T);
        }
        public static GameObject Clone(GameObject src, Transform parent)
        {
            var g = new GameObject(src.name);
            g._active = src._active;
            g.transform.localPosition = src.transform.localPosition; g.transform.localScale = src.transform.localScale;
            g.transform.localRotation = src.transform.localRotation;
            foreach (var c in src.components)
            {
                if (c is Transform) continue;
                var copy = (Component)typeof(object).GetMethod("MemberwiseClone", BindingFlags.Instance | BindingFlags.NonPublic).Invoke(c, null);
                copy.gameObject = g; g.components.Add(copy);
                var mr = copy as Renderer; if (mr != null) mr.ResetInstance();
            }
            if (parent != null) g.transform.SetParent(parent, false);
            foreach (var ch in new List<Transform>(src.transform.children)) Clone(ch.gameObject, g.transform);
            return g;
        }
    }

    public enum Space { World, Self }

    public class Transform : Component, IEnumerable
    {
        public Transform parent;
        public List<Transform> children = new List<Transform>();
        public Vector3 localPosition = Vector3.zero, localScale = Vector3.one, localEulerAngles = Vector3.zero;
        public Quaternion localRotation = Quaternion.identity;
        public Quaternion rotation { get { return parent == null ? localRotation : parent.rotation * localRotation; } set { localRotation = parent == null ? value : Quaternion.Inverse(parent.rotation) * value; } }
        public int childCount { get { return children.Count; } }
        public Transform GetChild(int i) { return children[i]; }
        public Transform Find(string n) { foreach (var c in children) if (c.gameObject.name == n) return c; return null; }
        public void SetParent(Transform p, bool worldPositionStays = false)
        {
            if (parent != null) parent.children.Remove(this);
            parent = p;
            if (p != null) p.children.Add(this);
        }
        public Vector3 lossyScale { get { var s = localScale; return parent == null ? s : Vector3.Scale(parent.lossyScale, s); } }
        // rotation is ignored headlessly (the DxR geometry under test is built without rotations)
        public Vector3 TransformPoint(Vector3 p) { var w = localRotation * Vector3.Scale(localScale, p) + localPosition; return parent == null ? w : parent.TransformPoint(w); }
        public Vector3 InverseTransformPoint(Vector3 p) { var l = parent == null ? p : parent.InverseTransformPoint(p); l = Quaternion.Inverse(localRotation) * (l - localPosition); return new Vector3(l.x / localScale.x, l.y / localScale.y, l.z / localScale.z); }
        public Vector3 InverseTransformVector(Vector3 v) { return v; }
        public Vector3 position { get { return parent == null ? localPosition : parent.TransformPoint(localPosition); } set { localPosition = parent == null ? value : parent.InverseTransformPoint(value); } }
        public Vector3 forward { get { return Vector3.forward; } }
        public Vector3 up { get { return Vector3.up; } }
        public Vector3 right { get { return Vector3.right; } }
        public void Rotate(float x, float y, float z, Space s = Space.Self) { localRotation = localRotation * Quaternion.Euler(x, y, z); localEulerAngles += new Vector3(x, y, z); }
        public void Rotate(float x, float y, float z) { Rotate(x, y, z, Space.Self); }
        public void Translate(float x, float y, float z) { localPosition += new Vector3(x, y, z); }
        public void LookAt(Vector3 p, Vector3 up) { }
        public IEnumerator GetEnumerator() { return new List<Transform>(children).GetEnumerator(); }
    }

    public struct Vector2
    {
        public float x, y;
        public Vector2(float a, float b) { x = a; y = b; }
        public static Vector2 zero { get { return new Vector2(0, 0); } }
        public static implicit operator Vector3(Vector2 v) { return new Vector3(v.x, v.y, 0); }
        public static Vector2 operator *(Vector2 a, float f) { return new Vector2(a.x * f, a.y * f); }
    }

    public struct Vector3
    {
        public float x, y, z;
        public Vector3(float a, float b, float c) { x = a; y = b; z = c; }
        public float this[int i] { get { return i == 0 ? x : i == 1 ? y : z; } set { if (i == 0) x = value; else if (i == 1) y = value; else z = value; } }
        public static Vector3 zero { get { return new Vector3(0, 0, 0); } }
        public static Vector3 one { get { return new Vector3(1, 1, 1); } }
        public static Vector3 up { get { return new Vector3(0, 1, 0); } }
        public static Vector3 down { get { return new Vector3(0, -1, 0); } }
        public static Vector3 left { get { return new Vector3(-1, 0, 0); } }
        public static Vector3 right { get { return new Vector3(1, 0, 0); } }
        public static Vector3 forward { get { return new Vector3(0, 0, 1); } }
        public static Vector3 back { get { return new Vector3(0, 0, -1); } }
        public float magnitude { get { return (float)Math.Sqrt(x * x + y * y + z * z); } }
        public float sqrMagnitude { get { return x * x + y * y + z * z; } }
        public Vector3 normalized { get { float m = magnitude; return m > 1e-9f ? this / m : zero; } }
        public void Normalize() { this = normalized; }
        public static Vector3 operator +(Vector3 a, Vector3 b) { return new Vector3(a.x + b.x, a.y + b.y, a.z + b.z); }
        public static Vector3 operator -(Vector3 a, Vector3 b) { return new Vector3(a.x - b.x, a.y - b.y, a.z - b.z); }
        public static Vector3 operator -(Vector3 a) { return new Vector3(-a.x, -a.y, -a.z); }
        public static Vector3 operator *(Vector3 a, float f) { return new Vector3(a.x * f, a.y * f, a.z * f); }
        public static Vector3 operator *(float f, Vector3 a) { return a * f; }
        public static Vector3 operator /(Vector3 a, float f) { return new Vector3(a.x / f, a.y / f, a.z / f); }
        public static bool operator ==(Vector3 a, Vector3 b) { return (a - b).sqrMagnitude < 1e-12f; }
        public static bool operator !=(Vector3 a, Vector3 b) { return !(a == b); }
        public override bool Equals(object o) { return o is Vector3 && (Vector3)o == this; }
        public override int GetHashCode() { return x.GetHashCode() ^ y.GetHashCode(); }
        public static float Dot(Vector3 a, Vector3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
        public static Vector3 Cross(Vector3 a, Vector3 b) { return new Vector3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x); }
        public static Vector3 Lerp(Vector3 a, Vector3 b, float t) { return a + (b - a) * t; }
        public static Vector3 Scale(Vector3 a, Vector3 b) { return new Vector3(a.x * b.x, a.y * b.y, a.z * b.z); }
        public static Vector3 Min(Vector3 a, Vector3 b) { return new Vector3(Math.Min(a.x, b.x), Math.Min(a.y, b.y), Math.Min(a.z, b.z)); }
        public static Vector3 Max(Vector3 a, Vector3 b) { return new Vector3(Math.Max(a.x, b.x), Math.Max(a.y, b.y), Math.Max(a.z, b.z)); }
        public static implicit operator Vector2(Vector3 v) { return new Vector2(v.x, v.y); }
        public override string ToString() { return string.Format(CultureInfo.InvariantCulture, "({0:0.####}, {1:0.####}, {2:0.####})", x, y, z); }
    }

    public struct Quaternion
    {
        public float x, y, z, w;
        public Quaternion(float a, float b, float c, float d) { x = a; y = b; z = c; w = d; }
        public static Quaternion identity { get { return new Quaternion(0, 0, 0, 1); } }
        public static Quaternion AngleAxis(float deg, Vector3 axis)
        {
            axis = axis.normalized; float h = deg * Mathf.Deg2Rad * 0.5f, s = (float)Math.Sin(h);
            return new Quaternion(axis.x * s, axis.y * s, axis.z * s, (float)Math.Cos(h));
        }
        // Unity order: Z, then X, then Y (applied as q = Y * X * Z)
        public static Quaternion Euler(float ex, float ey, float ez) { return AngleAxis(ey, Vector3.up) * AngleAxis(ex, Vector3.right) * AngleAxis(ez, Vector3.forward); }
        public static Quaternion LookRotation(Vector3 f) { return LookRotation(f, Vector3.up); }
        public static Quaternion LookRotation(Vector3 f, Vector3 u)
        {
            f = f.normalized; Vector3 r = Vector3.Cross(u, f).normalized; if (r.sqrMagnitude < 1e-9f) r = Vector3.right; u = Vector3.Cross(f, r);
            // rotation matrix columns r, u, f -> quaternion
            float m00 = r.x, m01 = u.x, m02 = f.x, m10 = r.y, m11 = u.y, m12 = f.y, m20 = r.z, m21 = u.z, m22 = f.z;
            float tr = m00 + m11 + m22; Quaternion q;
            if (tr > 0) { float s = (float)Math.Sqrt(tr + 1) * 2; q = new Quaternion((m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s, 0.25f * s); }
            else if (m00 > m11 && m00 > m22) { float s = (float)Math.Sqrt(1 + m00 - m11 - m22) * 2; q = new Quaternion(0.25f * s, (m01 + m10) / s, (m02 + m20) / s, (m21 - m12) / s); }
            else if (m11 > m22) { float s = (float)Math.Sqrt(1 + m11 - m00 - m22) * 2; q = new Quaternion((m01 + m10) / s, 0.25f * s, (m12 + m21) / s, (m02 - m20) / s); }
            else { float s = (float)Math.Sqrt(1 + m22 - m00 - m11) * 2; q = new Quaternion((m02 + m20) / s, (m12 + m21) / s, 0.25f * s, (m10 - m01) / s); }
            return q;
        }
        public static Quaternion Inverse(Quaternion q) { return new Quaternion(-q.x, -q.y, -q.z, q.w); }
        public static Quaternion FromToRotation(Vector3 a, Vector3 b) { return identity; }
        public static Quaternion operator *(Quaternion a, Quaternion b)
        {
            return new Quaternion(a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y, a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x,
                                  a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w, a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z);
        }
        public static Vector3 operator *(Quaternion q, Vector3 v)
        {
            Vector3 u = new Vector3(q.x, q.y, q.z);
            return u * (2f * Vector3.Dot(u, v)) + v * (q.w * q.w - Vector3.Dot(u, u)) + Vector3.Cross(u, v) * (2f * q.w);
        }
        public static bool operator ==(Quaternion a, Quaternion b) { return a.x == b.x && a.y == b.y && a.z == b.z && a.w == b.w; }
        public static bool operator !=(Quaternion a, Quaternion b) { return !(a == b); }
        public override bool Equals(object o) { return o is Quaternion && (Quaternion)o == this; }
        public override int GetHashCode() { return 0; }
    }

    public struct Color
    {
        public float r, g, b, a;
        public Color(float r, float g, float b, float a = 1f) { this.r = r; this.g = g; this.b = b; this.a = a; }
        public static Color white { get { return new Color(1, 1, 1, 1); } }
        public static Color black { get { return new Color(0, 0, 0, 1); } }
        public static Color gray { get { return new Color(.5f, .5f, .5f, 1); } }
        public static Color operator *(Color c, float f) { return new Color(c.r * f, c.g * f, c.b * f, c.a * f); }
        public static bool operator ==(Color x, Color y) { return x.r == y.r && x.g == y.g && x.b == y.b && x.a == y.a; }
        public static bool operator !=(Color x, Color y) { return !(x == y); }
        public override bool Equals(object o) { return o is Color && (Color)o == this; }
        public override int GetHashCode() { return 0; }
        public static Color Lerp(Color x, Color y, float t) { return new Color(x.r + (y.r - x.r) * t, x.g + (y.g - x.g) * t, x.b + (y.b - x.b) * t, x.a + (y.a - x.a) * t); }
    }

    public static class ColorUtility
    {
        public static bool TryParseHtmlString(string s, out Color c)
        {
            c = Color.white;
            if (string.IsNullOrEmpty(s) || s[0] != '#' || (s.Length != 7 && s.Length != 9)) return false;
            try
            {
                int r = Convert.ToInt32(s.Substring(1, 2), 16), g = Convert.ToInt32(s.Substring(3, 2), 16), b = Convert.ToInt32(s.Substring(5, 2), 16);
                int a = s.Length == 9 ? Convert.ToInt32(s.Substring(7, 2), 16) : 255;
                c = new Color(r / 255f, g / 255f, b / 255f, a / 255f); return true;
            }
            catch { return false; }
        }
        static int B(float f) { return Math.Max(0, Math.Min(255, (int)Math.Round(f * 255))); }
        public static string ToHtmlStringRGB(Color c) { return B(c.r).ToString("X2") + B(c.g).ToString("X2") + B(c.b).ToString("X2"); }
        public static string ToHtmlStringRGBA(Color c) { return ToHtmlStringRGB(c) + B(c.a).ToString("X2"); }
    }

    public static class Mathf
    {
        public const float Deg2Rad = (float)(Math.PI / 180.0);
        public const float PI = (float)Math.PI;
        public static float Sin(float f) { return (float)Math.Sin(f); }
        public static float Cos(float f) { return (float)Math.Cos(f); }
        public static float Sqrt(float f) { return (float)Math.Sqrt(f); }
        public static float Abs(float f) { return Math.Abs(f); }
        public static float Max(float a, float b) { return Math.Max(a, b); }
        public static int Max(int a, int b) { return Math.Max(a, b); }
        public static float Min(float a, float b) { return Math.Min(a, b); }
        public static int Min(int a, int b) { return Math.Min(a, b); }
        public static float Clamp(float v, float a, float b) { return Math.Max(a, Math.Min(b, v)); }
        public static int Clamp(int v, int a, int b) { return Math.Max(a, Math.Min(b, v)); }
        public static float Lerp(float a, float b, float t) { return a + (b - a) * Clamp(t, 0, 1); }
        public static float Pow(float a, float b) { return (float)Math.Pow(a, b); }
        public static float Log(float a) { return (float)Math.Log(a); }
        public static int FloorToInt(float a) { return (int)Math.Floor(a); }
        public static int CeilToInt(float a) { return (int)Math.Ceiling(a); }
        public static int RoundToInt(float a) { return (int)Math.Round(a); }
    }

    public struct Bounds
    {
        public Vector3 center, size;
        public Bounds(Vector3 c, Vector3 s) { center = c; size = s; }
        public Vector3 min { get { return center - size * 0.5f; } }
        public Vector3 max { get { return center + size * 0.5f; } }
    }

    public class Mesh : Object
    {
        public List<Vector3> verts = new List<Vector3>();
        public List<int> tris = new List<int>();
        public Bounds bounds;
        public Rendering.IndexFormat indexFormat;
        public List<Color> cols = new List<Color>();
        public Vector3[] vertices { get { return verts.ToArray(); } set { verts = new List<Vector3>(value); } }
        public Vector3[] normals { get; set; }
        public Vector2[] uv { get; set; }
        public int[] triangles { get { return tris.ToArray(); } set { tris = new List<int>(value); } }
        public void RecalculateBounds()
        {
            if (verts.Count == 0) { bounds = new Bounds(Vector3.zero, Vector3.zero); return; }
            Vector3 mn = verts[0], mx = verts[0];
            foreach (var v in verts) { mn = Vector3.Min(mn, v); mx = Vector3.Max(mx, v); }
            bounds = new Bounds((mn + mx) * 0.5f, mx - mn);
        }
        public void RecalculateNormals() { }
        public void SetVertices(List<Vector3> v) { verts = new List<Vector3>(v); RecalculateBounds(); }
        public void SetNormals(List<Vector3> v) { }
        public void SetTriangles(List<int> t, int s) { tris = new List<int>(t); }
        public void SetUVs(int c, List<Vector2> u) { }
        public void SetColors(List<Color> c) { cols = new List<Color>(c); }
        public void Clear() { verts.Clear(); tris.Clear(); }
        public void MarkDynamic() { }
        public Mesh Copy() { var m = new Mesh { name = name, verts = new List<Vector3>(verts), tris = new List<int>(tris), bounds = bounds }; return m; }
    }

    public class MeshFilter : Component
    {
        public Mesh sharedMesh;
        Mesh _inst;
        public Mesh mesh { get { if (_inst == null || _inst.destroyed) { _inst = sharedMesh != null ? sharedMesh.Copy() : new Mesh(); } return _inst; } set { _inst = value; } }
    }

    public class Renderer : Component
    {
        public Material sharedMaterial;
        Material _inst;
        public Rendering.ShadowCastingMode shadowCastingMode;
        public bool receiveShadows;
        public void ResetInstance() { _inst = null; }
        public Material material { get { if (_inst == null) { _inst = sharedMaterial != null ? sharedMaterial.Copy() : new Material((Shader)null); sharedMaterial = _inst; } return _inst; } set { _inst = value; sharedMaterial = value; } }
        public Bounds bounds
        {
            get
            {
                var mf = GetComponent<MeshFilter>();
                Mesh m = mf == null ? null : mf.mesh;
                if (m == null) return new Bounds(transform.position, Vector3.zero);
                m.RecalculateBounds();
                Vector3 a = m.bounds.min, b = m.bounds.max, mn = new Vector3(1e9f, 1e9f, 1e9f), mx = -mn;
                for (int i = 0; i < 8; i++)
                {
                    var p = transform.TransformPoint(new Vector3((i & 1) == 0 ? a.x : b.x, (i & 2) == 0 ? a.y : b.y, (i & 4) == 0 ? a.z : b.z));
                    mn = Vector3.Min(mn, p); mx = Vector3.Max(mx, p);
                }
                return new Bounds((mn + mx) * 0.5f, mx - mn);
            }
        }
    }
    public class MeshRenderer : Renderer { }

    public class Texture : Object { }
    public class Shader : Object { public static Shader Find(string n) { return new Shader { name = n }; } }
    public class Material : Object
    {
        public Shader shader;
        public Color color = Color.white;
        public bool enableInstancing;
        public int renderQueue;
        public Texture mainTexture;
        public Material(Shader s) { shader = s; }
        public void SetColor(string n, Color c) { if (n == "_Color") color = c; }
        public void SetFloat(string n, float f) { }
        public void SetInt(string n, int i) { }
        public void EnableKeyword(string k) { }
        public void DisableKeyword(string k) { }
        public Material Copy() { var m = new Material(shader) { color = color, name = name }; return m; }
    }
    public class TextAsset : Object { public string text; }

    public static class Resources
    {
        public static string Root;   // folder containing Resources files (tests)
        public static T Load<T>(string path) where T : Object
        {
            if (typeof(T) == typeof(Shader)) return (T)(Object)new Shader { name = path };
            if (typeof(T) == typeof(TextAsset))
            {
                string f = System.IO.Path.Combine(Root, path + ".json");
                if (!System.IO.File.Exists(f)) return null;
                return (T)(Object)new TextAsset { text = System.IO.File.ReadAllText(f) };
            }
            return null;
        }
        public static T GetBuiltinResource<T>(string p) where T : Object { return null; }
    }

    public enum FontStyle { Normal, Bold }
    public struct CharacterInfo { public int minX, maxX, minY, maxY, advance; public Vector2 uvBottomLeft, uvBottomRight, uvTopRight, uvTopLeft; }
    public class Font : Object
    {
        public static event Action<Font> textureRebuilt;
        public Material material;
        public void RequestCharactersInTexture(string s, int size, FontStyle st) { }
        public bool GetCharacterInfo(char c, out CharacterInfo ci, int size, FontStyle st) { ci = default(CharacterInfo); return false; }
        static void Touch() { if (textureRebuilt != null) textureRebuilt(null); }
    }

    public enum CameraClearFlags { Skybox, SolidColor }
    public class Camera : Behaviour { public static Camera main; public float nearClipPlane, farClipPlane, fieldOfView; public CameraClearFlags clearFlags; public Color backgroundColor; public Ray ScreenPointToRay(Vector3 p) { return default(Ray); } }
    public class AudioListener : Behaviour { }
    public struct Ray { public Vector3 origin, direction; public Ray(Vector3 o, Vector3 d) { origin = o; direction = d; } }
    public enum RuntimePlatform { Android, WindowsEditor, OSXEditor }
    public static class Application
    {
        public static event Action onBeforeRender;
        public static string persistentDataPath = "/tmp", streamingAssetsPath = "/tmp", version = "test", unityVersion = "headless", dataPath = "/tmp";
        public static bool isPlaying = true;
        public static RuntimePlatform platform = RuntimePlatform.OSXEditor;
        static void Touch() { if (onBeforeRender != null) onBeforeRender(); }
    }
    public static class Debug
    {
        public static bool Quiet = true;
        public static void Log(object o) { if (!Quiet) Console.WriteLine(o); }
        public static void LogWarning(object o) { Console.WriteLine("WARN " + o); }
        public static void LogError(object o) { Console.WriteLine("ERROR " + o); }
        public static void LogException(Exception e) { Console.WriteLine("EXC " + e); }
    }
    public static class Time { public static float deltaTime = 1f / 72f, unscaledDeltaTime = 1f / 72f; }
    public static class PlayerPrefs { public static string GetString(string k, string d) { return d; } public static void SetString(string k, string v) { } public static int GetInt(string k, int d) { return d; } public static void SetInt(string k, int v) { } public static void Save() { } }
    public static class SystemInfo { public static string deviceModel = "headless"; }
    public static class Input { public static bool GetMouseButton(int b) { return false; } public static float GetAxis(string a) { return 0; } public static Vector3 mousePosition; public static bool GetKey(KeyCode k) { return false; } }
    public enum KeyCode { W, A, S, D, Q, E, G, R, T, J, L, I, K, C, V, RightArrow, LeftArrow, Period, Comma }
    public class HeaderAttribute : Attribute { public HeaderAttribute(string s) { } }
    public class TextAreaAttribute : Attribute { }
    public interface ISubsystem { bool running { get; } }
    public static class SubsystemManager { public static void GetSubsystems<T>(List<T> l) { } }
    public class Collider : Component { }
    public class BoxCollider : Collider { public Vector3 size; }
    public struct RaycastHit { public float distance; public Collider collider; }
    public enum QueryTriggerInteraction { UseGlobal, Ignore, Collide }
    public static class Physics { public static bool Raycast(Ray r, out RaycastHit h, float d, int m, QueryTriggerInteraction q) { h = default(RaycastHit); return false; } public static void SyncTransforms() { } }

    public static class Headless { public static bool RunAwake = false; }
}
namespace UnityEngine.Rendering
{
    public enum ShadowCastingMode { Off, On }
    public enum BlendMode { Zero, One, SrcAlpha, OneMinusSrcAlpha }
    public enum IndexFormat { UInt16, UInt32 }
}
namespace UnityEngine.XR
{
    public enum XRNode { LeftHand, RightHand, CenterEye, Head }
    public struct InputFeatureUsage<T> { public InputFeatureUsage(string n) { } }
    public static class CommonUsages
    {
        public static InputFeatureUsage<bool> isTracked, primaryButton, secondaryButton, menuButton, primary2DAxisClick;
        public static InputFeatureUsage<float> trigger, grip;
        public static InputFeatureUsage<Vector2> primary2DAxis;
        public static InputFeatureUsage<Vector3> devicePosition, centerEyePosition;
        public static InputFeatureUsage<Quaternion> deviceRotation, centerEyeRotation;
    }
    public struct HapticCapabilities { public bool supportsImpulse; }
    public struct InputDevice
    {
        public bool isValid;
        public bool TryGetFeatureValue(InputFeatureUsage<bool> u, out bool v) { v = false; return false; }
        public bool TryGetFeatureValue(InputFeatureUsage<float> u, out float v) { v = 0; return false; }
        public bool TryGetFeatureValue(InputFeatureUsage<Vector2> u, out Vector2 v) { v = default(Vector2); return false; }
        public bool TryGetFeatureValue(InputFeatureUsage<Vector3> u, out Vector3 v) { v = default(Vector3); return false; }
        public bool TryGetFeatureValue(InputFeatureUsage<Quaternion> u, out Quaternion v) { v = default(Quaternion); return false; }
        public bool TryGetHapticCapabilities(out HapticCapabilities c) { c = default(HapticCapabilities); return false; }
        public bool SendHapticImpulse(uint ch, float a, float d) { return true; }
    }
    public static class InputDevices { public static InputDevice GetDeviceAtXRNode(XRNode n) { return default(InputDevice); } }
    public static class XRSettings { public static bool isDeviceActive; public static string loadedDeviceName = ""; }
    [Flags] public enum TrackingOriginModeFlags { Unknown = 0, Device = 1, Floor = 2 }
    public class XRInputSubsystem : ISubsystem { public bool running { get { return false; } } public bool TrySetTrackingOriginMode(TrackingOriginModeFlags f) { return true; } public TrackingOriginModeFlags GetTrackingOriginMode() { return 0; } }
}
namespace UnityEngine.Networking
{
    public class DownloadHandler { public string text; }
    public class UnityWebRequestAsyncOperation { public bool isDone = true; }
    public class UnityWebRequest : IDisposable
    {
        public enum Result { InProgress, Success, ConnectionError }
        public Result result; public string error; public DownloadHandler downloadHandler = new DownloadHandler();
        public static UnityWebRequest Get(string u) { return new UnityWebRequest(); }
        public UnityWebRequestAsyncOperation SendWebRequest() { return new UnityWebRequestAsyncOperation(); }
        public void Dispose() { }
    }
}
