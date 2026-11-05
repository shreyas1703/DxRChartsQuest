using System.Collections.Generic;
using UnityEngine;

namespace VLMCharts
{
    /// <summary>Material + mesh factory. Shaders live in Runtime/Resources so they are always in the build.</summary>
    public static class Mats
    {
        static Shader _unlit, _transparent, _text;
        static readonly Dictionary<string, Material> Cache = new Dictionary<string, Material>();

        static Shader Load(ref Shader s, string name)
        {
            if (s == null) s = Resources.Load<Shader>(name);
            if (s == null) { Debug.LogError("[DxRCharts] Shader '" + name + "' missing from Resources."); s = Shader.Find("Hidden/InternalErrorShader"); }
            return s;
        }

        public static Material Opaque(Color c, float shade = 0f)
        {
            string key = "o" + ColorUtility.ToHtmlStringRGBA(c) + shade.ToString("0.00");
            Material m;
            if (Cache.TryGetValue(key, out m) && m != null) return m;
            m = new Material(Load(ref _unlit, "DxRChartsUnlit")) { name = "DXC Opaque " + key };
            m.SetColor("_Color", c);
            m.SetFloat("_Shade", shade);
            m.enableInstancing = true;
            Cache[key] = m;
            return m;
        }

        public static Material Transparent(Color c, int queueOffset = 0)
        {
            string key = "t" + ColorUtility.ToHtmlStringRGBA(c) + queueOffset;
            Material m;
            if (Cache.TryGetValue(key, out m) && m != null) return m;
            m = new Material(Load(ref _transparent, "DxRChartsTransparent")) { name = "DXC Transparent " + key };
            m.SetColor("_Color", c);
            m.renderQueue = 3000 + queueOffset;
            Cache[key] = m;
            return m;
        }

        public static Material Text(Texture fontTexture)
        {
            string key = "text";
            Material m;
            if (!Cache.TryGetValue(key, out m) || m == null)
            {
                m = new Material(Load(ref _text, "DxRChartsText")) { name = "DXC Text" };
                Cache[key] = m;
            }
            if (fontTexture != null) m.mainTexture = fontTexture;
            return m;
        }

        // ---------- palette (Okabe-Ito + Tableau extensions; distinct on a dark background and in video)
        public static readonly Color[] Palette =
        {
            Hex("#4E9BFF"), Hex("#FF9F1C"), Hex("#2EC4B6"), Hex("#FF5C8A"), Hex("#C3E956"), Hex("#B28DFF"),
            Hex("#FFD23F"), Hex("#8D6E63"), Hex("#F2F2F2"), Hex("#3DDC84"), Hex("#FF6B35"), Hex("#7FDBFF"),
        };
        public static readonly Color Background = Hex("#15181E");
        public static readonly Color Axis = Hex("#E8EAED");
        public static readonly Color Grid = Hex("#3A404B");
        public static readonly Color Accent = Hex("#FFE14D");
        public static readonly Color PanelBg = new Color(0.10f, 0.11f, 0.14f, 0.92f);
        public static readonly Color PlateBg = new Color(0.02f, 0.02f, 0.03f, 0.78f);

        public static Color Hex(string h) { Color c; ColorUtility.TryParseHtmlString(h, out c); return c; }
    }

    public static class Prims
    {
        static Mesh _cube, _sphere, _quad;

        public static Mesh CubeMesh { get { if (_cube == null) _cube = BuildCube(); return _cube; } }
        public static Mesh SphereMesh { get { if (_sphere == null) _sphere = BuildIcoSphere(2); return _sphere; } }
        public static Mesh QuadMesh { get { if (_quad == null) _quad = BuildQuad(); return _quad; } }

        public static GameObject MeshObject(string name, Transform parent, Mesh mesh, Material mat)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = mat;
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            mr.receiveShadows = false;
            return go;
        }

        public static GameObject Box(string name, Transform parent, Vector3 localPos, Vector3 localScale, Material mat)
        {
            var go = MeshObject(name, parent, CubeMesh, mat);
            go.transform.localPosition = localPos;
            go.transform.localScale = localScale;
            return go;
        }

        /// <summary>A thin box from a to b (local space of parent). Scales correctly with the parent.</summary>
        public static GameObject Line(string name, Transform parent, Vector3 a, Vector3 b, float thickness, Material mat)
        {
            var go = MeshObject(name, parent, CubeMesh, mat);
            SetLine(go.transform, a, b, thickness);
            return go;
        }

        public static void SetLine(Transform t, Vector3 a, Vector3 b, float thickness)
        {
            Vector3 d = b - a;
            float len = d.magnitude;
            t.localPosition = (a + b) * 0.5f;
            t.localRotation = len > 1e-6f ? Quaternion.LookRotation(d / len, Mathf.Abs(Vector3.Dot(d / len, Vector3.up)) > 0.99f ? Vector3.forward : Vector3.up) : Quaternion.identity;
            t.localScale = new Vector3(thickness, thickness, Mathf.Max(len, 1e-5f));
        }

        static Mesh BuildQuad()
        {
            var m = new Mesh { name = "DXC Quad" };
            m.vertices = new[] { new Vector3(-0.5f, -0.5f, 0), new Vector3(0.5f, -0.5f, 0), new Vector3(0.5f, 0.5f, 0), new Vector3(-0.5f, 0.5f, 0) };
            m.uv = new[] { new Vector2(0, 0), new Vector2(1, 0), new Vector2(1, 1), new Vector2(0, 1) };
            m.normals = new[] { Vector3.back, Vector3.back, Vector3.back, Vector3.back };
            m.triangles = new[] { 0, 2, 1, 0, 3, 2 };
            m.RecalculateBounds();
            return m;
        }

        static Mesh BuildCube()
        {
            var m = new Mesh { name = "DXC Cube" };
            var v = new List<Vector3>(); var n = new List<Vector3>(); var t = new List<int>();
            Vector3[] dirs = { Vector3.right, Vector3.left, Vector3.up, Vector3.down, Vector3.forward, Vector3.back };
            foreach (var d in dirs)
            {
                Vector3 u = Mathf.Abs(d.y) > 0.5f ? Vector3.right : Vector3.up;
                Vector3 r = Vector3.Cross(u, d);
                int b = v.Count;
                v.Add((d - r - u) * 0.5f); v.Add((d + r - u) * 0.5f); v.Add((d + r + u) * 0.5f); v.Add((d - r + u) * 0.5f);
                for (int i = 0; i < 4; i++) n.Add(d);
                t.AddRange(new[] { b, b + 1, b + 2, b, b + 2, b + 3 });
            }
            m.SetVertices(v); m.SetNormals(n); m.SetTriangles(t, 0); m.RecalculateBounds();
            return m;
        }

        // Low-poly sphere (320 tris at subdiv 2) of diameter 1 — cheap enough for thousands of points on Quest 2.
        static Mesh BuildIcoSphere(int subdiv)
        {
            float p = (1f + Mathf.Sqrt(5f)) / 2f;
            var verts = new List<Vector3>
            {
                new Vector3(-1, p, 0), new Vector3(1, p, 0), new Vector3(-1, -p, 0), new Vector3(1, -p, 0),
                new Vector3(0, -1, p), new Vector3(0, 1, p), new Vector3(0, -1, -p), new Vector3(0, 1, -p),
                new Vector3(p, 0, -1), new Vector3(p, 0, 1), new Vector3(-p, 0, -1), new Vector3(-p, 0, 1)
            };
            for (int i = 0; i < verts.Count; i++) verts[i] = verts[i].normalized;
            var tris = new List<int> { 0,11,5, 0,5,1, 0,1,7, 0,7,10, 0,10,11, 1,5,9, 5,11,4, 11,10,2, 10,7,6, 7,1,8,
                                       3,9,4, 3,4,2, 3,2,6, 3,6,8, 3,8,9, 4,9,5, 2,4,11, 6,2,10, 8,6,7, 9,8,1 };
            for (int s = 0; s < subdiv; s++)
            {
                var cache = new Dictionary<long, int>();
                var nt = new List<int>();
                for (int i = 0; i < tris.Count; i += 3)
                {
                    int a = tris[i], b = tris[i + 1], c = tris[i + 2];
                    int ab = Mid(a, b, verts, cache), bc = Mid(b, c, verts, cache), ca = Mid(c, a, verts, cache);
                    nt.AddRange(new[] { a, ab, ca, b, bc, ab, c, ca, bc, ab, bc, ca });
                }
                tris = nt;
            }
            // Make every triangle face outward for Unity's clockwise front faces.
            for (int i = 0; i < tris.Count; i += 3)
            {
                Vector3 a = verts[tris[i]], b = verts[tris[i + 1]], c = verts[tris[i + 2]];
                if (Vector3.Dot(Vector3.Cross(b - a, c - a), a + b + c) < 0) { int tmp = tris[i + 1]; tris[i + 1] = tris[i + 2]; tris[i + 2] = tmp; }
            }
            var m = new Mesh { name = "DXC Sphere" };
            var scaled = new List<Vector3>();
            foreach (var v in verts) scaled.Add(v * 0.5f);
            m.SetVertices(scaled); m.SetNormals(verts); m.SetTriangles(tris, 0); m.RecalculateBounds();
            return m;
        }

        static int Mid(int a, int b, List<Vector3> verts, Dictionary<long, int> cache)
        {
            long key = a < b ? ((long)a << 32) + b : ((long)b << 32) + a;
            int idx;
            if (cache.TryGetValue(key, out idx)) return idx;
            verts.Add(((verts[a] + verts[b]) * 0.5f).normalized);
            idx = verts.Count - 1;
            cache[key] = idx;
            return idx;
        }
    }
}
